"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"];

// Renders the chart spec the agent sends back: { type, title, x, y: [...], data: [...] }
export default function ResultChart({ chart }) {
  if (!chart || chart.type === "none" || !chart.data || chart.data.length === 0) {
    return null;
  }

  const isLine = chart.type === "line";
  const Wrapper = isLine ? LineChart : BarChart;

  return (
    <div className="chart">
      <div className="chart-title">{chart.title}</div>
      <ResponsiveContainer width="100%" height={280}>
        <Wrapper data={chart.data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={chart.x} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          {chart.y.length > 1 && <Legend />}
          {chart.y.map((key, i) =>
            isLine ? (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} />
            ) : (
              <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} />
            )
          )}
        </Wrapper>
      </ResponsiveContainer>
    </div>
  );
}
