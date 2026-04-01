import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getSessions, getTrades, getPnl } from "../api/client";
import PnLChart from "../components/PnLChart";
import TradeLog from "../components/TradeLog";
import ComparisonView from "../components/ComparisonView";

export default function Reports() {
  const location = useLocation();
  const backtestResult = location.state?.backtestResult;

  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [trades, setTrades] = useState([]);
  const [pnl, setPnl] = useState(null);

  useEffect(() => {
    if (backtestResult) return;
    getSessions().then(r => setSessions(r.data));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([getTrades(selectedId), getPnl(selectedId)]).then(([t, p]) => {
      setTrades(t.data);
      setPnl(p.data.all_time);
    });
  }, [selectedId]);

  if (backtestResult) {
    return (
      <div style={{ padding: "1rem" }}>
        <h2>Backtest Results</h2>
        <PnLChart trades={backtestResult.trades} />
        <ComparisonView trades={backtestResult.trades} summary={backtestResult.summary} />
        <h3>Trade Log</h3>
        <TradeLog trades={backtestResult.trades} />
      </div>
    );
  }

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Reports</h2>
      <select value={selectedId || ""} onChange={e => setSelectedId(e.target.value)}>
        <option value="">Select a session...</option>
        {sessions.map(s => (
          <option key={s.id} value={s.id}>{s.symbol} — {s.strategy} ({s.mode}) — {new Date(s.created_at).toLocaleDateString()}</option>
        ))}
      </select>
      {pnl && trades.length > 0 && (<>
        <PnLChart trades={trades} />
        <ComparisonView trades={trades} summary={pnl} />
        <h3>Trade Log</h3>
        <TradeLog trades={trades} />
      </>)}
    </div>
  );
}
