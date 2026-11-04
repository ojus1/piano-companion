"""Database tables (SQLite via SQLModel).

The shape is deliberately small. The pedagogy thread will decide the curriculum; these tables
hold whatever it produces: pieces, practice items (spaced-repetition cards), sessions and reviews.
"""

from datetime import UTC, datetime

from sqlmodel import JSON, Column, Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Piece(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Stable id from the research catalog (catalog.json / catalog_vgm.json); None for manual uploads.
    catalog_id: str | None = Field(default=None, index=True, unique=True)
    title: str
    composer: str | None = None
    arranger: str | None = None
    category: str | None = None  # repertoire | etudes | technique | vgm | not_downloaded
    level_henle: int | None = None
    level_abrsm: int | None = None
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    license: str | None = None
    source_url: str | None = None
    # Library-relative paths of the score files (MusicXML preferred, PDF fallback).
    musicxml_path: str | None = None
    pdf_path: str | None = None
    midi_path: str | None = None  # reference performance / alignment target
    pdf_annotated_path: str | None = None  # the PDF with the user's pen/text annotations saved in
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # Everything else from the catalog row (features, keys, unrendered .ly/.mscx paths, ...).
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class PracticeItem(SQLModel, table=True):
    """Anything that gets scheduled: a scale, an etude passage, a sight-reading drill, a piece section."""

    id: int | None = Field(default=None, primary_key=True)
    kind: str = "exercise"  # technique | repertoire | vgm | theory | ear | sight_reading | improv | exercise | ...
    title: str
    # Idempotency key for seeded items, e.g. "S1:technique:<catalog id>" or "concept:t_five_finger".
    source_key: str | None = Field(default=None, index=True, unique=True)
    stage: str | None = None  # curriculum stage id, S1..S7
    piece_id: int | None = Field(default=None, foreign_key="piece.id")
    # e.g. {"measures": [1, 8], "hands": "RH", "target_bpm": 80}
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Serialized fsrs.Card (stability, difficulty, due, ...). See srs.py.
    srs_state: dict = Field(default_factory=dict, sa_column=Column(JSON))
    due: datetime = Field(default_factory=utcnow, index=True)
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class PracticeSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=utcnow, index=True)
    ended_at: datetime | None = None
    source: str = "midi"  # midi | audio | manual
    midi_path: str | None = None  # relative to recordings_dir
    audio_path: str | None = None
    note_count: int = 0
    # Quick metrics computed at session end (analysis.py). AI analysis lands in `analysis`.
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))
    analysis: dict = Field(default_factory=dict, sa_column=Column(JSON))
    notes: str | None = None
    practice_item_id: int | None = Field(default=None, foreign_key="practiceitem.id")


class Review(SQLModel, table=True):
    """One graded attempt at a practice item (self-graded now, auto-graded later)."""

    id: int | None = Field(default=None, primary_key=True)
    practice_item_id: int = Field(foreign_key="practiceitem.id", index=True)
    session_id: int | None = Field(default=None, foreign_key="practicesession.id")
    rating: int  # 1 Again, 2 Hard, 3 Good, 4 Easy (FSRS)
    reviewed_at: datetime = Field(default_factory=utcnow)
    log: dict = Field(default_factory=dict, sa_column=Column(JSON))
