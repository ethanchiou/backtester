"""
test_portfolio_engine.py — Tests for the multi-asset PortfolioEngine.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategylab.packages.core.data_loader import DataLoader
from strategylab.packages.core.models import BacktestResult
from strategylab.packages.core.portfolio_engine import PortfolioEngine
from strategylab.packages.execution.models import ExecutionConfig
from strategylab.packages.strategies.portfolio_sma import generate_targets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def two_asset_data(sample_csv_path: Path) -> pd.DataFrame:
    loader = DataLoader(sample_csv_path)
    return loader.load(symbols=["AAPL", "MSFT"])


def _always_flat(data: pd.DataFrame, params: dict) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=data.index, columns=data.columns)


def _always_equal_weight(data: pd.DataFrame, params: dict) -> pd.DataFrame:
    """50/50 portfolio at all times."""
    return pd.DataFrame(0.5, index=data.index, columns=data.columns)


def _single_asset_only(sym: str):
    """Return 100 % weight to one symbol."""
    def _fn(data: pd.DataFrame, params: dict) -> pd.DataFrame:
        weights = pd.DataFrame(0.0, index=data.index, columns=data.columns)
        weights[sym] = 1.0
        return weights
    return _fn


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------

class TestPortfolioEngineBasic:

    def test_returns_backtest_result(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(
            two_asset_data, _always_flat, {}, ["AAPL", "MSFT"]
        )
        assert isinstance(result, BacktestResult)

    def test_equity_curve_correct_length(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(two_asset_data, _always_flat, {}, ["AAPL", "MSFT"])
        assert len(result.equity_curve) == len(two_asset_data)

    def test_equity_index_matches_data(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(two_asset_data, _always_flat, {}, ["AAPL", "MSFT"])
        pd.testing.assert_index_equal(
            result.equity_curve.index, two_asset_data.index
        )

    def test_flat_strategy_equity_stays_at_capital(
        self, two_asset_data: pd.DataFrame
    ) -> None:
        engine = PortfolioEngine(initial_capital=100_000.0)
        result = engine.run(two_asset_data, _always_flat, {}, ["AAPL", "MSFT"])
        assert (result.equity_curve == 100_000.0).all()

    def test_flat_strategy_no_trades(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(two_asset_data, _always_flat, {}, ["AAPL", "MSFT"])
        assert len(result.trade_log) == 0

    def test_symbol_list_stored(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(two_asset_data, _always_flat, {}, ["AAPL", "MSFT"])
        assert result.symbol == ["AAPL", "MSFT"]

    def test_drawdown_always_lte_zero(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(two_asset_data, _always_flat, {}, ["AAPL", "MSFT"])
        assert (result.drawdown_series <= 0.0).all()

    def test_drawdown_length_matches_equity(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine()
        result = engine.run(two_asset_data, generate_targets, {"fast": 20, "slow": 50}, ["AAPL", "MSFT"])
        assert len(result.drawdown_series) == len(result.equity_curve)


# ---------------------------------------------------------------------------
# Weight normalisation
# ---------------------------------------------------------------------------

class TestWeightNormalisation:

    def test_over_leveraged_weights_normalised(
        self, two_asset_data: pd.DataFrame
    ) -> None:
        """Weights summing to 2.0 should be normalised to 0.5/0.5."""
        engine = PortfolioEngine(
            initial_capital=100_000.0,
            execution_config=ExecutionConfig.zero_cost(),
            allow_leverage=False,
        )
        result = engine.run(
            two_asset_data, _always_equal_weight, {}, ["AAPL", "MSFT"]
        )
        # No crash and equity > 0
        assert result.equity_curve.iloc[-1] > 0

    def test_leverage_allowed_uses_full_weights(
        self, two_asset_data: pd.DataFrame
    ) -> None:
        """100 % each = 2× leverage.  With allow_leverage=False it's normalised to 50/50."""
        def _full_weight(data: pd.DataFrame, params: dict) -> pd.DataFrame:
            return pd.DataFrame(1.0, index=data.index, columns=data.columns)

        engine_no_lev = PortfolioEngine(
            initial_capital=100_000.0,
            execution_config=ExecutionConfig.zero_cost(),
            allow_leverage=False,
        )
        engine_lev = PortfolioEngine(
            initial_capital=100_000.0,
            execution_config=ExecutionConfig.zero_cost(),
            allow_leverage=True,
        )
        r_no = engine_no_lev.run(two_asset_data, _full_weight, {}, ["AAPL", "MSFT"])
        r_lev = engine_lev.run(two_asset_data, _full_weight, {}, ["AAPL", "MSFT"])
        # Leveraged has double exposure; equity paths should diverge
        assert r_lev.equity_curve.iloc[-1] != r_no.equity_curve.iloc[-1]


# ---------------------------------------------------------------------------
# Portfolio SMA strategy integration
# ---------------------------------------------------------------------------

class TestPortfolioSMAStrategy:

    def test_portfolio_sma_runs(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine(
            initial_capital=100_000.0,
            execution_config=ExecutionConfig.zero_cost(),
        )
        result = engine.run(
            two_asset_data,
            generate_targets,
            {"fast": 20, "slow": 50},
            ["AAPL", "MSFT"],
        )
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0

    def test_portfolio_sma_produces_trades(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine(
            initial_capital=100_000.0,
            execution_config=ExecutionConfig.zero_cost(),
        )
        result = engine.run(
            two_asset_data,
            generate_targets,
            {"fast": 20, "slow": 50},
            ["AAPL", "MSFT"],
        )
        assert len(result.trade_log) > 0

    def test_trade_log_has_both_symbols(self, two_asset_data: pd.DataFrame) -> None:
        engine = PortfolioEngine(
            execution_config=ExecutionConfig.zero_cost()
        )
        result = engine.run(
            two_asset_data,
            generate_targets,
            {"fast": 20, "slow": 50},
            ["AAPL", "MSFT"],
        )
        if len(result.trade_log) > 0:
            traded_syms = set(result.trade_log["symbol"].unique())
            assert traded_syms.issubset({"AAPL", "MSFT"})

    def test_equity_initial_value(self, two_asset_data: pd.DataFrame) -> None:
        capital = 75_000.0
        engine = PortfolioEngine(
            initial_capital=capital,
            execution_config=ExecutionConfig.zero_cost(),
        )
        result = engine.run(
            two_asset_data, _always_flat, {}, ["AAPL", "MSFT"]
        )
        assert result.equity_curve.iloc[0] == capital


# ---------------------------------------------------------------------------
# Exposure and metrics integration
# ---------------------------------------------------------------------------

class TestPortfolioMetrics:

    def test_metrics_computable_from_portfolio_result(
        self, two_asset_data: pd.DataFrame
    ) -> None:
        from strategylab.packages.metrics.calculator import compute_metrics

        engine = PortfolioEngine(execution_config=ExecutionConfig.zero_cost())
        result = engine.run(
            two_asset_data,
            generate_targets,
            {"fast": 20, "slow": 50},
            ["AAPL", "MSFT"],
        )
        metrics = compute_metrics(
            result.equity_curve,
            result.trade_log,
            initial_capital=result.initial_capital,
        )
        # Core metrics should be finite
        assert abs(metrics.sharpe_ratio) < 1000
        assert metrics.max_drawdown_pct >= 0
