import { useState } from "react";
import TradeDrawer from "./TradeDrawer";

export default function TradeLog({ trades }) {
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [expandedIds, setExpandedIds] = useState(new Set());

  function toggleExpand(id, e) {
    e.stopPropagation();
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #ddd" }}>
            <th style={{ width: 24 }}></th>
            <th>Action</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Reason</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {trades.map(t => {
            const hasReasoning = !!t.reasoning_text;
            const isExpanded = expandedIds.has(t.id);
            const displayReason = t.reasoning_text || t.signal_reason;
            return (
              <>
                <tr
                  key={t.id}
                  style={{ borderBottom: isExpanded ? "none" : "1px solid #f0f0f0", cursor: "pointer" }}
                  onClick={() => setSelectedTrade(t)}
                >
                  <td style={{ textAlign: "center", padding: "0 4px" }}>
                    {hasReasoning && (
                      <button
                        onClick={(e) => toggleExpand(t.id, e)}
                        title={isExpanded ? "Hide reasoning" : "Show reasoning"}
                        style={{ background: "none", border: "none", cursor: "pointer", color: "#00e676", fontSize: 12 }}
                      >
                        {isExpanded ? "▲" : "▼"}
                      </button>
                    )}
                  </td>
                  <td style={{ color: t.action === "buy" ? "green" : "red" }}>{t.action.toUpperCase()}</td>
                  <td>${parseFloat(t.price_at_signal).toFixed(2)}</td>
                  <td>{t.price_at_close ? `$${parseFloat(t.price_at_close).toFixed(2)}` : "—"}</td>
                  <td style={{ color: t.pnl > 0 ? "green" : t.pnl < 0 ? "red" : "inherit" }}>
                    {t.pnl != null ? `${t.pnl > 0 ? "+" : ""}$${parseFloat(t.pnl).toFixed(2)}` : "—"}
                  </td>
                  <td
                    style={{ fontSize: 12, color: "#666", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                    title={displayReason}
                  >
                    {t.signal_reason}
                  </td>
                  <td>{t.status}</td>
                </tr>
                {isExpanded && hasReasoning && (
                  <tr key={`${t.id}-reasoning`} style={{ borderBottom: "1px solid #f0f0f0" }}>
                    <td colSpan={7} style={{ padding: "6px 12px 10px 36px", background: "#f9f9f9" }}>
                      <p style={{ margin: 0, fontSize: 12, color: "#444", fontStyle: "italic" }}>
                        {t.reasoning_text}
                      </p>
                    </td>
                  </tr>
                )}
              </>
            );
          })}
        </tbody>
      </table>

      <TradeDrawer
        trade={selectedTrade}
        isOpen={!!selectedTrade}
        onClose={() => setSelectedTrade(null)}
      />
    </>
  );
}
