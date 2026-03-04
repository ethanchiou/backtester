"""
execution/costs.py — Cost calculation functions.

Each function is a pure, side-effect-free calculation.  The BacktestEngine
calls these at fill time.
"""

from __future__ import annotations

from .models import CommissionConfig, SlippageConfig, SpreadConfig


# ---------------------------------------------------------------------------
# Commission
# ---------------------------------------------------------------------------

def calc_commission(notional: float, config: CommissionConfig) -> float:
    """Calculate the commission charged on a trade.

    Parameters
    ----------
    notional:
        Absolute trade value in currency units (shares × fill_price).
    config:
        Commission model configuration.

    Returns
    -------
    float
        Commission amount in currency units (always >= 0).
    """
    if config.commission_type == "percent":
        raw = notional * config.value
    else:
        raw = config.value  # fixed per trade

    return max(raw, config.min_commission)


# ---------------------------------------------------------------------------
# Spread
# ---------------------------------------------------------------------------

def apply_spread(price: float, direction: int, config: SpreadConfig) -> float:
    """Adjust a fill price for the bid-ask spread.

    Long  entries and short covers pay the ask (price + adjustment).
    Short entries and long  exits   get the bid (price - adjustment).

    Parameters
    ----------
    price:
        The raw fill price (typically next-bar open).
    direction:
        ``+1`` for a buy (long entry / short cover).
        ``-1`` for a sell (long exit / short entry).
    config:
        Spread model configuration.

    Returns
    -------
    float
        Spread-adjusted fill price.
    """
    adjustment = price * config.bps / 10_000.0
    return price + adjustment if direction == 1 else price - adjustment


# ---------------------------------------------------------------------------
# Slippage
# ---------------------------------------------------------------------------

def apply_slippage(price: float, direction: int, config: SlippageConfig) -> float:
    """Adjust a fill price for execution slippage.

    Slippage always moves the fill price against the trader:
    longs pay more, shorts receive less.

    Parameters
    ----------
    price:
        The spread-adjusted fill price.
    direction:
        ``+1`` for a buy, ``-1`` for a sell.
    config:
        Slippage model configuration.

    Returns
    -------
    float
        Slippage-adjusted fill price.
    """
    adjustment = price * config.bps / 10_000.0
    return price + adjustment if direction == 1 else price - adjustment


# ---------------------------------------------------------------------------
# Combined fill price
# ---------------------------------------------------------------------------

def calc_fill_price(
    raw_price: float,
    direction: int,
    spread_config: SpreadConfig,
    slippage_config: SlippageConfig,
) -> float:
    """Apply spread and slippage to a raw fill price.

    Parameters
    ----------
    raw_price:
        The unmodified next-bar open price.
    direction:
        ``+1`` for buy, ``-1`` for sell.
    spread_config:
        Spread model configuration.
    slippage_config:
        Slippage model configuration.

    Returns
    -------
    float
        Effective fill price after spread and slippage.
    """
    price = apply_spread(raw_price, direction, spread_config)
    price = apply_slippage(price, direction, slippage_config)
    return price
