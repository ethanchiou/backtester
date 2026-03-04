# ARCHITECTURE.md — StrategyLab System Design

---

## 1. System Overview

StrategyLab is a **monorepo** containing a Python quant engine, a FastAPI REST
service, a Next.js web dashboard, and a Typer CLI. The quant engine is the
authoritative core — all other layers call into it.

```
┌─────────────────────────────────────────────────────────────┐
│                        Clients                              │
│                                                             │
│   ┌───────────────┐              ┌────────────────────┐     │
│   │  CLI (Typer)  │              │  Web (Next.js)     │     │
│   └───────┬───────┘              └─────────┬──────────┘     │
│           │ direct Python import           │ HTTP/REST       │
└───────────┼───────────────────────────────┼─────────────────┘
            │                               │
            ▼                               ▼
┌───────────────────────────────────────────────────────────┐
│                   FastAPI Service (apps/api)               │
│                                                           │
│  /strategies   /run   /runs/:id   /runs/:id/metrics       │
│  /runs/:id/equity     /runs/:id/montecarlo                │
└───────────────────────┬───────────────────────────────────┘
                        │ imports
         ┌──────────────┼──────────────────────────┐
         │              │                          │
         ▼              ▼                          ▼
  ┌──────────┐   ┌──────────────┐         ┌──────────────┐
  │  core    │   │  montecarlo  │         │     db       │
  │ engine   │   │  package     │         │  (SQLite)    │
  └────┬─────┘   └──────┬───────┘         └──────────────┘
       │                │
       │     ┌──────────┘
       ▼     ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │  strategies  │   │   metrics    │   │  execution   │
  │  package     │   │   package    │   │  package     │
  └──────────────┘   └──────────────┘   └──────────────┘
```

---

## 2. Package Responsibilities

### `packages/core` — Backtesting Engine

The engine is the heart of the system. It is framework-agnostic Python.

**Responsibilities:**
- Load and pivot CSV price data into aligned DataFrames.
- Call `strategy.generate_targets()` to get position signals.
- Pass signals through the execution model.
- Simulate the equity curve bar by bar.
- Produce a `BacktestResult` containing equity curve, trade log, drawdown series.

**Key classes:**
- `DataLoader` — reads CSV Format B, pivots to wide format.
- `BacktestEngine` — orchestrates a single-asset or portfolio backtest.
- `BacktestResult` — dataclass holding all outputs.
- `ExecutionConfig` — configures costs (commission, spread, slippage).

**Does NOT:**
- Talk to the database.
- Know about HTTP or CLI.
- Import from `apps/`.

---

### `packages/strategies` — Strategy Modules

Each strategy is a self-contained Python module. Strategies know nothing about
the engine, database, or UI.

**Interface contract (every strategy must define):**
```python
STRATEGY_META: dict       # name, version, description, tags
PARAM_SCHEMA: dict        # default parameters
generate_targets(data, params) -> pd.Series | pd.DataFrame
```

**Provided examples:**
- `sma_crossover.py` — Simple Moving Average crossover (fast/slow windows).
- `ema_crossover.py` — Exponential Moving Average crossover (fast/slow windows).

**Position encoding:**
- Single asset: `pd.Series` with values `{-1, 0, 1}`.
- Portfolio: `pd.DataFrame` with float weights per symbol column.

---

### `packages/metrics` — Performance Calculations

Pure functions operating on equity curves and trade logs. No side effects.

**Computed metrics:**
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- CAGR, Max Drawdown, Drawdown Duration
- Net P&L, Profit Factor, Win Rate, Expectancy
- Average Holding Period, Volatility, Exposure
- Largest Win, Largest Loss, Consecutive Wins/Losses

**Chart series produced:**
- Underwater drawdown series
- Rolling Sharpe series

**Key function:**
```python
def compute_metrics(equity: pd.Series, trades: pd.DataFrame,
                    risk_free_rate: float = 0.0) -> MetricsResult
```

---

### `packages/execution` — Execution Cost Models

Models realistic trade execution. Applied by the engine at fill time.

**Models:**
- `CommissionModel` — fixed per-trade or percent-of-notional.
- `SpreadModel` — basis points applied to entry/exit price.
- `SlippageModel` — basis points applied to fill price.

**Execution assumption:** All trades fill at the **next bar open** price. This
prevents look-ahead bias.

