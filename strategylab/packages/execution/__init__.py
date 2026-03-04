"""
strategylab.execution — Execution cost models.

Public API
----------
ExecutionConfig   unified cost configuration
CommissionConfig  commission model
SpreadConfig      bid-ask spread model
SlippageConfig    slippage model
calc_commission   compute commission on a trade
apply_spread      adjust fill price for spread
apply_slippage    adjust fill price for slippage
calc_fill_price   apply spread + slippage in one call
"""

from .costs import apply_slippage, apply_spread, calc_commission, calc_fill_price
from .models import (
    CommissionConfig,
    ExecutionConfig,
    SlippageConfig,
    SpreadConfig,
)

__all__ = [
    "ExecutionConfig",
    "CommissionConfig",
    "SpreadConfig",
    "SlippageConfig",
    "calc_commission",
    "apply_spread",
    "apply_slippage",
    "calc_fill_price",
]
