# CLAUDE.md — StrategyLab Engineering Reference

This file defines the engineering rules, architecture constraints, and development
workflow for StrategyLab. All contributors and AI assistants must follow these rules
exactly. Do not deviate without explicit approval.

---

## Project Identity

**Name:** StrategyLab
**Purpose:** Quantitative trading research platform — backtest strategies, run Monte
Carlo simulations, analyze performance via CLI and web dashboard.
**Monorepo root:** `strategylab/`

---

## Milestone Order (strict)

Build and fully validate each milestone before starting the next.

| # | Milestone | Key Deliverable |
|---|-----------|-----------------|
| 1 | Core backtesting engine | Single-asset engine, SMA/EMA strategies, basic metrics |
| 2 | Execution cost models | Commission, spread, slippage |
| 3 | Monte Carlo simulations | Shuffle, bootstrap, parameter sampling |
| 4 | Portfolio mode | Multi-asset, weights, rebalancing |
| 5 | Database + strategy library | SQLite, save/favorite/rerun |
| 6 | FastAPI service | REST API, typed schemas |
| 7 | Next.js dashboard | Library, Run, Results, MC pages |
| 8 | MC animation + comparison | Framer Motion fan chart, strategy comparison |

**Rule:** Never implement milestone N+1 while milestone N has failing tests or
incomplete contracts.

---

## Repository Layout

```
strategylab/
│
├── apps/
│   ├── api/            FastAPI backend
│   ├── web/            Next.js dashboard
│   └── cli/            Typer CLI
│
├── packages/
│   ├── core/           Backtesting engine
│   ├── strategies/     User strategy modules
│   ├── metrics/        Performance calculations
│   ├── montecarlo/     MC simulation engine
│   ├── execution/      Fee/slippage/spread models
│   └── db/             Database models + migrations
│
├── data/
│   └── csv/            Input price data (CSV Format B)
│
├── tests/              All tests, mirroring package structure
├── CLAUDE.md           This file
├── ARCHITECTURE.md     System design document
└── README.md
```

---

## Engineering Rules

### General

- All Python must be **type-hinted** (use `from __future__ import annotations` at top
  of each file).
- All public functions and classes must have **docstrings**.
- Code must be **modular** — one responsibility per module.
- No circular imports. Dependency direction: `db → core → metrics → montecarlo → execution`.
- Do not mix UI logic into any quant engine package.
- The quant engine (`packages/`) must be importable as a standalone Python library
  with no web framework dependency.

### Python Style

- Follow PEP 8.
- Max line length: 100 characters.
- Use `dataclasses` or `Pydantic` models for structured data transfer between layers.
- Prefer explicit over implicit. Avoid magic.
- Never use `**kwargs` in public API functions — always define named parameters.

### Data Contracts

- **Input data:** CSV Format B — columns: `date, symbol, open, high, low, close, volume`.
- **Internally:** pivot to wide-format DataFrames indexed by `date`, columns by `symbol`.
- **Strategy output:** target position weights per timestamp (`-1`, `0`, `1` for
  single asset; float weights per symbol for portfolio).
- **Engine output:** always returns `BacktestResult` dataclass containing
  `equity_curve`, `trade_log`, `drawdown_series`, and `metrics`.

### Strategy Interface

Every strategy module in `packages/strategies/` must define exactly:

```python
STRATEGY_META: dict   # name, version, description, tags
PARAM_SCHEMA: dict    # default parameter values
def generate_targets(data: pd.DataFrame, params: dict) -> pd.Series | pd.DataFrame:
    ...
```

Strategies output **target positions**, not orders. The engine handles execution.

### Execution Model

- Trades always execute at the **next bar open** (no look-ahead bias).
- Costs are applied at fill time: commission + spread + slippage.
- All cost models are **configurable** via `ExecutionConfig` dataclass.

### Testing

- Every package must have a corresponding `tests/` subdirectory.
- Every public function must have at least one unit test.
- Backtesting engine tests must use deterministic synthetic data (not live prices).
- Run tests with: `pytest tests/ -v`
- Tests must pass before any PR or milestone advance.

### FastAPI Rules

- All request/response bodies use **Pydantic models**.
- Endpoints return typed responses — no bare `dict` returns.
- All endpoints must be documented with OpenAPI `summary` and `description`.

### Next.js Rules

- TypeScript strict mode (`"strict": true` in tsconfig).
- No `any` types unless absolutely unavoidable and commented.
- All API calls go through a typed client module (`apps/web/lib/api.ts`).
- Charts built exclusively with Recharts.
- Animations built exclusively with Framer Motion.
- No additional charting or animation libraries.

### Database Rules

- SQLite for initial version. Schema defined in `packages/db/`.
- All migrations must be written and applied via Alembic.
- Never access the database directly from the quant engine packages.
- Only `apps/api/` and `packages/db/` interact with the database.

---

## Development Workflow

### Setup

```bash
# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e "packages/core[dev]"
pip install -e "packages/strategies"
pip install -e "packages/metrics"
# ... etc for each package

# Frontend
cd apps/web
npm install
```

### Running Tests

```bash
pytest tests/ -v                    # all tests
pytest tests/core/ -v               # engine tests only
pytest tests/metrics/ -v            # metrics tests only
```

### Running the Stack

```bash
# API
uvicorn apps.api.main:app --reload

# Web
cd apps/web && npm run dev

# CLI
python -m apps.cli.main --help
```

---

## What NOT to Do

- Do not skip milestones.
- Do not add features not in the spec without noting the deviation.
- Do not install new libraries without updating requirements and noting the reason.
- Do not use `print()` for logging — use Python's `logging` module.
- Do not hardcode file paths — use `pathlib.Path` and config.
- Do not use mutable default arguments in Python functions.
- Do not add market impact modeling (out of scope for current version).
- Do not use anything other than Recharts for charts or Framer Motion for animation.
