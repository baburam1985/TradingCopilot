import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

function formatTimestamp(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  return (
    <div className="bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-xs">
      <div className="text-[#888] mb-1">{label}</div>
      <div className="text-white font-semibold">${value.toFixed(2)}</div>
    </div>
  );
}

export default function EquityCurveChart({ points, startingCapital }) {
  if (!points || points.length < 2) {
    return (
      <p className="text-[#555] text-xs text-center py-8">
        Not enough closed trades to render equity curve.
      </p>
    );
  }

  const data = points.map((p) => ({
    timestamp: formatTimestamp(p.timestamp),
    portfolio_value: p.portfolio_value,
  }));

  const values = points.map((p) => p.portfolio_value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const lastVal = values[values.length - 1];
  const isProfit = lastVal >= startingCapital;

  return (
    <div className="w-full" style={{ touchAction: "pan-y" }}>
    <ResponsiveContainer width="100%" height={220} minHeight={160}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="5%"
              stopColor={isProfit ? "#00e676" : "#dc2626"}
              stopOpacity={0.25}
            />
            <stop
              offset="95%"
              stopColor={isProfit ? "#00e676" : "#dc2626"}
              stopOpacity={0}
            />
          </linearGradient>
        </defs>
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
        <ReferenceLine
          y={startingCapital}
          stroke="#444"
          strokeDasharray="4 4"
          strokeWidth={1}
        />
        <Area
          type="monotone"
          dataKey="portfolio_value"
          stroke={isProfit ? "#00e676" : "#dc2626"}
          strokeWidth={2}
          fill="url(#equityGradient)"
          dot={false}
          activeDot={{ r: 4, fill: isProfit ? "#00e676" : "#dc2626" }}
        />
      </AreaChart>
    </ResponsiveContainer>
    </div>
  );
}
