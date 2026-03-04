"""
test_ema_crossover.py — Tests for the EMA Crossover strategy.
"""

from __future__ import annotations

import pandas as pd
import pytest

from strategylab.packages.strategies.ema_crossover import (
    PARAM_SCHEMA,
    STRATEGY_META,
    generate_targets,
)


def _make_price_df(prices: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(prices))
    return pd.DataFrame({"SYNTH": prices}, index=dates)


class TestEMACrossoverMeta:
    def test_meta_has_required_keys(self) -> None:
        for key in ("name", "version", "description", "tags"):
            assert key in STRATEGY_META

    def test_param_schema_has_fast_slow(self) -> None:
        assert "fast" in PARAM_SCHEMA
        assert "slow" in PARAM_SCHEMA

    def test_fast_less_than_slow_in_defaults(self) -> None:
        assert PARAM_SCHEMA["fast"] < PARAM_SCHEMA["slow"]


class TestEMACrossoverSignals:

    def test_returns_series(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        assert isinstance(targets, pd.Series)

    def test_output_length_matches_input(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        assert len(targets) == len(df)

    def test_values_in_valid_set(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        targets = generate_targets(df, PARAM_SCHEMA)
        assert set(targets.unique()).issubset({-1, 0, 1})

    def test_no_signal_before_slow_period(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        params = {"fast": 5, "slow": 20}
        targets = generate_targets(df, params)
        assert (targets.iloc[: params["slow"] - 1] == 0).all()

    def test_long_on_rising_prices(self) -> None:
        rising = list(range(1, 101))
        df = _make_price_df(rising)
        params = {"fast": 5, "slow": 20}
        targets = generate_targets(df, params)
        assert (targets.iloc[params["slow"] :] == 1).all()

    def test_flat_on_falling_prices(self) -> None:
        falling = list(range(100, 0, -1))
        df = _make_price_df(falling)
        params = {"fast": 5, "slow": 20, "allow_short": False}
        targets = generate_targets(df, params)
        assert (targets.iloc[params["slow"] :] == 0).all()

    def test_short_on_falling_when_allowed(self) -> None:
        falling = list(range(100, 0, -1))
        df = _make_price_df(falling)
        params = {"fast": 5, "slow": 20, "allow_short": True}
        targets = generate_targets(df, params)
        assert (targets.iloc[params["slow"] :] == -1).all()

    def test_invalid_params_raises(self, synthetic_close: pd.Series) -> None:
        df = synthetic_close.to_frame()
        with pytest.raises(ValueError, match="must be less than"):
            generate_targets(df, {"fast": 30, "slow": 10})

    def test_ema_reacts_faster_than_sma(self) -> None:
        """EMA should generate a crossover sooner than SMA on the same data."""
        from strategylab.packages.strategies.sma_crossover import (
            generate_targets as sma_targets,
        )

        # Price rises sharply after a dip
        prices = [100] * 30 + [90] * 10 + [110] * 60
        df = _make_price_df(prices)
        params = {"fast": 5, "slow": 20}

        ema_sig = generate_targets(df, params)
        sma_sig = sma_targets(df, params)

        # Find first long signal after the dip (index > 40)
        ema_first_long = (ema_sig.iloc[40:] == 1).idxmax()
        sma_first_long = (sma_sig.iloc[40:] == 1).idxmax()

        # EMA crossover should occur no later than SMA crossover
        assert ema_first_long <= sma_first_long
