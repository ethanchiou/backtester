"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/api";

interface Props {
  data: EquityPoint[];
  /** Optional label for the equity line */
  label?: string;
  /** Optional second series (e.g. benchmark) */
  benchmarkData?: EquityPoint[];
  benchmarkLabel?: string;
}

export default function EquityCurveChart({
  data,
  label = "Portfolio",
  benchmarkData,
  benchmarkLabel = "Benchmark",
}: Props) {
  // Merge series on date key
  const merged = data.map((pt, i) => ({
    date: pt.date,
    [label]: Math.round(pt.value),
    ...(benchmarkData?.[i]
      ? { [benchmarkLabel]: Math.round(benchmarkData[i].value) }
      : {}),
  }));

  const formatValue = (v: number) =>
    `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

  const formatDate = (d: string) => {
    const dt = new Date(d);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={merged} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
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
        <Legend wrapperStyle={{ color: "#9ca3af" }} />
        <Line
          type="monotone"
          dataKey={label}
          stroke="#3b82f6"
          dot={false}
          strokeWidth={2}
        />
        {benchmarkData && (
          <Line
            type="monotone"
            dataKey={benchmarkLabel}
            stroke="#6b7280"
            dot={false}
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
