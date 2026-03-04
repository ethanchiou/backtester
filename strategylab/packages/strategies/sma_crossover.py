"""
sma_crossover.py — Simple Moving Average Crossover strategy.

Signal logic
------------
* Go long  (+1) when the fast SMA crosses **above** the slow SMA.
* Go flat   (0) when the fast SMA crosses **below** the slow SMA.
* Short positions (-1) are not used by default (``allow_short=False``).

This module is an example strategy.  Users are encouraged to copy and
modify it as a starting point for their own strategies.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Strategy metadata — required by the StrategyLab interface
# ---------------------------------------------------------------------------

STRATEGY_META: dict = {
    "name": "SMA_Crossover",
    "version": "1.0",
    "description": (
        "Generates long signals when a fast Simple Moving Average crosses "
        "above a slow Simple Moving Average, and exits when it crosses below."
    ),
    "tags": ["trend", "moving-average", "example"],
}

PARAM_SCHEMA: dict = {
    "fast": 20,        # fast SMA window (bars)
    "slow": 50,        # slow SMA window (bars)
    "allow_short": False,  # if True, use -1 instead of 0 on bearish cross
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
            f"SMA Crossover: 'fast' ({fast}) must be less than 'slow' ({slow})."
        )

    # Use the first column if multiple columns are provided
    price: pd.Series = data.iloc[:, 0] if isinstance(data, pd.DataFrame) else data

    fast_sma = price.rolling(window=fast, min_periods=fast).mean()
    slow_sma = price.rolling(window=slow, min_periods=slow).mean()

    # Raw signal: +1 when fast > slow, else -1
    raw_signal = (fast_sma > slow_sma).astype(int)
    raw_signal = raw_signal.replace(0, -1 if allow_short else 0)

    # Zero out signal before the slow SMA has enough data
    targets = raw_signal.where(slow_sma.notna(), other=0)
    targets.name = "target"
    return targets.astype(int)
