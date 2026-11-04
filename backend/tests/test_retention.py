import os

from sqlmodel import Session, select

from piano_companion import config, db
from piano_companion.models import PracticeSession
from piano_companion.retention import enforce_recordings_cap


def _file(root, rel, size, mtime):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    os.utime(p, (mtime, mtime))
    return rel


def test_oldest_files_deleted_until_under_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("PC_DATA_DIR", str(tmp_path))
    config.get_settings.cache_clear()
    db.reset_engine()
    db.get_engine()  # creates the tables
    rec = tmp_path / "recordings"
    a = _file(rec, "2026-11-01/100000.mid", 400, 1000)
    b = _file(rec, "2026-11-02/100000.mid", 400, 2000)
    c = _file(rec, "2026-11-03/100000.mid", 400, 3000)
    with Session(db.get_engine()) as s:
        for rel in (a, b, c):
            s.add(PracticeSession(midi_path=rel, note_count=10))
        s.commit()

    assert enforce_recordings_cap(rec, 1000) == [a]
    assert not (rec / "2026-11-01").exists()  # empty day folder removed
    assert (rec / b).exists() and (rec / c).exists()
    with Session(db.get_engine()) as s:
        paths = sorted(str(r.midi_path) for r in s.exec(select(PracticeSession)))
    assert paths == sorted([b, c, "None"])  # session row kept, path cleared

    # The newest file is never deleted, even when it alone exceeds the cap.
    assert enforce_recordings_cap(rec, 100) == [b]
    assert (rec / c).exists()
    assert enforce_recordings_cap(rec, 0) == []
    config.get_settings.cache_clear()
    db.reset_engine()
