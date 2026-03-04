"use client";
/**
 * /results/[id] — Backtest results page.
 * Shows equity curve, drawdown chart, metrics cards, and trade list.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { runApi, type EquityPoint, type MetricsResponse, type RunMetadata } from "@/lib/api";
import EquityCurveChart from "@/components/charts/EquityCurveChart";
import DrawdownChart from "@/components/charts/DrawdownChart";

interface Props {
  params: { id: string };
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-xl font-bold text-white mt-1">{value}</p>
    </div>
  );
}

function fmt(n: number, pct = false, decimals = 2) {
  if (pct) return `${(n * 100).toFixed(decimals)}%`;
  return n.toLocaleString("en-US", { maximumFractionDigits: decimals });
}

export default function ResultsPage({ params }: Props) {
  const { id } = params;
  const [metadata, setMetadata] = useState<RunMetadata | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [meta, eq, met] = await Promise.all([
          runApi.getMetadata(id),
          runApi.getEquity(id),
          runApi.getMetrics(id),
        ]);
        setMetadata(meta);
        setEquity(eq.equity);
        setMetrics(met);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-950 flex items-center justify-center">
        <span className="text-gray-500">Loading results…</span>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gray-950 p-8">
        <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4">
          {error}
        </div>
      </main>
    );
  }

  const m = metrics?.metrics ?? {};
  const sharpe = typeof m.sharpe_ratio === "number" ? m.sharpe_ratio : 0;
  const cagr = typeof m.cagr === "number" ? m.cagr : 0;
  const maxdd = typeof m.max_drawdown_pct === "number" ? m.max_drawdown_pct : 0;
  const wr = typeof m.win_rate === "number" ? m.win_rate : 0;
  const trades = typeof m.total_trades === "number" ? m.total_trades : 0;
  const netpnl = typeof m.net_pnl === "number" ? m.net_pnl : 0;

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Link href="/" className="hover:text-gray-300">Library</Link>
              <span>›</span>
              <span>Results</span>
            </div>
            <h1 className="text-2xl font-bold text-white">
              {metadata?.mode === "portfolio" ? "Portfolio" : "Single Asset"} Backtest
            </h1>
            <p className="text-gray-400 text-sm mt-0.5">
              {metadata?.symbols.join(", ")} ·{" "}
              {metadata?.date_range_start} → {metadata?.date_range_end}
            </p>
          </div>
          <Link
            href={`/montecarlo/${id}`}
            className="bg-purple-700 hover:bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
          >
            Monte Carlo →
          </Link>
        </div>

        {/* Key metrics */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <MetricCard label="CAGR" value={`${(cagr * 100).toFixed(1)}%`} />
          <MetricCard label="Sharpe" value={sharpe.toFixed(2)} />
          <MetricCard label="Max DD" value={`${maxdd.toFixed(1)}%`} />
          <MetricCard label="Win Rate" value={`${(wr * 100).toFixed(1)}%`} />
          <MetricCard label="Trades" value={String(trades)} />
          <MetricCard
            label="Net P&L"
            value={`$${netpnl.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          />
        </div>

        {/* Charts */}
        <div className="space-y-6">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
              Equity Curve
            </h2>
            <EquityCurveChart data={equity} />
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
              Underwater Drawdown
            </h2>
            <DrawdownChart equityData={equity} />
          </div>
        </div>

        {/* All metrics table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mt-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Full Metrics
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-8 gap-y-2">
            {Object.entries(m).map(([key, val]) => (
              <div key={key} className="flex justify-between py-1.5 border-b border-gray-800">
                <span className="text-gray-400 text-sm capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-white text-sm font-mono">
                  {typeof val === "number" ? val.toFixed(4) : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
