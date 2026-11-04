from collections.abc import Iterator

from sqlalchemy import event
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
    return _engine


def reset_engine() -> None:
    """Tests use this after changing settings."""
    global _engine
    _engine = None


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
