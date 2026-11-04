from __future__ import annotations

import asyncio
import shutil
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, col, select

from .. import srs
from ..config import get_settings
from ..db import get_session
from ..models import Piece, PracticeItem, PracticeSession, Review, utcnow

router = APIRouter(prefix="/api")

SCORE_SUFFIXES = {".musicxml": "musicxml", ".xml": "musicxml", ".mxl": "musicxml", ".pdf": "pdf"}


def _safe_join(base: Path, rel: str) -> Path:
    p = (base / rel).resolve()
    if not p.is_relative_to(base.resolve()) or not p.is_file():
        raise HTTPException(404)
    return p


# ---------- health / status ----------


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/status")
def status(request: Request):
    rec = getattr(request.app.state, "recorder", None)
    return rec.status() if rec else {"midi_enabled": False}


# ---------- practice sessions ----------


class SessionPatch(BaseModel):
    notes: str | None = None
    practice_item_id: int | None = None


@router.get("/sessions")
def list_sessions(limit: int = 50, db: Session = Depends(get_session)):
    q = select(PracticeSession).order_by(col(PracticeSession.started_at).desc()).limit(limit)
    return db.exec(q).all()


@router.get("/sessions/{sid}")
def get_session_row(sid: int, db: Session = Depends(get_session)):
    row = db.get(PracticeSession, sid)
    if not row:
        raise HTTPException(404)
    return row


@router.patch("/sessions/{sid}")
def patch_session(sid: int, body: SessionPatch, db: Session = Depends(get_session)):
    row = db.get(PracticeSession, sid)
    if not row:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/sessions/{sid}/{kind}")
def session_file(sid: int, kind: str, db: Session = Depends(get_session)):
    row = db.get(PracticeSession, sid)
    rel = {"midi": row.midi_path, "audio": row.audio_path}.get(kind) if row else None
    if not rel:
        raise HTTPException(404)
    return FileResponse(_safe_join(get_settings().recordings_dir, rel))


# ---------- library (pieces + score files) ----------


class PieceIn(BaseModel):
    title: str
    composer: str | None = None
    arranger: str | None = None
    tags: list[str] = []


@router.get("/pieces")
def list_pieces(db: Session = Depends(get_session)):
    return db.exec(select(Piece).order_by(Piece.title)).all()


@router.post("/pieces", status_code=201)
def create_piece(body: PieceIn, db: Session = Depends(get_session)):
    p = Piece(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.post("/pieces/{pid}/files")
def upload_score(pid: int, file: UploadFile, db: Session = Depends(get_session)):
    p = db.get(Piece, pid)
    if not p:
        raise HTTPException(404)
    suffix = Path(file.filename or "").suffix.lower()
    kind = SCORE_SUFFIXES.get(suffix)
    if not kind:
        raise HTTPException(415, f"unsupported score type {suffix!r}")
    rel = f"pieces/{pid}/score{suffix}"
    dest = get_settings().library_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    setattr(p, f"{kind}_path", rel)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/library/{rel:path}")
def library_file(rel: str):
    return FileResponse(_safe_join(get_settings().library_dir, rel))


# ---------- spaced-repetition practice queue ----------


class ItemIn(BaseModel):
    title: str
    kind: str = "exercise"
    piece_id: int | None = None
    details: dict = {}


class ReviewIn(BaseModel):
    rating: int  # 1..4
    session_id: int | None = None


@router.post("/practice/items", status_code=201)
def create_item(body: ItemIn, db: Session = Depends(get_session)):
    item = PracticeItem(**body.model_dump(), srs_state=srs.new_state())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/practice/items")
def list_items(db: Session = Depends(get_session)):
    return db.exec(select(PracticeItem).order_by(PracticeItem.due)).all()


@router.get("/practice/queue")
def practice_queue(limit: int = 10, db: Session = Depends(get_session)):
    """Today's assignments: everything due now, most overdue first."""
    now = utcnow()
    q = select(PracticeItem).where(PracticeItem.active, PracticeItem.due <= now).order_by(PracticeItem.due).limit(limit)
    items = db.exec(q).all()
    return [{**i.model_dump(), "retrievability": round(srs.retrievability(i.srs_state, now), 3)} for i in items]


@router.post("/practice/items/{iid}/review")
def review_item(iid: int, body: ReviewIn, db: Session = Depends(get_session)):
    if body.rating not in (1, 2, 3, 4):
        raise HTTPException(422, "rating must be 1..4")
    item = db.get(PracticeItem, iid)
    if not item:
        raise HTTPException(404)
    state, due, log = srs.grade(item.srs_state, body.rating)
    item.srs_state, item.due = state, due
    db.add(item)
    db.add(Review(practice_item_id=iid, session_id=body.session_id, rating=body.rating, log=log))
    db.commit()
    db.refresh(item)
    return item


# ---------- progress ----------


@router.get("/stats")
def stats(days: int = 30, db: Session = Depends(get_session)):
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.exec(select(PracticeSession).where(PracticeSession.started_at >= since)).all()
    minutes: dict[str, float] = defaultdict(float)
    for r in rows:
        if r.ended_at:
            start = r.started_at.replace(tzinfo=r.started_at.tzinfo or UTC)
            end = r.ended_at.replace(tzinfo=r.ended_at.tzinfo or UTC)
            day = start.astimezone().date().isoformat()
            minutes[day] += (end - start).total_seconds() / 60
    streak, d = 0, date.today()
    if d.isoformat() not in minutes:  # today not practised yet doesn't break the streak
        d -= timedelta(days=1)
    while d.isoformat() in minutes:
        streak += 1
        d -= timedelta(days=1)
    return {
        "streak_days": streak,
        "minutes_by_day": {k: round(v, 1) for k, v in sorted(minutes.items())},
        "total_minutes": round(sum(minutes.values()), 1),
        "sessions": len(rows),
    }


# ---------- live MIDI stream for the tablet ----------


@router.websocket("/live")
async def live(ws: WebSocket):
    await ws.accept()
    rec = getattr(ws.app.state, "recorder", None)
    if not rec or not rec.capture:
        # MIDI disabled (e.g. dev laptop): stay connected so the app shows "Piano off", not "Pi offline".
        await ws.send_json({"type": "status", "midi": None})
        try:
            while True:
                await asyncio.sleep(20)
                await ws.send_json({"type": "ping"})
        except (WebSocketDisconnect, RuntimeError):
            return
    q = rec.capture.subscribe()
    await ws.send_json({"type": "status", "midi": rec.capture.port_name})
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=20)
            except TimeoutError:
                event = {"type": "ping"}
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        rec.capture.unsubscribe(q)
