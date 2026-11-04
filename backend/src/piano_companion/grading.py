"""Turn MIDI attempt metrics into an FSRS rating, following curriculum scheduler_defaults.grading.

Metrics (computed per attempt by score alignment, see the research notes):
  accuracy      A: (matched correct-pitch notes - 0.5 * extra notes) / expected notes
  tempo_ratio   T: achieved BPM / current tempo-ladder rung BPM
  timing_dev_ms: median absolute onset deviation from the smoothed local tempo curve
  breakdowns:   stops/restarts (gaps > 2 beats or backward jumps)
  ibi_cv:       coefficient of variation of inter-beat intervals (evenness)
  next_rung_ratio: next_rung / current_rung (Easy requires T to reach it)

The thresholds are the research thread's editorial proposal; they are read from curriculum.json when
present and the defaults below mirror it. The user can always override a grade.
"""

from dataclasses import dataclass

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4


@dataclass
class Attempt:
    accuracy: float
    tempo_ratio: float = 1.0
    breakdowns: int = 0
    timing_dev_ms: float | None = None
    ibi_cv: float | None = None
    next_rung_ratio: float | None = None


@dataclass
class Thresholds:
    again_accuracy: float = 0.85
    again_breakdowns: int = 2
    good_accuracy: float = 0.95
    good_tempo: float = 0.95
    hard_tempo: float = 0.8
    easy_accuracy: float = 0.98
    easy_timing_dev_ms: float = 30.0
    technique_good_ibi_cv: float = 0.08
    technique_easy_ibi_cv: float = 0.05

    @classmethod
    def from_curriculum(cls, grading: dict) -> "Thresholds":
        t = cls()
        extra = grading.get("technique_drill_extra", {})
        t.technique_good_ibi_cv = extra.get("Good_requires_ibi_cv_max", t.technique_good_ibi_cv)
        t.technique_easy_ibi_cv = extra.get("Easy_requires_ibi_cv_max", t.technique_easy_ibi_cv)
        return t


def grade_attempt(a: Attempt, technique: bool = False, t: Thresholds | None = None) -> int:
    t = t or Thresholds()
    if a.accuracy < t.again_accuracy or a.breakdowns >= t.again_breakdowns:
        return AGAIN
    if a.accuracy < t.good_accuracy or a.tempo_ratio < t.hard_tempo or a.breakdowns == 1:
        return HARD
    if a.tempo_ratio < t.good_tempo:
        # Between Hard's and Good's tempo bars (0.8 <= T < 0.95): accurate but under tempo.
        return HARD
    rating = GOOD
    if (
        a.accuracy >= t.easy_accuracy
        and a.timing_dev_ms is not None
        and a.timing_dev_ms < t.easy_timing_dev_ms
        and (a.next_rung_ratio is None or a.tempo_ratio >= a.next_rung_ratio)
    ):
        rating = EASY
    if technique and a.ibi_cv is not None:
        if a.ibi_cv > t.technique_good_ibi_cv:
            rating = HARD
        elif rating == EASY and a.ibi_cv > t.technique_easy_ibi_cv:
            rating = GOOD
    return rating


def grade_drill(correct: bool, latency_s: float) -> int:
    """Theory/ear drills: wrong = Again, slow (>3 s) = Hard, 1-3 s = Good, <1 s = Easy."""
    if not correct:
        return AGAIN
    if latency_s > 3:
        return HARD
    return GOOD if latency_s >= 1 else EASY
