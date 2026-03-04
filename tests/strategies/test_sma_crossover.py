"""
test_sma_crossover.py — Tests for the SMA Crossover strategy.
"""

from __future__ import annotations

import pandas as pd
import pytest

from strategylab.packages.strategies.sma_crossover import (
    PARAM_SCHEMA,
    STRATEGY_META,
    generate_targets,
)


def _make_price_df(prices: list[float]) -> pd.DataFrame:
    """Wrap a list of prices into a single-column DataFrame."""
    dates = pd.bdate_range("2020-01-01", periods=len(prices))
    return pd.DataFrame({"SYNTH": prices}, index=dates)


class TestSMACrossoverMeta:
    def test_meta_has_required_keys(self) -> None:
        for key in ("name", "version", "description", "tags"):
            assert key in STRATEGY_META

    def test_param_schema_has_fast_slow(self) -> None:
        assert "fast" in PARAM_SCHEMA
        assert "slow" in PARAM_SCHEMA

    def test_fast_less_than_slow_in_defaults(self) -> None:
        assert PARAM_SCHEMA["fast"] < PARAM_SCHEMA["slow"]


class TestSMACrossoverSignals:

    def test_returns_series(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        assert isinstance(targets, pd.Series)

    def test_output_length_matches_input(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        assert len(targets) == len(df)

    def test_output_index_matches_input(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        pd.testing.assert_index_equal(targets.index, df.index)

    def test_values_in_valid_set(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        assert set(targets.unique()).issubset({-1, 0, 1})

    def test_no_signal_before_slow_period(self, synthetic_close: pd.Series) -> None:
        """All signals before slow window are complete must be 0."""
        df = synthetic_close.to_frame()
        params = {"fast": 5, "slow": 20}
        targets = generate_targets(df, params)
        # First slow-1 bars must be flat (not enough data for slow SMA)
        assert (targets.iloc[: params["slow"] - 1] == 0).all()

    def test_long_signal_when_fast_above_slow(self) -> None:
        """Manually construct data where fast SMA > slow SMA → expect long."""
        # Rising prices: fast SMA will be above slow SMA
        rising = list(range(1, 101))  # 1 to 100
        df = _make_price_df(rising)
        params = {"fast": 5, "slow": 20}
        targets = generate_targets(df, params)
        # After warm-up, all signals should be long (1)
        assert (targets.iloc[params["slow"] :] == 1).all()

    def test_flat_signal_when_fast_below_slow(self) -> None:
        """Falling prices: fast SMA will be below slow SMA → expect 0 (no short)."""
        falling = list(range(100, 0, -1))
        df = _make_price_df(falling)
        params = {"fast": 5, "slow": 20, "allow_short": False}
        targets = generate_targets(df, params)
        # After warm-up falling prices → flat
        assert (targets.iloc[params["slow"] :] == 0).all()

    def test_short_signal_when_allowed(self) -> None:
        """With allow_short=True and falling prices, expect -1 after warm-up."""
        falling = list(range(100, 0, -1))
        df = _make_price_df(falling)
        params = {"fast": 5, "slow": 20, "allow_short": True}
        targets = generate_targets(df, params)
        assert (targets.iloc[params["slow"] :] == -1).all()

    def test_invalid_fast_slow_raises(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        with pytest.raises(ValueError, match="must be less than"):
            generate_targets(df, {"fast": 50, "slow": 20})


class TestSMACrossoverCustomParams:
    def test_custom_fast_slow(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, {"fast": 10, "slow": 30})
        assert len(targets) == len(df)
        assert set(targets.unique()).issubset({-1, 0, 1})
