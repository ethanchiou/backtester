"""
montecarlo/simulator.py — Monte Carlo simulation engine.

Three simulation methods
------------------------
1. trade_shuffle          — randomly reorder trade P&Ls, rebuild equity
2. block_bootstrap        — block bootstrap daily returns, rebuild equity
3. parameter_uncertainty  — resample strategy params, re-run full backtests

Each method runs ``n_simulations`` paths and collects:
    * final equity
    * max drawdown
    * CAGR

Then computes percentile bands across all paths.
"""

from __future__ import annotations

import logging
import math
from typing import Callable

import numpy as np
import pandas as pd

from strategylab.packages.core.models import BacktestResult

from .models import PERCENTILES, MCResult, SimulationConfig

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_simulation(
    result: BacktestResult,
    config: SimulationConfig | None = None,
    *,
    # Needed only for method 3 (parameter_uncertainty)
    generate_targets: Callable | None = None,
    run_backtest: Callable | None = None,
    params: dict | None = None,
    param_bounds: dict[str, tuple[float, float]] | None = None,
) -> MCResult:
    """Run a Monte Carlo simulation on a completed backtest result.

    Parameters
    ----------
    result:
        Output of a completed :class:`BacktestEngine` run.
    config:
        Simulation configuration.  Defaults to 1000-path trade shuffle.
    generate_targets:
        Strategy function — required for ``parameter_uncertainty`` method.
    run_backtest:
        Callable ``(params) -> BacktestResult`` — required for method 3.
    params:
        Base parameter dict — required for method 3.
    param_bounds:
        Optional ``{param: (min, max)}`` bounds to clamp sampled params.

    Returns
    -------
    MCResult
    """
    if config is None:
        config = SimulationConfig()

    rng = np.random.default_rng(config.seed)

    if config.method == "trade_shuffle":
        return _trade_shuffle(result, config, rng)
    elif config.method == "block_bootstrap":
        return _block_bootstrap(result, config, rng)
    elif config.method == "parameter_uncertainty":
        if run_backtest is None or params is None:
            raise ValueError(
                "parameter_uncertainty requires 'run_backtest' and 'params' arguments."
            )
        return _parameter_uncertainty(result, config, rng, run_backtest, params, param_bounds)
    else:
        raise ValueError(f"Unknown simulation method: {config.method!r}")


# ---------------------------------------------------------------------------
# Method 1 — Trade Sequence Shuffle
# ---------------------------------------------------------------------------

