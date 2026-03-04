"""
db/repository.py — CRUD operations for the strategy library.

All functions accept a SQLAlchemy Session as their first argument.
They do NOT manage transactions (caller is responsible for commit/rollback).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from .schema import Run, Strategy


# ---------------------------------------------------------------------------
# Strategy CRUD
# ---------------------------------------------------------------------------

def create_strategy(
    session: Session,
    name: str,
    version: str = "1.0",
    description: str = "",
    tags: list[str] | None = None,
    module_path: str = "",
) -> Strategy:
    """Insert a new strategy record and return it.

    Parameters
    ----------
    session:
        Active database session.
    name:
        Unique display name for the strategy.
    version:
        Semantic version string.
    description:
        Human-readable description.
    tags:
        List of tag strings (e.g. ``["trend", "sma"]``).
    module_path:
        Importable module path (e.g. ``"strategylab.packages.strategies.sma_crossover"``).

    Returns
    -------
    Strategy
    """
    strategy = Strategy(
        name=name,
        version=version,
        description=description,
        module_path=module_path,
        favorite=False,
    )
    strategy.set_tags(tags or [])
    session.add(strategy)
    session.flush()  # populate id without committing
    return strategy


def get_strategy(session: Session, strategy_id: int) -> Optional[Strategy]:
    """Fetch a strategy by primary key."""
    return session.get(Strategy, strategy_id)


def list_strategies(
    session: Session,
    favorites_only: bool = False,
    tag: str | None = None,
) -> list[Strategy]:
    """Return all strategies, optionally filtered.

    Parameters
    ----------
    favorites_only:
        If True, return only favorited strategies.
    tag:
        If provided, only return strategies whose tags include this string.
    """
    q = session.query(Strategy)
    if favorites_only:
        q = q.filter(Strategy.favorite.is_(True))
    strategies = q.order_by(Strategy.created_at.desc()).all()
    if tag is not None:
        strategies = [s for s in strategies if tag in s.tags_list()]
    return strategies


def toggle_favorite(session: Session, strategy_id: int) -> Strategy:
    """Toggle the favorite flag on a strategy and return the updated record."""
    strategy = session.get(Strategy, strategy_id)
    if strategy is None:
        raise ValueError(f"Strategy with id={strategy_id} not found.")
    strategy.favorite = not strategy.favorite
    session.flush()
    return strategy


def delete_strategy(session: Session, strategy_id: int) -> None:
    """Delete a strategy and all its associated runs (cascade)."""
    strategy = session.get(Strategy, strategy_id)
    if strategy is None:
        raise ValueError(f"Strategy with id={strategy_id} not found.")
    session.delete(strategy)
    session.flush()


# ---------------------------------------------------------------------------
# Run CRUD
# ---------------------------------------------------------------------------

def save_run(
    session: Session,
    strategy_id: int | None,
    parameters: dict,
    date_range_start: str,
    date_range_end: str,
    symbols: list[str],
    mode: str,
    execution_settings: dict,
    metrics: dict,
    equity_curve: pd.Series,
) -> Run:
    """Persist a completed backtest run.

    Parameters
    ----------
    equity_curve:
        Equity series indexed by DatetimeIndex.  Stored as JSON
        ``{date_str: value}``.

    Returns
    -------
    Run
    """
    equity_dict = {
        str(k.date()): round(v, 4)
        for k, v in equity_curve.items()
    }

    run = Run(
        run_id=str(uuid.uuid4()),
        strategy_id=strategy_id,
        parameters=json.dumps(parameters),
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        symbols=json.dumps(symbols),
        mode=mode,
        execution_settings=json.dumps(execution_settings),
        metrics_json=json.dumps(metrics),
        equity_json=json.dumps(equity_dict),
    )
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, run_id: str) -> Optional[Run]:
    """Fetch a run by its UUID."""
    return session.get(Run, run_id)


def list_runs(
    session: Session,
    strategy_id: int | None = None,
    limit: int = 50,
) -> list[Run]:
    """Return recent runs, optionally filtered by strategy."""
    q = session.query(Run)
    if strategy_id is not None:
        q = q.filter(Run.strategy_id == strategy_id)
    return q.order_by(Run.created_at.desc()).limit(limit).all()


def delete_run(session: Session, run_id: str) -> None:
    """Delete a run record."""
    run = session.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run with id={run_id!r} not found.")
    session.delete(run)
    session.flush()
