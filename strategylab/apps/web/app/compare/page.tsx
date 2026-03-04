"use client";
/**
 * /compare — Overlay and compare two backtest runs.
 */

import { useState } from "react";
import { runApi, type EquityPoint, type MetricsResponse } from "@/lib/api";
import EquityCurveChart from "@/components/charts/EquityCurveChart";

export default function ComparePage() {
  const [runId1, setRunId1] = useState("");
  const [runId2, setRunId2] = useState("");
  const [equity1, setEquity1] = useState<EquityPoint[] | null>(null);
  const [equity2, setEquity2] = useState<EquityPoint[] | null>(null);
  const [metrics1, setMetrics1] = useState<MetricsResponse | null>(null);
  const [metrics2, setMetrics2] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCompare() {
    if (!runId1 || !runId2) return;
    setLoading(true);
    setError(null);
    try {
      const [eq1, eq2, m1, m2] = await Promise.all([
        runApi.getEquity(runId1),
        runApi.getEquity(runId2),
        runApi.getMetrics(runId1),
        runApi.getMetrics(runId2),
      ]);
      setEquity1(eq1.equity);
      setEquity2(eq2.equity);
      setMetrics1(m1);
      setMetrics2(m2);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const COMPARE_METRICS = [
    "cagr", "sharpe_ratio", "sortino_ratio", "calmar_ratio",
    "max_drawdown_pct", "win_rate", "profit_factor", "total_trades",
  ];

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-2">Compare Runs</h1>
        <p className="text-gray-400 mb-8">Enter two run IDs to overlay their equity curves.</p>

        {/* Input */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-48">
            <label className="block text-sm text-gray-400 mb-1">Run ID 1</label>
            <input
              type="text"
              value={runId1}
              onChange={(e) => setRunId1(e.target.value)}
              placeholder="UUID…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex-1 min-w-48">
            <label className="block text-sm text-gray-400 mb-1">Run ID 2</label>
            <input
              type="text"
              value={runId2}
              onChange={(e) => setRunId2(e.target.value)}
              placeholder="UUID…"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={handleCompare}
            disabled={loading || !runId1 || !runId2}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-medium transition"
          >
            {loading ? "Loading…" : "Compare"}
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6">
            {error}
          </div>
        )}

        {equity1 && equity2 && (
          <div className="space-y-6">
            {/* Overlay chart */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                Equity Curves
              </h2>
              <EquityCurveChart
                data={equity1}
                label="Run 1"
                benchmarkData={equity2}
                benchmarkLabel="Run 2"
              />
            </div>

            {/* Metrics table */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                Metrics Comparison
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-left">
                    <th className="py-2 pr-4">Metric</th>
                    <th className="py-2 pr-4 text-blue-400">Run 1</th>
                    <th className="py-2 text-gray-300">Run 2</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARE_METRICS.map((key) => {
                    const v1 = metrics1?.metrics[key];
                    const v2 = metrics2?.metrics[key];
                    const fmt = (v: unknown) =>
                      typeof v === "number" ? v.toFixed(4) : String(v ?? "—");
                    return (
                      <tr key={key} className="border-t border-gray-800">
                        <td className="py-2 pr-4 text-gray-400 capitalize">
                          {key.replace(/_/g, " ")}
                        </td>
                        <td className="py-2 pr-4 font-mono text-blue-300">{fmt(v1)}</td>
                        <td className="py-2 font-mono text-gray-300">{fmt(v2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
