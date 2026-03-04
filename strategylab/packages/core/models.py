"""
core/models.py — Data transfer objects for the backtesting engine.

ExecutionConfig lives in packages/execution; re-exported here for convenience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


@dataclass
class Trade:
    """A single completed round-trip trade."""

    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    symbol: str
    direction: Literal["long", "short"]
    entry_price: float
    exit_price: float
    shares: float
    gross_pnl: float
    commission: float
    net_pnl: float
    holding_bars: int


@dataclass
class BacktestResult:
    """All outputs from a completed backtest run.

    Parameters
    ----------
    equity_curve:
        Portfolio value at close of each bar.  Index is DatetimeIndex.
    trade_log:
        DataFrame of completed round-trip trades with columns matching
        :class:`Trade` fields.
    drawdown_series:
        Percentage drawdown from the running peak at each bar.
        Values are <= 0 (e.g. -0.15 = 15 % drawdown).
    initial_capital:
        Starting portfolio value used in this run.
    symbol:
        Ticker(s) traded. Single string for single-asset, list for portfolio.
    strategy_name:
        Name of the strategy that produced this result.
    params:
        Parameter dict used during this run.
    """

    equity_curve: pd.Series
    trade_log: pd.DataFrame
    drawdown_series: pd.Series
    initial_capital: float
    symbol: str | list[str]
    strategy_name: str
    params: dict = field(default_factory=dict)
