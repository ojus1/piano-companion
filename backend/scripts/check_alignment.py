"""Sanity-check auto-grading on a real score with synthetic takes (needs the `align` extra).

    uv run --extra align python scripts/check_alignment.py path/to/score.musicxml [first_bar last_bar]
"""

import sys
import tempfile
from pathlib import Path

import mido
import numpy as np

from piano_companion import alignment as al
from piano_companion.grading import grade_attempt


def perform(sna, bpm, jitter=0.01, drop=0.0, wrong=0, stall=False, seed=0) -> Path:
    rng = np.random.default_rng(seed)
    spq = 60 / bpm
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    ev = []
    half = np.median(sna["onset_quarter"])
    for n in sna:
        if rng.random() < drop:
            continue
        t = n["onset_quarter"] * spq + rng.normal(0, jitter) + 1
        if stall and n["onset_quarter"] > half:
            t += 4 * spq
        d = max(0.05, n["duration_quarter"] * spq * 0.9)
        ev += [(t, 1, int(n["pitch"])), (t + d, 0, int(n["pitch"]))]
    for _ in range(wrong):
        t = rng.uniform(1, sna["onset_quarter"].max() * spq)
        ev += [(t, 1, 30), (t + 0.1, 0, 30)]
    ev.sort()
    last = 0
    for t, on, p in ev:
        tick = int(mido.second2tick(t, 480, 500000))
        kind = "note_on" if on else "note_off"
        tr.append(mido.Message(kind, note=p, velocity=64 if on else 0, time=tick - last))
        last = tick
    f = tempfile.NamedTemporaryFile(suffix=".mid", delete=False)
    mid.save(f.name)
    return Path(f.name)


def main():
    score = Path(sys.argv[1])
    bars = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else None
    sna = al.load_score_notes(score, bars)
    print(f"{len(sna)} score notes")
    cases = {
        "clean": dict(bpm=120, jitter=0.005),
        "slow (90 of 120)": dict(bpm=90),
        "one stall": dict(bpm=120, stall=True),
        "sloppy": dict(bpm=120, drop=0.1, wrong=10, jitter=0.04),
    }
    for label, kw in cases.items():
        a, raw = al.attempt_from_files(score, perform(sna, **kw), target_bpm=120, measures=bars)
        print(f"{label:18s} -> {'?AHGE'[grade_attempt(a)]}  {raw}")


if __name__ == "__main__":
    main()
