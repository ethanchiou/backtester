"""
api/runner.py — Orchestration layer between API and quant engine.

This module translates API requests into engine calls and returns
structured results. It does NOT touch the database — callers handle
persistence.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pandas as pd

from strategylab.packages.core.data_loader import DataLoader
from strategylab.packages.core.engine import BacktestEngine
from strategylab.packages.core.models import BacktestResult
from strategylab.packages.core.portfolio_engine import PortfolioEngine
from strategylab.packages.execution.models import (
    CommissionConfig,
    ExecutionConfig,
    SlippageConfig,
    SpreadConfig,
)
from strategylab.packages.metrics.calculator import MetricsResult, compute_metrics
from strategylab.packages.montecarlo.models import SimulationConfig
from strategylab.packages.montecarlo.simulator import run_simulation

from .schemas import ExecutionSettingsSchema, MCRequest, RunRequest

logger = logging.getLogger(__name__)

# Registry: strategy name → module path
_STRATEGY_REGISTRY: dict[str, str] = {
    "SMA_Crossover": "strategylab.packages.strategies.sma_crossover",
    "EMA_Crossover": "strategylab.packages.strategies.ema_crossover",
    "Portfolio_SMA_Crossover": "strategylab.packages.strategies.portfolio_sma",
}

# Root path for resolving CSV files
_REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _load_strategy(name: str):
    """Import and return a strategy module by name."""
    module_path = _STRATEGY_REGISTRY.get(name)
    if module_path is None:
        raise ValueError(
            f"Unknown strategy: {name!r}. "
            f"Available: {sorted(_STRATEGY_REGISTRY)}"
        )
    return importlib.import_module(module_path)


def _build_execution_config(settings: ExecutionSettingsSchema) -> ExecutionConfig:
    return ExecutionConfig(
        commission=CommissionConfig(
            commission_type=settings.commission_type,
            value=settings.commission_value,
        ),
        spread=SpreadConfig(bps=settings.spread_bps),
        slippage=SlippageConfig(bps=settings.slippage_bps),
    )


def execute_run(request: RunRequest) -> tuple[BacktestResult, MetricsResult]:
    """Run a backtest for the given request and return result + metrics.

    Parameters
    ----------
    request:
        Validated RunRequest from the API.

    Returns
    -------
    tuple[BacktestResult, MetricsResult]
    """
    strategy_module = _load_strategy(request.strategy_name)
    exec_cfg = _build_execution_config(request.execution_settings)

    csv_path = _REPO_ROOT / request.csv_path
    loader = DataLoader(csv_path)
    data = loader.load(
        symbols=request.symbols,
        start=request.start_date,
        end=request.end_date,
    )

    if request.mode == "single":
        if len(request.symbols) != 1:
            raise ValueError(
                "Single-asset mode requires exactly one symbol."
            )
        engine = BacktestEngine(
            initial_capital=request.initial_capital,
            execution_config=exec_cfg,
        )
        result = engine.run(
            data=data,
            generate_targets=strategy_module.generate_targets,
            params=request.params or strategy_module.PARAM_SCHEMA,
            symbol=request.symbols[0],
            strategy_name=request.strategy_name,
        )
    else:
        engine_p = PortfolioEngine(
            initial_capital=request.initial_capital,
            execution_config=exec_cfg,
        )
        result = engine_p.run(
            data=data,
            generate_targets=strategy_module.generate_targets,
            params=request.params or strategy_module.PARAM_SCHEMA,
            symbols=request.symbols,
            strategy_name=request.strategy_name,
        )

    metrics = compute_metrics(
        equity=result.equity_curve,
        trades=result.trade_log,
        initial_capital=request.initial_capital,
    )

    return result, metrics


def execute_montecarlo(
    result: BacktestResult,
    mc_request: MCRequest,
) -> dict:
    """Run Monte Carlo on a BacktestResult and return serialisable output."""
    config = SimulationConfig(
        method=mc_request.method,
        n_simulations=mc_request.n_simulations,
        seed=mc_request.seed,
        block_size=mc_request.block_size,
        param_uncertainty_pct=mc_request.param_uncertainty_pct,
    )

    mc_result = run_simulation(result, config)
    return mc_result
