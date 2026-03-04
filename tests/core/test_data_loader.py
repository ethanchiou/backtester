"""
test_data_loader.py — Unit tests for DataLoader.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from strategylab.packages.core.data_loader import DataLoader, DataLoaderError


class TestDataLoaderLoad:
    """Tests for DataLoader.load() with the sample CSV."""

    def test_load_returns_dataframe(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load()
        assert isinstance(result, pd.DataFrame)

    def test_load_has_multiindex_columns(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load()
        assert isinstance(result.columns, pd.MultiIndex)
        assert result.columns.names == ["field", "symbol"]

    def test_load_contains_expected_fields(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load()
        fields = result.columns.get_level_values("field").unique().tolist()
        for expected in ["open", "high", "low", "close", "volume"]:
            assert expected in fields

    def test_load_contains_expected_symbols(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load()
        symbols = result.columns.get_level_values("symbol").unique().tolist()
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_load_index_is_datetime(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load()
        assert isinstance(result.index, pd.DatetimeIndex)
        assert result.index.name == "date"

    def test_load_is_sorted_by_date(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load()
        assert result.index.is_monotonic_increasing

    def test_symbol_filter(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load(symbols=["AAPL"])
        symbols = result.columns.get_level_values("symbol").unique().tolist()
        assert symbols == ["AAPL"]

    def test_date_range_filter_start(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load(start="2021-01-01")
        assert result.index.min() >= pd.Timestamp("2021-01-01")

    def test_date_range_filter_end(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load(end="2021-12-31")
        assert result.index.max() <= pd.Timestamp("2021-12-31")

    def test_date_range_filter_both(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load(start="2021-01-01", end="2021-12-31")
        assert result.index.min() >= pd.Timestamp("2021-01-01")
        assert result.index.max() <= pd.Timestamp("2021-12-31")

    def test_load_close_returns_simple_df(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load_close(symbols=["AAPL"])
        assert isinstance(result, pd.DataFrame)
        assert not isinstance(result.columns, pd.MultiIndex)
        assert "AAPL" in result.columns

    def test_no_missing_values_in_close(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        result = loader.load_close()
        assert not result.isnull().any().any()


class TestDataLoaderErrors:
    """Tests for error handling in DataLoader."""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        loader = DataLoader(tmp_path / "nonexistent.csv")
        with pytest.raises(DataLoaderError, match="not found"):
            loader.load()

    def test_missing_columns_raises(self, tmp_path: Path) -> None:
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("date,symbol,close\n2020-01-01,AAPL,100\n")
        loader = DataLoader(bad_csv)
        with pytest.raises(DataLoaderError, match="missing required columns"):
            loader.load()

    def test_unknown_symbol_raises(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        with pytest.raises(DataLoaderError, match="not found"):
            loader.load(symbols=["XYZZY"])

    def test_empty_after_filter_raises(self, sample_csv_path: Path) -> None:
        loader = DataLoader(sample_csv_path)
        with pytest.raises(DataLoaderError, match="No data remaining"):
            loader.load(start="2099-01-01")
