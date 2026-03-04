"""
api/dependencies.py — FastAPI dependency injection helpers.

Provides a shared database engine and session factory.
The engine is initialised once at startup; sessions are per-request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy.orm import Session

from strategylab.packages.db.database import create_tables, get_engine, get_session

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).parent.parent.parent.parent / "strategylab.db"
_engine = get_engine(_DB_PATH)
create_tables(_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session per request."""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False
    )
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_test_db(engine) -> Generator[Session, None, None]:
    """Yield a test DB session (accepts an engine — for dependency override)."""
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
