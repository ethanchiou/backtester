"""
ema_crossover.py — Exponential Moving Average Crossover strategy.

Signal logic
------------
* Go long  (+1) when the fast EMA crosses **above** the slow EMA.
* Go flat   (0) when the fast EMA crosses **below** the slow EMA.
* Short positions (-1) are optionally enabled via ``allow_short=True``.

EMA reacts faster to recent price changes than SMA, making this strategy
more responsive to trend shifts.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Strategy metadata — required by the StrategyLab interface
# ---------------------------------------------------------------------------

STRATEGY_META: dict = {
    "name": "EMA_Crossover",
    "version": "1.0",
    "description": (
        "Generates long signals when a fast Exponential Moving Average crosses "
        "above a slow EMA, and exits when it crosses below.  More responsive "
        "to recent price action than SMA."
    ),
    "tags": ["trend", "moving-average", "ema", "example"],
}

PARAM_SCHEMA: dict = {
    "fast": 12,        # fast EMA window (bars)
    "slow": 26,        # slow EMA window (bars)
    "allow_short": False,
}


# ---------------------------------------------------------------------------
# Strategy function — required by the StrategyLab interface
# ---------------------------------------------------------------------------

def generate_targets(data: pd.DataFrame, params: dict) -> pd.Series:
    """Generate target position signals.

    Parameters
    ----------
    data:
        DataFrame with a price column.  If multi-column, the first column
        is used (expected to be close prices for the traded symbol).
    params:
        Dictionary with keys ``fast``, ``slow``, and optionally
        ``allow_short``.

    Returns
    -------
    pd.Series
        Integer series with values ``{-1, 0, 1}`` indexed by date.
        ``+1`` = long, ``0`` = flat, ``-1`` = short.
    """
    fast: int = int(params.get("fast", PARAM_SCHEMA["fast"]))
    slow: int = int(params.get("slow", PARAM_SCHEMA["slow"]))
    allow_short: bool = bool(params.get("allow_short", PARAM_SCHEMA["allow_short"]))

    if fast >= slow:
        raise ValueError(
            f"EMA Crossover: 'fast' ({fast}) must be less than 'slow' ({slow})."
        )

    # Use the first column if multiple columns are provided
    price: pd.Series = data.iloc[:, 0] if isinstance(data, pd.DataFrame) else data

    # EMA: adjust=False gives the standard recursive EMA formula
    fast_ema = price.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_ema = price.ewm(span=slow, adjust=False, min_periods=slow).mean()

    # Raw signal: +1 when fast > slow
    raw_signal = (fast_ema > slow_ema).astype(int)
    raw_signal = raw_signal.replace(0, -1 if allow_short else 0)

    # Zero out signal before the slow EMA has enough data
    targets = raw_signal.where(slow_ema.notna(), other=0)
    targets.name = "target"
    return targets.astype(int)
