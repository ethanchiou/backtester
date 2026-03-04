"""
test_api.py — Integration tests for the FastAPI service.

Uses TestClient with an in-memory SQLite database override.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from strategylab.apps.api.main import app
from strategylab.apps.api.dependencies import get_db
from strategylab.packages.db.database import create_tables, get_engine


# ---------------------------------------------------------------------------
# Test database override
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_engine():
    engine = get_engine(":memory:")
    create_tables(engine)
    return engine


@pytest.fixture(scope="module")
def client(test_engine):
    """TestClient with in-memory DB dependency override."""
    from sqlalchemy.orm import sessionmaker

    def override_get_db():
        SessionLocal = sessionmaker(
            bind=test_engine, autoflush=False, expire_on_commit=False
        )
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Strategy endpoints
# ---------------------------------------------------------------------------

class TestStrategyEndpoints:

    def test_list_strategies_empty(self, client: TestClient) -> None:
        resp = client.get("/strategies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_strategy(self, client: TestClient) -> None:
        resp = client.post("/strategies", json={
            "name": "SMA_Crossover",
            "version": "1.0",
            "description": "Test strategy",
            "tags": ["trend"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "SMA_Crossover"
        assert data["id"] is not None
        assert data["favorite"] is False

    def test_list_strategies_returns_created(self, client: TestClient) -> None:
        resp = client.get("/strategies")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "SMA_Crossover" in names

    def test_toggle_favorite(self, client: TestClient) -> None:
        # Create a fresh strategy
        create_resp = client.post("/strategies", json={"name": "FavTest"})
        sid = create_resp.json()["id"]

        resp = client.patch(f"/strategies/{sid}/favorite")
        assert resp.status_code == 200
        assert resp.json()["favorite"] is True

        resp2 = client.patch(f"/strategies/{sid}/favorite")
        assert resp2.json()["favorite"] is False

    def test_toggle_nonexistent_strategy_404(self, client: TestClient) -> None:
        resp = client.patch("/strategies/9999/favorite")
        assert resp.status_code == 404

    def test_list_favorites_only(self, client: TestClient) -> None:
        # Create and favorite one strategy
        create_resp = client.post("/strategies", json={"name": "FavOnly"})
        sid = create_resp.json()["id"]
        client.patch(f"/strategies/{sid}/favorite")

        resp = client.get("/strategies?favorites_only=true")
        assert resp.status_code == 200
        favs = resp.json()
        assert any(s["name"] == "FavOnly" for s in favs)
        assert all(s["favorite"] for s in favs)


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------

class TestRunEndpoints:

    @pytest.fixture(scope="class")
    def run_id(self, client: TestClient) -> str:
        """Create one real backtest run and return its ID."""
        resp = client.post("/run", json={
            "strategy_name": "SMA_Crossover",
            "symbols": ["AAPL"],
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
            "params": {"fast": 20, "slow": 50},
            "mode": "single",
            "initial_capital": 100000.0,
            "save": True,
        })
        assert resp.status_code == 201, resp.text
        return resp.json()["run_id"]

    def test_run_returns_201(self, client: TestClient) -> None:
        resp = client.post("/run", json={
            "strategy_name": "SMA_Crossover",
            "symbols": ["AAPL"],
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "params": {"fast": 20, "slow": 50},
            "mode": "single",
            "save": False,
        })
        assert resp.status_code == 201

    def test_run_response_has_run_id(self, client: TestClient) -> None:
        resp = client.post("/run", json={
            "strategy_name": "EMA_Crossover",
            "symbols": ["AAPL"],
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "params": {"fast": 12, "slow": 26},
            "mode": "single",
            "save": False,
        })
        assert "run_id" in resp.json()

    def test_run_response_has_metrics_summary(self, client: TestClient) -> None:
        resp = client.post("/run", json={
            "strategy_name": "SMA_Crossover",
            "symbols": ["AAPL"],
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "mode": "single",
            "save": False,
        })
        data = resp.json()
        assert "metrics_summary" in data
        summary = data["metrics_summary"]
        assert "sharpe_ratio" in summary
        assert "cagr" in summary

    def test_run_unknown_strategy_400(self, client: TestClient) -> None:
        resp = client.post("/run", json={
            "strategy_name": "NonExistentStrategy",
            "symbols": ["AAPL"],
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "mode": "single",
            "save": False,
        })
        assert resp.status_code == 400

    def test_get_run_metadata(self, client: TestClient, run_id: str) -> None:
        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["symbols"] == ["AAPL"]

    def test_get_run_metrics(self, client: TestClient, run_id: str) -> None:
        resp = client.get(f"/runs/{run_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "sharpe_ratio" in data["metrics"]

    def test_get_run_equity(self, client: TestClient, run_id: str) -> None:
        resp = client.get(f"/runs/{run_id}/equity")
        assert resp.status_code == 200
        data = resp.json()
        assert "equity" in data
        assert len(data["equity"]) > 0
        first = data["equity"][0]
        assert "date" in first
        assert "value" in first

    def test_get_run_404(self, client: TestClient) -> None:
        resp = client.get("/runs/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_metrics_404(self, client: TestClient) -> None:
        resp = client.get("/runs/00000000-0000-0000-0000-000000000000/metrics")
        assert resp.status_code == 404

    def test_get_equity_404(self, client: TestClient) -> None:
        resp = client.get("/runs/00000000-0000-0000-0000-000000000000/equity")
        assert resp.status_code == 404

    def test_montecarlo_endpoint(self, client: TestClient, run_id: str) -> None:
        resp = client.post(
            f"/runs/{run_id}/montecarlo",
            json={"method": "trade_shuffle", "n_simulations": 50, "seed": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert len(data["percentile_bands"]) == 5
        labels = {b["label"] for b in data["percentile_bands"]}
        assert labels == {"p5", "p25", "p50", "p75", "p95"}

    def test_portfolio_run(self, client: TestClient) -> None:
        resp = client.post("/run", json={
            "strategy_name": "Portfolio_SMA_Crossover",
            "symbols": ["AAPL", "MSFT"],
            "start_date": "2022-01-01",
            "end_date": "2022-12-31",
            "params": {"fast": 20, "slow": 50},
            "mode": "portfolio",
            "save": False,
        })
        assert resp.status_code == 201
        assert resp.json()["mode"] == "portfolio"
