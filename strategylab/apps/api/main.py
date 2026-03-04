"""
api/main.py — FastAPI application entry point.

Run with:
    uvicorn strategylab.apps.api.main:app --reload
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from strategylab.packages.db import repository as repo

from .dependencies import get_db
from .runner import execute_montecarlo, execute_run
from .schemas import (
    EquityPoint,
    EquityResponse,
    FavoriteToggleResponse,
    MCBand,
    MCRequest,
    MCResponse,
    MetricsResponse,
    MetricsSummary,
    RunMetadataResponse,
    RunRequest,
    RunResponse,
    StrategyCreate,
    StrategyResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="StrategyLab API",
    description="Quantitative trading strategy backtesting and analysis platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Strategy endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/strategies",
    response_model=list[StrategyResponse],
    summary="List all saved strategies",
    tags=["strategies"],
)
def list_strategies(
    favorites_only: bool = False,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[StrategyResponse]:
    """Return all saved strategies, optionally filtered by favorite or tag."""
    strategies = repo.list_strategies(db, favorites_only=favorites_only, tag=tag)
    return [
        StrategyResponse(
            id=s.id,
            name=s.name,
            version=s.version,
            description=s.description or "",
            tags=s.tags_list(),
            module_path=s.module_path or "",
            favorite=s.favorite,
            created_at=str(s.created_at),
        )
        for s in strategies
    ]


@app.post(
    "/strategies",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new strategy",
    tags=["strategies"],
)
def create_strategy(
    body: StrategyCreate,
    db: Session = Depends(get_db),
) -> StrategyResponse:
    """Register a new strategy in the library."""
    s = repo.create_strategy(
        db,
        name=body.name,
        version=body.version,
        description=body.description,
        tags=body.tags,
        module_path=body.module_path,
    )
    return StrategyResponse(
        id=s.id,
        name=s.name,
        version=s.version,
        description=s.description or "",
        tags=s.tags_list(),
        module_path=s.module_path or "",
        favorite=s.favorite,
        created_at=str(s.created_at),
    )


@app.patch(
    "/strategies/{strategy_id}/favorite",
    response_model=FavoriteToggleResponse,
    summary="Toggle favorite flag on a strategy",
    tags=["strategies"],
)
def toggle_favorite(
    strategy_id: int,
    db: Session = Depends(get_db),
) -> FavoriteToggleResponse:
    """Flip the favorite flag for a strategy."""
    try:
        s = repo.toggle_favorite(db, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FavoriteToggleResponse(id=s.id, favorite=s.favorite)


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/run",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a backtest",
    tags=["runs"],
)
def run_backtest(
    body: RunRequest,
    db: Session = Depends(get_db),
) -> RunResponse:
    """Run a backtest for the given strategy and parameters."""
    try:
        result, metrics = execute_run(body)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    metrics_dict = {
        "cagr": metrics.cagr,
        "sharpe_ratio": metrics.sharpe_ratio,
        "sortino_ratio": metrics.sortino_ratio,
        "calmar_ratio": metrics.calmar_ratio,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "net_pnl": metrics.net_pnl,
        "total_return_pct": metrics.total_return_pct,
        "win_rate": metrics.win_rate,
        "profit_factor": metrics.profit_factor,
        "total_trades": metrics.total_trades,
        "volatility_annual": metrics.volatility_annual,
        "avg_holding_bars": metrics.avg_holding_bars,
        "largest_win": metrics.largest_win,
        "largest_loss": metrics.largest_loss,
        "max_consecutive_wins": metrics.max_consecutive_wins,
        "max_consecutive_losses": metrics.max_consecutive_losses,
        "exposure": metrics.exposure,
    }

    run_record = None
    if body.save:
        run_record = repo.save_run(
            session=db,
            strategy_id=body.strategy_id,
            parameters=body.params,
            date_range_start=body.start_date,
            date_range_end=body.end_date,
            symbols=body.symbols,
            mode=body.mode,
            execution_settings={
                "commission_type": body.execution_settings.commission_type,
                "commission_value": body.execution_settings.commission_value,
                "spread_bps": body.execution_settings.spread_bps,
                "slippage_bps": body.execution_settings.slippage_bps,
            },
            metrics=metrics_dict,
            equity_curve=result.equity_curve,
        )

    run_id = run_record.run_id if run_record else "unsaved"

    return RunResponse(
        run_id=run_id,
        strategy_name=result.strategy_name,
        symbols=body.symbols,
        mode=body.mode,
        metrics_summary=MetricsSummary(**{k: metrics_dict[k] for k in MetricsSummary.model_fields}),
    )


@app.get(
    "/runs/{run_id}",
    response_model=RunMetadataResponse,
    summary="Get run metadata",
    tags=["runs"],
)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunMetadataResponse:
    """Fetch metadata for a completed run by its UUID."""
    run = repo.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    return RunMetadataResponse(
        run_id=run.run_id,
        strategy_id=run.strategy_id,
        parameters=run.get_parameters(),
        date_range_start=run.date_range_start,
        date_range_end=run.date_range_end,
        symbols=run.get_symbols(),
        mode=run.mode,
        created_at=str(run.created_at),
    )


@app.get(
    "/runs/{run_id}/metrics",
    response_model=MetricsResponse,
    summary="Get computed metrics for a run",
    tags=["runs"],
)
def get_metrics(run_id: str, db: Session = Depends(get_db)) -> MetricsResponse:
    """Return all computed performance metrics for a run."""
    run = repo.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    return MetricsResponse(run_id=run.run_id, metrics=run.get_metrics())


@app.get(
    "/runs/{run_id}/equity",
    response_model=EquityResponse,
    summary="Get equity curve for a run",
    tags=["runs"],
)
def get_equity(run_id: str, db: Session = Depends(get_db)) -> EquityResponse:
    """Return the equity curve (date, value) series for a run."""
    run = repo.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    equity_dict = run.get_equity()
    equity_points = [
        EquityPoint(date=date, value=value) for date, value in equity_dict.items()
    ]
    return EquityResponse(run_id=run.run_id, equity=equity_points)


@app.post(
    "/runs/{run_id}/montecarlo",
    response_model=MCResponse,
    summary="Run Monte Carlo simulation on a completed run",
    tags=["runs"],
)
def run_montecarlo(
    run_id: str,
    body: MCRequest,
    db: Session = Depends(get_db),
) -> MCResponse:
    """Execute a Monte Carlo simulation on the trade history of a run."""
    run = repo.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")

    # Reconstruct a minimal BacktestResult from stored data
    import numpy as np
    import pandas as pd
    from strategylab.packages.core.models import BacktestResult

    equity_dict = run.get_equity()
    if not equity_dict:
        raise HTTPException(
            status_code=400, detail="No equity data stored for this run."
        )

    dates = pd.to_datetime(list(equity_dict.keys()))
    values = list(equity_dict.values())
    equity_series = pd.Series(values, index=dates, name="equity", dtype=float)
    drawdown = (equity_series - equity_series.cummax()) / equity_series.cummax()

    # Build a minimal trade log from metrics
    metrics = run.get_metrics()
    total_trades = metrics.get("total_trades", 0)
    net_pnl = metrics.get("net_pnl", 0.0)
    if total_trades > 0:
        avg_pnl = net_pnl / total_trades
        trade_log = pd.DataFrame({
            "net_pnl": [avg_pnl] * total_trades,
            "gross_pnl": [avg_pnl] * total_trades,
            "commission": [0.0] * total_trades,
            "holding_bars": [5] * total_trades,
        })
    else:
        trade_log = pd.DataFrame(columns=["net_pnl", "gross_pnl", "commission", "holding_bars"])

    backtest_result = BacktestResult(
        equity_curve=equity_series,
        trade_log=trade_log,
        drawdown_series=drawdown,
        initial_capital=equity_series.iloc[0] if len(equity_series) else 100_000.0,
        symbol=run.get_symbols(),
        strategy_name="",
    )

    mc_result = execute_montecarlo(backtest_result, body)

    # Build response
    bands: list[MCBand] = []
    for label, eq_series in mc_result.equity_percentiles.items():
        points = [
            EquityPoint(date=str(d.date()), value=round(float(v), 2))
            for d, v in eq_series.items()
        ]
        bands.append(MCBand(label=label, equity=points))

    return MCResponse(
        run_id=run_id,
        method=mc_result.method,
        n_simulations=mc_result.n_simulations,
        percentile_bands=bands,
        summary=mc_result.summary(),
    )
