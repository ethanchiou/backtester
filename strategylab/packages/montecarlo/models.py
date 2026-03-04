"""
montecarlo/models.py — Data models for Monte Carlo simulation outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


SimulationMethod = Literal["trade_shuffle", "block_bootstrap", "parameter_uncertainty"]

PERCENTILES = (5, 25, 50, 75, 95)


@dataclass
class SimulationConfig:
    """Configuration for a Monte Carlo simulation run.

    Parameters
    ----------
    method:
        Which MC method to use.
    n_simulations:
        Number of simulation paths to generate.
    seed:
        Random seed for reproducibility.  None = non-deterministic.
    block_size:
        Block length for block bootstrap (method 2 only).
    param_uncertainty_pct:
        For method 3: each parameter is sampled as
        ``param * (1 + N(0, param_uncertainty_pct))``.
    """

    method: SimulationMethod = "trade_shuffle"
    n_simulations: int = 1000
    seed: "int | None" = 42
    block_size: int = 20
    param_uncertainty_pct: float = 0.10


@dataclass
class MCResult:
    """All outputs from a Monte Carlo simulation.

    Percentile keys are strings: "p5", "p25", "p50", "p75", "p95".

    Parameters
    ----------
    method:
        The simulation method used.
    n_simulations:
        Actual number of completed paths.
    equity_percentiles:
        Dict mapping percentile label → equity curve (pd.Series).
    drawdown_percentiles:
        Dict mapping percentile label → drawdown curve (pd.Series).
    cagr_distribution:
        Array of per-simulation CAGR values.
    final_equity_distribution:
        Array of per-simulation final equity values.
    max_drawdown_distribution:
        Array of per-simulation max drawdown values (positive, as %).
    initial_capital:
        Capital used in the base backtest.
    """

    method: SimulationMethod
    n_simulations: int
    equity_percentiles: dict[str, pd.Series]
    drawdown_percentiles: dict[str, pd.Series]
    cagr_distribution: np.ndarray
    final_equity_distribution: np.ndarray
    max_drawdown_distribution: np.ndarray
    initial_capital: float

    def summary(self) -> dict:
        """Return a scalar summary of the MC results (for display/storage)."""
        return {
            "method": self.method,
            "n_simulations": self.n_simulations,
            "median_cagr": float(np.median(self.cagr_distribution)),
            "p5_cagr": float(np.percentile(self.cagr_distribution, 5)),
            "p95_cagr": float(np.percentile(self.cagr_distribution, 95)),
            "median_max_drawdown": float(np.median(self.max_drawdown_distribution)),
            "p95_max_drawdown": float(np.percentile(self.max_drawdown_distribution, 95)),
            "median_final_equity": float(np.median(self.final_equity_distribution)),
            "p5_final_equity": float(np.percentile(self.final_equity_distribution, 5)),
            "p95_final_equity": float(np.percentile(self.final_equity_distribution, 95)),
        }
