"""Score-to-performance alignment and attempt metrics, for automatic grading.

Uses partitura (score/MIDI parsing: MusicXML, MIDI, **kern, MEI) and parangonar's DualDTWNoteMatcher
(note alignment), both Apache-2.0, as recommended by the research thread. They are in the optional
`align` extra; `available()` says whether they are installed.

Metrics follow curriculum.json scheduler_defaults.grading.metrics.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np

from .grading import Attempt


def available() -> bool:
    try:
        import parangonar  # noqa: F401
        import partitura  # noqa: F401
    except ImportError:
        return False
    return True


def load_score_notes(path: Path, measures: tuple[int, int] | None = None) -> np.ndarray:
    """Score note array; `measures` (inclusive, 1-based numbers) restricts it to a passage."""
    import partitura as pt

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # partitura warns on every unsupported direction/text
        score = pt.load_score(str(path))
    na = score.note_array(include_grace_notes=True)
    if measures:
        part = score.parts[0]
        ms = [m for m in part.measures if measures[0] <= (m.number or 0) <= measures[1]]
        if ms:
            q0, q1 = part.quarter_map([ms[0].start.t, ms[-1].end.t])
            na = na[(na["onset_quarter"] >= q0) & (na["onset_quarter"] < q1)]
    return na


def load_performance_notes(path: Path) -> np.ndarray:
    import partitura as pt

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pt.load_performance_midi(str(path)).note_array()


def align(score_na: np.ndarray, perf_na: np.ndarray) -> list[dict]:
    import parangonar as pa

    return pa.DualDTWNoteMatcher()(score_na, perf_na)


def metrics_from_alignment(
    score_na: np.ndarray,
    perf_na: np.ndarray,
    alignment: list[dict],
    target_bpm: float | None = None,
    next_rung_ratio: float | None = None,
) -> tuple[Attempt, dict]:
    """Returns the Attempt used for grading, plus a dict of raw metrics to log."""
    n_expected = len(score_na)
    s_on = dict(zip(score_na["id"], score_na["onset_quarter"], strict=True))
    p_on = dict(zip(perf_na["id"], perf_na["onset_sec"], strict=True))
    matches = [a for a in alignment if a["label"] == "match"]
    matches = _main_attempt(matches, s_on, p_on)
    # Only notes played *during* the attempt count as extra: noodling before/after (or the rest of
    # the piece, when grading a passage) is not an error.
    if matches:
        t0 = min(p_on[m["performance_id"]] for m in matches)
        t1 = max(p_on[m["performance_id"]] for m in matches)
        extra = sum(1 for a in alignment if a["label"] == "insertion" and t0 <= p_on[a["performance_id"]] <= t1)
    else:
        extra = 0
    missed = n_expected - len(matches)
    accuracy = max(0.0, (len(matches) - 0.5 * extra) / n_expected) if n_expected else 0.0
    pairs = sorted((p_on[m["performance_id"]], s_on[m["score_id"]]) for m in matches)
    raw: dict = {"expected": n_expected, "matched": len(matches), "extra": extra, "missed": missed}

    tempo_ratio, timing_dev, ibi_cv, breakdowns = 1.0, None, None, 0
    if len(pairs) >= 4:
        perf_t = np.array([p for p, _ in pairs])
        score_q = np.array([q for _, q in pairs])
        # Collapse chords: one point per distinct score onset (mean performed time).
        uq, inv = np.unique(score_q, return_inverse=True)
        ut = np.array([perf_t[inv == i].mean() for i in range(len(uq))])
        dq, dt = np.diff(uq), np.diff(ut)
        ok = dq > 0
        spq_local = dt[ok] / dq[ok]  # seconds per quarter between consecutive onsets
        spq = float(np.median(spq_local[spq_local > 0])) if np.any(spq_local > 0) else None
        if spq:
            bpm = 60.0 / spq
            raw["achieved_bpm_quarter"] = round(bpm, 1)
            if target_bpm:
                tempo_ratio = bpm / target_bpm
            # Breakdowns: a stall longer than 2 beats beyond what the score asks, or a jump back.
            expected_dt = dq * spq
            breakdowns = int(np.sum((dt - expected_dt) > 2 * spq))
            score_seq = score_q  # performance order
            breakdowns += int(np.sum(np.diff(score_seq) < -1.0))
            # Timing deviation from a smoothed local tempo curve (rolling linear fit, 9 onsets).
            res = []
            for i in range(len(uq)):
                lo, hi = max(0, i - 4), min(len(uq), i + 5)
                if hi - lo >= 3:
                    a, b = np.polyfit(uq[lo:hi], ut[lo:hi], 1)
                    res.append(abs(ut[i] - (a * uq[i] + b)))
            timing_dev = float(np.median(res) * 1000) if res else None
            # Evenness: spread of performed/expected inter-onset ratios.
            r = (dt[ok] / dq[ok]) / spq
            r = r[(r > 0.25) & (r < 4)]
            ibi_cv = float(r.std() / r.mean()) if len(r) >= 3 else None
    raw.update(
        accuracy=round(accuracy, 3),
        tempo_ratio=round(tempo_ratio, 3),
        timing_dev_ms=None if timing_dev is None else round(timing_dev, 1),
        ibi_cv=None if ibi_cv is None else round(ibi_cv, 3),
        breakdowns=breakdowns,
    )
    attempt = Attempt(
        accuracy=accuracy,
        tempo_ratio=tempo_ratio,
        breakdowns=breakdowns,
        timing_dev_ms=timing_dev,
        ibi_cv=ibi_cv,
        next_rung_ratio=next_rung_ratio,
    )
    return attempt, raw


def _main_attempt(matches: list[dict], s_on: dict, p_on: dict) -> list[dict]:
    """Keep the matches that belong to one coherent run through the score.

    A take may hold several attempts or the whole piece while only a passage is graded, so the
    aligner can pair score notes with performed notes far away in time. We estimate the dominant
    time offset (performed time minus score position at the median tempo) and drop matches that
    sit more than 8 beats away from it.
    """
    if len(matches) < 8:
        return matches
    pts = sorted(((p_on[m["performance_id"]], s_on[m["score_id"]], m) for m in matches), key=lambda p: (p[0], p[1]))
    t = np.array([p[0] for p in pts])
    q = np.array([p[1] for p in pts])
    dq, dt = np.diff(q), np.diff(t)
    ok = (dq > 0) & (dt > 0)
    if not ok.any():
        return matches
    spq = float(np.median(dt[ok] / dq[ok]))
    offset = t - q * spq
    center = float(np.median(offset))
    keep = np.abs(offset - center) <= 8 * spq
    return [p[2] for p, k in zip(pts, keep, strict=True) if k]


def attempt_from_files(
    score_path: Path,
    performance_midi: Path,
    target_bpm: float | None = None,
    measures: tuple[int, int] | None = None,
) -> tuple[Attempt, dict]:
    sna = load_score_notes(score_path, measures)
    pna = load_performance_notes(performance_midi)
    return metrics_from_alignment(sna, pna, align(sna, pna), target_bpm)
