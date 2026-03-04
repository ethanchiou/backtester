"""
execution/models.py — Pluggable execution cost models.

All models are pure functions / lightweight classes with no side effects.
They are consumed by the BacktestEngine at fill time.

Execution assumption (enforced by the engine, not here):
    Trades always fill at the NEXT BAR OPEN price.

Cost application order:
    fill_price → spread adjustment → slippage adjustment → commission
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class CommissionConfig:
    """Commission model configuration.

    Parameters
    ----------
    commission_type:
        ``"fixed"``   — flat fee per trade, in currency units.
        ``"percent"`` — fraction of trade notional (e.g. 0.001 = 0.10 %).
    value:
        Magnitude of the commission (meaning depends on ``commission_type``).
    min_commission:
        Floor applied after calculation (useful for fixed brokers with
        per-ticket minimums).  Set to 0.0 to disable.
    """

    commission_type: Literal["fixed", "percent"] = "percent"
    value: float = 0.001          # 0.10 % per trade
    min_commission: float = 0.0


@dataclass
class SpreadConfig:
    """Bid-ask spread cost configuration.

    The spread is applied as a symmetric cost: half a tick lost on entry
    and half on exit.  For simplicity we apply the full ``bps`` value
    to every fill (one-way).

    Parameters
    ----------
    bps:
        Half-spread in basis points (one-way cost per fill).
        1 bp = 0.01 %.
    """

    bps: float = 1.0   # 1 bp one-way


@dataclass
class SlippageConfig:
    """Market slippage model configuration.

    Models execution imprecision: the fill price is worse than the quoted
    open by ``bps`` basis points.  Direction-aware: longs pay more, shorts
    receive less.

    Parameters
    ----------
    bps:
        Slippage in basis points per fill (one-way).
    """

    bps: float = 1.0   # 1 bp one-way


@dataclass
class ExecutionConfig:
    """Unified execution cost configuration passed to the BacktestEngine.

    All three sub-configs default to minimal but non-zero realistic values.
    """

    commission: CommissionConfig = None          # type: ignore[assignment]
    spread: SpreadConfig = None                  # type: ignore[assignment]
    slippage: SlippageConfig = None              # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.commission is None:
            self.commission = CommissionConfig()
        if self.spread is None:
            self.spread = SpreadConfig()
        if self.slippage is None:
            self.slippage = SlippageConfig()

    @classmethod
    def zero_cost(cls) -> "ExecutionConfig":
        """Return a config with all costs set to zero (for testing)."""
        return cls(
            commission=CommissionConfig(value=0.0, min_commission=0.0),
            spread=SpreadConfig(bps=0.0),
            slippage=SlippageConfig(bps=0.0),
        )

    @classmethod
    def realistic(cls) -> "ExecutionConfig":
        """Return a config approximating a retail brokerage (e.g. IB).

        ~0.05 % commission, 1 bp spread, 1 bp slippage.
        """
        return cls(
            commission=CommissionConfig(commission_type="percent", value=0.0005),
            spread=SpreadConfig(bps=1.0),
            slippage=SlippageConfig(bps=1.0),
        )
