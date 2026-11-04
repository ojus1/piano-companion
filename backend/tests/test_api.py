from datetime import UTC

from piano_companion.models import PracticeSession


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}
    assert client.get("/api/status").json()["midi_enabled"] is False


def test_practice_queue_and_review(client):
    item = client.post("/api/practice/items", json={"title": "C major scale, HT, 2 oct", "kind": "scale"}).json()
    queue = client.get("/api/practice/queue").json()
    assert [q["id"] for q in queue] == [item["id"]]
    r = client.post(f"/api/practice/items/{item['id']}/review", json={"rating": 3})
    assert r.status_code == 200
    assert r.json()["due"] > item["due"]
    # Good on a new card schedules a short relearning step, so it's no longer due right now.
    assert client.get("/api/practice/queue").json() == []
    assert client.post(f"/api/practice/items/{item['id']}/review", json={"rating": 7}).status_code == 422


def test_piece_upload_and_fetch(client):
    p = client.post("/api/pieces", json={"title": "Etude Op. 10 No. 3", "composer": "Chopin"}).json()
    xml = b"<?xml version='1.0'?><score-partwise/>"
    r = client.post(f"/api/pieces/{p['id']}/files", files={"file": ("tristesse.musicxml", xml)})
    assert r.status_code == 200
    rel = r.json()["musicxml_path"]
    assert client.get(f"/api/library/{rel}").content == xml
    assert client.get("/api/library/../piano.db").status_code == 404
    bad = client.post(f"/api/pieces/{p['id']}/files", files={"file": ("x.exe", b"x")})
    assert bad.status_code == 415


def test_sessions_and_stats(client):
    from datetime import datetime, timedelta

    from sqlmodel import Session

    from piano_companion.db import get_engine

    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        db.add(PracticeSession(started_at=now - timedelta(minutes=20), ended_at=now, note_count=500))
        db.commit()
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    sid = sessions[0]["id"]
    assert client.patch(f"/api/sessions/{sid}", json={"notes": "LH weak"}).json()["notes"] == "LH weak"
    st = client.get("/api/stats").json()
    assert st["streak_days"] == 1 and 19.9 < st["total_minutes"] < 20.1


def test_recorder_saves_session_end_to_end(client):
    """Notes fed into the app's own recorder become a PracticeSession with a MIDI file."""
    import mido

    rec = client.app.state.recorder
    for i, n in enumerate([60, 64, 67, 72, 67, 64, 60, 64, 67, 72]):
        rec.segmenter.feed(mido.Message("note_on", note=n, velocity=70), now=10 + i * 0.3)
        rec.segmenter.feed(mido.Message("note_off", note=n), now=10.2 + i * 0.3)
    rec.segmenter.flush()
    [s] = client.get("/api/sessions").json()
    assert s["note_count"] == 10 and s["metrics"]["pitch_high"] == 72
    midi = client.get(f"/api/sessions/{s['id']}/midi")
    assert midi.status_code == 200 and midi.content[:4] == b"MThd"


def test_live_socket_without_midi(client):
    with client.websocket_connect("/api/live") as ws:
        assert ws.receive_json() == {"type": "status", "midi": None}


def test_annotated_pdf_roundtrip(client):
    p = client.post("/api/pieces", json={"title": "Nocturne"}).json()
    assert client.put(f"/api/pieces/{p['id']}/annotated-pdf", content=b"not a pdf").status_code == 415
    r = client.put(f"/api/pieces/{p['id']}/annotated-pdf", content=b"%PDF-1.7 fake")
    assert r.status_code == 200
    assert client.get(f"/api/library/{r.json()['pdf_annotated_path']}").content == b"%PDF-1.7 fake"


def test_play_without_piano(client):
    assert client.post("/api/play", json={"piece_id": 999}).status_code == 404


def test_adds_columns_to_an_old_database(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv("PC_DATA_DIR", str(tmp_path))
    con = sqlite3.connect(tmp_path / "piano.db")
    con.execute("CREATE TABLE piece (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL, tags JSON, created_at DATETIME)")
    con.execute("INSERT INTO piece (title, tags) VALUES ('Old', '[]')")
    con.commit()
    con.close()
    from piano_companion import config, db

    config.get_settings.cache_clear()
    db.reset_engine()
    from sqlmodel import Session, select

    from piano_companion.models import Piece

    with Session(db.get_engine()) as s:
        [p] = s.exec(select(Piece)).all()
    assert p.title == "Old" and p.pdf_annotated_path is None
    config.get_settings.cache_clear()
    db.reset_engine()
