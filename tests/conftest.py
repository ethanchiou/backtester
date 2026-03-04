"""
conftest.py — Shared pytest fixtures for all StrategyLab tests.

All fixtures use deterministic synthetic data so tests are reproducible
without any live market data or network access.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Path to the generated sample CSV
SAMPLE_CSV = Path(__file__).parent.parent / "data" / "csv" / "sample.csv"


# ---------------------------------------------------------------------------
# Price fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def synthetic_close() -> pd.Series:
    """250-bar synthetic close price series (single asset, seed=0)."""
    rng = np.random.default_rng(0)
    n = 250
    log_returns = rng.normal(0.0003, 0.012, n)
    prices = 100.0 * np.exp(np.cumsum(log_returns))
    dates = pd.bdate_range("2020-01-01", periods=n)
    return pd.Series(prices, index=dates, name="SYNTH")


@pytest.fixture(scope="session")
def synthetic_ohlcv(synthetic_close: pd.Series) -> pd.DataFrame:
    """Wide-format DataFrame with MultiIndex columns for a single synthetic asset."""
    rng = np.random.default_rng(1)
    prices = synthetic_close.values
    n = len(prices)

    open_ = np.roll(prices, 1)
    open_[0] = prices[0]
    high = np.maximum(prices, open_) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(prices, open_) * (1 - rng.uniform(0, 0.01, n))
    volume = rng.integers(1_000_000, 10_000_000, n).astype(float)

    idx = pd.MultiIndex.from_tuples(
        [("open", "SYNTH"), ("high", "SYNTH"), ("low", "SYNTH"),
         ("close", "SYNTH"), ("volume", "SYNTH")],
        names=["field", "symbol"],
    )
    data = np.column_stack([open_, high, low, prices, volume])
    df = pd.DataFrame(data, index=synthetic_close.index, columns=idx)
    return df


@pytest.fixture(scope="session")
def sample_csv_path() -> Path:
    """Path to the generated sample CSV (Format B)."""
    return SAMPLE_CSV


# ---------------------------------------------------------------------------
# Equity curve fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def trending_equity() -> pd.Series:
    """Steadily growing equity curve — useful for metrics sanity checks."""
    dates = pd.bdate_range("2020-01-01", periods=252)
    values = np.linspace(100_000, 140_000, 252)
    return pd.Series(values, index=dates, name="equity")


@pytest.fixture(scope="session")
def drawdown_equity() -> pd.Series:
    """Equity curve with a known 20 % drawdown in the middle."""
    dates = pd.bdate_range("2020-01-01", periods=252)
    # Rise to 120k, drop to 96k (20 % drawdown), recover to 130k
    values = (
        list(np.linspace(100_000, 120_000, 84))
        + list(np.linspace(120_000, 96_000, 84))
        + list(np.linspace(96_000, 130_000, 84))
    )
    return pd.Series(values, index=dates, name="equity")
