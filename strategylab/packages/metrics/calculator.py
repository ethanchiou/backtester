"""
calculator.py — Performance metrics for backtested strategies.

All functions operate on plain pandas Series / DataFrames.
No side effects, no database access, no web framework imports.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Trading days per year assumption
TRADING_DAYS_PER_YEAR: int = 252


@dataclass
class MetricsResult:
    """Container for all computed performance metrics.

    All ratio metrics use daily returns as their base unit.
    """

    # --- Return metrics ---------------------------------------------------
    cagr: float                     # Compound Annual Growth Rate
    net_pnl: float                  # Final equity minus initial capital
    total_return_pct: float         # Total return as a percentage

    # --- Risk-adjusted metrics -------------------------------------------
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility_annual: float        # Annualised daily return std dev

    # --- Drawdown metrics ------------------------------------------------
    max_drawdown: float             # Maximum peak-to-trough (negative fraction)
    max_drawdown_pct: float         # As a percentage (positive, e.g. 15.3)
    max_drawdown_duration: int      # Longest drawdown in calendar days

    # --- Trade statistics ------------------------------------------------
    total_trades: int
    win_rate: float                 # Fraction of winning trades
    profit_factor: float            # Gross profit / gross loss
    expectancy: float               # Average net P&L per trade (EV)
    avg_holding_bars: float         # Average trade duration in bars
    largest_win: float
    largest_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # --- Exposure --------------------------------------------------------
    exposure: float                 # Fraction of bars with a non-zero position

    # --- Chart series (not scalar) ----------------------------------------
    rolling_sharpe: pd.Series = field(default_factory=pd.Series)
    underwater: pd.Series = field(default_factory=pd.Series)


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

def compute_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    initial_capital: float = 100_000.0,
    risk_free_rate: float = 0.0,
    rolling_sharpe_window: int = 63,
) -> MetricsResult:
    """Compute all performance metrics from an equity curve and trade log.

    Parameters
    ----------
    equity:
        Portfolio value series indexed by date (DatetimeIndex).
    trades:
        Trade log DataFrame with columns: net_pnl, entry_date, exit_date,
        holding_bars.  May be empty (strategy never traded).
    initial_capital:
        Starting portfolio value.
    risk_free_rate:
        Annual risk-free rate (decimal, e.g. 0.04 for 4 %).
    rolling_sharpe_window:
        Look-back window (bars) for the rolling Sharpe series.

    Returns
    -------
    MetricsResult
    """
    if equity.empty:
        return _empty_metrics(initial_capital)

    daily_returns = equity.pct_change().fillna(0.0)
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR

    cagr = _compute_cagr(equity, initial_capital)
    net_pnl = float(equity.iloc[-1] - initial_capital)
    total_return_pct = (net_pnl / initial_capital) * 100.0

    vol = _annualised_volatility(daily_returns)
    sharpe = _sharpe(daily_returns, rf_daily)
    sortino = _sortino(daily_returns, rf_daily)
    max_dd, max_dd_pct, dd_duration = _drawdown_stats(equity)
    calmar = cagr / max_dd_pct if max_dd_pct > 0 else 0.0

    trade_stats = _trade_statistics(trades)
    underwater = _underwater_series(equity)
    rolling_sh = _rolling_sharpe(daily_returns, window=rolling_sharpe_window)

    return MetricsResult(
        cagr=cagr,
        net_pnl=net_pnl,
        total_return_pct=total_return_pct,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        volatility_annual=vol,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration=dd_duration,
        rolling_sharpe=rolling_sh,
        underwater=underwater,
        **trade_stats,
    )


# ---------------------------------------------------------------------------
# Return / growth metrics
# ---------------------------------------------------------------------------

def _compute_cagr(equity: pd.Series, initial_capital: float) -> float:
    """Compound Annual Growth Rate."""
    if initial_capital <= 0 or equity.empty:
        return 0.0
    years = len(equity) / TRADING_DAYS_PER_YEAR
    if years <= 0:
        return 0.0
    final = float(equity.iloc[-1])
    if final <= 0:
        return -1.0
    return (final / initial_capital) ** (1.0 / years) - 1.0


def _annualised_volatility(daily_returns: pd.Series) -> float:
    """Annualised standard deviation of daily returns."""
    return float(daily_returns.std() * math.sqrt(TRADING_DAYS_PER_YEAR))


# ---------------------------------------------------------------------------
# Risk-adjusted metrics
# ---------------------------------------------------------------------------

def _sharpe(daily_returns: pd.Series, rf_daily: float = 0.0) -> float:
    """Annualised Sharpe Ratio."""
    excess = daily_returns - rf_daily
    std = excess.std()
    if std == 0:
        return 0.0
    return float((excess.mean() / std) * math.sqrt(TRADING_DAYS_PER_YEAR))


def _sortino(daily_returns: pd.Series, rf_daily: float = 0.0) -> float:
    """Annualised Sortino Ratio (uses downside deviation)."""
    excess = daily_returns - rf_daily
    downside = excess[excess < 0]
    if downside.empty:
        return float("inf")
    downside_std = math.sqrt((downside**2).mean()) * math.sqrt(TRADING_DAYS_PER_YEAR)
    if downside_std == 0:
        return 0.0
    return float(excess.mean() * TRADING_DAYS_PER_YEAR / downside_std)


# ---------------------------------------------------------------------------
# Drawdown metrics
# ---------------------------------------------------------------------------

def _drawdown_stats(
    equity: pd.Series,
) -> tuple[float, float, int]:
    """Return (max_drawdown, max_drawdown_pct, max_drawdown_duration_days).

    max_drawdown is a negative fraction (e.g. -0.35).
    max_drawdown_pct is the same value expressed as a positive percentage.
    Duration is measured in calendar days.
    """
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max

    max_dd = float(drawdown.min())          # negative
    max_dd_pct = abs(max_dd) * 100.0

    # Duration: longest consecutive period where equity < running_max
    is_underwater = (drawdown < 0).astype(int)
    duration_days = _max_consecutive_duration(is_underwater, equity.index)

    return max_dd, max_dd_pct, duration_days


def _max_consecutive_duration(
    underwater: pd.Series, index: pd.DatetimeIndex
) -> int:
    """Return the longest period (in calendar days) continuously underwater."""
    max_duration = 0
    start = None
    for i, val in enumerate(underwater):
        if val == 1:
            if start is None:
                start = index[i]
        else:
            if start is not None:
                duration = (index[i] - start).days
                max_duration = max(max_duration, duration)
                start = None
    if start is not None:
        duration = (index[-1] - start).days
        max_duration = max(max_duration, duration)
    return max_duration


# ---------------------------------------------------------------------------
# Chart series
# ---------------------------------------------------------------------------

def _underwater_series(equity: pd.Series) -> pd.Series:
    """Percentage drawdown from peak at each bar (negative values)."""
    running_max = equity.cummax()
    underwater = ((equity - running_max) / running_max) * 100.0
    underwater.name = "underwater_pct"
    return underwater


def _rolling_sharpe(daily_returns: pd.Series, window: int = 63) -> pd.Series:
    """Rolling annualised Sharpe Ratio over a trailing window."""
    rolling_mean = daily_returns.rolling(window).mean()
    rolling_std = daily_returns.rolling(window).std()
    sharpe = (rolling_mean / rolling_std.replace(0, float("nan"))) * math.sqrt(
        TRADING_DAYS_PER_YEAR
    )
    sharpe.name = "rolling_sharpe"
    return sharpe


# ---------------------------------------------------------------------------
# Trade statistics
# ---------------------------------------------------------------------------

def _trade_statistics(trades: pd.DataFrame) -> dict:
    """Compute all trade-level statistics from the trade log."""
    if trades.empty:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "avg_holding_bars": 0.0,
            "largest_win": 0.0,
            "largest_loss": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "exposure": 0.0,
        }

    pnls = trades["net_pnl"]
    winners = pnls[pnls > 0]
    losers = pnls[pnls <= 0]

    total = len(pnls)
    win_rate = len(winners) / total if total > 0 else 0.0

    gross_profit = float(winners.sum())
    gross_loss = abs(float(losers.sum()))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    expectancy = float(pnls.mean()) if total > 0 else 0.0
    avg_holding = (
        float(trades["holding_bars"].mean()) if "holding_bars" in trades.columns else 0.0
    )
    largest_win = float(winners.max()) if not winners.empty else 0.0
    largest_loss = float(losers.min()) if not losers.empty else 0.0

    consec_wins, consec_losses = _consecutive_runs(pnls)

    # Exposure: fraction of total backtest bars with open position
    # Approximated as sum of holding bars / total bars in equity
    exposure = 0.0
    if "holding_bars" in trades.columns and total > 0:
        total_holding = trades["holding_bars"].sum()
        # We don't have total bars here; set to NaN-safe 0, engine injects it
        exposure = 0.0  # will be computed by engine if needed

    return {
        "total_trades": total,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_holding_bars": avg_holding,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "max_consecutive_wins": consec_wins,
        "max_consecutive_losses": consec_losses,
        "exposure": exposure,
    }


def _consecutive_runs(pnls: pd.Series) -> tuple[int, int]:
    """Return (max consecutive wins, max consecutive losses)."""
    max_wins = max_losses = 0
    cur_wins = cur_losses = 0
    for pnl in pnls:
        if pnl > 0:
            cur_wins += 1
            cur_losses = 0
        else:
            cur_losses += 1
            cur_wins = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses


# ---------------------------------------------------------------------------
# Fallback for empty results
# ---------------------------------------------------------------------------

def _empty_metrics(initial_capital: float) -> MetricsResult:
    """Return a zeroed MetricsResult when no backtest data is available."""
    return MetricsResult(
        cagr=0.0,
        net_pnl=0.0,
        total_return_pct=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        calmar_ratio=0.0,
        volatility_annual=0.0,
        max_drawdown=0.0,
        max_drawdown_pct=0.0,
        max_drawdown_duration=0,
        total_trades=0,
        win_rate=0.0,
        profit_factor=0.0,
        expectancy=0.0,
        avg_holding_bars=0.0,
        largest_win=0.0,
        largest_loss=0.0,
        max_consecutive_wins=0,
        max_consecutive_losses=0,
        exposure=0.0,
    )
