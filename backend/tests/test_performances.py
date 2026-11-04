import mido

from piano_companion.midi_recorder import MidiCapture, SessionSegmenter, TakeRecorder


def notes(rec, start, pitches, step=0.25):
    t = start
    for n in pitches:
        rec.feed(mido.Message("note_on", note=n, velocity=64), now=t)
        rec.feed(mido.Message("note_off", note=n, velocity=0), now=t + step * 0.8)
        t += step
    return t


def test_take_trims_leading_silence_and_keeps_early_pedal(tmp_path):
    take = TakeRecorder(tmp_path)
    assert take.start("Merry-Go-Round of Life", "cover", now=0.0)
    take.feed(mido.Message("control_change", control=64, value=127), now=2.0)
    notes(take, 5.0, [60, 64, 67, 72])
    ft = take.stop()
    assert not take.active
    assert ft.title == "Merry-Go-Round of Life" and ft.kind == "cover" and ft.note_count == 4
    mid = mido.MidiFile(ft.midi_path)
    msgs = [m for m in mid if not m.is_meta]
    assert msgs[0].type == "control_change" and msgs[0].time == 0  # pedal pulled to t=0
    assert msgs[1].type == "note_on" and msgs[1].time == 0  # first note at t=0
    assert abs(mid.length - (3 * 0.25 + 0.2)) < 0.01
    assert ft.duration_s == 0.95


def test_empty_take_writes_nothing_and_cancel(tmp_path):
    take = TakeRecorder(tmp_path)
    take.start("nothing", now=0.0)
    assert take.stop() is None
    assert list(tmp_path.iterdir()) == []
    take.start("cancel me", now=0.0)
    notes(take, 1.0, [60, 62])
    assert take.cancel() and not take.active


def test_take_auto_stops_after_silence(tmp_path):
    saved = []
    take = TakeRecorder(tmp_path, idle_seconds=10, on_auto_stop=saved.append)
    take.start("forgot to stop", now=0.0)
    end = notes(take, 1.0, [60, 62, 64])
    take.tick(now=end + 5)
    assert take.active
    take.tick(now=end + 11)
    assert not take.active and saved[0].auto_stopped and saved[0].note_count == 3


def test_capture_routes_to_take_not_practice_session(tmp_path):
    done = []
    seg = SessionSegmenter(tmp_path / "rec", idle_seconds=5, min_notes=1, on_finished=done.append)
    take = TakeRecorder(tmp_path / "perf")
    cap = MidiCapture(seg, "auto", loop=None, take=take)
    for t, n in [(0.0, 60), (0.5, 62)]:
        cap.route(mido.Message("note_on", note=n, velocity=60), now=t)
    take.start("piece", now=1.0)
    seg.end_active()
    assert len(done) == 1  # practice session closed when the take began
    cap.route(mido.Message("note_on", note=64, velocity=60), now=2.0)
    assert not seg.active and take.info()["note_count"] == 1


def test_performance_api_flow(client):
    rec = client.app.state.recorder
    assert client.get("/api/status").json()["take"] is None
    r = client.post("/api/performances/start", json={"title": "Liebestraum No. 3", "kind": "performance"})
    assert r.status_code == 200 and r.json()["title"] == "Liebestraum No. 3"
    assert client.post("/api/performances/start", json={"title": "again"}).status_code == 409
    assert client.get("/api/status").json()["take"]["title"] == "Liebestraum No. 3"
    assert client.post("/api/play", json={"session_id": 1}).status_code == 409
    for n in (60, 64, 67):
        rec.take.feed(mido.Message("note_on", note=n, velocity=70))
        rec.take.feed(mido.Message("note_off", note=n, velocity=0))
    perf = client.post("/api/performances/stop").json()["performance"]
    assert perf["note_count"] == 3 and perf["kind"] == "performance"
    assert client.post("/api/performances/stop").status_code == 409

    listed = client.get("/api/performances").json()
    assert [p["id"] for p in listed] == [perf["id"]]
    midi = client.get(f"/api/performances/{perf['id']}/midi")
    assert midi.status_code == 200 and midi.content.startswith(b"MThd")
    assert "Liebestraum%20No.%203.mid" in midi.headers["content-disposition"]

    p = client.patch(f"/api/performances/{perf['id']}", json={"title": "Liebestraum take 2", "favorite": True}).json()
    assert p["title"] == "Liebestraum take 2" and p["favorite"] is True
    assert client.patch(f"/api/performances/{perf['id']}", json={"kind": "jam"}).status_code == 422

    # Performances live outside the recordings dir, so the recordings cap never sees them.
    from piano_companion.config import get_settings

    s = get_settings()
    f = s.performances_dir / perf["midi_path"]
    assert f.is_file() and not f.resolve().is_relative_to(s.recordings_dir.resolve())
    assert client.delete(f"/api/performances/{perf['id']}").status_code == 204
    assert not f.exists() and client.get("/api/performances").json() == []


def test_empty_take_and_default_title(client):
    r = client.post("/api/performances/start", json={"kind": "cover"}).json()
    assert r["title"].startswith("Untitled cover")
    assert client.post("/api/performances/stop").json() == {"performance": None}
    assert client.post("/api/performances/start", json={"kind": "jam"}).status_code == 422
