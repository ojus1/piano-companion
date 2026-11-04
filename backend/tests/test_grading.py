from datetime import UTC, datetime, timedelta

from piano_companion import srs
from piano_companion.grading import AGAIN, EASY, GOOD, HARD, Attempt, grade_attempt, grade_drill


def test_piece_rules():
    assert grade_attempt(Attempt(accuracy=0.80)) == AGAIN
    assert grade_attempt(Attempt(accuracy=0.99, breakdowns=2)) == AGAIN
    assert grade_attempt(Attempt(accuracy=0.90)) == HARD
    assert grade_attempt(Attempt(accuracy=0.99, tempo_ratio=0.75)) == HARD
    assert grade_attempt(Attempt(accuracy=0.99, breakdowns=1)) == HARD
    assert grade_attempt(Attempt(accuracy=0.96, tempo_ratio=1.0)) == GOOD
    assert grade_attempt(Attempt(accuracy=0.99, timing_dev_ms=20)) == EASY
    # Easy also needs the next tempo rung
    assert grade_attempt(Attempt(accuracy=0.99, timing_dev_ms=20, next_rung_ratio=1.11)) == GOOD


def test_technique_evenness():
    good = Attempt(accuracy=0.99, timing_dev_ms=20, ibi_cv=0.06)
    assert grade_attempt(good, technique=True) == GOOD  # Easy needs ibi_cv <= 0.05
    assert grade_attempt(Attempt(accuracy=0.99, ibi_cv=0.12), technique=True) == HARD


def test_drills():
    assert [grade_drill(False, 0.5), grade_drill(True, 4), grade_drill(True, 2), grade_drill(True, 0.5)] == [
        AGAIN,
        HARD,
        GOOD,
        EASY,
    ]


def test_srs_decks_and_sight_reading():
    now = datetime(2026, 11, 4, 18, tzinfo=UTC)
    state, due, _ = srs.grade(srs.new_state(), GOOD, "technique", now)
    assert due > now + timedelta(hours=12)  # learning steps disabled: next review is a later day
    same, due_sr, log = srs.grade({}, GOOD, "sight_reading", now)
    assert due_sr == datetime(2026, 11, 5, tzinfo=UTC) and log["scheduler"] == "daily"
