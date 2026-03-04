"""
strategylab.db — Database layer (SQLite via SQLAlchemy).

Public API
----------
get_engine          create SQLite engine
create_tables       initialise schema
get_session         context manager for DB sessions
create_strategy     insert a strategy
get_strategy        fetch by id
list_strategies     query all strategies
toggle_favorite     flip favorite flag
delete_strategy     remove a strategy
save_run            persist a backtest run
get_run             fetch run by UUID
list_runs           query runs
delete_run          remove a run
"""

from .database import create_tables, get_engine, get_session
from .repository import (
    create_strategy,
    delete_run,
    delete_strategy,
    get_run,
    get_strategy,
    list_runs,
    list_strategies,
    save_run,
    toggle_favorite,
)
from .schema import Run, Strategy

__all__ = [
    "get_engine",
    "create_tables",
    "get_session",
    "Strategy",
    "Run",
    "create_strategy",
    "get_strategy",
    "list_strategies",
    "toggle_favorite",
    "delete_strategy",
    "save_run",
    "get_run",
    "list_runs",
    "delete_run",
]
