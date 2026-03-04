"""
generate_sample_data.py — Create deterministic synthetic price data for testing.

Generates a CSV in Format B (date, symbol, open, high, low, close, volume)
for two synthetic assets: AAPL and MSFT.

Usage
-----
    python data/generate_sample_data.py

Output
------
    data/csv/sample.csv
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

# Reproducibility seed — never change this so test data stays consistent
SEED: int = 42

START_DATE: str = "2019-01-01"
END_DATE: str = "2023-12-31"

ASSETS: dict[str, dict] = {
    "AAPL": {"start_price": 150.0, "annual_vol": 0.30, "annual_drift": 0.15},
    "MSFT": {"start_price": 100.0, "annual_vol": 0.25, "annual_drift": 0.12},
}


def generate_ohlcv(
    start_price: float,
    annual_vol: float,
    annual_drift: float,
    n_days: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Simulate daily OHLCV for a single asset using geometric Brownian motion."""
    daily_vol = annual_vol / (252**0.5)
    daily_drift = annual_drift / 252

    # Daily close returns
    log_returns = rng.normal(
        loc=daily_drift - 0.5 * daily_vol**2,
        scale=daily_vol,
        size=n_days,
    )
    close = start_price * np.exp(np.cumsum(log_returns))

    # Simulate open, high, low from close
    open_ = np.roll(close, 1)
    open_[0] = start_price

    intraday_range = np.abs(rng.normal(0, daily_vol, n_days)) * close
    high = np.maximum(close, open_) + intraday_range * rng.uniform(0.1, 0.5, n_days)
    low = np.minimum(close, open_) - intraday_range * rng.uniform(0.1, 0.5, n_days)
    low = np.maximum(low, close * 0.5)  # floor at 50 % of close

    volume = rng.integers(5_000_000, 30_000_000, n_days).astype(float)

    return pd.DataFrame(
        {
            "open": np.round(open_, 2),
            "high": np.round(high, 2),
            "low": np.round(low, 2),
            "close": np.round(close, 2),
            "volume": volume,
        }
    )


def main() -> None:
    rng = np.random.default_rng(SEED)

    dates = pd.bdate_range(start=START_DATE, end=END_DATE)  # business days only
    n_days = len(dates)

    rows: list[pd.DataFrame] = []
    for symbol, cfg in ASSETS.items():
        ohlcv = generate_ohlcv(
            start_price=cfg["start_price"],
            annual_vol=cfg["annual_vol"],
            annual_drift=cfg["annual_drift"],
            n_days=n_days,
            rng=rng,
        )
        ohlcv.insert(0, "date", dates.date)
        ohlcv.insert(1, "symbol", symbol)
        rows.append(ohlcv)

    df = pd.concat(rows, ignore_index=True)
    df.sort_values(["date", "symbol"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    out_path = Path(__file__).parent / "csv" / "sample.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(f"  Date range: {df['date'].min()} → {df['date'].max()}")
    print(f"  Symbols: {sorted(df['symbol'].unique())}")


if __name__ == "__main__":
    main()
