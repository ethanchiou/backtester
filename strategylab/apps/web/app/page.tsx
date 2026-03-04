"use client";
/**
 * / — Strategy Library page.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { strategyApi, type Strategy } from "@/lib/api";

export default function LibraryPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  async function fetchStrategies() {
    try {
      setLoading(true);
      const data = await strategyApi.list({ favorites_only: favoritesOnly });
      setStrategies(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStrategies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [favoritesOnly]);

  async function handleToggleFavorite(id: number) {
    await strategyApi.toggleFavorite(id);
    fetchStrategies();
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white">Strategy Library</h1>
            <p className="text-gray-400 mt-1">
              Manage, favorite, and run your trading strategies.
            </p>
          </div>
          <Link
            href="/run"
            className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg font-medium transition"
          >
            + New Run
          </Link>
        </div>

        <div className="flex gap-3 mb-6">
          <button
            onClick={() => setFavoritesOnly(false)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition ${
              !favoritesOnly
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFavoritesOnly(true)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition ${
              favoritesOnly
                ? "bg-yellow-500 text-gray-900"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            ★ Favorites
          </button>
        </div>

        {loading && <div className="text-gray-500 text-center py-16">Loading…</div>}
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4">
            Cannot connect to API: {error}
          </div>
        )}
        {!loading && !error && strategies.length === 0 && (
          <div className="text-center text-gray-500 py-16">
            <p className="text-lg">No strategies saved yet.</p>
            <p className="mt-2 text-sm">Run a backtest and save it to see it here.</p>
          </div>
        )}
        {!loading && !error && strategies.length > 0 && (
          <div className="grid gap-4">
            {strategies.map((s) => (
              <div
                key={s.id}
                className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-start justify-between"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-white">{s.name}</span>
                    <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                      v{s.version}
                    </span>
                    {s.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="text-sm text-gray-400 mt-1">{s.description}</p>
                </div>
                <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                  <button
                    onClick={() => handleToggleFavorite(s.id)}
                    className="text-xl transition hover:scale-110"
                  >
                    {s.favorite ? "★" : "☆"}
                  </button>
                  <Link
                    href={`/run?strategy=${s.name}`}
                    className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-1.5 rounded-lg transition"
                  >
                    Run
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
