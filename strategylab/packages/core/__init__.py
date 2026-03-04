"""
strategylab.core — Backtesting engine (single-asset and portfolio).

Public API
----------
DataLoader       load CSV Format B price data
BacktestEngine   single-asset backtesting engine
PortfolioEngine  multi-asset portfolio backtesting engine
BacktestResult   unified output container
ExecutionConfig  cost model configuration (from execution package)
Trade            single trade record
"""

from strategylab.packages.execution.models import ExecutionConfig

from .data_loader import DataLoader, DataLoaderError
from .engine import BacktestEngine
from .models import BacktestResult, Trade
from .portfolio_engine import PortfolioEngine

__all__ = [
    "DataLoader",
    "DataLoaderError",
    "BacktestEngine",
    "PortfolioEngine",
    "BacktestResult",
    "ExecutionConfig",
    "Trade",
]
