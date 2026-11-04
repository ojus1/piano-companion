"""End-to-end auto-grading: a reference MIDI as the score, a recorded take as the session."""

import mido
import pytest

from piano_companion import alignment

pytestmark = pytest.mark.skipif(not alignment.available(), reason="needs the `align` extra")

SCALE = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60, 64, 67, 72]


def _write(path, notes, spb=0.5, skip=()):
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    for i, n in enumerate(notes):
        if i in skip:
            tr.append(mido.Message("note_off", note=0, velocity=0, time=int(480 * spb / 0.5)))
            continue
        tr.append(mido.Message("note_on", note=n, velocity=70, time=0))
        tr.append(mido.Message("note_off", note=n, velocity=0, time=int(480 * spb / 0.5)))
    mid.save(path)


@pytest.mark.parametrize(("skip", "expected"), [((), 4), ((2, 5, 9, 12), 1)])
def test_autograde(client, skip, expected):
    from sqlmodel import Session

    from piano_companion.config import get_settings
    from piano_companion.db import get_engine
    from piano_companion.models import PracticeSession

    s = get_settings()
    p = client.post("/api/pieces", json={"title": "C major scale"}).json()
    score = s.library_dir / "scale.mid"
    _write(score, SCALE)
    take = s.recordings_dir / "take.mid"
    _write(take, SCALE, skip=skip)
    with Session(get_engine()) as db:
        from piano_companion.models import Piece

        piece = db.get(Piece, p["id"])
        piece.midi_path = "scale.mid"
        db.add(piece)
        db.add(PracticeSession(midi_path="take.mid", note_count=len(SCALE)))
        db.commit()
    item = client.post(
        "/api/practice/items",
        json={"title": "Scale", "kind": "repertoire", "piece_id": p["id"], "details": {"target_bpm": 120}},
    ).json()
    r = client.post(f"/api/practice/items/{item['id']}/autograde", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rating"] == expected, body
    assert client.get(f"/api/sessions/{body['session_id']}").json()["analysis"]
