import random

from piano_companion.technique import Played, score_attempt

C_MAJOR_UP_DOWN = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60]


def play(seq, bpm, steps_per_beat, jitter=0.0, start=100.0, seed=1):
    rng = random.Random(seed)
    step = 60 / bpm / steps_per_beat
    return [Played(p, start + i * step + rng.uniform(-jitter, jitter)) for i, p in enumerate(seq)]


def test_clean_scale_scores_full_marks():
    steps = [[p] for p in C_MAJOR_UP_DOWN]
    a, m = score_attempt(steps, play(C_MAJOR_UP_DOWN, 80, 2, jitter=0.005), 80, 2)
    assert m["accuracy"] == 1.0
    assert abs(m["achieved_bpm"] - 80) < 2
    assert m["ibi_cv"] < 0.05
    assert m["breakdowns"] == 0


def test_wrong_note_and_slow_tempo():
    seq = C_MAJOR_UP_DOWN.copy()
    seq[3] = 66  # F# instead of F
    a, m = score_attempt([[p] for p in C_MAJOR_UP_DOWN], play(seq, 60, 2), 80, 2)
    assert m["matched"] == 14 and m["extra"] == 1
    assert abs(a.accuracy - (14 - 0.5) / 15) < 1e-6
    assert abs(m["tempo_ratio"] - 0.75) < 0.02


def test_noodling_before_and_after_is_ignored():
    notes = [Played(30, 90.0), Played(31, 90.3)] + play(C_MAJOR_UP_DOWN, 80, 2) + [Played(100, 120.0)]
    _, m = score_attempt([[p] for p in C_MAJOR_UP_DOWN], notes, 80, 2)
    assert m["accuracy"] == 1.0 and m["extra"] == 0


def test_chords_group_and_breakdown_counted():
    steps = [[60, 64, 67], [64, 67, 72], [67, 72, 76], [72, 76, 79]]
    notes = []
    for i, chord in enumerate(steps):
        t = 10 + i * 1.0 + (3.0 if i >= 2 else 0)  # a 4-second gap before the third chord
        notes += [Played(p, t + k * 0.015) for k, p in enumerate(chord)]
    _, m = score_attempt(steps, notes, 60, 1)
    assert m["accuracy"] == 1.0
    assert m["breakdowns"] == 1


def test_nothing_played():
    a, m = score_attempt([[60]], [], 80, 1)
    assert a.accuracy == 0 and m["matched"] == 0


def test_attempt_endpoint_applies_once_while_due(client):
    body = {
        "family": "scale_major",
        "title": "C major scale, RH, 1 octave",
        "concept_id": "t_scales_major_hs",
        "bpm": 80,
        "steps_per_beat": 2,
        "steps": [[p] for p in C_MAJOR_UP_DOWN],
        "notes": [{"note": n.note, "t": n.t} for n in play(C_MAJOR_UP_DOWN, 80, 2, jitter=0.004)],
        "drill": {"key": "C"},
    }
    r = client.post("/api/technique/attempts", json=body)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["rating"] >= 3 and first["applied"] is True
    items = client.get("/api/practice/items").json()
    assert [i["source_key"] for i in items] == ["concept:t_scales_major_hs"]
    # Second run the same day: logged, but the card isn't due any more so FSRS isn't touched.
    second = client.post("/api/technique/attempts", json=body).json()
    assert second["applied"] is False
    hist = client.get("/api/technique/attempts").json()
    assert len(hist) == 2 and "drill" not in hist[0]
    assert client.post("/api/technique/attempts", json={**body, "bpm": 0}).status_code == 422


def test_pitch_class_mode_accepts_any_voicing():
    steps = [[60, 64, 67], [62, 65, 69]]  # C, Dm
    notes = [Played(p, 5.0 + k * 0.01) for k, p in enumerate([52, 60, 67, 72])]  # E3 C4 G4 C5
    notes += [Played(p, 9.0 + k * 0.01) for k, p in enumerate([50, 57, 65])]
    _, m = score_attempt(steps, notes, 60, 0.25, pitch_class=True)
    assert m["accuracy"] == 1.0 and m["extra"] == 0
    _, strict = score_attempt(steps, notes, 60, 0.25)
    assert strict["accuracy"] < 1.0
