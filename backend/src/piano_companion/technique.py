"""Score a technique drill (scale, arpeggio, chord sequence) played on the piano against its expected notes.

The tablet generates the drill and knows the expected sequence of *steps* (each step is the set of
pitches that sound together: one note for a hands-separate scale, two for hands together, three or
four for a block chord). It streams the notes it heard from the Pi's live MIDI feed back here with
the Pi's own timestamps, so network jitter between the Pi and the tablet doesn't affect timing.

Metrics mirror grading.Attempt so the curriculum's FSRS rules apply unchanged:
  accuracy      (matched correct-pitch notes - 0.5 * extra notes) / expected notes
  tempo_ratio   achieved BPM (least-squares fit of step onsets) / target BPM
  timing_dev_ms median absolute onset deviation from that fitted steady pulse
  ibi_cv        coefficient of variation of the intervals between consecutive steps (evenness)
  breakdowns    gaps longer than two beats between notes
"""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, median, pstdev

from .grading import Attempt


@dataclass
class Played:
    note: int
    t: float  # seconds, any monotonic clock


def group_onsets(notes: Sequence[Played], window: float) -> list[list[Played]]:
    """Notes struck within `window` seconds of a group's first note count as one chord/step."""
    groups: list[list[Played]] = []
    for n in sorted(notes, key=lambda n: n.t):
        if groups and n.t - groups[-1][0].t <= window:
            groups[-1].append(n)
        else:
            groups.append([n])
    return groups


def align(steps: Sequence[set[int]], groups: Sequence[list[Played]]) -> list[tuple[int, int, int]]:
    """Order-preserving alignment of played groups to expected steps maximising correct pitches.

    Returns (step index, group index, correct pitches) for every aligned pair with at least one hit.
    """
    n, m = len(steps), len(groups)
    pitches = [{p.note for p in g} for g in groups]
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            hit = len(steps[i - 1] & pitches[j - 1])
            score[i][j] = max(score[i - 1][j], score[i][j - 1], score[i - 1][j - 1] + hit if hit else 0)
    pairs = []
    i, j = n, m
    while i > 0 and j > 0:
        hit = len(steps[i - 1] & pitches[j - 1])
        if hit and score[i][j] == score[i - 1][j - 1] + hit:
            pairs.append((i - 1, j - 1, hit))
            i, j = i - 1, j - 1
        elif score[i][j] == score[i - 1][j]:
            i -= 1
        else:
            j -= 1
    return pairs[::-1]


def _fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mx, my = mean(xs), mean(ys)
    var = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False)) / var if var else 0.0
    return slope, my - slope * mx


def score_attempt(
    steps: Sequence[Sequence[int]],
    notes: Sequence[Played],
    bpm: float,
    steps_per_beat: float,
    pitch_class: bool = False,
) -> tuple[Attempt, dict]:
    """pitch_class=True accepts any octave or inversion (chord-symbol drills); doublings aren't errors."""
    if pitch_class:
        steps = [{p % 12 for p in s} for s in steps]
        notes = [Played(n.note % 12, n.t) for n in notes]
    expected = [set(s) for s in steps]
    total = sum(len(s) for s in expected) or 1
    beat = 60.0 / bpm
    step_dur = beat / steps_per_beat
    groups = group_onsets(notes, window=min(0.08, 0.45 * step_dur))
    pairs = align(expected, groups)

    if not pairs:
        metrics = {
            "accuracy": 0.0,
            "tempo_ratio": None,
            "achieved_bpm": None,
            "ibi_cv": None,
            "timing_dev_ms": None,
            "breakdowns": 0,
            "matched": 0,
            "expected": total,
            "extra": len(notes),
        }
        return Attempt(accuracy=0.0, tempo_ratio=0.0), metrics

    # Only judge the stretch from the first to the last matched step: warm-up noodling and
    # trailing notes after the drill aren't counted as errors.
    first_g, last_g = pairs[0][1], pairs[-1][1]
    window = groups[first_g : last_g + 1]
    played_count = sum(len({p.note for p in g}) if pitch_class else len(g) for g in window)
    matched = sum(h for _, _, h in pairs)
    extra = played_count - matched
    accuracy = max(0.0, (matched - 0.5 * extra) / total)

    breakdowns = sum(1 for a, b in zip(window, window[1:], strict=False) if b[0].t - a[0].t > 2 * beat)

    onsets = [(s, groups[g][0].t) for s, g, _ in pairs]
    tempo_ratio = achieved = timing_dev_ms = ibi_cv = None
    if len(onsets) >= 3:
        slope, icpt = _fit([float(s) for s, _ in onsets], [t for _, t in onsets])
        if slope > 0:
            achieved = 60.0 / (slope * steps_per_beat)
            tempo_ratio = achieved / bpm
            timing_dev_ms = median(abs(t - (icpt + slope * s)) for s, t in onsets) * 1000
        ibis = [(t2 - t1) for (s1, t1), (s2, t2) in zip(onsets, onsets[1:], strict=False) if s2 - s1 == 1]
        if len(ibis) >= 2 and mean(ibis) > 0:
            ibi_cv = pstdev(ibis) / mean(ibis)

    attempt = Attempt(
        accuracy=accuracy,
        tempo_ratio=tempo_ratio if tempo_ratio is not None else 0.0,
        breakdowns=breakdowns,
        timing_dev_ms=timing_dev_ms,
        ibi_cv=ibi_cv,
    )
    r = lambda x, d=3: None if x is None else round(x, d)  # noqa: E731
    metrics = {
        "accuracy": r(accuracy),
        "tempo_ratio": r(tempo_ratio),
        "achieved_bpm": r(achieved, 1),
        "ibi_cv": r(ibi_cv),
        "timing_dev_ms": r(timing_dev_ms, 1),
        "breakdowns": breakdowns,
        "matched": matched,
        "expected": total,
        "extra": extra,
    }
    return attempt, metrics
