"""
engine.py — Single-asset backtesting engine.

Execution model
---------------
* Signals (target positions) are generated on bar ``t`` using data up to
  bar ``t`` (no look-ahead).
* Trades execute at the **open** of bar ``t+1``.
* Costs applied at fill time via the execution package:
    1. Spread  — adjusts the raw fill price
    2. Slippage — further adjusts the spread-adjusted price
    3. Commission — charged on notional value

Position encoding
-----------------
* +1  long
*  0  flat
* -1  short
"""

from __future__ import annotations

import logging
from typing import Callable

import pandas as pd

from strategylab.packages.execution.costs import (
    calc_commission,
    calc_fill_price,
)
from strategylab.packages.execution.models import ExecutionConfig

from .models import BacktestResult, Trade

logger = logging.getLogger(__name__)

TargetsFn = Callable[[pd.DataFrame, dict], pd.Series]

_TRADE_COLUMNS = [
    "entry_date", "exit_date", "symbol", "direction",
    "entry_price", "exit_price", "shares",
    "gross_pnl", "commission", "net_pnl", "holding_bars",
]


class BacktestEngine:
    """Single-asset bar-by-bar backtesting engine.

    Parameters
    ----------
    initial_capital:
        Starting portfolio value in currency units.
    execution_config:
        Cost model configuration.  Defaults to realistic retail costs.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        execution_config: ExecutionConfig | None = None,
    ) -> None:
        self.initial_capital = initial_capital
        self.execution_config = execution_config or ExecutionConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        data: pd.DataFrame,
        generate_targets: TargetsFn,
        params: dict,
        symbol: str,
        strategy_name: str = "unknown",
    ) -> BacktestResult:
        """Run a single-asset backtest.

        Parameters
        ----------
        data:
            Wide-format DataFrame with MultiIndex columns ``(field, symbol)``.
            Must contain ``open`` and ``close`` fields for ``symbol``.
        generate_targets:
            Strategy function returning ``pd.Series`` of ``{-1, 0, 1}``.
        params:
            Parameter dict passed directly to ``generate_targets``.
        symbol:
            Ticker to trade (must exist in ``data``).
        strategy_name:
            Label stored on the returned :class:`BacktestResult`.

        Returns
        -------
        BacktestResult
        """
        close = self._extract_series(data, "close", symbol)
        open_ = self._extract_series(data, "open", symbol)

        targets = generate_targets(close.to_frame(name=symbol), params)
        targets = self._align_targets(targets, close)

        equity, trades = self._simulate(close, open_, targets, symbol)
        drawdown = self._compute_drawdown(equity)

        trade_df = (
            pd.DataFrame([t.__dict__ for t in trades], columns=_TRADE_COLUMNS)
            if trades
            else pd.DataFrame(columns=_TRADE_COLUMNS)
        )

        logger.info(
            "Backtest '%s': %d bars, %d trades, final equity %.2f",
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
            symbol=symbol,
            strategy_name=strategy_name,
            params=params,
        )

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _simulate(
        self,
        close: pd.Series,
        open_: pd.Series,
        targets: pd.Series,
        symbol: str,
    ) -> tuple[pd.Series, list[Trade]]:
        """Bar-by-bar simulation with next-bar-open execution.

        State machine
        -------------
        * ``position`` tracks the current holding direction {-1, 0, 1}.
        * When ``targets[t-1] != position``, a trade fires at ``open_[t]``.
        * The portfolio is marked to market at ``close[t]`` each bar.

        Short accounting
        ----------------
        Short proceeds are held in a notional proceeds variable.
        At close:  equity = initial_capital + (entry_price - current_close) * shares - commissions_paid
        """
        cfg = self.execution_config
        capital = self.initial_capital
        cash: float = capital
        shares: float = 0.0
        position: int = 0

        # Track total commission paid for open short (for M2M calculation)
        open_commission: float = 0.0

        equity_values: list[float] = []
        trades: list[Trade] = []

        entry_date: pd.Timestamp | None = None
        entry_price: float = 0.0
        entry_direction: str = "long"

        dates = close.index
        n = len(dates)
        date_iloc: dict[pd.Timestamp, int] = {d: i for i, d in enumerate(dates)}

        for i, date in enumerate(dates):
            prev_target = int(targets.iloc[i - 1]) if i > 0 else 0

            # ---- Execute at open[i] when signal changed -----------------
            if i > 0 and prev_target != position and i < n:
                raw_open = float(open_.iloc[i])

                # --- Close existing position ---
                if position != 0 and shares > 0:
                    # Direction of the closing trade is opposite to open
                    close_dir = -position  # closing a long = sell (-1)
                    fill = calc_fill_price(
                        raw_open, close_dir, cfg.spread, cfg.slippage
                    )
                    notional = shares * fill
                    commission = calc_commission(notional, cfg.commission)

                    if position == 1:
                        gross_pnl = (fill - entry_price) * shares
                        cash += notional - commission
                    else:  # short
                        gross_pnl = (entry_price - fill) * shares
                        # Buy back: deduct cost + commission
                        cash = capital + gross_pnl - open_commission - commission

                    trades.append(
                        Trade(
                            entry_date=entry_date,          # type: ignore[arg-type]
                            exit_date=date,
                            symbol=symbol,
                            direction=entry_direction,      # type: ignore[arg-type]
                            entry_price=entry_price,
                            exit_price=fill,
                            shares=shares,
                            gross_pnl=gross_pnl,
                            commission=open_commission + commission,
                            net_pnl=gross_pnl - open_commission - commission,
                            holding_bars=i - date_iloc[entry_date],  # type: ignore[arg-type]
                        )
                    )
                    shares = 0.0
                    position = 0
                    open_commission = 0.0

                # --- Open new position ---
                if prev_target != 0:
                    open_dir = prev_target  # +1 = buy, -1 = sell short
                    fill = calc_fill_price(
                        raw_open, open_dir, cfg.spread, cfg.slippage
                    )
                    trade_value = abs(cash)
                    commission = calc_commission(trade_value, cfg.commission)
                    shares = (trade_value - commission) / fill
                    entry_price = fill
                    entry_date = date
                    entry_direction = "long" if prev_target == 1 else "short"
                    open_commission = commission
                    position = prev_target

                    if prev_target == 1:
                        cash -= shares * fill + commission

            # ---- Mark-to-market at close[i] ----------------------------
            current_close = float(close.iloc[i])
            if position == 1:
                mtm = cash + shares * current_close
            elif position == -1:
                # Short: profit if price falls below entry
                gross_unrealised = (entry_price - current_close) * shares
                mtm = capital + gross_unrealised - open_commission
            else:
                mtm = cash
            equity_values.append(mtm)

        # ---- Force-close any open position at end of history ------------
        if position != 0 and shares > 0 and n > 0:
            last_close = float(close.iloc[-1])
            close_dir = -position
            fill = calc_fill_price(
                last_close, close_dir, cfg.spread, cfg.slippage
            )
            notional = shares * fill
            commission = calc_commission(notional, cfg.commission)

            if position == 1:
                gross_pnl = (fill - entry_price) * shares
            else:
                gross_pnl = (entry_price - fill) * shares

            trades.append(
                Trade(
                    entry_date=entry_date,              # type: ignore[arg-type]
                    exit_date=dates[-1],
                    symbol=symbol,
                    direction=entry_direction,          # type: ignore[arg-type]
                    entry_price=entry_price,
                    exit_price=fill,
                    shares=shares,
                    gross_pnl=gross_pnl,
                    commission=open_commission + commission,
                    net_pnl=gross_pnl - open_commission - commission,
                    holding_bars=n - 1 - date_iloc[entry_date],  # type: ignore[arg-type]
                )
            )

        equity = pd.Series(equity_values, index=dates, name="equity")
        return equity, trades

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_series(
        data: pd.DataFrame, field: str, symbol: str
    ) -> pd.Series:
        """Extract a single field/symbol price series from wide-format data."""
        if isinstance(data.columns, pd.MultiIndex):
            if (field, symbol) in data.columns:
                return data[(field, symbol)].dropna()
            raise KeyError(
                f"MultiIndex column ({field!r}, {symbol!r}) not found. "
                f"Available: {list(data.columns)}"
            )
        # Plain DataFrame fallback (e.g. just close prices passed in)
        if symbol in data.columns:
            return data[symbol].dropna()
        raise KeyError(
            f"Column {symbol!r} not found. Available: {list(data.columns)}"
        )

    @staticmethod
    def _align_targets(targets: pd.Series, price: pd.Series) -> pd.Series:
        """Align and forward-fill targets to the price index."""
        aligned = targets.reindex(price.index, method="ffill").fillna(0)
        return aligned.astype(int)

    @staticmethod
    def _compute_drawdown(equity: pd.Series) -> pd.Series:
        """Running percentage drawdown from the peak (values <= 0)."""
        running_max = equity.cummax()
        dd = (equity - running_max) / running_max
        dd.name = "drawdown"
        return dd
