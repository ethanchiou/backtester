"""
test_calculator.py — Unit tests for the metrics calculator.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from strategylab.packages.metrics.calculator import (
    MetricsResult,
    _compute_cagr,
    _sharpe,
    _sortino,
    _drawdown_stats,
    compute_metrics,
)


def _make_trades(pnls: list[float], holding_bars: int = 5) -> pd.DataFrame:
    """Helper: build a minimal trade log from a list of P&L values."""
    n = len(pnls)
    dates = pd.bdate_range("2020-01-01", periods=n * 2)
    return pd.DataFrame(
        {
            "net_pnl": pnls,
            "gross_pnl": pnls,
            "commission": [0.0] * n,
            "entry_date": dates[::2][:n],
            "exit_date": dates[1::2][:n],
            "holding_bars": [holding_bars] * n,
        }
    )


# ---------------------------------------------------------------------------
# CAGR
# ---------------------------------------------------------------------------

class TestCagr:

    def test_flat_equity_cagr_is_zero(self) -> None:
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(100_000.0, index=dates)
        cagr = _compute_cagr(equity, 100_000.0)
        assert abs(cagr) < 1e-6

    def test_doubling_equity_approximately_correct(self) -> None:
        """Equity doubles over exactly 1 year → CAGR ≈ 100 %."""
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(np.linspace(100_000, 200_000, 252), index=dates)
        cagr = _compute_cagr(equity, 100_000.0)
        assert abs(cagr - 1.0) < 0.05  # within 5 pp

    def test_empty_equity_returns_zero(self) -> None:
        cagr = _compute_cagr(pd.Series(dtype=float), 100_000.0)
        assert cagr == 0.0


# ---------------------------------------------------------------------------
# Sharpe / Sortino
# ---------------------------------------------------------------------------

class TestRiskAdjustedMetrics:

    def test_sharpe_all_positive_returns(self) -> None:
        returns = pd.Series([0.001] * 252)
        sharpe = _sharpe(returns)
        assert sharpe > 0

    def test_sharpe_zero_returns_is_zero(self) -> None:
        returns = pd.Series([0.0] * 252)
        sharpe = _sharpe(returns)
        assert sharpe == 0.0

    def test_sharpe_positive_exceeds_negative(self) -> None:
        pos_returns = pd.Series([0.002] * 252)
        neg_returns = pd.Series([-0.002] * 252)
        assert _sharpe(pos_returns) > _sharpe(neg_returns)

    def test_sortino_no_downside_is_inf(self) -> None:
        returns = pd.Series([0.001] * 252)
        sortino = _sortino(returns)
        assert math.isinf(sortino)

    def test_sortino_greater_than_sharpe_for_positive_skew(self) -> None:
        """For returns with mostly upside, Sortino should exceed Sharpe."""
        rng = np.random.default_rng(42)
        returns = pd.Series(
            np.abs(rng.normal(0.001, 0.01, 252))  # all positive
        )
        assert _sortino(returns) >= _sharpe(returns)


# ---------------------------------------------------------------------------
# Drawdown stats
# ---------------------------------------------------------------------------

class TestDrawdownStats:

    def test_no_drawdown_for_monotone_rising(
        self, trending_equity: pd.Series
    ) -> None:
        max_dd, max_dd_pct, duration = _drawdown_stats(trending_equity)
        assert max_dd <= 0
        assert max_dd_pct < 0.01  # essentially zero

    def test_known_drawdown_amount(self, drawdown_equity: pd.Series) -> None:
        max_dd, max_dd_pct, duration = _drawdown_stats(drawdown_equity)
        # We constructed a 20 % drawdown (120k → 96k)
        assert abs(max_dd_pct - 20.0) < 2.0  # within 2 pp

    def test_drawdown_duration_positive(
        self, drawdown_equity: pd.Series
    ) -> None:
        _, _, duration = _drawdown_stats(drawdown_equity)
        assert duration > 0

    def test_max_drawdown_negative_or_zero(
        self, drawdown_equity: pd.Series
    ) -> None:
        max_dd, _, _ = _drawdown_stats(drawdown_equity)
        assert max_dd <= 0


# ---------------------------------------------------------------------------
# compute_metrics (integration)
# ---------------------------------------------------------------------------

class TestComputeMetrics:

    def test_returns_metrics_result(self, trending_equity: pd.Series) -> None:
        trades = _make_trades([100.0, 200.0, -50.0])
        result = compute_metrics(trending_equity, trades, initial_capital=100_000.0)
        assert isinstance(result, MetricsResult)

    def test_empty_equity_returns_zeroed_result(self) -> None:
        result = compute_metrics(pd.Series(dtype=float), pd.DataFrame())
        assert result.cagr == 0.0
        assert result.sharpe_ratio == 0.0

    def test_positive_equity_positive_cagr(
        self, trending_equity: pd.Series
    ) -> None:
        result = compute_metrics(
            trending_equity, pd.DataFrame(), initial_capital=100_000.0
        )
        assert result.cagr > 0

    def test_net_pnl_matches_equity_change(
        self, trending_equity: pd.Series
    ) -> None:
        capital = 100_000.0
        result = compute_metrics(trending_equity, pd.DataFrame(), capital)
        expected = trending_equity.iloc[-1] - capital
        assert abs(result.net_pnl - expected) < 1.0

    def test_win_rate_all_wins(self) -> None:
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(np.linspace(100_000, 120_000, 252), index=dates)
        trades = _make_trades([100.0, 200.0, 150.0])
        result = compute_metrics(equity, trades)
        assert result.win_rate == 1.0

    def test_win_rate_all_losses(self) -> None:
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(np.linspace(100_000, 80_000, 252), index=dates)
        trades = _make_trades([-100.0, -200.0, -50.0])
        result = compute_metrics(equity, trades)
        assert result.win_rate == 0.0

    def test_profit_factor_all_wins(self) -> None:
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(np.linspace(100_000, 120_000, 252), index=dates)
        trades = _make_trades([100.0, 200.0])
        result = compute_metrics(equity, trades)
        assert math.isinf(result.profit_factor)

    def test_max_drawdown_correct(self, drawdown_equity: pd.Series) -> None:
        result = compute_metrics(
            drawdown_equity, pd.DataFrame(), initial_capital=100_000.0
        )
        assert abs(result.max_drawdown_pct - 20.0) < 2.0

    def test_rolling_sharpe_has_correct_length(
        self, trending_equity: pd.Series
    ) -> None:
        result = compute_metrics(trending_equity, pd.DataFrame())
        assert len(result.rolling_sharpe) == len(trending_equity)

    def test_underwater_has_correct_length(
        self, trending_equity: pd.Series
    ) -> None:
        result = compute_metrics(trending_equity, pd.DataFrame())
        assert len(result.underwater) == len(trending_equity)

    def test_consecutive_wins(self) -> None:
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(np.linspace(100_000, 120_000, 252), index=dates)
        pnls = [100, 200, 300, -50, 100, 100, 100, 100, -10]
        trades = _make_trades(pnls)
        result = compute_metrics(equity, trades)
        # Sequence: W W W L W W W W L → max streak = 4 (positions 4-7)
        assert result.max_consecutive_wins == 4
        assert result.max_consecutive_losses == 1

    def test_largest_win_and_loss(self) -> None:
        dates = pd.bdate_range("2020-01-01", periods=252)
        equity = pd.Series(np.linspace(100_000, 115_000, 252), index=dates)
        trades = _make_trades([500.0, -300.0, 200.0, -100.0])
        result = compute_metrics(equity, trades)
        assert abs(result.largest_win - 500.0) < 1e-6
        assert abs(result.largest_loss - (-300.0)) < 1e-6
