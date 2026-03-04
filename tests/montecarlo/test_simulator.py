"""
test_simulator.py — Tests for the Monte Carlo simulation engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategylab.packages.core.engine import BacktestEngine
from strategylab.packages.core.models import BacktestResult
from strategylab.packages.execution.models import ExecutionConfig
from strategylab.packages.montecarlo.models import MCResult, SimulationConfig
from strategylab.packages.montecarlo.simulator import (
    _block_bootstrap_returns,
    _cagr,
    _max_dd_pct,
    run_simulation,
)
from strategylab.packages.strategies.sma_crossover import generate_targets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_result(n_bars: int = 252, n_trades: int = 10) -> BacktestResult:
    """Build a minimal BacktestResult for testing."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=n_bars)
    equity = pd.Series(
        100_000.0 * np.cumprod(1 + rng.normal(0.0005, 0.01, n_bars)),
        index=dates,
        name="equity",
    )
    drawdown = (equity - equity.cummax()) / equity.cummax()

    # Build a small trade log
    pnls = rng.normal(50, 300, n_trades)
    trade_dates = pd.bdate_range("2020-01-05", periods=n_trades * 2)
    trades = pd.DataFrame({
        "net_pnl": pnls,
        "gross_pnl": pnls,
        "commission": [5.0] * n_trades,
        "entry_date": trade_dates[::2][:n_trades],
        "exit_date": trade_dates[1::2][:n_trades],
        "holding_bars": [5] * n_trades,
        "symbol": ["SYNTH"] * n_trades,
        "direction": ["long"] * n_trades,
        "entry_price": [100.0] * n_trades,
        "exit_price": [101.0] * n_trades,
        "shares": [100.0] * n_trades,
    })

    return BacktestResult(
        equity_curve=equity,
        trade_log=trades,
        drawdown_series=drawdown,
        initial_capital=100_000.0,
        symbol="SYNTH",
        strategy_name="test",
        params={"fast": 20, "slow": 50},
    )


@pytest.fixture
def base_result() -> BacktestResult:
    return _make_result()


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_max_dd_positive(self) -> None:
        equity = np.array([100.0, 120.0, 90.0, 110.0])
        dd = _max_dd_pct(equity)
        # Peak is 120, trough is 90 → 25 % drawdown
        assert abs(dd - 25.0) < 1.0

    def test_max_dd_no_drawdown(self) -> None:
        equity = np.linspace(100.0, 200.0, 100)
        assert _max_dd_pct(equity) < 0.01

    def test_cagr_doubling_in_one_year(self) -> None:
        cagr = _cagr(200_000.0, 100_000.0, 252)
        assert abs(cagr - 1.0) < 0.01

    def test_cagr_flat_is_zero(self) -> None:
        assert abs(_cagr(100_000.0, 100_000.0, 252)) < 1e-9

    def test_block_bootstrap_correct_length(self) -> None:
        rng = np.random.default_rng(0)
        returns = np.random.randn(252)
        bootstrapped = _block_bootstrap_returns(returns, 252, 20, rng)
        assert len(bootstrapped) == 252


# ---------------------------------------------------------------------------
# Trade shuffle
# ---------------------------------------------------------------------------

