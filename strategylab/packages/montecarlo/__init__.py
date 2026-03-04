"""
strategylab.montecarlo — Monte Carlo simulation engine.

Public API
----------
run_simulation    run a MC simulation on a BacktestResult
MCResult          result container
SimulationConfig  simulation configuration
"""

from .models import MCResult, SimulationConfig, SimulationMethod
from .simulator import run_simulation

__all__ = [
    "run_simulation",
    "MCResult",
    "SimulationConfig",
    "SimulationMethod",
]
