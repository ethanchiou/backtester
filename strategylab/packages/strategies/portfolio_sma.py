"""
portfolio_sma.py — Multi-asset SMA Crossover portfolio strategy.

Returns target weights (not positions) for each symbol.
Each asset independently generates a long/flat signal; the weights
are equal-weighted across bullish assets.

This is an example multi-asset strategy demonstrating the portfolio interface.
"""

from __future__ import annotations

import pandas as pd

STRATEGY_META: dict = {
    "name": "Portfolio_SMA_Crossover",
    "version": "1.0",
    "description": (
        "Equal-weight portfolio SMA crossover.  Each asset independently "
        "goes long when its fast SMA > slow SMA, and exits otherwise."
    ),
    "tags": ["trend", "portfolio", "sma", "example"],
}

PARAM_SCHEMA: dict = {
    "fast": 20,
    "slow": 50,
}


def generate_targets(data: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Return target weight DataFrame indexed by date, columns by symbol.

    Parameters
    ----------
    data:
        DataFrame of close prices — index = dates, columns = symbols.
    params:
        ``fast`` and ``slow`` SMA windows.

    Returns
    -------
    pd.DataFrame
        Float weights per symbol.  Rows sum to ≤ 1.
        Values in ``{0.0, 1/n_active}`` where ``n_active`` is the count
        of assets with a bullish signal.
    """
    fast: int = int(params.get("fast", PARAM_SCHEMA["fast"]))
    slow: int = int(params.get("slow", PARAM_SCHEMA["slow"]))

    if fast >= slow:
        raise ValueError(f"Portfolio SMA: fast ({fast}) must be < slow ({slow}).")

    signals = pd.DataFrame(0.0, index=data.index, columns=data.columns)

    for sym in data.columns:
        price = data[sym].dropna()
        fast_sma = price.rolling(fast, min_periods=fast).mean()
        slow_sma = price.rolling(slow, min_periods=slow).mean()
        signal = (fast_sma > slow_sma).astype(float)
        signal = signal.where(slow_sma.notna(), other=0.0)
        signals[sym] = signal.reindex(data.index, fill_value=0.0)

    # Equal-weight across active assets, capped at 1/n per asset
    n_active = signals.sum(axis=1).replace(0, float("nan"))
    weights = signals.div(n_active, axis=0).fillna(0.0)
    return weights