def _trade_shuffle(
    result: BacktestResult,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> MCResult:
    """Shuffle trade P&L order N times, reconstruct equity curve each time."""
    if result.trade_log.empty:
        logger.warning("Trade log is empty — returning degenerate MC result.")
        return _degenerate_result(result, config)

    pnls = result.trade_log["net_pnl"].values.copy()
    capital = result.initial_capital
    n_trades = len(pnls)

    # Pre-allocate output arrays
    final_equities = np.empty(config.n_simulations)
    max_drawdowns = np.empty(config.n_simulations)
    cagrs = np.empty(config.n_simulations)

    # We need a time axis to compute CAGR — use the original equity curve length
    n_bars = len(result.equity_curve)

    all_equity_curves: list[np.ndarray] = []

    for i in range(config.n_simulations):
        shuffled = rng.permutation(pnls)
        # Rebuild equity: each trade contributes its P&L to cumulative sum
        # We spread trades evenly across the bar timeline for visualisation
        equity = _pnl_to_equity_curve(shuffled, capital, n_bars)
        all_equity_curves.append(equity)

        final_equities[i] = equity[-1]
        max_drawdowns[i] = _max_dd_pct(equity)
        cagrs[i] = _cagr(equity[-1], capital, n_bars)

    equity_pcts, dd_pcts = _compute_percentile_bands(
        all_equity_curves, result.equity_curve.index, capital
    )

    return MCResult(
        method="trade_shuffle",
        n_simulations=config.n_simulations,
        equity_percentiles=equity_pcts,
        drawdown_percentiles=dd_pcts,
        cagr_distribution=cagrs,
        final_equity_distribution=final_equities,
        max_drawdown_distribution=max_drawdowns,
        initial_capital=capital,
    )


# ---------------------------------------------------------------------------
# Method 2 — Block Bootstrap
# ---------------------------------------------------------------------------

def _block_bootstrap(
    result: BacktestResult,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> MCResult:
    """Block-bootstrap daily returns and reconstruct equity N times."""
    equity = result.equity_curve
    capital = result.initial_capital
    daily_returns = equity.pct_change().fillna(0.0).values
    n_bars = len(daily_returns)
    block_size = config.block_size

    final_equities = np.empty(config.n_simulations)
    max_drawdowns = np.empty(config.n_simulations)
    cagrs = np.empty(config.n_simulations)

    all_equity_curves: list[np.ndarray] = []

    for i in range(config.n_simulations):
        bootstrapped = _block_bootstrap_returns(daily_returns, n_bars, block_size, rng)
        sim_equity = capital * np.cumprod(1.0 + bootstrapped)
        all_equity_curves.append(sim_equity)

        final_equities[i] = sim_equity[-1]
        max_drawdowns[i] = _max_dd_pct(sim_equity)
        cagrs[i] = _cagr(sim_equity[-1], capital, n_bars)

    equity_pcts, dd_pcts = _compute_percentile_bands(
        all_equity_curves, equity.index, capital
    )

    return MCResult(
        method="block_bootstrap",
        n_simulations=config.n_simulations,
        equity_percentiles=equity_pcts,
        drawdown_percentiles=dd_pcts,
        cagr_distribution=cagrs,
        final_equity_distribution=final_equities,
        max_drawdown_distribution=max_drawdowns,
        initial_capital=capital,
    )


# ---------------------------------------------------------------------------
# Method 3 — Parameter Uncertainty
# ---------------------------------------------------------------------------

def _parameter_uncertainty(
    result: BacktestResult,
    config: SimulationConfig,
    rng: np.random.Generator,
    run_backtest: Callable[[dict], BacktestResult],
    base_params: dict,
    param_bounds: dict[str, tuple[float, float]] | None,
) -> MCResult:
    """Sample params around defaults, run a full backtest for each sample."""
    sigma = config.param_uncertainty_pct
    capital = result.initial_capital
    n_bars = len(result.equity_curve)

    final_equities = np.empty(config.n_simulations)
    max_drawdowns = np.empty(config.n_simulations)
    cagrs = np.empty(config.n_simulations)

    all_equity_curves: list[np.ndarray] = []

    for i in range(config.n_simulations):
        sampled = {}
        for k, v in base_params.items():
            if isinstance(v, (int, float)):
                noise = rng.normal(0, abs(v) * sigma)
                val = v + noise
                if param_bounds and k in param_bounds:
                    lo, hi = param_bounds[k]
                    val = float(np.clip(val, lo, hi))
                # Integer params stay integer
                sampled[k] = int(round(val)) if isinstance(v, int) else float(val)
            else:
                sampled[k] = v

        try:
            sim_result = run_backtest(sampled)
            equity = sim_result.equity_curve.values
        except Exception:
            # Bad params (e.g. fast >= slow) — skip this path
            equity = np.full(n_bars, capital)

        all_equity_curves.append(equity)
        final_equities[i] = equity[-1]
        max_drawdowns[i] = _max_dd_pct(equity)
        cagrs[i] = _cagr(equity[-1], capital, n_bars)

    equity_pcts, dd_pcts = _compute_percentile_bands(
        all_equity_curves, result.equity_curve.index, capital
    )

    return MCResult(
        method="parameter_uncertainty",
        n_simulations=config.n_simulations,
        equity_percentiles=equity_pcts,
        drawdown_percentiles=dd_pcts,
        cagr_distribution=cagrs,
        final_equity_distribution=final_equities,
        max_drawdown_distribution=max_drawdowns,
        initial_capital=capital,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pnl_to_equity_curve(
    pnls: np.ndarray, capital: float, n_bars: int
) -> np.ndarray:
    """Spread trade P&Ls evenly across ``n_bars`` to form an equity curve."""
    equity = np.full(n_bars, capital)
    if len(pnls) == 0 or n_bars == 0:
        return equity

    # Distribute each trade's P&L at evenly spaced bar indices
    step = n_bars / len(pnls)
    cum_pnl = 0.0
    for j, pnl in enumerate(pnls):
        bar = min(int(j * step), n_bars - 1)
        cum_pnl += pnl
        equity[bar:] = capital + cum_pnl

    return equity


def _block_bootstrap_returns(
    returns: np.ndarray, n_bars: int, block_size: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw blocks of returns with replacement to fill ``n_bars``."""
    n = len(returns)
    result: list[np.ndarray] = []
    while sum(len(b) for b in result) < n_bars:
        start = rng.integers(0, max(1, n - block_size))
        block = returns[start : start + block_size]
        result.append(block)
    combined = np.concatenate(result)[:n_bars]
    return combined


def _max_dd_pct(equity: np.ndarray) -> float:
    """Maximum drawdown as a positive percentage."""
    if len(equity) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / np.where(running_max != 0, running_max, 1)
    return float(abs(dd.min()) * 100.0)


def _cagr(final_equity: float, initial_capital: float, n_bars: int) -> float:
    """Compound Annual Growth Rate from bar count."""
    if initial_capital <= 0 or final_equity <= 0 or n_bars <= 0:
        return 0.0
    years = n_bars / TRADING_DAYS_PER_YEAR
    return (final_equity / initial_capital) ** (1.0 / years) - 1.0


def _compute_percentile_bands(
    all_curves: list[np.ndarray],
    index: pd.DatetimeIndex,
    capital: float,
) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    """Compute equity and drawdown percentile bands across all simulation paths."""
    if not all_curves:
        empty: dict[str, pd.Series] = {
            f"p{p}": pd.Series(dtype=float) for p in PERCENTILES
        }
        return empty, empty

    # Stack all curves into a matrix (n_sims × n_bars)
    n_bars = len(index)
    matrix = np.array([
        c if len(c) == n_bars else np.resize(c, n_bars)
        for c in all_curves
    ])

    equity_pcts: dict[str, pd.Series] = {}
    dd_pcts: dict[str, pd.Series] = {}

    for p in PERCENTILES:
        pct_label = f"p{p}"

        # Equity percentile
        eq_band = np.percentile(matrix, p, axis=0)
        equity_pcts[pct_label] = pd.Series(eq_band, index=index, name=pct_label)

        # Drawdown of the percentile equity curve
        running_max = np.maximum.accumulate(eq_band)
        denom = np.where(running_max != 0, running_max, 1)
        dd_band = (eq_band - running_max) / denom * 100.0  # negative %
        dd_pcts[pct_label] = pd.Series(dd_band, index=index, name=pct_label)

    return equity_pcts, dd_pcts


def _degenerate_result(
    result: BacktestResult, config: SimulationConfig
) -> MCResult:
    """Return a zeroed MCResult when there are no trades to simulate."""
    n = config.n_simulations
    capital = result.initial_capital
    flat = np.full(n, capital)
    empty_pcts: dict[str, pd.Series] = {
        f"p{p}": pd.Series(capital, index=result.equity_curve.index)
        for p in PERCENTILES
    }
    return MCResult(
        method=config.method,
        n_simulations=n,
        equity_percentiles=empty_pcts,
        drawdown_percentiles={
            f"p{p}": pd.Series(0.0, index=result.equity_curve.index)
            for p in PERCENTILES
        },
        cagr_distribution=np.zeros(n),
        final_equity_distribution=flat,
        max_drawdown_distribution=np.zeros(n),
        initial_capital=capital,
    )
