import mido

from piano_companion.midi_recorder import SessionSegmenter


def play(seg, start, notes, step=0.25):
    t = start
    for n in notes:
        seg.feed(mido.Message("note_on", note=n, velocity=64), now=t)
        seg.feed(mido.Message("note_off", note=n, velocity=0), now=t + step * 0.8)
        t += step
    return t


def test_session_split_on_silence(tmp_path):
    done = []
    seg = SessionSegmenter(tmp_path, idle_seconds=10, min_notes=4, on_finished=done.append)
    end = play(seg, 100.0, [60, 62, 64, 65, 67, 69, 71, 72])
    assert seg.active and not done
    seg.tick(now=end + 11)
    assert not seg.active and len(done) == 1
    s = done[0]
    assert s.note_count == 8 and s.midi_path.exists()
    assert s.metrics["ioi_median_ms"] == 250 and s.metrics["ioi_cv"] < 0.01
    # File round-trips with the same notes and timing.
    mid = mido.MidiFile(s.midi_path)
    ons = [m for m in mid if m.type == "note_on" and m.velocity > 0]
    assert [m.note for m in ons] == [60, 62, 64, 65, 67, 69, 71, 72]
    assert abs(mid.length - 7 * 0.25 - 0.2) < 0.01


def test_blip_discarded_and_active_sensing_ignored(tmp_path):
    done = []
    seg = SessionSegmenter(tmp_path, idle_seconds=5, min_notes=4, on_finished=done.append)
    seg.feed(mido.Message("active_sensing"), now=0)
    assert not seg.active
    end = play(seg, 1.0, [60, 61])
    seg.tick(now=end + 6)
    assert done == []


def test_two_sessions(tmp_path):
    done = []
    seg = SessionSegmenter(tmp_path, idle_seconds=5, min_notes=2, on_finished=done.append)
    end = play(seg, 0.0, [60, 62, 64])
    play(seg, end + 30, [65, 67, 69])  # feeding after the gap closes the first one
    seg.flush()
    assert len(done) == 2
