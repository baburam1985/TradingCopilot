export default function TradeLog({ trades }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{ borderBottom: "1px solid #ddd" }}>
          <th>Action</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Reason</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        {trades.map(t => (
          <tr key={t.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
            <td style={{ color: t.action === "buy" ? "green" : "red" }}>{t.action.toUpperCase()}</td>
            <td>${parseFloat(t.price_at_signal).toFixed(2)}</td>
            <td>{t.price_at_close ? `$${parseFloat(t.price_at_close).toFixed(2)}` : "—"}</td>
            <td style={{ color: t.pnl > 0 ? "green" : t.pnl < 0 ? "red" : "inherit" }}>
              {t.pnl != null ? `${t.pnl > 0 ? "+" : ""}$${parseFloat(t.pnl).toFixed(2)}` : "—"}
            </td>
            <td style={{ fontSize: 12, color: "#666" }}>{t.signal_reason}</td>
            <td>{t.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
