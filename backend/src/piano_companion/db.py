import logging
from collections.abc import Iterator

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        s.ensure_dirs()
        _engine = create_engine(f"sqlite:///{s.db_path}", connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def _pragmas(dbapi_conn, _):  # WAL survives power cuts better on an SD card / NVMe
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        SQLModel.metadata.create_all(_engine)
        _add_missing_columns(_engine)
    return _engine


def _add_missing_columns(engine) -> None:
    """Additive schema migration: new nullable/defaulted model fields become new columns.

    create_all() only creates missing tables, so without this an existing piano.db on the Pi would
    break whenever a field is added. Renames and type changes still need a manual migration.
    """
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = col.type.compile(engine.dialect)
                default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                clause = f" DEFAULT {default!r}" if isinstance(default, (int, float, str)) else ""
                if isinstance(default, bool):
                    clause = f" DEFAULT {int(default)}"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{clause}'))
                logging.getLogger(__name__).info("added column %s.%s", table.name, col.name)
            for index in table.indexes:
                index.create(conn, checkfirst=True)


def reset_engine() -> None:
    """Tests use this after changing settings."""
    global _engine
    _engine = None


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