**Key class:**
```python
@dataclass
class ExecutionConfig:
    commission_type: Literal["fixed", "percent"]
    commission_value: float
    spread_bps: float
    slippage_bps: float
```

---

### `packages/montecarlo` — Monte Carlo Engine

Three simulation methods, all operating on pre-computed backtest results.

**Method 1 — Trade Sequence Shuffle:**
Randomly reorder trades from the trade log, reconstruct equity curve, repeat N times.

**Method 2 — Return Bootstrapping:**
Block bootstrap the daily return series, reconstruct equity curve, repeat N times.

**Method 3 — Parameter Uncertainty:**
Sample parameter values around their defaults using a configurable distribution,
run a full backtest for each sample, collect results.

**Outputs for each method:**
```python
@dataclass
class MCResult:
    equity_percentiles: dict[str, pd.Series]   # "5", "25", "50", "75", "95"
    drawdown_percentiles: dict[str, pd.Series]
    cagr_distribution: np.ndarray
    final_equity_distribution: np.ndarray
    max_drawdown_distribution: np.ndarray
```

---

### `packages/db` — Database Layer

SQLite schema and data access layer. Only `apps/api/` and `apps/cli/` use this.
The quant engine packages never import from here.

**Tables:**

```sql
-- Saved strategies
CREATE TABLE strategies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    version     TEXT NOT NULL,
    description TEXT,
    tags        TEXT,       -- JSON array
    favorite    BOOLEAN DEFAULT FALSE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Backtest runs
CREATE TABLE runs (
    run_id              TEXT PRIMARY KEY,   -- UUID
    strategy_id         INTEGER REFERENCES strategies(id),
    parameters          TEXT,               -- JSON
    date_range_start    DATE,
    date_range_end      DATE,
    symbols             TEXT,               -- JSON array
    mode                TEXT,               -- "single" | "portfolio"
    execution_settings  TEXT,               -- JSON
    metrics_json        TEXT,               -- JSON
    equity_json         TEXT,               -- JSON (date->value)
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

### `apps/api` — FastAPI Service

REST API consumed by the web dashboard and optionally the CLI.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/strategies` | List all saved strategies |
| POST | `/strategies` | Save a new strategy |
| PATCH | `/strategies/{id}/favorite` | Toggle favorite |
| POST | `/run` | Execute a backtest |
| GET | `/runs/{id}` | Get run metadata |
| GET | `/runs/{id}/metrics` | Get computed metrics |
| GET | `/runs/{id}/equity` | Get equity curve series |
| GET | `/runs/{id}/montecarlo` | Get MC simulation results |

**Request flow for `/run`:**
```
Client → POST /run (RunRequest)
  → DataLoader.load()
  → strategy.generate_targets()
  → BacktestEngine.run()
  → metrics.compute_metrics()
  → db.save_run()
  → return RunResponse
```

---

### `apps/cli` — Typer CLI

CLI interface for local use without the web server.

**Commands:**
```
strategylab strategies list           List all strategies
strategylab strategies add            Register a strategy
strategylab run                       Run a backtest (outputs table)
strategylab report <run_id>           Print metrics report
strategylab mc <run_id>               Run Monte Carlo on a completed run
```

CLI imports the quant engine packages directly (no HTTP). For strategy library
operations, it imports from `packages/db/`.

**Output:** Rich tables to terminal. `--json` flag exports raw JSON.

---

### `apps/web` — Next.js Dashboard

**Pages:**

| Route | Purpose |
|-------|---------|
| `/` | Strategy Library — list, search, favorite, run |
| `/run` | Configure and launch a new backtest |
| `/results/[id]` | Equity curve, drawdown, metrics cards, trade list |
| `/montecarlo/[id]` | Fan chart, CAGR/drawdown distributions |
| `/compare` | Overlay equity curves, metrics comparison table |

**API client:** All HTTP calls in `apps/web/lib/api.ts` (typed with Zod or TS interfaces).

**Charts (Recharts):**
- `EquityCurveChart` — line chart with benchmark overlay
- `DrawdownChart` — area chart (underwater equity)
- `RollingSharpeChart` — line chart
- `MCFanChart` — percentile band area chart
- `DistributionChart` — histogram bars

**Animations (Framer Motion):**
- Monte Carlo fan chart: 3-second progressive reveal of percentile bands.
- Distribution charts: bars fill in sequentially.

---

## 3. Data Flow — End to End

### Backtest Request (Web)

