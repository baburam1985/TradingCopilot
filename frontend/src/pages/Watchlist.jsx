import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSessions, getPnl, stopSession } from "../api/client";
import PageHeader from "../components/PageHeader";

const POLL_INTERVAL_MS = 10_000;

function modeBadge(mode) {
  const isPaper = mode === "paper" || mode === "alpaca_paper";
  return (
    <span
      className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
        isPaper ? "bg-[#1e3a2e] text-[#00e676]" : "bg-[#3a1e1e] text-[#ff4444]"
      }`}
    >
      {isPaper ? "Paper" : "Live"}
    </span>
  );
}

function statusBadge(status) {
  const map = {
    active: "text-[#00e676]",
    paused: "text-[#f0a500]",
    closed: "text-[#888]",
  };
  return (
    <span className={`text-xs font-semibold uppercase ${map[status] ?? "text-[#888]"}`}>
      {status}
    </span>
  );
}

function SessionCard({ session, pnl, onStop }) {
  const navigate = useNavigate();
  const totalPnl = pnl?.total_pnl != null ? parseFloat(pnl.total_pnl) : null;
  const winRate = pnl?.win_rate != null ? `${(parseFloat(pnl.win_rate) * 100).toFixed(0)}%` : "—";
  const pnlPositive = totalPnl !== null && totalPnl > 0;
  const pnlNegative = totalPnl !== null && totalPnl < 0;

  return (
    <div
      data-testid="session-card"
      className="bg-[#141414] border border-[#1e1e1e] rounded p-4 flex flex-col gap-3"
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-white font-bold text-xl tracking-wider">{session.symbol}</span>
        <div className="flex items-center gap-2">
          {modeBadge(session.mode)}
          {statusBadge(session.status)}
        </div>
      </div>

      {/* Strategy */}
      <div className="text-[#888] text-xs">
        Strategy: <span className="text-[#aaa]">{session.strategy}</span>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-[#555] text-[10px] uppercase tracking-wider">P&amp;L</span>
          <span
            data-testid="pnl-value"
            className={`text-sm font-semibold ${
              pnlPositive ? "text-[#00e676]" : pnlNegative ? "text-[#ff4444]" : "text-[#888]"
            }`}
          >
            {totalPnl !== null ? `$${totalPnl.toFixed(2)}` : "—"}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[#555] text-[10px] uppercase tracking-wider">Win Rate</span>
          <span className="text-sm font-semibold text-white">{winRate}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => navigate(`/dashboard/${session.id}`)}
          className="flex-1 text-xs font-semibold py-1.5 rounded bg-[#1e1e1e] text-[#00e676] hover:bg-[#252525] transition-colors border border-[#00e676]/30"
        >
          View
        </button>
        {session.status === "active" && (
          <button
            onClick={() => onStop(session.id)}
            className="flex-1 text-xs font-semibold py-1.5 rounded bg-[#1e1e1e] text-[#ff4444] hover:bg-[#252525] transition-colors border border-[#ff4444]/30"
          >
            Stop
          </button>
        )}
      </div>
    </div>
  );
}

export default function Watchlist() {
  const [sessions, setSessions] = useState([]);
  const [pnlMap, setPnlMap] = useState({});
  const [loading, setLoading] = useState(true);

  function fetchSessions() {
    getSessions()
      .then((r) => setSessions(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  function fetchPnl(sessionList) {
    sessionList.forEach((s) => {
      getPnl(s.id)
        .then((r) => setPnlMap((prev) => ({ ...prev, [s.id]: r.data.all_time ?? null })))
        .catch(() => setPnlMap((prev) => ({ ...prev, [s.id]: null })));
    });
  }

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (sessions.length > 0) fetchPnl(sessions);
  }, [sessions]);

  async function handleStop(sessionId) {
    await stopSession(sessionId);
    fetchSessions();
  }

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › WATCHLIST"
        title="Session Watchlist"
        subtitle="All active trading sessions — refreshes every 10s"
      />

      {loading && (
        <div className="text-[#888] text-sm mt-8 text-center">Loading sessions…</div>
      )}

      {!loading && sessions.length === 0 && (
        <div className="text-[#888] text-sm mt-8 text-center">
          No sessions found. Start a new session to see it here.
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-6">
        {sessions.map((s) => (
          <SessionCard
            key={s.id}
            session={s}
            pnl={pnlMap[s.id]}
            onStop={handleStop}
          />
        ))}
      </div>
    </div>
  );
}
