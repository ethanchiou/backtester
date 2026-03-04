"""
test_costs.py — Unit tests for the execution cost models.
"""

from __future__ import annotations

import pytest

from strategylab.packages.execution.costs import (
    apply_slippage,
    apply_spread,
    calc_commission,
    calc_fill_price,
)
from strategylab.packages.execution.models import (
    CommissionConfig,
    ExecutionConfig,
    SlippageConfig,
    SpreadConfig,
)


# ---------------------------------------------------------------------------
# Commission
# ---------------------------------------------------------------------------

class TestCalcCommission:

    def test_percent_commission(self) -> None:
        cfg = CommissionConfig(commission_type="percent", value=0.001)
        result = calc_commission(100_000.0, cfg)
        assert abs(result - 100.0) < 1e-9

    def test_fixed_commission(self) -> None:
        cfg = CommissionConfig(commission_type="fixed", value=5.0)
        result = calc_commission(100_000.0, cfg)
        assert result == 5.0

    def test_fixed_commission_independent_of_notional(self) -> None:
        cfg = CommissionConfig(commission_type="fixed", value=5.0)
        assert calc_commission(1_000.0, cfg) == calc_commission(100_000.0, cfg)

    def test_percent_commission_scales_with_notional(self) -> None:
        cfg = CommissionConfig(commission_type="percent", value=0.001)
        small = calc_commission(10_000.0, cfg)
        large = calc_commission(100_000.0, cfg)
        assert abs(large / small - 10.0) < 1e-9

    def test_min_commission_floor(self) -> None:
        cfg = CommissionConfig(
            commission_type="percent", value=0.00001, min_commission=5.0
        )
        # Tiny notional → raw commission below floor
        result = calc_commission(100.0, cfg)
        assert result == 5.0

    def test_zero_commission(self) -> None:
        cfg = CommissionConfig(commission_type="percent", value=0.0)
        assert calc_commission(100_000.0, cfg) == 0.0

    def test_commission_non_negative(self) -> None:
        cfg = CommissionConfig(commission_type="percent", value=0.001)
        assert calc_commission(50_000.0, cfg) >= 0.0


# ---------------------------------------------------------------------------
# Spread
# ---------------------------------------------------------------------------

class TestApplySpread:

    def test_buy_pays_more(self) -> None:
        cfg = SpreadConfig(bps=10.0)
        adjusted = apply_spread(100.0, direction=1, config=cfg)
        assert adjusted > 100.0

    def test_sell_receives_less(self) -> None:
        cfg = SpreadConfig(bps=10.0)
        adjusted = apply_spread(100.0, direction=-1, config=cfg)
        assert adjusted < 100.0

    def test_spread_magnitude(self) -> None:
        """10 bps spread on $100 → $0.10 adjustment."""
        cfg = SpreadConfig(bps=10.0)
        buy_price = apply_spread(100.0, direction=1, config=cfg)
        assert abs(buy_price - 100.10) < 1e-9

    def test_zero_spread_no_change(self) -> None:
        cfg = SpreadConfig(bps=0.0)
        assert apply_spread(100.0, 1, cfg) == 100.0
        assert apply_spread(100.0, -1, cfg) == 100.0

    def test_buy_sell_symmetric(self) -> None:
        cfg = SpreadConfig(bps=5.0)
        buy = apply_spread(100.0, 1, cfg)
        sell = apply_spread(100.0, -1, cfg)
        assert abs((buy - 100.0) - (100.0 - sell)) < 1e-9


# ---------------------------------------------------------------------------
# Slippage
# ---------------------------------------------------------------------------

class TestApplySlippage:

    def test_buy_pays_more(self) -> None:
        cfg = SlippageConfig(bps=5.0)
        assert apply_slippage(100.0, 1, cfg) > 100.0

    def test_sell_receives_less(self) -> None:
        cfg = SlippageConfig(bps=5.0)
        assert apply_slippage(100.0, -1, cfg) < 100.0

    def test_slippage_magnitude(self) -> None:
        """5 bps slippage on $200 → $0.10 adjustment."""
        cfg = SlippageConfig(bps=5.0)
        adjusted = apply_slippage(200.0, 1, cfg)
        assert abs(adjusted - 200.10) < 1e-9

    def test_zero_slippage_no_change(self) -> None:
        cfg = SlippageConfig(bps=0.0)
        assert apply_slippage(100.0, 1, cfg) == 100.0


# ---------------------------------------------------------------------------
# Combined fill price
# ---------------------------------------------------------------------------

class TestCalcFillPrice:

    def test_buy_worse_than_raw(self) -> None:
        spread = SpreadConfig(bps=5.0)
        slip = SlippageConfig(bps=5.0)
        fill = calc_fill_price(100.0, 1, spread, slip)
        assert fill > 100.0

    def test_sell_worse_than_raw(self) -> None:
        spread = SpreadConfig(bps=5.0)
        slip = SlippageConfig(bps=5.0)
        fill = calc_fill_price(100.0, -1, spread, slip)
        assert fill < 100.0

    def test_zero_cost_equals_raw(self) -> None:
        spread = SpreadConfig(bps=0.0)
        slip = SlippageConfig(bps=0.0)
        assert calc_fill_price(100.0, 1, spread, slip) == 100.0
        assert calc_fill_price(100.0, -1, spread, slip) == 100.0

    def test_combined_worse_than_individual(self) -> None:
        """Combined spread+slip should be worse than spread alone."""
        spread = SpreadConfig(bps=5.0)
        slip_zero = SlippageConfig(bps=0.0)
        slip_non = SlippageConfig(bps=5.0)
        no_slip = calc_fill_price(100.0, 1, spread, slip_zero)
        with_slip = calc_fill_price(100.0, 1, spread, slip_non)
        assert with_slip > no_slip


# ---------------------------------------------------------------------------
# ExecutionConfig presets
# ---------------------------------------------------------------------------

class TestExecutionConfigPresets:

    def test_zero_cost_all_zero(self) -> None:
        cfg = ExecutionConfig.zero_cost()
        assert cfg.commission.value == 0.0
        assert cfg.spread.bps == 0.0
        assert cfg.slippage.bps == 0.0

    def test_realistic_non_zero(self) -> None:
        cfg = ExecutionConfig.realistic()
        assert cfg.commission.value > 0.0
        assert cfg.spread.bps > 0.0
        assert cfg.slippage.bps > 0.0

    def test_default_creates_all_sub_configs(self) -> None:
        cfg = ExecutionConfig()
        assert cfg.commission is not None
        assert cfg.spread is not None
        assert cfg.slippage is not None
