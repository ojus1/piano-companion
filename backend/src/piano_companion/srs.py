"""Spaced repetition via FSRS (the algorithm Anki adopted; open source, research-backed).

Each PracticeItem carries a serialized fsrs.Card. Grading an attempt updates the card and its due date.
Swap or extend this module if the pedagogy thread picks a different model (e.g. half-life regression).
"""

from datetime import UTC, datetime

from fsrs import Card, Rating, Scheduler

# Desired retention 0.9 is FSRS's default. Practice skills decay slower than vocab, so we can
# tune this later from our own review logs (fsrs has an optimizer).
_scheduler = Scheduler(desired_retention=0.9)


def new_state() -> dict:
    return Card().to_dict()


def grade(state: dict, rating: int, when: datetime | None = None) -> tuple[dict, datetime, dict]:
    card = Card.from_dict(state) if state else Card()
    card, log = _scheduler.review_card(card, Rating(rating), review_datetime=when)
    return card.to_dict(), card.due, log.to_dict()


def retrievability(state: dict, now: datetime | None = None) -> float:
    if not state:
        return 0.0
    return float(_scheduler.get_card_retrievability(Card.from_dict(state), now or datetime.now(UTC)))
