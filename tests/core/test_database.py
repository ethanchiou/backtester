"""
test_database.py — Tests for the database layer (packages/db).

All tests use an in-memory SQLite database.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from strategylab.packages.db.database import create_tables, get_engine, get_session
from strategylab.packages.db.repository import (
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
from strategylab.packages.db.schema import Run, Strategy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """In-memory SQLite engine — reset for each test."""
    e = get_engine(":memory:")
    create_tables(e)
    return e


@pytest.fixture
def equity_curve() -> pd.Series:
    dates = pd.bdate_range("2020-01-01", periods=50)
    values = 100_000 * np.cumprod(1 + np.random.default_rng(0).normal(0.001, 0.01, 50))
    return pd.Series(values, index=dates)


# ---------------------------------------------------------------------------
# Strategy CRUD
# ---------------------------------------------------------------------------

class TestStrategyCRUD:

    def test_create_strategy(self, engine) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="SMA_Crossover", tags=["trend"])
        with get_session(engine) as sess:
            fetched = get_strategy(sess, s.id)
            assert fetched is not None
            assert fetched.name == "SMA_Crossover"

    def test_strategy_has_id_after_create(self, engine) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="TestStrategy")
            assert s.id is not None

    def test_create_with_tags(self, engine) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="EMA", tags=["trend", "ema"])
            sid = s.id
        with get_session(engine) as sess:
            s = get_strategy(sess, sid)
            assert s.tags_list() == ["trend", "ema"]

    def test_list_strategies_returns_all(self, engine) -> None:
        with get_session(engine) as sess:
            create_strategy(sess, name="A")
            create_strategy(sess, name="B")
            create_strategy(sess, name="C")
        with get_session(engine) as sess:
            strategies = list_strategies(sess)
            assert len(strategies) == 3

    def test_list_favorites_only(self, engine) -> None:
        with get_session(engine) as sess:
            s1 = create_strategy(sess, name="A")
            s2 = create_strategy(sess, name="B")
            s1id, s2id = s1.id, s2.id
        with get_session(engine) as sess:
            toggle_favorite(sess, s1id)
        with get_session(engine) as sess:
            favs = list_strategies(sess, favorites_only=True)
            assert len(favs) == 1
            assert favs[0].name == "A"

    def test_list_by_tag(self, engine) -> None:
        with get_session(engine) as sess:
            create_strategy(sess, name="A", tags=["trend"])
            create_strategy(sess, name="B", tags=["mean-reversion"])
        with get_session(engine) as sess:
            trend_strats = list_strategies(sess, tag="trend")
            assert len(trend_strats) == 1
            assert trend_strats[0].name == "A"

    def test_toggle_favorite_on_and_off(self, engine) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="Test")
            sid = s.id
        with get_session(engine) as sess:
            s = toggle_favorite(sess, sid)
            assert s.favorite is True
        with get_session(engine) as sess:
            s = toggle_favorite(sess, sid)
            assert s.favorite is False

    def test_delete_strategy(self, engine) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="Delete me")
            sid = s.id
        with get_session(engine) as sess:
            delete_strategy(sess, sid)
        with get_session(engine) as sess:
            assert get_strategy(sess, sid) is None

    def test_get_nonexistent_strategy_returns_none(self, engine) -> None:
        with get_session(engine) as sess:
            assert get_strategy(sess, 9999) is None

    def test_toggle_nonexistent_raises(self, engine) -> None:
        with pytest.raises(ValueError, match="not found"):
            with get_session(engine) as sess:
                toggle_favorite(sess, 9999)

    def test_favorite_default_is_false(self, engine) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="Default")
            assert s.favorite is False


# ---------------------------------------------------------------------------
# Run CRUD
# ---------------------------------------------------------------------------

class TestRunCRUD:

    def test_save_run_creates_record(self, engine, equity_curve) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="SMA")
            sid = s.id
        with get_session(engine) as sess:
            run = save_run(
                session=sess,
                strategy_id=sid,
                parameters={"fast": 20, "slow": 50},
                date_range_start="2020-01-01",
                date_range_end="2020-12-31",
                symbols=["AAPL"],
                mode="single",
                execution_settings={"commission": 0.001},
                metrics={"sharpe": 1.2, "cagr": 0.15},
                equity_curve=equity_curve,
            )
            run_id = run.run_id
        with get_session(engine) as sess:
            r = get_run(sess, run_id)
            assert r is not None
            assert r.run_id == run_id

    def test_run_stores_parameters_as_json(self, engine, equity_curve) -> None:
        params = {"fast": 10, "slow": 30}
        with get_session(engine) as sess:
            s = create_strategy(sess, name="X")
            sid = s.id
        with get_session(engine) as sess:
            run = save_run(
                sess, sid, params, "2020-01-01", "2020-12-31",
                ["AAPL"], "single", {}, {}, equity_curve
            )
            run_id = run.run_id
        with get_session(engine) as sess:
            r = get_run(sess, run_id)
            assert r.get_parameters() == params

    def test_run_stores_symbols(self, engine, equity_curve) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="Multi")
            sid = s.id
        with get_session(engine) as sess:
            run = save_run(
                sess, sid, {}, "2020-01-01", "2020-12-31",
                ["AAPL", "MSFT"], "portfolio", {}, {}, equity_curve
            )
            run_id = run.run_id
        with get_session(engine) as sess:
            r = get_run(sess, run_id)
            assert r.get_symbols() == ["AAPL", "MSFT"]

    def test_run_equity_json_is_parseable(self, engine, equity_curve) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="E")
            sid = s.id
        with get_session(engine) as sess:
            run = save_run(
                sess, sid, {}, "2020-01-01", "2020-12-31",
                ["AAPL"], "single", {}, {}, equity_curve
            )
            run_id = run.run_id
        with get_session(engine) as sess:
            r = get_run(sess, run_id)
            eq = r.get_equity()
            assert isinstance(eq, dict)
            assert len(eq) > 0

    def test_list_runs_returns_all(self, engine, equity_curve) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="Listed")
            sid = s.id
        with get_session(engine) as sess:
            for _ in range(3):
                save_run(sess, sid, {}, "2020-01-01", "2020-12-31",
                         ["AAPL"], "single", {}, {}, equity_curve)
        with get_session(engine) as sess:
            runs = list_runs(sess, strategy_id=sid)
            assert len(runs) == 3

    def test_list_runs_filter_by_strategy(self, engine, equity_curve) -> None:
        with get_session(engine) as sess:
            s1 = create_strategy(sess, name="S1")
            s2 = create_strategy(sess, name="S2")
            s1id, s2id = s1.id, s2.id
        with get_session(engine) as sess:
            save_run(sess, s1id, {}, "2020-01-01", "2020-12-31",
                     ["AAPL"], "single", {}, {}, equity_curve)
            save_run(sess, s2id, {}, "2020-01-01", "2020-12-31",
                     ["MSFT"], "single", {}, {}, equity_curve)
        with get_session(engine) as sess:
            runs = list_runs(sess, strategy_id=s1id)
            assert len(runs) == 1

    def test_delete_run(self, engine, equity_curve) -> None:
        with get_session(engine) as sess:
            s = create_strategy(sess, name="Del")
            sid = s.id
        with get_session(engine) as sess:
            run = save_run(sess, sid, {}, "2020-01-01", "2020-12-31",
                           ["AAPL"], "single", {}, {}, equity_curve)
            run_id = run.run_id
        with get_session(engine) as sess:
            delete_run(sess, run_id)
        with get_session(engine) as sess:
            assert get_run(sess, run_id) is None

    def test_save_run_no_strategy_id(self, engine, equity_curve) -> None:
        """Runs can exist without a linked strategy."""
        with get_session(engine) as sess:
            run = save_run(
                sess, None, {}, "2020-01-01", "2020-12-31",
                ["AAPL"], "single", {}, {}, equity_curve
            )
            run_id = run.run_id
        with get_session(engine) as sess:
            r = get_run(sess, run_id)
            assert r is not None
            assert r.strategy_id is None

    def test_run_has_uuid_format(self, engine, equity_curve) -> None:
        import re
        UUID_RE = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        with get_session(engine) as sess:
            run = save_run(sess, None, {}, "2020-01-01", "2020-12-31",
                           ["AAPL"], "single", {}, {}, equity_curve)
            assert UUID_RE.match(run.run_id)
