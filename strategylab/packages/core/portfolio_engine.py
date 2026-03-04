"""
portfolio_engine.py — Multi-asset portfolio backtesting engine.

Design
------
* Strategy returns target **weights** per symbol per bar (pd.DataFrame).
  Weights sum to ≤ 1.0 and may be negative (short).
* The engine rebalances to target weights at the next bar open.
* Cash earns no interest (conservative default).
* Execution costs are applied per-symbol per rebalance trade.

Portfolio value is marked-to-market at close each bar.

Weight conventions
------------------
* +0.5  = 50 % of portfolio in long position
*  0.0  = no position
* -0.3  = 30 % of portfolio short
* Weights are normalised if sum(abs) > 1 (no leverage by default).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from strategylab.packages.execution.costs import calc_commission, calc_fill_price
from strategylab.packages.execution.models import ExecutionConfig

from .models import BacktestResult, Trade

logger = logging.getLogger(__name__)

PortfolioTargetsFn = Callable[[pd.DataFrame, dict], pd.DataFrame]

_TRADE_COLUMNS = [
    "entry_date", "exit_date", "symbol", "direction",
    "entry_price", "exit_price", "shares",
    "gross_pnl", "commission", "net_pnl", "holding_bars",
]


@dataclass
class PortfolioState:
    """Mutable state carried through the simulation loop."""

    cash: float
    positions: dict[str, float] = field(default_factory=dict)   # symbol → shares
    entry_prices: dict[str, float] = field(default_factory=dict)
    entry_dates: dict[str, pd.Timestamp] = field(default_factory=dict)
    entry_directions: dict[str, str] = field(default_factory=dict)


class PortfolioEngine:
    """Multi-asset bar-by-bar portfolio backtesting engine.

    Parameters
    ----------
    initial_capital:
        Starting portfolio value.
    execution_config:
        Cost model applied to every rebalance trade.
    allow_leverage:
        If False (default), weights are normalised so sum(abs) ≤ 1.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        execution_config: ExecutionConfig | None = None,
        allow_leverage: bool = False,
    ) -> None:
        self.initial_capital = initial_capital
        self.execution_config = execution_config or ExecutionConfig()
        self.allow_leverage = allow_leverage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        data: pd.DataFrame,
        generate_targets: PortfolioTargetsFn,
        params: dict,
        symbols: list[str],
        strategy_name: str = "portfolio",
    ) -> BacktestResult:
        """Run a multi-asset portfolio backtest.

        Parameters
        ----------
        data:
            Wide-format DataFrame with MultiIndex columns ``(field, symbol)``.
        generate_targets:
            Function returning a DataFrame of target weights indexed by date,
            columns = symbols.
        params:
            Strategy parameters passed to ``generate_targets``.
        symbols:
            List of ticker symbols to include in the portfolio.
        strategy_name:
            Label stored on the result.

        Returns
        -------
        BacktestResult
        """
        close_df = data["close"][symbols]
        open_df = data["open"][symbols]

        targets_df = generate_targets(close_df, params)
        targets_df = self._align_targets(targets_df, close_df)

        if not self.allow_leverage:
            targets_df = self._normalise_weights(targets_df)

        equity, trades = self._simulate(close_df, open_df, targets_df, symbols)
        drawdown = self._compute_drawdown(equity)

        trade_df = (
            pd.DataFrame([t.__dict__ for t in trades], columns=_TRADE_COLUMNS)
            if trades
            else pd.DataFrame(columns=_TRADE_COLUMNS)
        )

        logger.info(
            "Portfolio backtest '%s': %d bars, %d trades, final equity %.2f",
            strategy_name,
            len(equity),
            len(trades),
            equity.iloc[-1] if len(equity) else 0.0,
        )

        return BacktestResult(
            equity_curve=equity,
            trade_log=trade_df,
            drawdown_series=drawdown,
            initial_capital=self.initial_capital,
            symbol=symbols,
            strategy_name=strategy_name,
            params=params,
        )

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def _simulate(
        self,
        close_df: pd.DataFrame,
        open_df: pd.DataFrame,
        targets_df: pd.DataFrame,
        symbols: list[str],
    ) -> tuple[pd.Series, list[Trade]]:
        """Bar-by-bar portfolio simulation."""
        cfg = self.execution_config
        state = PortfolioState(cash=self.initial_capital)
        trades: list[Trade] = []
        equity_values: list[float] = []

        dates = close_df.index
        n = len(dates)
        date_iloc: dict = {d: i for i, d in enumerate(dates)}

        # Track the APPLIED weights (what's actually in the portfolio).
        # Starts as all zeros (cash only).
        applied_weights = pd.Series(0.0, index=symbols)

        for i, date in enumerate(dates):
            if i > 0:
                # Signal from previous bar — execute at open[i]
                desired_weights = targets_df.iloc[i - 1]

                # Rebalance whenever the desired allocation differs from applied
                if not desired_weights.equals(applied_weights):
                    self._rebalance(
                        state=state,
                        date=date,
                        prev_weights=applied_weights,
                        new_weights=desired_weights,
                        open_prices=open_df.iloc[i],
                        symbols=symbols,
                        cfg=cfg,
                        trades=trades,
                        date_iloc=date_iloc,
                        bar_index=i,
                    )
                    applied_weights = desired_weights.copy()

            # Mark-to-market at close[i]
            portfolio_value = state.cash
            for sym in symbols:
                shares = state.positions.get(sym, 0.0)
                if shares != 0.0:
                    close_price = float(close_df[sym].iloc[i])
                    entry_p = state.entry_prices.get(sym, close_price)
                    if shares > 0:
                        portfolio_value += shares * close_price
                    else:
                        # Short: cash + unrealised P&L
                        unrealised = (entry_p - close_price) * abs(shares)
                        portfolio_value += unrealised  # short already locked cash at entry

            equity_values.append(portfolio_value)

        # Force-close all positions at end
        if n > 0:
            last_date = dates[-1]
            for sym in list(state.positions.keys()):
                shares = state.positions.get(sym, 0.0)
                if shares != 0.0:
                    close_price = float(close_df[sym].iloc[-1])
                    direction = 1 if shares > 0 else -1
                    fill = calc_fill_price(
                        close_price, -direction, cfg.spread, cfg.slippage
                    )
                    commission = calc_commission(abs(shares) * fill, cfg.commission)
                    entry_p = state.entry_prices.get(sym, fill)
                    gross_pnl = (fill - entry_p) * shares
                    entry_d = state.entry_dates.get(sym, last_date)
                    trades.append(
                        Trade(
                            entry_date=entry_d,
                            exit_date=last_date,
                            symbol=sym,
                            direction=state.entry_directions.get(sym, "long"),  # type: ignore[arg-type]
                            entry_price=entry_p,
                            exit_price=fill,
                            shares=abs(shares),
                            gross_pnl=gross_pnl,
                            commission=commission,
                            net_pnl=gross_pnl - commission,
                            holding_bars=n - 1 - date_iloc.get(entry_d, n - 1),
                        )
                    )

        equity = pd.Series(equity_values, index=dates, name="equity")
        return equity, trades

    def _rebalance(
        self,
        state: PortfolioState,
        date: pd.Timestamp,
        prev_weights: pd.Series,
        new_weights: pd.Series,
        open_prices: pd.Series,
        symbols: list[str],
        cfg: ExecutionConfig,
        trades: list[Trade],
        date_iloc: dict,
        bar_index: int,
    ) -> None:
        """Execute rebalance trades to move from prev_weights to new_weights."""
        # Compute current portfolio value at the open prices
        portfolio_value = state.cash
        for sym in symbols:
            shares = state.positions.get(sym, 0.0)
            if shares != 0.0:
                entry_p = state.entry_prices.get(sym, float(open_prices[sym]))
                if shares > 0:
                    portfolio_value += shares * float(open_prices[sym])
                else:
                    unrealised = (entry_p - float(open_prices[sym])) * abs(shares)
                    portfolio_value += unrealised

        for sym in symbols:
            old_w = float(prev_weights.get(sym, 0.0))
            new_w = float(new_weights.get(sym, 0.0))

            if abs(new_w - old_w) < 1e-9:
                continue  # no change

            raw_price = float(open_prices[sym])
            current_shares = state.positions.get(sym, 0.0)

            # Target shares from weight
            target_shares_unsigned = abs(new_w) * portfolio_value / raw_price
            target_shares = target_shares_unsigned * (1 if new_w >= 0 else -1)
            delta_shares = target_shares - current_shares

            if abs(delta_shares) < 1e-6:
                continue

            trade_direction = 1 if delta_shares > 0 else -1
            fill = calc_fill_price(raw_price, trade_direction, cfg.spread, cfg.slippage)
            notional = abs(delta_shares) * fill
            commission = calc_commission(notional, cfg.commission)

            # Close or reduce existing position if switching sides
            if current_shares != 0.0 and (
                (current_shares > 0 and delta_shares < 0 and abs(delta_shares) >= current_shares)
                or (current_shares < 0 and delta_shares > 0 and abs(delta_shares) >= abs(current_shares))
            ):
                # Closing out old leg first
                entry_p = state.entry_prices.get(sym, fill)
                gross_pnl = (fill - entry_p) * current_shares
                entry_d = state.entry_dates.get(sym, date)
                trades.append(
                    Trade(
                        entry_date=entry_d,
                        exit_date=date,
                        symbol=sym,
                        direction=state.entry_directions.get(sym, "long"),  # type: ignore[arg-type]
                        entry_price=entry_p,
                        exit_price=fill,
                        shares=abs(current_shares),
                        gross_pnl=gross_pnl,
                        commission=commission,
                        net_pnl=gross_pnl - commission,
                        holding_bars=bar_index - date_iloc.get(entry_d, bar_index),
                    )
                )
                # Adjust cash
                state.cash += current_shares * fill - commission
                state.positions[sym] = 0.0
                current_shares = 0.0

            # Open / adjust to new weight
            if abs(new_w) > 1e-9:
                entry_dir = "long" if new_w > 0 else "short"
                state.positions[sym] = target_shares
                state.entry_prices[sym] = fill
                state.entry_dates[sym] = date
                state.entry_directions[sym] = entry_dir

                if new_w > 0:
                    state.cash -= target_shares * fill + commission
                # (shorts handled via position tracking)
            else:
                state.positions[sym] = 0.0
                state.entry_prices.pop(sym, None)
                state.entry_dates.pop(sym, None)
                state.entry_directions.pop(sym, None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _align_targets(
        targets: pd.DataFrame, prices: pd.DataFrame
    ) -> pd.DataFrame:
        """Forward-fill target weights to the price index."""
        aligned = targets.reindex(prices.index, method="ffill").fillna(0.0)
        return aligned

    @staticmethod
    def _normalise_weights(weights: pd.DataFrame) -> pd.DataFrame:
        """Normalise weights so the sum of absolute values ≤ 1.0."""
        abs_sum = weights.abs().sum(axis=1)
        # Only normalise rows where abs_sum > 1
        needs_norm = abs_sum > 1.0
        result = weights.copy()
        result.loc[needs_norm] = weights.loc[needs_norm].div(
            abs_sum[needs_norm], axis=0
        )
        return result

    @staticmethod
    def _compute_drawdown(equity: pd.Series) -> pd.Series:
        """Running percentage drawdown from peak (values <= 0)."""
        running_max = equity.cummax()
        dd = (equity - running_max) / running_max
        dd.name = "drawdown"
        return dd
