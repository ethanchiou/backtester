"""
api/schemas.py — Pydantic request/response models for the FastAPI service.

All public API shapes are defined here. No SQLAlchemy models are exposed
directly — they are converted to these Pydantic schemas at the boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Strategy schemas
# ---------------------------------------------------------------------------

class StrategyBase(BaseModel):
    name: str
    version: str = "1.0"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    module_path: str = ""


class StrategyCreate(StrategyBase):
    """Request body for POST /strategies."""


class StrategyResponse(StrategyBase):
    """Response for GET /strategies and POST /strategies."""

    id: int
    favorite: bool
    created_at: str

    model_config = {"from_attributes": True}


class FavoriteToggleResponse(BaseModel):
    id: int
    favorite: bool


# ---------------------------------------------------------------------------
# Run schemas
# ---------------------------------------------------------------------------

class ExecutionSettingsSchema(BaseModel):
    commission_type: Literal["fixed", "percent"] = "percent"
    commission_value: float = 0.001
    spread_bps: float = 1.0
    slippage_bps: float = 1.0


class RunRequest(BaseModel):
    """Request body for POST /run."""

    strategy_name: str = Field(
        description="Name matching STRATEGY_META['name'] in a strategy module."
    )
    symbols: list[str] = Field(
        min_length=1,
        description="One or more ticker symbols present in the CSV data.",
    )
    start_date: str = Field(description="YYYY-MM-DD inclusive start date.")
    end_date: str = Field(description="YYYY-MM-DD inclusive end date.")
    params: dict[str, Any] = Field(default_factory=dict)
    mode: Literal["single", "portfolio"] = "single"
    initial_capital: float = Field(default=100_000.0, gt=0)
    execution_settings: ExecutionSettingsSchema = Field(
        default_factory=ExecutionSettingsSchema
    )
    csv_path: str = Field(
        default="data/csv/sample.csv",
        description="Path to input CSV file (relative to repo root).",
    )
    save: bool = Field(
        default=True,
        description="If True, persist this run to the database.",
    )
    strategy_id: Optional[int] = Field(
        default=None,
        description="Optional ID of a saved strategy to link this run to.",
    )


class MetricsSummary(BaseModel):
    """Scalar metrics returned inline with a run response."""

    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    net_pnl: float
    total_return_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    volatility_annual: float


class RunResponse(BaseModel):
    """Response for POST /run."""

    run_id: str
    strategy_name: str
    symbols: list[str]
    mode: str
    metrics_summary: MetricsSummary


class RunMetadataResponse(BaseModel):
    """Response for GET /runs/{id}."""

    run_id: str
    strategy_id: Optional[int]
    parameters: dict
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    symbols: list[str]
    mode: str
    created_at: str


class MetricsResponse(BaseModel):
    """Response for GET /runs/{id}/metrics."""

    run_id: str
    metrics: dict[str, Any]


class EquityPoint(BaseModel):
    date: str
    value: float


class EquityResponse(BaseModel):
    """Response for GET /runs/{id}/equity."""

    run_id: str
    equity: list[EquityPoint]


# ---------------------------------------------------------------------------
# Monte Carlo schemas
# ---------------------------------------------------------------------------

class MCRequest(BaseModel):
    """Request body for POST /runs/{id}/montecarlo."""

    method: Literal["trade_shuffle", "block_bootstrap", "parameter_uncertainty"] = (
        "trade_shuffle"
    )
    n_simulations: int = Field(default=500, ge=10, le=5000)
    seed: Optional[int] = 42
    block_size: int = Field(default=20, ge=5)
    param_uncertainty_pct: float = Field(default=0.10, ge=0.0, le=1.0)


class MCBand(BaseModel):
    label: str                # "p5", "p25", etc.
    equity: list[EquityPoint]


class MCResponse(BaseModel):
    """Response for GET /runs/{id}/montecarlo."""

    run_id: str
    method: str
    n_simulations: int
    percentile_bands: list[MCBand]
    summary: dict[str, Any]
