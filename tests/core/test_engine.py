"""
test_engine.py — Unit tests for the single-asset BacktestEngine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategylab.packages.core.engine import BacktestEngine
from strategylab.packages.core.models import BacktestResult
from strategylab.packages.execution.models import ExecutionConfig


def _always_long(data: pd.DataFrame, params: dict) -> pd.Series:
    """Trivial strategy: always hold long."""
    price = data.iloc[:, 0]
    return pd.Series(1, index=price.index, dtype=int)


def _always_flat(data: pd.DataFrame, params: dict) -> pd.Series:
    """Trivial strategy: never trade."""
    price = data.iloc[:, 0]
    return pd.Series(0, index=price.index, dtype=int)


def _alternating(data: pd.DataFrame, params: dict) -> pd.Series:
    """Alternate long/flat every 20 bars."""
    price = data.iloc[:, 0]
    positions = pd.Series(0, index=price.index, dtype=int)
    for i in range(0, len(positions), 40):
        positions.iloc[i : i + 20] = 1
    return positions


class TestBacktestEngineBasic:

    def test_returns_backtest_result(self, synthetic_ohlcv: pd.DataFrame) -> None:
        engine = BacktestEngine()
        result = engine.run(
            data=synthetic_ohlcv,
            generate_targets=_always_long,
            params={},
            symbol="SYNTH",
        )
        assert isinstance(result, BacktestResult)

    def test_equity_is_series_with_correct_length(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _always_long, {}, "SYNTH")
        assert isinstance(result.equity_curve, pd.Series)
        assert len(result.equity_curve) == len(synthetic_ohlcv)

    def test_equity_index_matches_data_index(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _always_long, {}, "SYNTH")
        pd.testing.assert_index_equal(
            result.equity_curve.index, synthetic_ohlcv.index
        )

    def test_flat_strategy_equity_stays_at_capital(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine(initial_capital=100_000.0)
        result = engine.run(synthetic_ohlcv, _always_flat, {}, "SYNTH")
        # With no positions, equity should remain at initial capital throughout
        assert (result.equity_curve == 100_000.0).all()

    def test_flat_strategy_produces_no_trades(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _always_flat, {}, "SYNTH")
        assert len(result.trade_log) == 0

    def test_initial_equity_equals_capital(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        capital = 50_000.0
        engine = BacktestEngine(initial_capital=capital)
        result = engine.run(synthetic_ohlcv, _always_flat, {}, "SYNTH")
        assert result.equity_curve.iloc[0] == capital

    def test_drawdown_series_has_correct_length(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _always_long, {}, "SYNTH")
        assert len(result.drawdown_series) == len(synthetic_ohlcv)

    def test_drawdown_series_always_lte_zero(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _always_long, {}, "SYNTH")
        assert (result.drawdown_series <= 0.0).all()

    def test_strategy_name_stored(self, synthetic_ohlcv: pd.DataFrame) -> None:
        engine = BacktestEngine()
        result = engine.run(
            synthetic_ohlcv, _always_long, {}, "SYNTH", strategy_name="TestStrat"
        )
        assert result.strategy_name == "TestStrat"

    def test_symbol_stored(self, synthetic_ohlcv: pd.DataFrame) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _always_long, {}, "SYNTH")
        assert result.symbol == "SYNTH"

    def test_params_stored(self, synthetic_ohlcv: pd.DataFrame) -> None:
        engine = BacktestEngine()
        params = {"fast": 10, "slow": 30}
        result = engine.run(synthetic_ohlcv, _always_flat, {}, "SYNTH")
        result2 = engine.run(synthetic_ohlcv, _always_flat, params, "SYNTH")
        assert result2.params == params


class TestBacktestEngineTrades:

    def test_alternating_strategy_produces_trades(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine(execution_config=ExecutionConfig.zero_cost())
        result = engine.run(synthetic_ohlcv, _alternating, {}, "SYNTH")
        assert len(result.trade_log) > 0

    def test_trade_log_has_expected_columns(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _alternating, {}, "SYNTH")
        expected = {
            "entry_date", "exit_date", "symbol", "direction",
            "entry_price", "exit_price", "shares", "gross_pnl",
            "commission", "net_pnl", "holding_bars",
        }
        assert expected.issubset(set(result.trade_log.columns))

    def test_net_pnl_equals_gross_minus_commission(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _alternating, {}, "SYNTH")
        if len(result.trade_log) == 0:
            pytest.skip("No trades generated")
        diff = (
            result.trade_log["gross_pnl"]
            - result.trade_log["commission"]
            - result.trade_log["net_pnl"]
        )
        assert (diff.abs() < 1e-6).all()

    def test_holding_bars_positive(self, synthetic_ohlcv: pd.DataFrame) -> None:
        engine = BacktestEngine()
        result = engine.run(synthetic_ohlcv, _alternating, {}, "SYNTH")
        if len(result.trade_log) == 0:
            pytest.skip("No trades generated")
        assert (result.trade_log["holding_bars"] >= 0).all()


class TestBacktestEngineCostModels:

    def test_zero_cost_vs_default_cost(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        """Zero-cost run should produce equal or higher final equity."""
        zero_cfg = ExecutionConfig.zero_cost()
        default_cfg = ExecutionConfig()

        engine_zero = BacktestEngine(execution_config=zero_cfg)
        engine_default = BacktestEngine(execution_config=default_cfg)

        result_zero = engine_zero.run(synthetic_ohlcv, _alternating, {}, "SYNTH")
        result_default = engine_default.run(
            synthetic_ohlcv, _alternating, {}, "SYNTH"
        )

        # Zero-cost should outperform or equal default cost
        assert result_zero.equity_curve.iloc[-1] >= result_default.equity_curve.iloc[-1]
