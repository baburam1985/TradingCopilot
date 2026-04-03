import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";

const COLORS = ["#00e676", "#2196f3", "#ff9800", "#e91e63", "#9c27b0", "#00bcd4"];

function MetricRow({ label, results, accessor, format }) {
  return (
    <div className="flex items-center gap-0 mb-1">
      <span className="text-[#555] text-xs w-36 shrink-0">{label}</span>
      {results.map((r, i) => {
        const val = accessor(r.summary);
        return (
          <span
            key={i}
            className="flex-1 text-xs text-center font-mono"
            style={{ color: COLORS[i % COLORS.length] }}
          >
            {val != null ? format(val) : "—"}
          </span>
        );
      })}
    </div>
  );
}

export default function StrategyComparisonChart({ results }) {
  if (!results || results.length === 0) {
    return <p className="text-[#555] text-xs text-center py-8">No comparison results.</p>;
  }

  // Build bar chart data: one entry per metric
  const pnlData = results.map((r, i) => ({
    strategy: r.strategy,
    total_pnl: parseFloat(r.summary.total_pnl?.toFixed(2) ?? 0),
    color: COLORS[i % COLORS.length],
  }));

  return (
    <div>
      {/* Strategy name legend */}
      <div className="flex gap-4 mb-4 flex-wrap">
        {results.map((r, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            <span className="text-xs text-white">{r.strategy}</span>
          </div>
        ))}
      </div>

      {/* P&L bar chart */}
      <div className="mb-6">
        <p className="text-[#555] text-xs uppercase tracking-wider mb-2">Total P&amp;L</p>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={pnlData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <XAxis dataKey="strategy" tick={{ fontSize: 10, fill: "#666" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#666" }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} />
            <Tooltip formatter={v => [`$${parseFloat(v).toFixed(2)}`, "P&L"]} />
            <Bar dataKey="total_pnl">
              {pnlData.map((entry, i) => (
                <Cell key={i} fill={entry.total_pnl >= 0 ? COLORS[i % COLORS.length] : "#dc2626"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Metrics comparison table */}
      <div className="bg-[#0a0a0a] rounded p-3">
        <div className="flex items-center gap-0 mb-2 border-b border-[#222] pb-2">
          <span className="text-[#555] text-xs w-36 shrink-0">Metric</span>
          {results.map((r, i) => (
            <span key={i} className="flex-1 text-xs text-center font-semibold" style={{ color: COLORS[i % COLORS.length] }}>
              {r.strategy}
            </span>
          ))}
        </div>
        <MetricRow label="Win Rate" results={results} accessor={s => s.win_rate} format={v => `${(v * 100).toFixed(1)}%`} />
        <MetricRow label="Trades" results={results} accessor={s => s.num_trades} format={v => v} />
        <MetricRow label="Sharpe Ratio" results={results} accessor={s => s.sharpe_ratio} format={v => v.toFixed(2)} />
        <MetricRow label="Sortino Ratio" results={results} accessor={s => s.sortino_ratio} format={v => v.toFixed(2)} />
        <MetricRow label="Max Drawdown" results={results} accessor={s => s.max_drawdown_pct} format={v => `${v.toFixed(2)}%`} />
        <MetricRow label="Profit Factor" results={results} accessor={s => s.profit_factor} format={v => v.toFixed(2)} />
        <MetricRow label="Ending Capital" results={results} accessor={s => s.ending_capital} format={v => `$${v.toFixed(2)}`} />
      </div>
    </div>
  );
}
