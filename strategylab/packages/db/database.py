"""
db/database.py — Database connection and session management.

Usage
-----
    from strategylab.packages.db.database import get_engine, get_session

    engine = get_engine()          # default: strategylab.db in project root
    with get_session(engine) as session:
        session.add(...)
        session.commit()
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .schema import Base

# Default database file location (relative to repo root)
_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "strategylab.db"


def get_engine(db_path: str | Path | None = None) -> Engine:
    """Create and return a SQLAlchemy engine connected to a SQLite file.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.  If ``None``, uses the default
        location at the repo root (``strategylab.db``).
        Pass ``":memory:"`` for an in-memory database (tests).

    Returns
    -------
    Engine
    """
    if db_path is None:
        db_path = _DEFAULT_DB_PATH

    if str(db_path) == ":memory:":
        # StaticPool forces all connections to share one in-memory database
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        url = f"sqlite:///{db_path}"
        engine = create_engine(url, connect_args={"check_same_thread": False})

    # Enable WAL mode for better concurrent read performance
    @event.listens_for(engine, "connect")
    def set_wal_mode(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def create_tables(engine: Engine) -> None:
    """Create all tables if they don't already exist."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    """Context manager yielding a database session with auto-commit/rollback.

    Usage
    -----
        with get_session(engine) as session:
            session.add(obj)
    """
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
