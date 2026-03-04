"use client";
/**
 * MCFanChart.tsx — Monte Carlo fan chart with percentile bands.
 *
 * Milestone 8: animated progressive reveal via Framer Motion + JS timers.
 * When animated=true, bands reveal sequentially over ~3 seconds
 * (one band every 600 ms × 5 bands = 3 000 ms).
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MCBand } from "@/lib/api";

/** Interval between each band reveal in milliseconds */
const REVEAL_INTERVAL_MS = 600;

interface Props {
  bands: MCBand[];
  /** When true, bands animate in sequentially over ~3 s */
  animated?: boolean;
}

const BAND_COLORS: Record<string, string> = {
  p5: "#1d4ed8",
  p25: "#2563eb",
  p50: "#3b82f6",
  p75: "#60a5fa",
  p95: "#93c5fd",
};

const BAND_LABELS: Record<string, string> = {
  p5: "5th percentile",
  p25: "25th percentile",
  p50: "Median",
  p75: "75th percentile",
  p95: "95th percentile",
};

const SORTED_KEYS = ["p5", "p25", "p50", "p75", "p95"];

export default function MCFanChart({ bands, animated = false }: Props) {
  if (!bands || bands.length === 0) return null;

  // Determine which percentile labels are present in the data
  const presentLabels = SORTED_KEYS.filter((l) =>
    bands.some((b) => b.label === l)
  );

  // How many bands are currently visible (0 = none, up to presentLabels.length)
  const [visibleCount, setVisibleCount] = useState(
    animated ? 0 : presentLabels.length
  );

  useEffect(() => {
    if (!animated) {
      setVisibleCount(presentLabels.length);
      return;
    }

    // Reset then reveal one band at a time
    setVisibleCount(0);
    let count = 0;
    const timer = setInterval(() => {
      count += 1;
      setVisibleCount(count);
      if (count >= presentLabels.length) clearInterval(timer);
    }, REVEAL_INTERVAL_MS);

    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [animated, bands]);

  // Merge all bands into a flat array of data points keyed by date
  const dateMap = new Map<string, Record<string, number>>();
  for (const band of bands) {
    for (const pt of band.equity) {
      const existing = dateMap.get(pt.date) ?? {};
      existing[band.label] = Math.round(pt.value);
      dateMap.set(pt.date, existing);
    }
  }

  const data = Array.from(dateMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({ date, ...values }));

  const formatValue = (v: number) =>
    `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

  const formatDate = (d: string) => {
    const dt = new Date(d);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
  };

  const visibleLabels = presentLabels.slice(0, visibleCount);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d2d2d" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatValue}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickLine={false}
            width={90}
          />
          <Tooltip
            formatter={(value: number | undefined) => formatValue(value ?? 0)}
            contentStyle={{ background: "#1f2937", border: "1px solid #374151" }}
            labelStyle={{ color: "#f9fafb" }}
          />
          <Legend
            formatter={(value: string) => BAND_LABELS[value] ?? value}
            wrapperStyle={{ color: "#9ca3af" }}
          />
          {visibleLabels.map((label) => (
            <Area
              key={label}
              type="monotone"
              dataKey={label}
              stroke={BAND_COLORS[label] ?? "#3b82f6"}
              fill={BAND_COLORS[label] ?? "#3b82f6"}
              fillOpacity={label === "p50" ? 0 : 0.1}
              strokeWidth={label === "p50" ? 2.5 : 1}
              dot={false}
              isAnimationActive={true}
              animationDuration={550}
              animationEasing="ease-out"
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
