"use client";
/**
 * DistributionChart.tsx — Histogram for MC distribution outputs.
 *
 * Milestone 8: bars fill progressively upward via Recharts native animation
 * (animationDuration=2000) and the container fades in with Framer Motion.
 */

import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  /** Raw values array (e.g. CAGR distribution) */
  values: number[];
  label: string;
  /** Number of histogram bins */
  bins?: number;
  /** Format function for axis/tooltip values */
  formatter?: (v: number) => string;
  color?: string;
}

function buildHistogram(
  values: number[],
  bins: number
): { bucket: string; count: number; midpoint: number }[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    return [{ bucket: String(min.toFixed(2)), count: values.length, midpoint: min }];
  }

  const step = (max - min) / bins;
  const counts = Array(bins).fill(0);

  for (const v of values) {
    const idx = Math.min(Math.floor((v - min) / step), bins - 1);
    counts[idx]++;
  }

  return counts.map((count, i) => {
    const lo = min + i * step;
    const hi = lo + step;
    const midpoint = (lo + hi) / 2;
    return { bucket: `${lo.toFixed(2)}–${hi.toFixed(2)}`, count, midpoint };
  });
}

export default function DistributionChart({
  values,
  label,
  bins = 20,
  formatter = (v) => v.toFixed(2),
  color = "#3b82f6",
}: Props) {
  const data = buildHistogram(values, bins);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
    >
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d2d2d" />
          <XAxis
            dataKey="bucket"
            tick={false}
            tickLine={false}
            label={{
              value: label,
              position: "insideBottom",
              fill: "#9ca3af",
              fontSize: 12,
            }}
            height={30}
          />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickLine={false}
          />
          <Tooltip
            formatter={(v: number | undefined) => [v ?? 0, "Count"]}
            labelFormatter={(l) => `Range: ${l}`}
            contentStyle={{ background: "#1f2937", border: "1px solid #374151" }}
            labelStyle={{ color: "#f9fafb" }}
          />
          <Bar
            dataKey="count"
            fill={color}
            radius={[2, 2, 0, 0]}
            isAnimationActive={true}
            animationDuration={2000}
            animationEasing="ease-out"
          />
        </BarChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
