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
from ..models import Performance, Piece, PracticeItem, PracticeSession, Review, utcnow

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


# ---------- performance / cover takes (Record screen) ----------


class TakeIn(BaseModel):
    title: str = ""
    kind: str = "performance"  # performance | cover
    piece_id: int | None = None


class PerformancePatch(BaseModel):
    title: str | None = None
    kind: str | None = None
    piece_id: int | None = None
    favorite: bool | None = None
    notes: str | None = None


TAKE_KINDS = {"performance", "cover"}


def _recorder(request: Request):
    rec = getattr(request.app.state, "recorder", None)
    if rec is None:
        raise HTTPException(503, "recorder not running")
    return rec


@router.get("/performances")
def list_performances(limit: int = 100, db: Session = Depends(get_session)):
    q = select(Performance).order_by(col(Performance.started_at).desc()).limit(limit)
    return db.exec(q).all()


@router.post("/performances/start")
def start_take(body: TakeIn, request: Request):
    if body.kind not in TAKE_KINDS:
        raise HTTPException(422, f"kind must be one of {sorted(TAKE_KINDS)}")
    rec = _recorder(request)
    title = body.title.strip() or f"Untitled {body.kind}, {datetime.now().astimezone():%b %d %H:%M}"
    if not rec.start_take(title, body.kind, body.piece_id):
        raise HTTPException(409, "a take is already recording")
    return rec.take.info()


@router.post("/performances/stop")
def stop_take(request: Request):
    """Save the take. `performance` is null when nothing was played."""
    rec = _recorder(request)
    if not rec.take.active:
        raise HTTPException(409, "no take is recording")
    return {"performance": rec.stop_take()}


@router.post("/performances/cancel")
def cancel_take(request: Request):
    return {"cancelled": _recorder(request).cancel_take()}


@router.get("/performances/{pid}")
def get_performance(pid: int, db: Session = Depends(get_session)):
    row = db.get(Performance, pid)
    if not row:
        raise HTTPException(404)
    return row


@router.patch("/performances/{pid}")
def patch_performance(pid: int, body: PerformancePatch, db: Session = Depends(get_session)):
    row = db.get(Performance, pid)
    if not row:
        raise HTTPException(404)
    patch = body.model_dump(exclude_unset=True)
    if "kind" in patch and patch["kind"] not in TAKE_KINDS:
        raise HTTPException(422, f"kind must be one of {sorted(TAKE_KINDS)}")
    if "title" in patch and not (patch["title"] or "").strip():
        raise HTTPException(422, "title cannot be empty")
    for k, v in patch.items():
        setattr(row, k, v)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/performances/{pid}", status_code=204)
def delete_performance(pid: int, db: Session = Depends(get_session)):
    row = db.get(Performance, pid)
    if not row:
        raise HTTPException(404)
    if row.midi_path:
        base = get_settings().performances_dir.resolve()
        f = (base / row.midi_path).resolve()
        if f.is_relative_to(base):
            f.unlink(missing_ok=True)
    db.delete(row)
    db.commit()


@router.get("/performances/{pid}/midi")
def performance_midi(pid: int, db: Session = Depends(get_session)):
    row = db.get(Performance, pid)
    if not row or not row.midi_path:
        raise HTTPException(404)
    safe = "".join(c if c.isalnum() or c in " -_.,()" else "_" for c in row.title).strip() or "take"
    return FileResponse(_safe_join(get_settings().performances_dir, row.midi_path), filename=f"{safe}.mid")


# ---------- library (pieces + score files) ----------


class PieceIn(BaseModel):
    title: str
    composer: str | None = None
    arranger: str | None = None
    tags: list[str] = []


@router.get("/pieces")
def list_pieces(
    q: str | None = None,
    category: str | None = None,
    max_henle: int | None = None,
    has_score: bool = False,
    limit: int = 200,
    db: Session = Depends(get_session),
):
    stmt = select(Piece)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(col(Piece.title).ilike(like) | col(Piece.composer).ilike(like))
    if category:
        stmt = stmt.where(Piece.category == category)
    if max_henle is not None:
        stmt = stmt.where(col(Piece.level_henle) <= max_henle)
    if has_score:
        stmt = stmt.where(col(Piece.musicxml_path).is_not(None) | col(Piece.pdf_path).is_not(None))
    return db.exec(stmt.order_by(Piece.level_henle, Piece.composer, Piece.title).limit(limit)).all()


@router.get("/pieces/{pid}")
def get_piece(pid: int, db: Session = Depends(get_session)):
    p = db.get(Piece, pid)
    if not p:
        raise HTTPException(404)
    return p


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


