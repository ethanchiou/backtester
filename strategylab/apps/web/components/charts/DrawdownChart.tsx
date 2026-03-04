"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/lib/api";

interface Props {
  /** Equity curve data — drawdown is derived internally. */
  equityData: EquityPoint[];
}

function computeDrawdown(equity: EquityPoint[]) {
  let peak = equity[0]?.value ?? 0;
  return equity.map((pt) => {
    if (pt.value > peak) peak = pt.value;
    const dd = peak === 0 ? 0 : ((pt.value - peak) / peak) * 100;
    return { date: pt.date, drawdown: parseFloat(dd.toFixed(2)) };
  });
}

export default function DrawdownChart({ equityData }: Props) {
  const data = computeDrawdown(equityData);

  const formatDate = (d: string) => {
    const dt = new Date(d);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
  };

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 16 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2d2d2d" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fill: "#9ca3af", fontSize: 11 }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => `${v.toFixed(1)}%`}
          tick={{ fill: "#9ca3af", fontSize: 11 }}
          tickLine={false}
        />
        <Tooltip
          formatter={(value: number | undefined) => [`${(value ?? 0).toFixed(2)}%`, "Drawdown"]}
          contentStyle={{ background: "#1f2937", border: "1px solid #374151" }}
          labelStyle={{ color: "#f9fafb" }}
        />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="#ef4444"
          fill="url(#ddGrad)"
          strokeWidth={1.5}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
