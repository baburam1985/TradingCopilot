import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";

const SERIES_COLORS = ["#00e676", "#ffd600", "#ff6d00"];

function formatTimestamp(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-xs">
      <div className="text-[#888] mb-1">{label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} style={{ color: entry.color }} className="font-semibold">
          {entry.name}: ${Number(entry.value).toFixed(2)}
        </div>
      ))}
    </div>
  );
}

/**
 * Renders multiple equity curves on one chart.
 *
 * Props:
 *   series: Array<{ label: string, points: Array<{ timestamp: string, portfolio_value: number }> }>
 */
export default function MultiEquityCurveChart({ series }) {
  if (!series || series.length === 0) return null;

  // Merge all timestamps into a unified timeline, then align each series.
  // We use the series index in the dataKey to distinguish columns.
  const allTimestamps = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.timestamp)))
  ).sort();

  // Build lookup maps: seriesIndex -> { timestamp -> portfolio_value }
  const lookups = series.map((s) => {
    const map = {};
    s.points.forEach((p) => { map[p.timestamp] = p.portfolio_value; });
    return map;
  });

  const data = allTimestamps.map((ts) => {
    const row = { timestamp: formatTimestamp(ts) };
    series.forEach((s, i) => {
      if (lookups[i][ts] != null) row[`series_${i}`] = lookups[i][ts];
    });
    return row;
  });

  // Y-axis bounds across all series
  const allValues = series.flatMap((s) => s.points.map((p) => p.portfolio_value));
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <XAxis
          dataKey="timestamp"
          tick={{ fontSize: 10, fill: "#666" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[minVal * 0.995, maxVal * 1.005]}
          tick={{ fontSize: 10, fill: "#666" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v.toFixed(0)}`}
          width={60}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 11, color: "#888", paddingTop: 8 }}
          formatter={(value) => {
            const idx = parseInt(value.replace("series_", ""), 10);
            return series[idx]?.label ?? value;
          }}
        />
        {series.map((s, i) => (
          <Line
            key={i}
            type="monotone"
            dataKey={`series_${i}`}
            name={`series_${i}`}
            stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
