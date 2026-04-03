import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getSessions, getTrades, getPnl } from "../api/client";
import PnLChart from "../components/PnLChart";
import TradeLog from "../components/TradeLog";
import ComparisonView from "../components/ComparisonView";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";

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

  // Compute metrics from sessions or backtest
  const totalSessions = backtestResult ? 1 : sessions.length;
  const rawPnl = pnl?.total_pnl != null
    ? parseFloat(pnl.total_pnl)
    : backtestResult
    ? backtestResult.trades.reduce((sum, t) => sum + parseFloat(t.pnl ?? 0), 0)
    : null;
  const totalPnl = rawPnl != null ? `$${rawPnl.toFixed(2)}` : "—";
  const avgWinRate = pnl?.win_rate != null
    ? `${(parseFloat(pnl.win_rate) * 100).toFixed(0)}%`
    : "—";

  if (backtestResult) {
    return (
      <div className="p-6">
        <PageHeader
          breadcrumb="HOME › REPORTS › BACKTEST"
          title="Backtest Results"
          subtitle="Historical simulation output"
        />

        <div className="grid grid-cols-3 gap-4 mb-8">
          <MetricCard label="Total Sessions" value={totalSessions} />
          <MetricCard label="Total P&L" value={totalPnl} valueColor={rawPnl != null ? (rawPnl >= 0 ? "green" : "red") : undefined} />
          <MetricCard label="Avg Win Rate" value={avgWinRate} valueColor="green" />
        </div>

        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
          <PnLChart trades={backtestResult.trades} />
          <ComparisonView trades={backtestResult.trades} summary={backtestResult.summary} />
        </div>

        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Trade Log</h2>
          <TradeLog trades={backtestResult.trades} />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › REPORTS"
        title="Reports"
        subtitle="Review session history and performance"
      />

      <div className="grid grid-cols-3 gap-4 mb-8">
        <MetricCard label="Total Sessions" value={totalSessions > 0 ? totalSessions : "—"} />
        <MetricCard
          label="Total P&L"
          value={totalPnl}
          valueColor={rawPnl != null ? (rawPnl >= 0 ? "green" : "red") : undefined}
        />
        <MetricCard label="Avg Win Rate" value={avgWinRate} valueColor={avgWinRate !== "—" ? "green" : undefined} />
      </div>

      {/* Session history list */}
      <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
        <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Session History</h2>
        <select
          className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors mb-4"
          value={selectedId || ""}
          onChange={e => setSelectedId(e.target.value)}
        >
          <option value="">Select a session...</option>
          {sessions.map(s => (
            <option key={s.id} value={s.id}>
              {s.symbol} — {s.strategy} ({s.mode}) — {new Date(s.created_at).toLocaleDateString()}
            </option>
          ))}
        </select>

        {sessions.length > 0 && (
          <div className="flex flex-col gap-2">
            {sessions.map(s => {
              const isSelected = s.id === selectedId;
              return (
                <div
                  key={s.id}
                  onClick={() => setSelectedId(s.id)}
                  className={`flex items-center justify-between px-4 py-3 rounded border cursor-pointer transition-colors ${
                    isSelected
                      ? "border-[#00e676] bg-[#0a0a0a]"
                      : "border-[#1e1e1e] hover:border-[#333] hover:bg-[#1a1a1a]"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="bg-[#00e676] text-black text-xs font-bold px-2 py-0.5 rounded">
                      {s.symbol}
                    </span>
                    <span className="text-white text-sm">{s.strategy}</span>
                    <span className="text-[#555] text-xs">{s.mode}</span>
                  </div>
                  <span className="text-[#555] text-xs">{new Date(s.created_at).toLocaleDateString()}</span>
                </div>
              );
            })}
          </div>
        )}

        {sessions.length === 0 && (
          <p className="text-[#555] text-sm">No sessions found.</p>
        )}
      </div>

      {pnl && trades.length > 0 && (
        <>
          <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
            <PnLChart trades={trades} />
            <ComparisonView trades={trades} summary={pnl} />
          </div>
          <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Trade Log</h2>
            <TradeLog trades={trades} />
          </div>
        </>
      )}
    </div>
  );
}
