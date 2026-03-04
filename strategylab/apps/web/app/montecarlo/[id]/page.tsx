"use client";
/**
 * /montecarlo/[id] — Monte Carlo results page.
 *
 * Milestone 8: Framer Motion 3-second progressive reveal animation.
 * - Summary cards stagger in (fade + slide-up) as soon as data arrives.
 * - MCFanChart receives animated=true so bands reveal one-by-one (~600 ms each).
 * - DistributionChart bars animate upward via Recharts native animation (2 s).
 */

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { runApi, type MCResponse } from "@/lib/api";
import MCFanChart from "@/components/charts/MCFanChart";
import DistributionChart from "@/components/charts/DistributionChart";

interface Props {
  params: { id: string };
}

const METHODS = [
  { value: "trade_shuffle", label: "Trade Shuffle" },
  { value: "block_bootstrap", label: "Block Bootstrap" },
] as const;

/** Framer Motion variants for staggered card entrance */
const containerVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12 },
  },
};

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" as const } },
};

export default function MonteCarlo({ params }: Props) {
  const { id } = params;
  const [method, setMethod] = useState<"trade_shuffle" | "block_bootstrap">("trade_shuffle");
  const [nSims, setNSims] = useState(500);
  const [result, setResult] = useState<MCResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runMC() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await runApi.getMontecarlo(id, {
        method,
        n_simulations: nSims,
        seed: 42,
      });
      setResult(resp);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  // Build a CAGR distribution array from the p50 band equity series
  // (approximated from the percentile bands summary values for histogram display)
  function buildCagrDistribution(res: MCResponse): number[] {
    // Use summary values as representative distribution points
    const { p5_cagr, p25_cagr, median_cagr, p75_cagr, p95_cagr } = res.summary as Record<string, number>;
    if (median_cagr === undefined) return [];
    // Linearly interpolate ~50 values across the distribution for a rough histogram
    const pts: number[] = [];
    const segments: [number, number, number][] = [
      [p5_cagr, p25_cagr, 10],
      [p25_cagr, median_cagr, 15],
      [median_cagr, p75_cagr, 15],
      [p75_cagr, p95_cagr, 10],
    ];
    for (const [lo, hi, n] of segments) {
      for (let i = 0; i < n; i++) {
        pts.push(lo + ((hi - lo) * i) / n);
      }
    }
    return pts;
  }

  const summaryCards = result
    ? [
        {
          label: "Median CAGR",
          value: `${((result.summary.median_cagr as number) * 100).toFixed(1)}%`,
        },
        {
          label: "5th CAGR",
          value: `${((result.summary.p5_cagr as number) * 100).toFixed(1)}%`,
        },
        {
          label: "95th CAGR",
          value: `${((result.summary.p95_cagr as number) * 100).toFixed(1)}%`,
        },
        {
          label: "Median Max DD",
          value: `${(result.summary.median_max_drawdown as number).toFixed(1)}%`,
        },
      ]
    : [];

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-5xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link href="/" className="hover:text-gray-300">Library</Link>
          <span>›</span>
          <Link href={`/results/${id}`} className="hover:text-gray-300">Results</Link>
          <span>›</span>
          <span>Monte Carlo</span>
        </div>
        <h1 className="text-3xl font-bold text-white mb-6">Monte Carlo Simulation</h1>

        {/* Config panel */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Method</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as typeof method)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            >
              {METHODS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Simulations</label>
            <select
              value={nSims}
              onChange={(e) => setNSims(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
            >
              {[100, 250, 500, 1000, 2000].map((n) => (
                <option key={n} value={n}>{n.toLocaleString()}</option>
              ))}
            </select>
          </div>
          <button
            onClick={runMC}
            disabled={loading}
            className="bg-purple-700 hover:bg-purple-600 disabled:bg-gray-700 text-white px-6 py-2 rounded-lg font-medium transition"
          >
            {loading ? "Simulating…" : "Run Simulation"}
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6">
            {error}
          </div>
        )}

        <AnimatePresence mode="wait">
          {result && (
            <motion.div
              key={`${method}-${nSims}`}
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0 }}
              className="space-y-6"
            >
              {/* Summary cards — stagger in */}
              <motion.div
                variants={containerVariants}
                className="grid grid-cols-2 md:grid-cols-4 gap-3"
              >
                {summaryCards.map((c) => (
                  <motion.div
                    key={c.label}
                    variants={cardVariants}
                    className="bg-gray-900 border border-gray-800 rounded-xl p-4"
                  >
                    <p className="text-xs text-gray-500 uppercase tracking-wider">{c.label}</p>
                    <p className="text-xl font-bold text-white mt-1">{c.value}</p>
                  </motion.div>
                ))}
              </motion.div>

              {/* Fan chart — animated progressive reveal */}
              <motion.div
                variants={cardVariants}
                className="bg-gray-900 border border-gray-800 rounded-xl p-6"
              >
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                  Equity Fan Chart · {result.n_simulations.toLocaleString()} paths
                </h2>
                <MCFanChart bands={result.percentile_bands} animated={true} />
              </motion.div>

              {/* CAGR distribution histogram */}
              {buildCagrDistribution(result).length > 0 && (
                <motion.div
                  variants={cardVariants}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-6"
                >
                  <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                    CAGR Distribution
                  </h2>
                  <DistributionChart
                    values={buildCagrDistribution(result)}
                    label="CAGR"
                    formatter={(v) => `${(v * 100).toFixed(1)}%`}
                    color="#a855f7"
                  />
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}
