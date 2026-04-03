import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSessions, getSessionSummary, getTrades, exportJournal } from "../api/client";
import PageHeader from "../components/PageHeader";
import TradeLog from "../components/TradeLog";
import PnLChart from "../components/PnLChart";

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric",
  });
}

function pnlColor(value) {
  if (value > 0) return "text-[#00e676]";
  if (value < 0) return "text-[#ff4444]";
  return "text-white";
}

// Group sessions by date label
function groupByDate(sessions) {
  const groups = {};
  for (const s of sessions) {
    const label = formatDate(s.created_at);
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  }
  return groups;
}

export default function SessionHistory() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [filterStrategy, setFilterStrategy] = useState("");
  const [filterSymbol, setFilterSymbol] = useState("");
  const [filterFromDate, setFilterFromDate] = useState("");
  const [filterToDate, setFilterToDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  // Drill-down state: { sessionId, trades, summary, loadingDetail }
  const [expanded, setExpanded] = useState(null);

  function buildFilters() {
    const f = {};
    if (filterStrategy) f.strategy = filterStrategy;
    if (filterSymbol) f.symbol = filterSymbol.trim().toUpperCase();
    if (filterFromDate) f.from_date = filterFromDate;
    if (filterToDate) f.to_date = filterToDate;
    if (filterStatus) f.status = filterStatus;
    return f;
  }

  function load(filters = {}) {
    setLoading(true);
    setError(null);
    getSessions(filters)
      .then((r) => setSessions(r.data))
      .catch(() => setError("Failed to load sessions."))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleApplyFilters(e) {
    e.preventDefault();
    setExpanded(null);
    load(buildFilters());
  }

  function handleClearFilters() {
    setFilterStrategy("");
    setFilterSymbol("");
    setFilterFromDate("");
    setFilterToDate("");
    setFilterStatus("");
    setExpanded(null);
    load({});
  }

  async function handleExpandRow(session) {
    if (expanded?.sessionId === session.id) {
      setExpanded(null);
      return;
    }
    setExpanded({ sessionId: session.id, trades: null, summary: null, loadingDetail: true });
    try {
      const [tradesRes, summaryRes] = await Promise.all([
        getTrades(session.id),
        getSessionSummary(session.id),
      ]);
      setExpanded({
        sessionId: session.id,
        trades: tradesRes.data,
        summary: summaryRes.data,
        loadingDetail: false,
      });
    } catch {
      setExpanded({ sessionId: session.id, trades: [], summary: null, loadingDetail: false });
    }
  }

  function handleReplay(session) {
    navigate("/", {
      state: {
        replay: {
          symbol: session.symbol,
          strategy: session.strategy,
          starting_capital: session.starting_capital,
        },
      },
    });
  }

  async function handleExport(sessionId, e) {
    e.stopPropagation();
    try {
      const res = await exportJournal(sessionId);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `journal_${sessionId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently ignore
    }
  }

  const grouped = groupByDate(sessions);

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <PageHeader breadcrumb="History" title="Session History" subtitle="Review, filter, and replay past trading sessions." />

      {/* Filters */}
      <form
        onSubmit={handleApplyFilters}
        className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6"
      >
        <div className="flex flex-col gap-1">
          <label className="text-[#888] text-xs uppercase tracking-wide">Strategy</label>
          <input
            className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
            placeholder="e.g. rsi"
            value={filterStrategy}
            onChange={(e) => setFilterStrategy(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[#888] text-xs uppercase tracking-wide">Symbol</label>
          <input
            className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] uppercase"
            placeholder="e.g. AAPL"
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[#888] text-xs uppercase tracking-wide">From Date</label>
          <input
            type="date"
            className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] [color-scheme:dark]"
            value={filterFromDate}
            onChange={(e) => setFilterFromDate(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[#888] text-xs uppercase tracking-wide">To Date</label>
          <input
            type="date"
            className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] [color-scheme:dark]"
            value={filterToDate}
            onChange={(e) => setFilterToDate(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[#888] text-xs uppercase tracking-wide">Status</label>
          <select
            className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        <div className="col-span-2 sm:col-span-3 lg:col-span-5 flex gap-2">
          <button
            type="submit"
            className="bg-[#00e676] text-black font-semibold text-sm px-4 py-2 rounded hover:bg-[#00c85d] transition-colors"
          >
            Apply Filters
          </button>
          <button
            type="button"
            onClick={handleClearFilters}
            className="bg-[#1e1e1e] text-[#888] text-sm px-4 py-2 rounded hover:text-white hover:bg-[#2a2a2a] transition-colors"
          >
            Clear
          </button>
        </div>
      </form>

      {/* Content */}
      {loading && (
        <p className="text-[#555] text-sm">Loading sessions...</p>
      )}
      {error && (
        <p className="text-[#ff4444] text-sm">{error}</p>
      )}
      {!loading && !error && sessions.length === 0 && (
        <p className="text-[#555] text-sm">No sessions match the current filters.</p>
      )}

      {!loading && !error && sessions.length > 0 && (
        <div className="space-y-6">
          {Object.entries(grouped).map(([dateLabel, group]) => (
            <div key={dateLabel}>
              <p className="text-[#555] text-xs uppercase tracking-widest mb-2">{dateLabel}</p>
              <div className="border border-[#1e1e1e] rounded overflow-hidden">
                {/* Table header */}
                <div className="hidden sm:grid grid-cols-[1fr_80px_100px_80px_70px_80px_100px] gap-2 px-4 py-2 bg-[#141414] text-[#555] text-xs uppercase tracking-wide">
                  <span>Symbol / Strategy</span>
                  <span>Capital</span>
                  <span>Duration</span>
                  <span>Trades</span>
                  <span>Win %</span>
                  <span>P&L</span>
                  <span>Status</span>
                </div>

                {group.map((session, idx) => {
                  const isExpanded = expanded?.sessionId === session.id;
                  return (
                    <div key={session.id} className={idx > 0 ? "border-t border-[#1e1e1e]" : ""}>
                      {/* Row */}
                      <button
                        onClick={() => handleExpandRow(session)}
                        className="w-full text-left px-4 py-3 hover:bg-[#141414] transition-colors"
                      >
                        {/* Mobile layout */}
                        <div className="sm:hidden flex justify-between items-start">
                          <div>
                            <span className="text-white font-semibold">{session.symbol}</span>
                            <span className="text-[#888] text-xs ml-2">{session.strategy}</span>
                          </div>
                          <span className={`text-sm font-semibold ${session.status === "active" ? "text-[#00e676]" : "text-[#555]"}`}>
                            {session.status}
                          </span>
                        </div>

                        {/* Desktop grid layout */}
                        <div className="hidden sm:grid grid-cols-[1fr_80px_100px_80px_70px_80px_100px] gap-2 items-center text-sm">
                          <div>
                            <span className="text-white font-semibold">{session.symbol}</span>
                            <span className="text-[#888] ml-2 text-xs">{session.strategy}</span>
                          </div>
                          <span className="text-[#aaa]">${session.starting_capital.toLocaleString()}</span>
                          <span className="text-[#aaa]">
                            {session.closed_at
                              ? formatDuration(Math.floor((new Date(session.closed_at) - new Date(session.created_at)) / 1000))
                              : "—"}
                          </span>
                          <span className="text-[#aaa]">—</span>
                          <span className="text-[#aaa]">—</span>
                          <span className="text-[#aaa]">—</span>
                          <span className={session.status === "active" ? "text-[#00e676]" : "text-[#555]"}>
                            {session.status}
                          </span>
                        </div>
                      </button>

                      {/* Expanded drill-down */}
                      {isExpanded && (
                        <div className="border-t border-[#1e1e1e] bg-[#0d0d0d] px-4 py-4">
                          {expanded.loadingDetail ? (
                            <p className="text-[#555] text-sm">Loading details...</p>
                          ) : (
                            <>
                              {/* Summary metrics */}
                              {expanded.summary && (
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                                  <div className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2">
                                    <p className="text-[#888] text-xs uppercase tracking-wide mb-1">Total P&L</p>
                                    <p className={`text-lg font-bold ${pnlColor(expanded.summary.total_pnl)}`}>
                                      ${expanded.summary.total_pnl?.toFixed(2) ?? "—"}
                                    </p>
                                  </div>
                                  <div className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2">
                                    <p className="text-[#888] text-xs uppercase tracking-wide mb-1">Win Rate</p>
                                    <p className="text-white text-lg font-bold">
                                      {expanded.summary.win_rate != null
                                        ? `${(expanded.summary.win_rate * 100).toFixed(0)}%`
                                        : "—"}
                                    </p>
                                  </div>
                                  <div className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2">
                                    <p className="text-[#888] text-xs uppercase tracking-wide mb-1">Trades</p>
                                    <p className="text-white text-lg font-bold">{expanded.summary.num_trades ?? "—"}</p>
                                  </div>
                                  <div className="bg-[#141414] border border-[#1e1e1e] rounded px-3 py-2">
                                    <p className="text-[#888] text-xs uppercase tracking-wide mb-1">Duration</p>
                                    <p className="text-white text-lg font-bold">
                                      {expanded.summary.duration_seconds != null
                                        ? formatDuration(expanded.summary.duration_seconds)
                                        : "—"}
                                    </p>
                                  </div>
                                </div>
                              )}

                              {/* P&L chart */}
                              {expanded.trades && expanded.trades.length > 0 && (
                                <div className="mb-4">
                                  <p className="text-[#555] text-xs uppercase tracking-wide mb-2">Trade P&L</p>
                                  <PnLChart trades={expanded.trades} />
                                </div>
                              )}

                              {/* Trade log */}
                              {expanded.trades && expanded.trades.length > 0 && (
                                <div className="mb-4">
                                  <p className="text-[#555] text-xs uppercase tracking-wide mb-2">Trade Log</p>
                                  <TradeLog trades={expanded.trades} />
                                </div>
                              )}

                              {expanded.trades && expanded.trades.length === 0 && (
                                <p className="text-[#555] text-sm mb-4">No trades recorded for this session.</p>
                              )}

                              {/* Actions */}
                              <div className="flex gap-2 flex-wrap">
                                <button
                                  onClick={() => handleReplay(session)}
                                  className="bg-[#00e676] text-black font-semibold text-xs px-3 py-1.5 rounded hover:bg-[#00c85d] transition-colors"
                                >
                                  Replay
                                </button>
                                <button
                                  onClick={(e) => handleExport(session.id, e)}
                                  className="bg-[#1e1e1e] text-[#888] text-xs px-3 py-1.5 rounded hover:text-white hover:bg-[#2a2a2a] transition-colors"
                                >
                                  Export CSV
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
