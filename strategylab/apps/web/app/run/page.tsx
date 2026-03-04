"use client";
/**
 * /run — Configure and launch a new backtest.
 */

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { runApi, type RunRequest } from "@/lib/api";

const STRATEGIES = [
  { name: "SMA_Crossover", defaultParams: { fast: 20, slow: 50 }, modes: ["single"] },
  { name: "EMA_Crossover", defaultParams: { fast: 12, slow: 26 }, modes: ["single"] },
  {
    name: "Portfolio_SMA_Crossover",
    defaultParams: { fast: 20, slow: 50 },
    modes: ["portfolio"],
  },
];

function RunForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialStrategy = searchParams.get("strategy") ?? STRATEGIES[0].name;

  const [strategyName, setStrategyName] = useState(initialStrategy);
  const [symbols, setSymbols] = useState("AAPL");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [fast, setFast] = useState(20);
  const [slow, setSlow] = useState(50);
  const [capital, setCapital] = useState(100000);
  const [mode, setMode] = useState<"single" | "portfolio">("single");
  const [save, setSave] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedStrategy = STRATEGIES.find((s) => s.name === strategyName);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const symbolList = symbols
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    const body: RunRequest = {
      strategy_name: strategyName,
      symbols: symbolList,
      start_date: startDate,
      end_date: endDate,
      params: { fast, slow },
      mode,
      initial_capital: capital,
      save,
    };

    try {
      const resp = await runApi.run(body);
      router.push(`/results/${resp.run_id}`);
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-2">New Backtest</h1>
        <p className="text-gray-400 mb-8">Configure your strategy and run a backtest.</p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Strategy */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <h2 className="text-lg font-semibold text-white">Strategy</h2>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Strategy</label>
              <select
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
              >
                {STRATEGIES.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Fast window</label>
                <input
                  type="number"
                  value={fast}
                  onChange={(e) => setFast(Number(e.target.value))}
                  min={2}
                  max={200}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Slow window</label>
                <input
                  type="number"
                  value={slow}
                  onChange={(e) => setSlow(Number(e.target.value))}
                  min={3}
                  max={500}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Data */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <h2 className="text-lg font-semibold text-white">Data</h2>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Symbols (comma-separated)
              </label>
              <input
                type="text"
                value={symbols}
                onChange={(e) => setSymbols(e.target.value)}
                placeholder="AAPL, MSFT"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Start date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">End date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as "single" | "portfolio")}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="single">Single Asset</option>
                  <option value="portfolio">Portfolio</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Initial Capital ($)</label>
                <input
                  type="number"
                  value={capital}
                  onChange={(e) => setCapital(Number(e.target.value))}
                  min={1000}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Options */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="save"
              checked={save}
              onChange={(e) => setSave(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="save" className="text-sm text-gray-400">
              Save run to library
            </label>
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white py-3 rounded-lg font-semibold transition"
          >
            {loading ? "Running backtest…" : "Run Backtest →"}
          </button>
        </form>
      </div>
    </main>
  );
}

export default function RunPage() {
  return (
    <Suspense>
      <RunForm />
    </Suspense>
  );
}
