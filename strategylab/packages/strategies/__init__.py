"""
strategylab.strategies — Built-in example strategies.

Each strategy module exposes:
    STRATEGY_META  dict
    PARAM_SCHEMA   dict
    generate_targets(data, params) -> pd.Series
"""

from . import ema_crossover, sma_crossover

__all__ = ["sma_crossover", "ema_crossover"]
