"""Spaced repetition via FSRS-6 (py-fsrs), configured from the curriculum's scheduler defaults.

Each PracticeItem carries a serialized fsrs.Card. Items are grouped into "decks" that have their own
desired retention (technique 0.85, passages 0.9, maintenance 0.8, ...). Learning steps are off: one
review per item per day, graded from the last full attempt. Sight-reading is not FSRS-scheduled
(always fresh material, rated by Elo), so those items simply come back daily.
"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

from fsrs import Card, Rating, Scheduler

from . import curriculum

# PracticeItem.kind -> desired-retention deck from scheduler_defaults.fsrs.desired_retention
KIND_DECK = {
    "technique": "technique",
    "scale": "technique",
    "chord": "technique",
    "exercise": "technique",
    "repertoire": "passage_learning",
    "piece_section": "passage_learning",
    "vgm": "passage_learning",
    "theory": "theory_ear_drill",
    "ear": "theory_ear_drill",
    "improv": "theory_ear_drill",
    "maintenance": "maintenance_repertoire",
}
NOT_FSRS = {"sight_reading"}
_FALLBACK_RETENTION = {
    "passage_learning": 0.9,
    "technique": 0.85,
    "theory_ear_drill": 0.9,
    "maintenance_repertoire": 0.8,
}


def deck_for(kind: str) -> str:
    return KIND_DECK.get(kind, "passage_learning")


@lru_cache
def scheduler(deck: str) -> Scheduler:
    cfg = curriculum.scheduler_defaults().get("fsrs", {})
    kwargs: dict = {
        "desired_retention": cfg.get("desired_retention", _FALLBACK_RETENTION).get(
            deck, _FALLBACK_RETENTION.get(deck, 0.9)
        ),
        "learning_steps": tuple(timedelta(minutes=m) for m in cfg.get("learning_steps", [])),
        "relearning_steps": tuple(timedelta(minutes=m) for m in cfg.get("relearning_steps", [])),
        "maximum_interval": cfg.get("maximum_interval_days", 180),
        "enable_fuzzing": cfg.get("enable_fuzzing", True),
    }
    if params := cfg.get("parameters"):
        kwargs["parameters"] = tuple(params)
    return Scheduler(**kwargs)


def reset() -> None:
    scheduler.cache_clear()


def new_state() -> dict:
    return Card().to_dict()


def grade(state: dict, rating: int, kind: str = "exercise", when: datetime | None = None):
    """Returns (new_state, due, log_dict)."""
    when = when or datetime.now(UTC)
    if kind in NOT_FSRS:
        due = (when + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return state, due, {"rating": rating, "review_datetime": when.isoformat(), "scheduler": "daily"}
    card = Card.from_dict(state) if state else Card()
    card, log = scheduler(deck_for(kind)).review_card(card, Rating(rating), review_datetime=when)
    return card.to_dict(), card.due, log.to_dict()


def retrievability(state: dict, kind: str = "exercise", now: datetime | None = None) -> float:
    if not state or kind in NOT_FSRS:
        return 0.0
    sched = scheduler(deck_for(kind))
    return float(sched.get_card_retrievability(Card.from_dict(state), now or datetime.now(UTC)))
