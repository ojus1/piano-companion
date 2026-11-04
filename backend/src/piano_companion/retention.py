"""Keep the recordings folder under a size cap by deleting the oldest files first.

Session rows stay in the database (their metrics, grades and notes still count toward progress); only
the MIDI/audio file is removed and the row's path is cleared, so the tablet stops offering playback.
The newest recording is never deleted, even if it alone is over the cap.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import Session, or_, select

from .db import get_engine
from .models import PracticeSession

log = logging.getLogger(__name__)


def enforce_recordings_cap(recordings_dir: Path, max_bytes: int) -> list[str]:
    """Delete the oldest files under `recordings_dir` until the total is <= max_bytes.

    Returns the deleted paths, relative to `recordings_dir`. `max_bytes <= 0` disables the cap.
    """
    if max_bytes <= 0 or not recordings_dir.is_dir():
        return []
    files = sorted(
        (p for p in recordings_dir.rglob("*") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
    )
    total = sum(p.stat().st_size for p in files)
    deleted: list[str] = []
    for p in files[:-1]:  # never the newest
        if total <= max_bytes:
            break
        size = p.stat().st_size
        try:
            p.unlink()
        except OSError:
            log.exception("could not delete %s", p)
            continue
        total -= size
        deleted.append(str(p.relative_to(recordings_dir)))
        parent = p.parent
        if parent != recordings_dir and not any(parent.iterdir()):
            parent.rmdir()
    if deleted:
        _clear_paths(set(deleted))
        log.info("recordings over cap: deleted %d oldest file(s), now %.1f MB", len(deleted), total / 1e6)
    return deleted


def _clear_paths(deleted: set[str]) -> None:
    with Session(get_engine()) as db:
        rows = db.exec(
            select(PracticeSession).where(
                or_(PracticeSession.midi_path.in_(deleted), PracticeSession.audio_path.in_(deleted))
            )
        ).all()
        for row in rows:
            if row.midi_path in deleted:
                row.midi_path = None
            if row.audio_path in deleted:
                row.audio_path = None
            db.add(row)
        db.commit()