class TestTradeShuffleMC:

    def test_returns_mc_result(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert isinstance(result, MCResult)

    def test_correct_method_label(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert result.method == "trade_shuffle"

    def test_n_simulations_matches(self, base_result: BacktestResult) -> None:
        n = 100
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=n, seed=0)
        result = run_simulation(base_result, cfg)
        assert result.n_simulations == n

    def test_distributions_have_correct_length(self, base_result: BacktestResult) -> None:
        n = 50
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=n, seed=0)
        result = run_simulation(base_result, cfg)
        assert len(result.cagr_distribution) == n
        assert len(result.final_equity_distribution) == n
        assert len(result.max_drawdown_distribution) == n

    def test_equity_percentiles_have_five_bands(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert set(result.equity_percentiles.keys()) == {"p5", "p25", "p50", "p75", "p95"}

    def test_drawdown_percentiles_have_five_bands(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert set(result.drawdown_percentiles.keys()) == {"p5", "p25", "p50", "p75", "p95"}

    def test_equity_percentile_length_matches_equity(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        n_bars = len(base_result.equity_curve)
        for band in result.equity_percentiles.values():
            assert len(band) == n_bars

    def test_p5_below_p95(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=200, seed=0)
        result = run_simulation(base_result, cfg)
        p5 = result.equity_percentiles["p5"].iloc[-1]
        p95 = result.equity_percentiles["p95"].iloc[-1]
        assert p5 <= p95

    def test_deterministic_with_same_seed(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=7)
        r1 = run_simulation(base_result, cfg)
        r2 = run_simulation(base_result, cfg)
        np.testing.assert_array_equal(
            r1.final_equity_distribution, r2.final_equity_distribution
        )

    def test_different_seeds_give_different_paths(self, base_result: BacktestResult) -> None:
        """Different seeds should produce different equity path shapes.

        Note: final equity is always equal across shuffle paths (trade P&L sum
        is invariant under permutation), so we compare mid-point equity bands.
        """
        r1 = run_simulation(base_result, SimulationConfig(n_simulations=100, seed=1))
        r2 = run_simulation(base_result, SimulationConfig(n_simulations=100, seed=2))
        mid = len(base_result.equity_curve) // 2
        p50_mid_r1 = r1.equity_percentiles["p50"].iloc[mid]
        p50_mid_r2 = r2.equity_percentiles["p50"].iloc[mid]
        assert p50_mid_r1 != p50_mid_r2

    def test_max_drawdown_non_negative(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert (result.max_drawdown_distribution >= 0).all()

    def test_empty_trades_returns_degenerate(self) -> None:
        """Empty trade log should not crash — returns degenerate result."""
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(100_000.0, index=dates)
        result = BacktestResult(
            equity_curve=equity,
            trade_log=pd.DataFrame(columns=["net_pnl"]),
            drawdown_series=pd.Series(0.0, index=dates),
            initial_capital=100_000.0,
            symbol="X",
            strategy_name="empty",
        )
        mc = run_simulation(result, SimulationConfig(n_simulations=10))
        assert mc.n_simulations == 10


# ---------------------------------------------------------------------------
# Block bootstrap
# ---------------------------------------------------------------------------

class TestBlockBootstrapMC:

    def test_returns_mc_result(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="block_bootstrap", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert isinstance(result, MCResult)

    def test_equity_percentiles_present(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="block_bootstrap", n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        assert len(result.equity_percentiles) == 5

    def test_distributions_correct_length(self, base_result: BacktestResult) -> None:
        n = 75
        cfg = SimulationConfig(method="block_bootstrap", n_simulations=n, seed=0)
        result = run_simulation(base_result, cfg)
        assert len(result.cagr_distribution) == n

    def test_deterministic(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="block_bootstrap", n_simulations=30, seed=99)
        r1 = run_simulation(base_result, cfg)
        r2 = run_simulation(base_result, cfg)
        np.testing.assert_array_almost_equal(
            r1.final_equity_distribution, r2.final_equity_distribution
        )


# ---------------------------------------------------------------------------
# Parameter uncertainty
# ---------------------------------------------------------------------------

class TestParameterUncertaintyMC:

    def test_returns_mc_result(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Run a real backtest first, then MC with parameter uncertainty."""
        engine = BacktestEngine(
            initial_capital=100_000.0,
            execution_config=ExecutionConfig.zero_cost(),
        )
        params = {"fast": 10, "slow": 30}
        base = engine.run(
            synthetic_ohlcv, generate_targets, params, "SYNTH", "SMA"
        )

        def run_backtest(p: dict) -> BacktestResult:
            return engine.run(synthetic_ohlcv, generate_targets, p, "SYNTH", "SMA")

        cfg = SimulationConfig(
            method="parameter_uncertainty",
            n_simulations=20,
            seed=42,
            param_uncertainty_pct=0.15,
        )
        result = run_simulation(
            base,
            cfg,
            run_backtest=run_backtest,
            params=params,
            param_bounds={"fast": (2, 20), "slow": (25, 60)},
        )
        assert isinstance(result, MCResult)
        assert result.n_simulations == 20

    def test_missing_run_backtest_raises(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="parameter_uncertainty", n_simulations=5)
        with pytest.raises(ValueError, match="run_backtest"):
            run_simulation(base_result, cfg, params={"fast": 10})

    def test_unknown_method_raises(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(method="trade_shuffle", n_simulations=5)
        cfg.method = "invalid_method"   # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unknown simulation method"):
            run_simulation(base_result, cfg)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestMCResultSummary:

    def test_summary_has_expected_keys(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        summary = result.summary()
        for key in (
            "method", "n_simulations", "median_cagr",
            "p5_cagr", "p95_cagr", "median_max_drawdown",
        ):
            assert key in summary

    def test_summary_values_are_scalars(self, base_result: BacktestResult) -> None:
        cfg = SimulationConfig(n_simulations=50, seed=0)
        result = run_simulation(base_result, cfg)
        summary = result.summary()
        for k, v in summary.items():
            if k not in ("method",):
                assert isinstance(v, (int, float))
