"""Motivation layer: streaks with freezes, goals, XP, achievements and progress series.

Design follows the research curriculum's `scheduler_defaults.gamification` and Duolingo's proven loop:

- **Day streak** counts consecutive practice days. A day counts once you play at least
  `streak_min_minutes` (a low bar on purpose: showing up is what the streak rewards).
- **Streak freezes** protect it. A missed day spends a freeze instead of resetting the streak. You start
  with one, earn one for every week you hit the weekly goal, and can bank at most `max_freezes` (2).
- **Weekly goal**: practise on `weekly_days` of 7 days (default 5). Consecutive weeks that hit it form a
  week streak, the research's "no harsh resets" streak.
- **Daily goal**: `daily_minutes` of practice (default 20).
- **XP = quality minutes**: practice minutes, plus drill XP weighted by accuracy, plus a bonus for each
  daily goal met. No leagues (single user, and the research advises against them).

Everything is derived from the recorded history, so there is no separate state to drift out of sync.
Days are calendar days in the Pi's local time zone.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import mean

DEFAULT_GOALS = {"daily_minutes": 20, "weekly_days": 5, "streak_min_minutes": 5}
MAX_FREEZES = 2
START_FREEZES = 1


def local_day(ts: datetime) -> date:
    """SQLite hands back naive datetimes that were stored as UTC."""
    return (ts if ts.tzinfo else ts.replace(tzinfo=UTC)).astimezone().date()


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday


# ---------- streaks ----------


@dataclass
class Streak:
    current: int = 0
    longest: int = 0
    freezes: int = START_FREEZES
    max_freezes: int = MAX_FREEZES
    practiced_today: bool = False
    at_risk: bool = False  # streak > 0 and today not yet practised
    week_days: int = 0  # practice days so far this week
    week_streak: int = 0  # consecutive weeks (incl. this one once it's hit) meeting the weekly goal
    best_week_streak: int = 0
    weeks_met: int = 0
    day_status: dict[date, str] = field(default_factory=dict)  # practiced | frozen | missed


def compute_streak(practiced: set[date], today: date, weekly_days: int = 5) -> Streak:
    s = Streak()
    if not practiced:
        return s
    d, first = min(practiced), min(practiced)
    week_count = 0
    run = 0  # current day streak while walking
    week_run = 0
    while d <= today:
        if d in practiced:
            run += 1
            week_count += 1
            s.day_status[d] = "practiced"
        elif d < today:
            if run > 0 and s.freezes > 0:
                s.freezes -= 1
                s.day_status[d] = "frozen"
            else:
                run = 0
                s.day_status[d] = "missed"
        s.longest = max(s.longest, run)
        if d.weekday() == 6 and d < today:  # a finished week (Mon..Sun)
            # The first, partial week counts if it could still have reached the goal from the first day.
            if week_count >= min(weekly_days, (d - max(first, week_start(d))).days + 1):
                week_run += 1
                s.weeks_met += 1
                s.freezes = min(s.max_freezes, s.freezes + 1)
            else:
                week_run = 0
            s.best_week_streak = max(s.best_week_streak, week_run)
            week_count = 0
        d += timedelta(days=1)
    s.current = run
    s.practiced_today = today in practiced
    s.at_risk = run > 0 and not s.practiced_today
    s.week_days = week_count
    this_week_met = week_count >= weekly_days
    s.week_streak = week_run + (1 if this_week_met else 0)
    s.best_week_streak = max(s.best_week_streak, s.week_streak)
    return s


# ---------- XP ----------


def drill_xp(accuracy: float | None, rating: int) -> int:
    """Up to 10 XP for accuracy, plus 5 for a Good or Easy grade."""
    return round(10 * max(0.0, accuracy or 0.0)) + (5 if rating >= 3 else 0)


GOAL_BONUS_XP = 10
REVIEW_XP = 2


def level_for(xp: int) -> dict:
    """Level n starts at 50 * n * (n - 1) XP: 0, 100, 300, 600, 1000, ... (each level 100 XP longer)."""
    n = 1
    while 50 * (n + 1) * n <= xp:
        n += 1
    lo, hi = 50 * n * (n - 1), 50 * (n + 1) * n
    return {"level": n, "xp": xp, "level_start": lo, "next_level": hi, "progress": round((xp - lo) / (hi - lo), 3)}


# ---------- technique series ----------

CLEAN = 0.9  # accuracy at which a drill's tempo counts as "clean"


def technique_series(attempts: list[dict]) -> dict:
    """attempts: dicts with created_at, family, concept_id, bpm, rating, metrics. Oldest first preferred."""
    by_family: dict[str, list[dict]] = defaultdict(list)
    for a in attempts:
        by_family[a["family"]].append(a)

    def daily(rows: list[dict]) -> list[dict]:
        days: dict[date, list[dict]] = defaultdict(list)
        for a in rows:
            days[local_day(a["created_at"])].append(a)
        out = []
        for d in sorted(days):
            rs = days[d]
            acc = [r["metrics"].get("accuracy") for r in rs if r["metrics"].get("accuracy") is not None]
            cv = [r["metrics"].get("ibi_cv") for r in rs if r["metrics"].get("ibi_cv") is not None]
            clean = [
                r["metrics"]["achieved_bpm"]
                for r in rs
                if r["metrics"].get("achieved_bpm") and (r["metrics"].get("accuracy") or 0) >= CLEAN
            ]
            out.append(
                {
                    "date": d.isoformat(),
                    "attempts": len(rs),
                    "accuracy": round(mean(acc), 3) if acc else None,
                    "evenness": round(max(0.0, 1 - mean(cv)), 3) if cv else None,  # 1 = perfectly even
                    "clean_bpm": round(max(clean), 1) if clean else None,
                    "rating": round(mean(r["rating"] for r in rs), 2),
                }
            )
        return out

    def summary(rows: list[dict], series: list[dict]) -> dict:
        acc = [p["accuracy"] for p in series if p["accuracy"] is not None]
        bpms = [p["clean_bpm"] for p in series if p["clean_bpm"]]
        k = max(1, min(3, len(acc) // 2))  # compare the first and latest few practice days
        first, last = acc[:k], acc[-k:]
        return {
            "attempts": len(rows),
            "days": len(series),
            "accuracy_now": round(mean(last), 3) if last else None,
            "accuracy_change": round(mean(last) - mean(first), 3) if len(acc) >= 2 else None,
            "best_clean_bpm": max(bpms) if bpms else None,
            "last_at": max(r["created_at"] for r in rows).isoformat() if rows else None,
        }

    fams = []
    for fam, rows in by_family.items():
        series = daily(rows)
        fams.append(
            {"family": fam, "concept_id": rows[-1].get("concept_id"), **summary(rows, series), "series": series}
        )
    fams.sort(key=lambda f: f["last_at"] or "", reverse=True)
    overall = daily(attempts)
    return {"overall": {**summary(attempts, overall), "series": overall}, "families": fams}


# ---------- achievements ----------


def achievements(
    *,
    longest: int,
    total_minutes: float,
    drills: int,
    easy_drills: int,
    best_week_streak: int,
    goal_days: int,
    practice_days: int,
) -> list[dict]:
    def a(id_: str, title: str, desc: str, value: float, target: float) -> dict:
        return {
            "id": id_,
            "title": title,
            "desc": desc,
            "earned": value >= target,
            "progress": round(min(1.0, value / target), 3),
        }

    out = [
        a("first_day", "First note", "Practise for the first time", practice_days, 1),
        a("streak_3", "Warming up", "3-day streak", longest, 3),
        a("streak_7", "One week strong", "7-day streak", longest, 7),
        a("streak_30", "Habit formed", "30-day streak", longest, 30),
        a("streak_100", "Centurion", "100-day streak", longest, 100),
        a("goal_10", "Goal getter", "Hit the daily goal on 10 days", goal_days, 10),
        a("weeks_4", "Steady month", "Hit the weekly goal 4 weeks in a row", best_week_streak, 4),
        a("hours_1", "First hour", "1 hour of practice", total_minutes, 60),
        a("hours_10", "Ten hours", "10 hours of practice", total_minutes, 600),
        a("hours_50", "Fifty hours", "50 hours of practice", total_minutes, 3000),
        a("hours_100", "Hundred hours", "100 hours of practice", total_minutes, 6000),
        a("drills_10", "Drill starter", "Finish 10 technique drills", drills, 10),
        a("drills_100", "Drill sergeant", "Finish 100 technique drills", drills, 100),
        a("easy_25", "Effortless", "25 drills graded Easy", easy_drills, 25),
    ]
    return out
