from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session

from piano_companion.progress import compute_streak, drill_xp, level_for, technique_series

MON = date(2026, 11, 2)  # a Monday


def days(*offsets: int) -> set[date]:
    return {MON + timedelta(days=o) for o in offsets}


def test_streak_counts_consecutive_days_and_today_pending():
    s = compute_streak(days(0, 1, 2), MON + timedelta(days=3))
    assert s.current == 3 and s.longest == 3
    assert not s.practiced_today and s.at_risk  # today not played yet: streak kept but at risk


def test_freeze_covers_a_missed_day_then_runs_out():
    # Start with 1 freeze. Miss Wed (frozen), keep going; miss Sat and Sun with no freezes left -> reset.
    s = compute_streak(days(0, 1, 3, 4), MON + timedelta(days=4))
    assert s.day_status[MON + timedelta(days=2)] == "frozen"
    assert s.current == 4 and s.freezes == 0
    s = compute_streak(days(0, 1, 3, 4, 7), MON + timedelta(days=7))
    assert s.day_status[MON + timedelta(days=5)] == "missed"
    assert s.current == 1 and s.longest == 4


def test_weekly_goal_earns_freeze_and_week_streak():
    # Week 1: 5 days (goal met) -> +1 freeze (cap 2). Week 2: Mon, Tue practised; Wed + Thu missed use freezes.
    s = compute_streak(days(0, 1, 2, 3, 4, 7, 8, 11), MON + timedelta(days=11))
    assert s.week_streak == 1 and s.weeks_met == 1
    assert s.day_status[MON + timedelta(days=5)] == "frozen"  # Sat uses the starting freeze
    # Sun: no freeze left until the week closes -> missed, so the streak restarts on the next Monday.
    assert s.day_status[MON + timedelta(days=6)] == "missed"
    assert s.day_status[MON + timedelta(days=9)] == "frozen"  # the earned freeze
    assert s.day_status[MON + timedelta(days=10)] == "missed"
    assert s.current == 1


def test_this_week_counts_once_goal_reached():
    s = compute_streak(days(0, 1, 2, 3, 4), MON + timedelta(days=4), weekly_days=5)
    assert s.week_days == 5 and s.week_streak == 1


def test_xp_levels_and_drill_xp():
    assert level_for(0)["level"] == 1 and level_for(99)["level"] == 1
    assert level_for(100)["level"] == 2 and level_for(300)["level"] == 3
    assert drill_xp(1.0, 4) == 15 and drill_xp(0.5, 1) == 5 and drill_xp(None, 2) == 0


def test_technique_series_tracks_clean_tempo_and_accuracy_change():
    t0 = datetime(2026, 11, 2, 12, tzinfo=UTC)
    rows = [
        {
            "created_at": t0,
            "family": "scale_major",
            "concept_id": "c",
            "bpm": 80,
            "rating": 2,
            "metrics": {"accuracy": 0.6, "achieved_bpm": 70, "ibi_cv": 0.2},
        },
        {
            "created_at": t0 + timedelta(days=1),
            "family": "scale_major",
            "concept_id": "c",
            "bpm": 90,
            "rating": 3,
            "metrics": {"accuracy": 0.95, "achieved_bpm": 88, "ibi_cv": 0.1},
        },
    ]
    out = technique_series(rows)
    fam = out["families"][0]
    assert fam["attempts"] == 2 and fam["best_clean_bpm"] == 88  # the 0.6-accuracy run isn't "clean"
    assert fam["accuracy_change"] == 0.35
    assert fam["series"][1]["evenness"] == 0.9


def test_progress_endpoint_and_goals(client):
    from piano_companion.db import get_engine
    from piano_companion.models import PracticeSession, TechniqueAttempt

    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        for i in range(3):
            start = now - timedelta(days=i, minutes=30)
            db.add(PracticeSession(started_at=start, ended_at=start + timedelta(minutes=25), note_count=300))
        db.add(
            TechniqueAttempt(
                family="scale_major",
                concept_id="t_scales_major_hs",
                title="C major",
                bpm=80,
                rating=4,
                metrics={"accuracy": 1.0, "achieved_bpm": 81, "ibi_cv": 0.05},
            )
        )
        db.commit()
    p = client.get("/api/progress").json()
    assert p["streak"]["current"] >= 2  # 3 days unless the run straddles midnight
    assert p["today_minutes"] > 0 and p["time"]["total_minutes"] == 75
    assert p["xp"]["xp"] >= 75 + 15
    assert p["technique"]["families"][0]["family"] == "scale_major"
    assert len(p["consistency"]["calendar"]) % 7 in range(1, 8)
    assert {a["id"] for a in p["achievements"] if a["earned"]} >= {"first_day", "hours_1"}

    assert client.put("/api/goals", json={"daily_minutes": 30}).json()["daily_minutes"] == 30
    assert client.get("/api/goals").json() == {"daily_minutes": 30, "weekly_days": 5, "streak_min_minutes": 5}
    assert client.put("/api/goals", json={"weekly_days": 9}).status_code == 422
