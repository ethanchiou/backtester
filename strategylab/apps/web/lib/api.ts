/**
 * api.ts — Typed API client for the StrategyLab backend.
 *
 * All HTTP calls to the FastAPI service go through this module.
 * No endpoint URLs are scattered across page components.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Strategy {
  id: number;
  name: string;
  version: string;
  description: string;
  tags: string[];
  module_path: string;
  favorite: boolean;
  created_at: string;
}

export interface StrategyCreate {
  name: string;
  version?: string;
  description?: string;
  tags?: string[];
  module_path?: string;
}

export interface ExecutionSettings {
  commission_type: "fixed" | "percent";
  commission_value: number;
  spread_bps: number;
  slippage_bps: number;
}

export interface RunRequest {
  strategy_name: string;
  symbols: string[];
  start_date: string;
  end_date: string;
  params?: Record<string, unknown>;
  mode: "single" | "portfolio";
  initial_capital?: number;
  execution_settings?: ExecutionSettings;
  csv_path?: string;
  save?: boolean;
  strategy_id?: number;
}

export interface MetricsSummary {
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  net_pnl: number;
  total_return_pct: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  volatility_annual: number;
}

export interface RunResponse {
  run_id: string;
  strategy_name: string;
  symbols: string[];
  mode: string;
  metrics_summary: MetricsSummary;
}

export interface RunMetadata {
  run_id: string;
  strategy_id: number | null;
  parameters: Record<string, unknown>;
  date_range_start: string | null;
  date_range_end: string | null;
  symbols: string[];
  mode: string;
  created_at: string;
}

export interface EquityPoint {
  date: string;
  value: number;
}

export interface EquityResponse {
  run_id: string;
  equity: EquityPoint[];
}

export interface MetricsResponse {
  run_id: string;
  metrics: Record<string, number | string>;
}

export interface MCBand {
  label: string;
  equity: EquityPoint[];
}

export interface MCRequest {
  method: "trade_shuffle" | "block_bootstrap" | "parameter_uncertainty";
  n_simulations: number;
  seed?: number;
  block_size?: number;
  param_uncertainty_pct?: number;
}

export interface MCResponse {
  run_id: string;
  method: string;
  n_simulations: number;
  percentile_bands: MCBand[];
  summary: Record<string, number | string>;
}

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }

  return resp.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Strategy endpoints
// ---------------------------------------------------------------------------

export const strategyApi = {
  list: (params?: { favorites_only?: boolean; tag?: string }) => {
    const qs = new URLSearchParams();
    if (params?.favorites_only) qs.set("favorites_only", "true");
    if (params?.tag) qs.set("tag", params.tag);
    const query = qs.toString() ? `?${qs}` : "";
    return apiFetch<Strategy[]>(`/strategies${query}`);
  },

  create: (body: StrategyCreate) =>
    apiFetch<Strategy>("/strategies", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  toggleFavorite: (id: number) =>
    apiFetch<{ id: number; favorite: boolean }>(`/strategies/${id}/favorite`, {
      method: "PATCH",
    }),
};

// ---------------------------------------------------------------------------
// Run endpoints
// ---------------------------------------------------------------------------

export const runApi = {
  run: (body: RunRequest) =>
    apiFetch<RunResponse>("/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getMetadata: (runId: string) =>
    apiFetch<RunMetadata>(`/runs/${runId}`),

  getMetrics: (runId: string) =>
    apiFetch<MetricsResponse>(`/runs/${runId}/metrics`),

  getEquity: (runId: string) =>
    apiFetch<EquityResponse>(`/runs/${runId}/equity`),

  getMontecarlo: (runId: string, body: MCRequest) =>
    apiFetch<MCResponse>(`/runs/${runId}/montecarlo`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
