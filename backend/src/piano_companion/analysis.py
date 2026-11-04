"""Cheap, deterministic metrics computed from a session's MIDI right after it ends.

These are signals for the dashboard and for the (later) LLM coach, not grades. Score-aware
analysis (wrong notes, rhythm vs. the written score) comes once a session is linked to a piece.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class NoteEvent:
    t: float  # seconds since session start
    note: int
    velocity: int
    duration: float | None = None


def session_metrics(notes: list[NoteEvent], pedal_downs: int = 0) -> dict:
    if not notes:
        return {"note_count": 0}
    times = np.array([n.t for n in notes])
    vel = np.array([n.velocity for n in notes], dtype=float)
    pitches = np.array([n.note for n in notes])
    duration = float(times[-1] - times[0]) if len(times) > 1 else 0.0

    # Onset clustering: notes within 30 ms are one "event" (a chord).
    onsets = [times[0]]
    for t in times[1:]:
        if t - onsets[-1] > 0.03:
            onsets.append(t)
    ioi = np.diff(onsets)
    # Inter-onset intervals over 2 s are pauses, not rhythm.
    ioi = ioi[(ioi > 0.05) & (ioi < 2.0)]

    out = {
        "note_count": len(notes),
        "duration_s": round(duration, 1),
        "notes_per_min": round(len(notes) / (duration / 60), 1) if duration > 0 else None,
        "velocity_mean": round(float(vel.mean()), 1),
        "velocity_std": round(float(vel.std()), 1),  # dynamic range proxy
        "pitch_low": int(pitches.min()),
        "pitch_high": int(pitches.max()),
        "left_hand_share": round(float((pitches < 60).mean()), 2),  # below middle C, rough
        "pedal_downs": pedal_downs,
    }
    if len(ioi) >= 4:
        # Coefficient of variation of inter-onset intervals: lower = steadier pulse.
        # Only meaningful for scale/etude drills with even note values.
        out["ioi_median_ms"] = round(float(np.median(ioi)) * 1000)
        out["ioi_cv"] = round(float(ioi.std() / ioi.mean()), 3)
    return out
