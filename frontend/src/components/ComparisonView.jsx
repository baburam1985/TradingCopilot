export default function ComparisonView({ trades, summary }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <div style={{ padding: "1rem", background: "#f0fdf4", borderRadius: 8 }}>
        <h4>Paper Trading Result</h4>
        <p>Total P&L: <strong style={{ color: summary.total_pnl >= 0 ? "green" : "red" }}>
          {summary.total_pnl >= 0 ? "+" : ""}${summary.total_pnl?.toFixed(2)}
        </strong></p>
        <p>Trades: {summary.num_trades} ({summary.num_wins}W / {summary.num_losses}L)</p>
        <p>Win Rate: {(summary.win_rate * 100).toFixed(1)}%</p>
        <p>Capital: ${summary.starting_capital?.toFixed(2)} → <strong>${summary.ending_capital?.toFixed(2)}</strong></p>
      </div>
      <div style={{ padding: "1rem", background: "#eff6ff", borderRadius: 8 }}>
        <h4>Actual Market Outcome</h4>
        {trades.filter(t => t.status === "closed").map(t => (
          <div key={t.id} style={{ fontSize: 13, borderBottom: "1px solid #e0e0e0", padding: "0.25rem 0" }}>
            {t.action.toUpperCase()} @ ${parseFloat(t.price_at_signal).toFixed(2)} →
            closed @ ${parseFloat(t.price_at_close).toFixed(2)} |
            <span style={{ color: parseFloat(t.pnl) >= 0 ? "green" : "red" }}>
              {" "}{parseFloat(t.pnl) >= 0 ? "+" : ""}${parseFloat(t.pnl).toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