@router.put("/pieces/{pid}/annotated-pdf")
async def save_annotated_pdf(pid: int, request: Request, db: Session = Depends(get_session)):
    """The tablet's PDF viewer saves the score with annotations baked in; the original is kept."""
    p = db.get(Piece, pid)
    if not p:
        raise HTTPException(404)
    body = await request.body()
    if not body.startswith(b"%PDF"):
        raise HTTPException(415, "expected a PDF body")
    rel = f"annotations/{pid}.pdf"
    dest = get_settings().library_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    p.pdf_annotated_path = rel
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
    pieces = {p.id: p for p in db.exec(select(Piece).where(col(Piece.id).in_([i.piece_id for i in items])))}
    return [
        {
            **i.model_dump(),
            "retrievability": round(srs.retrievability(i.srs_state, i.kind, now), 3),
            "piece": pieces.get(i.piece_id),
        }
        for i in items
    ]


@router.post("/practice/items/{iid}/review")
def review_item(iid: int, body: ReviewIn, db: Session = Depends(get_session)):
    if body.rating not in (1, 2, 3, 4):
        raise HTTPException(422, "rating must be 1..4")
    item = db.get(PracticeItem, iid)
    if not item:
        raise HTTPException(404)
    return _apply_review(db, item, body.rating, body.session_id)


def _apply_review(db: Session, item: PracticeItem, rating: int, session_id: int | None, extra: dict | None = None):
    state, due, log = srs.grade(item.srs_state, rating, item.kind)
    item.srs_state, item.due = state, due
    db.add(item)
    db.add(Review(practice_item_id=item.id, session_id=session_id, rating=rating, log=log | (extra or {})))
    db.commit()
    db.refresh(item)
    return item


class AutoGradeIn(BaseModel):
    session_id: int | None = None  # default: the most recent session
    target_bpm: float | None = None  # current tempo-ladder rung; default from item details
    measures: tuple[int, int] | None = None  # passage; default from item details
    apply: bool = True  # False = just report the suggested grade


@router.post("/practice/items/{iid}/autograde")
def autograde_item(iid: int, body: AutoGradeIn, db: Session = Depends(get_session)):
    """Align a recorded take to the item's score and grade it with the curriculum's rules."""
    from .. import alignment
    from ..grading import Thresholds, grade_attempt

    if not alignment.available():
        raise HTTPException(501, "install the backend with the `align` extra to enable auto-grading")
    item = db.get(PracticeItem, iid)
    piece = db.get(Piece, item.piece_id) if item and item.piece_id else None
    if not piece:
        raise HTTPException(404, "item has no piece")
    score_rel = piece.musicxml_path or piece.midi_path
    if not score_rel:
        raise HTTPException(409, "piece has no MusicXML or MIDI score to align against")
    if body.session_id:
        sess = db.get(PracticeSession, body.session_id)
    else:
        sess = db.exec(select(PracticeSession).order_by(col(PracticeSession.started_at).desc())).first()
    if not sess or not sess.midi_path:
        raise HTTPException(404, "no recorded session")
    s = get_settings()
    target = body.target_bpm or item.details.get("target_bpm")
    measures = body.measures or (tuple(item.details["measures"]) if item.details.get("measures") else None)
    attempt, metrics = alignment.attempt_from_files(
        s.library_dir / score_rel, s.recordings_dir / sess.midi_path, target, measures
    )
    from .. import curriculum

    t = Thresholds.from_curriculum(curriculum.scheduler_defaults().get("grading", {}))
    rating = grade_attempt(attempt, technique=item.kind == "technique", t=t)
    sess.analysis = {**sess.analysis, f"item_{iid}": {"rating": rating, **metrics}}
    sess.practice_item_id = iid
    db.add(sess)
    db.commit()
    if body.apply:
        _apply_review(db, item, rating, sess.id, {"auto": True, "metrics": metrics})
    return {"rating": rating, "metrics": metrics, "session_id": sess.id, "applied": body.apply}


# ---------- play MIDI on the piano itself ----------


class PlayIn(BaseModel):
    session_id: int | None = None
    piece_id: int | None = None
    performance_id: int | None = None
    tempo_scale: float = 1.0


@router.post("/play")
def play_on_piano(body: PlayIn, request: Request, db: Session = Depends(get_session)):
    """Send a recorded take or a piece's reference MIDI to the P-155, which plays it with its own sound."""
    rec = getattr(request.app.state, "recorder", None)
    s = get_settings()
    if rec and rec.take.active:
        raise HTTPException(409, "a take is recording")
    if body.session_id:
        row = db.get(PracticeSession, body.session_id)
        path = s.recordings_dir / row.midi_path if row and row.midi_path else None
    elif body.performance_id:
        perf = db.get(Performance, body.performance_id)
        path = s.performances_dir / perf.midi_path if perf and perf.midi_path else None
    else:
        row = db.get(Piece, body.piece_id) if body.piece_id else None
        path = s.library_dir / row.midi_path if row and row.midi_path else None
    if not path or not path.is_file():
        raise HTTPException(404, "no MIDI file")
    if not rec or not rec.play(path, body.tempo_scale):
        raise HTTPException(409, "piano not connected")
    return {"playing": str(path.name)}


@router.post("/play/stop")
def stop_playing(request: Request):
    rec = getattr(request.app.state, "recorder", None)
    if rec:
        rec.stop_playback()
    return {"stopped": True}


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