```
User fills Run form (symbol, date range, strategy, params)
  │
  ▼
apps/web POST /api/run
  │
  ▼
apps/api RunRequest validation (Pydantic)
  │
  ▼
packages/core DataLoader.load(csv_path, symbols, date_range)
  → returns wide DataFrame [dates × symbols]
  │
  ▼
packages/strategies sma_crossover.generate_targets(data, params)
  → returns position Series [dates]
  │
  ▼
packages/execution ExecutionConfig applied at each fill
  │
  ▼
packages/core BacktestEngine.run()
  → equity_curve, trade_log, drawdown_series
  │
  ▼
packages/metrics compute_metrics(equity_curve, trade_log)
  → MetricsResult
  │
  ▼
packages/db save_run(run_id, metrics, equity_curve, ...)
  │
  ▼
apps/api returns RunResponse { run_id, metrics_summary }
  │
  ▼
apps/web navigates to /results/[run_id]
  → fetches /runs/{id}/equity
  → fetches /runs/{id}/metrics
  → renders charts
```

---

### Monte Carlo Request

```
User triggers MC from Results page
  │
  ▼
apps/web POST /api/runs/{id}/montecarlo { method, n_simulations }
  │
  ▼
apps/api loads trade_log and equity_curve from db
  │
  ▼
packages/montecarlo run_simulation(method, equity, trades, n=1000)
  → MCResult with percentile bands
  │
  ▼
apps/api stores MCResult in db (or returns inline for small results)
  │
  ▼
apps/web receives MCResult
  → Framer Motion fan chart animates in over 3s
  → Distribution histograms fill progressively
```

---

### CLI Backtest (No Server)

```
User: strategylab run --strategy sma_crossover --symbol AAPL \
        --start 2020-01-01 --end 2023-01-01

apps/cli.run command
  → imports packages/core, packages/strategies, packages/metrics directly
  → DataLoader.load()
  → strategy.generate_targets()
  → BacktestEngine.run()
  → compute_metrics()
  → prints Rich table to terminal
  → optionally saves to local SQLite via packages/db
```

---

## 4. Dependency Rules (Strict)

```
apps/web        → apps/api (HTTP only)
apps/api        → packages/* (direct import)
apps/cli        → packages/* (direct import)

packages/core       → packages/execution, packages/strategies
packages/metrics    → (no internal package deps)
packages/montecarlo → packages/core, packages/metrics
packages/execution  → (no internal package deps)
packages/db         → (no internal package deps)
packages/strategies → (no internal package deps)
```

**Forbidden:**
- `packages/*` must never import from `apps/*`.
- `packages/core` must never import from `packages/db`.
- `packages/strategies` must never import from `packages/core`.

---

## 5. Monte Carlo Simulation Pipeline (Detail)

```
Input: BacktestResult (equity_curve, trade_log)
       SimulationConfig (method, n_simulations, seed)

Method 1 — Trade Shuffle:
  for i in range(n):
    shuffled_trades = random.shuffle(trade_log copy)
    equity_i = reconstruct_equity(shuffled_trades)
    collect equity_i[-1], max_drawdown(equity_i), cagr(equity_i)

Method 2 — Block Bootstrap:
  daily_returns = equity_curve.pct_change()
  for i in range(n):
    bootstrapped = block_bootstrap(daily_returns, block_size=20)
    equity_i = (1 + bootstrapped).cumprod() * initial_capital
    collect stats

Method 3 — Parameter Uncertainty:
  for i in range(n):
    sampled_params = {k: v + N(0, v*0.1) for k, v in params.items()}
    result_i = BacktestEngine.run(data, strategy, sampled_params)
    collect stats

Output: for each of the n curves, compute:
  → equity_percentiles at [5, 25, 50, 75, 95]
  → drawdown_percentiles at [5, 25, 50, 75, 95]
  → cagr_distribution (array of n values)
  → final_equity_distribution (array of n values)
  → max_drawdown_distribution (array of n values)
```

---

## 6. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Next-bar execution | Prevents look-ahead bias, reflects real trading |
| Position targets, not orders | Strategies stay simple; engine handles all execution complexity |
| Wide-format DataFrames internally | Vectorized portfolio operations, easy alignment |
| SQLite for storage | Zero infrastructure, local use, easy to swap for Postgres later |
| No market impact model | Out of scope; realistic for liquid instruments |
| Monorepo | Shared types, easy cross-package refactoring, single test suite |
| CSV Format B | Supports multi-asset in one file; easy to extend |
