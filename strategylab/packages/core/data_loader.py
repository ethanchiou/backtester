"""
data_loader.py — Load and pivot CSV Format B price data.

CSV Format B columns: date, symbol, open, high, low, close, volume

Internally produces wide-format DataFrames indexed by date with a
two-level column MultiIndex: (field, symbol).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

# Required columns in the source CSV
_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"date", "symbol", "open", "high", "low", "close", "volume"}
)

# OHLCV fields that are pivoted into the wide format
OHLCV_FIELDS: tuple[str, ...] = ("open", "high", "low", "close", "volume")


class DataLoaderError(Exception):
    """Raised when data loading or validation fails."""


class DataLoader:
    """Load CSV Format B price data and pivot it into wide-format DataFrames.

    The wide format has:
        - Index:   DatetimeIndex (daily)
        - Columns: MultiIndex (field, symbol) e.g. ("close", "AAPL")

    Parameters
    ----------
    csv_path:
        Path to the CSV file in Format B.
    """

    def __init__(self, csv_path: str | Path) -> None:
        self._path = Path(csv_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        symbols: Sequence[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Load and pivot data.

        Parameters
        ----------
        symbols:
            If provided, only include these ticker symbols.
        start:
            Inclusive start date string (``"YYYY-MM-DD"``). No filter if None.
        end:
            Inclusive end date string (``"YYYY-MM-DD"``). No filter if None.

        Returns
        -------
        pd.DataFrame
            Wide-format DataFrame indexed by date with MultiIndex columns
            ``(field, symbol)``.

        Raises
        ------
        DataLoaderError
            If the file is missing, columns are wrong, or requested symbols
            are absent after filtering.
        """
        raw = self._read_csv()
        raw = self._filter(raw, symbols=symbols, start=start, end=end)
        wide = self._pivot(raw)
        logger.info(
            "Loaded %d rows × %d symbols from '%s'",
            len(wide),
            len(wide.columns.get_level_values("symbol").unique()),
            self._path.name,
        )
        return wide

    def load_close(
        self,
        symbols: Sequence[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Convenience method — return only the ``close`` slice.

        Returns
        -------
        pd.DataFrame
            DataFrame with DatetimeIndex and symbol names as columns.
        """
        wide = self.load(symbols=symbols, start=start, end=end)
        return wide["close"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_csv(self) -> pd.DataFrame:
        """Read the raw CSV into a long-format DataFrame."""
        if not self._path.exists():
            raise DataLoaderError(f"CSV file not found: {self._path}")

        df = pd.read_csv(self._path, parse_dates=["date"])

        missing = _REQUIRED_COLUMNS - set(df.columns.str.lower())
        if missing:
            raise DataLoaderError(
                f"CSV is missing required columns: {sorted(missing)}"
            )

        # Normalise column names to lowercase
        df.columns = df.columns.str.lower()
        df["symbol"] = df["symbol"].str.upper().str.strip()
        df.sort_values(["date", "symbol"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def _filter(
        self,
        df: pd.DataFrame,
        symbols: Sequence[str] | None,
        start: str | None,
        end: str | None,
    ) -> pd.DataFrame:
        """Apply symbol and date-range filters."""
        if symbols is not None:
            requested = {s.upper().strip() for s in symbols}
            available = set(df["symbol"].unique())
            missing = requested - available
            if missing:
                raise DataLoaderError(
                    f"Requested symbols not found in data: {sorted(missing)}. "
                    f"Available: {sorted(available)}"
                )
            df = df[df["symbol"].isin(requested)].copy()

        if start is not None:
            df = df[df["date"] >= pd.Timestamp(start)].copy()

        if end is not None:
            df = df[df["date"] <= pd.Timestamp(end)].copy()

        if df.empty:
            raise DataLoaderError(
                "No data remaining after applying symbol/date filters."
            )

        return df

    def _pivot(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pivot long-format data to wide-format with MultiIndex columns."""
        wide = df.pivot_table(
            index="date",
            columns="symbol",
            values=list(OHLCV_FIELDS),
            aggfunc="last",  # keep last if duplicates exist
        )
        # Reorder MultiIndex level so outer level is field name
        wide.columns.names = ["field", "symbol"]
        wide.index.name = "date"
        wide.sort_index(inplace=True)
        return wide
