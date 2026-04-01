import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";

export default function PnLChart({ trades }) {
  const data = trades
    .filter(t => t.status === "closed" && t.pnl != null)
    .map((t, i) => ({
      name: `Trade ${i + 1}`,
      pnl: parseFloat(t.pnl),
    }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis />
        <Tooltip formatter={(v) => [`$${v.toFixed(2)}`, "P&L"]} />
        <Bar dataKey="pnl">
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.pnl >= 0 ? "#16a34a" : "#dc2626"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
