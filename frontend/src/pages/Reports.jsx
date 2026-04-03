import { useEffect, useState, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { getSessions, getTrades, getPnl, getEquityCurve, exportJournal } from "../api/client";
import PnLChart from "../components/PnLChart";
import EquityCurveChart from "../components/EquityCurveChart";
import MultiEquityCurveChart from "../components/MultiEquityCurveChart";
import StrategyComparisonChart from "../components/StrategyComparisonChart";
import TradeLog from "../components/TradeLog";
import ComparisonView from "../components/ComparisonView";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";

// ---------------------------------------------------------------------------
// Analytics tab
// ---------------------------------------------------------------------------

const MAX_COMPARE = 3;

function AnalyticsTab({ sessions }) {
  // Keyed by session id: pnl data or null while loading
  const [pnlMap, setPnlMap] = useState({});
  // Selected session ids for equity-curve comparison (max 3)
  const [selectedIds, setSelectedIds] = useState([]);
  // Equity curves keyed by session id
  const [curveMap, setCurveMap] = useState({});
  // Sort state for the sessions table
  const [sortKey, setSortKey] = useState("pnl");
  const [sortDir, setSortDir] = useState("desc");

  // Load P&L for all sessions on mount
  useEffect(() => {
    sessions.forEach((s) => {
      if (pnlMap[s.id] !== undefined) return;
      getPnl(s.id)
        .then((r) => setPnlMap((prev) => ({ ...prev, [s.id]: r.data.all_time ?? null })))
        .catch(() => setPnlMap((prev) => ({ ...prev, [s.id]: null })));
    });
  }, [sessions]); // eslint-disable-line react-hooks/exhaustive-deps

  // Lazily load equity curves when sessions are selected
  useEffect(() => {
    selectedIds.forEach((id) => {
      if (curveMap[id] !== undefined) return;
      getEquityCurve(id)
        .then((r) => setCurveMap((prev) => ({ ...prev, [id]: r.data })))
        .catch(() => setCurveMap((prev) => ({ ...prev, [id]: [] })));
    });
  }, [selectedIds]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- Summary metrics ----------
  const totalSessions = sessions.length;

  const totalPnlRaw = useMemo(() => {
    return Object.values(pnlMap).reduce((sum, p) => {
      const v = p?.total_pnl != null ? parseFloat(p.total_pnl) : 0;
      return sum + v;
    }, 0);
  }, [pnlMap]);

  const bestStrategy = useMemo(() => {
    const byStrategy = {};
    sessions.forEach((s) => {
      const p = pnlMap[s.id];
      const val = p?.total_pnl != null ? parseFloat(p.total_pnl) : 0;
      byStrategy[s.strategy] = (byStrategy[s.strategy] ?? 0) + val;
    });
    const entries = Object.entries(byStrategy);
    if (!entries.length) return "—";
    return entries.reduce((best, cur) => (cur[1] > best[1] ? cur : best), entries[0])[0];
  }, [sessions, pnlMap]);

  const overallWinRate = useMemo(() => {
    const entries = sessions
      .map((s) => pnlMap[s.id])
      .filter((p) => p?.win_rate != null);
    if (!entries.length) return null;
    const avg = entries.reduce((sum, p) => sum + parseFloat(p.win_rate), 0) / entries.length;
    return avg;
  }, [sessions, pnlMap]);

  // ---------- Sortable table ----------
  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sortedSessions = useMemo(() => {
    const copy = [...sessions];
    copy.sort((a, b) => {
      let av, bv;
      if (sortKey === "pnl") {
        av = parseFloat(pnlMap[a.id]?.total_pnl ?? 0);
        bv = parseFloat(pnlMap[b.id]?.total_pnl ?? 0);
      } else if (sortKey === "win_rate") {
        av = parseFloat(pnlMap[a.id]?.win_rate ?? 0);
        bv = parseFloat(pnlMap[b.id]?.win_rate ?? 0);
      } else if (sortKey === "capital") {
        av = parseFloat(a.capital ?? 0);
        bv = parseFloat(b.capital ?? 0);
      } else if (sortKey === "date") {
        av = new Date(a.created_at).getTime();
        bv = new Date(b.created_at).getTime();
      } else if (sortKey === "symbol") {
        av = a.symbol ?? "";
        bv = b.symbol ?? "";
      } else if (sortKey === "strategy") {
        av = a.strategy ?? "";
        bv = b.strategy ?? "";
      } else if (sortKey === "status") {
        av = a.status ?? "";
        bv = b.status ?? "";
      } else {
        return 0;
      }
      if (typeof av === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? av - bv : bv - av;
    });
    return copy;
  }, [sessions, pnlMap, sortKey, sortDir]);

  // ---------- Selection handling ----------
  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= MAX_COMPARE) return prev; // max 3
      return [...prev, id];
    });
  };

  // Build multi-series data for comparison chart
  const comparisonSeries = useMemo(() => {
    return selectedIds
      .filter((id) => Array.isArray(curveMap[id]) && curveMap[id].length >= 2)
      .map((id) => {
        const s = sessions.find((x) => x.id === id);
        return {
          label: s ? `${s.symbol} — ${s.strategy}` : id,
          points: curveMap[id],
        };
      });
  }, [selectedIds, curveMap, sessions]);

  // ---------- Column header helper ----------
  const SortableHeader = ({ colKey, label }) => {
    const active = sortKey === colKey;
    const arrow = active ? (sortDir === "asc" ? " ▲" : " ▼") : "";
    return (
      <th
        className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-left cursor-pointer hover:text-[#aaa] select-none whitespace-nowrap"
        onClick={() => handleSort(colKey)}
      >
        {label}{arrow}
      </th>
    );
  };

  return (
    <div>
      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <MetricCard
          label="Total Sessions"
          value={totalSessions > 0 ? totalSessions : "—"}
        />
        <MetricCard
          label="Total P&L"
          value={`$${totalPnlRaw.toFixed(2)}`}
          valueColor={totalPnlRaw >= 0 ? "green" : "red"}
        />
        <MetricCard label="Best Strategy" value={bestStrategy} />
        <MetricCard
          label="Overall Win Rate"
          value={overallWinRate != null ? `${(overallWinRate * 100).toFixed(0)}%` : "—"}
          valueColor={overallWinRate != null ? "green" : undefined}
        />
      </div>

      {/* Sessions table */}
      <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
        <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
          Sessions
          {selectedIds.length > 0 && (
            <span className="ml-2 text-[#888] normal-case">
              ({selectedIds.length}/{MAX_COMPARE} selected for comparison)
            </span>
          )}
        </h2>

        {sessions.length === 0 ? (
          <p className="text-[#555] text-sm">No sessions found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e1e1e]">
                  {/* checkbox column */}
                  <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-left w-8">
                    CMP
                  </th>
                  <SortableHeader colKey="symbol" label="Symbol" />
                  <SortableHeader colKey="strategy" label="Strategy" />
                  <SortableHeader colKey="capital" label="Capital" />
                  <SortableHeader colKey="pnl" label="P&L" />
                  <SortableHeader colKey="win_rate" label="Win Rate" />
                  <SortableHeader colKey="status" label="Status" />
                  <SortableHeader colKey="date" label="Date" />
                </tr>
              </thead>
              <tbody>
                {sortedSessions.map((s) => {
                  const p = pnlMap[s.id];
                  const pnlVal = p?.total_pnl != null ? parseFloat(p.total_pnl) : null;
                  const winRate = p?.win_rate != null ? parseFloat(p.win_rate) : null;
                  const isChecked = selectedIds.includes(s.id);
                  const canCheck = isChecked || selectedIds.length < MAX_COMPARE;
                  return (
                    <tr
                      key={s.id}
                      className="border-b border-[#1e1e1e] hover:bg-[#1a1a1a] transition-colors"
                    >
                      <td className="py-2 px-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          disabled={!canCheck}
                          onChange={() => toggleSelect(s.id)}
                          className="accent-[#00e676] cursor-pointer disabled:cursor-not-allowed"
                        />
                      </td>
                      <td className="py-2 px-3">
                        <span className="bg-[#00e676] text-black text-xs font-bold px-2 py-0.5 rounded">
                          {s.symbol}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-[#e0e0e0]">{s.strategy}</td>
                      <td className="py-2 px-3 text-[#e0e0e0]">
                        {s.capital != null ? `$${parseFloat(s.capital).toFixed(2)}` : "—"}
                      </td>
                      <td className="py-2 px-3 font-semibold">
                        {pnlVal != null ? (
                          <span className={pnlVal >= 0 ? "text-[#00e676]" : "text-red-400"}>
                            {pnlVal >= 0 ? "+" : ""}${pnlVal.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-[#555]">—</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-[#e0e0e0]">
                        {winRate != null ? `${(winRate * 100).toFixed(0)}%` : "—"}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`text-xs font-medium ${
                            s.status === "active"
                              ? "text-[#00e676]"
                              : s.status === "stopped"
                              ? "text-red-400"
                              : "text-[#888]"
                          }`}
                        >
                          {s.status ?? "—"}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-[#888] text-xs">
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Equity curve comparison */}
      {selectedIds.length >= 2 && (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
            Equity Curve Comparison
          </h2>
          {comparisonSeries.length < 2 ? (
            <p className="text-[#555] text-xs text-center py-8">
              Loading equity curves…
            </p>
          ) : (
            <MultiEquityCurveChart series={comparisonSeries} />
          )}
        </div>
      )}

      {selectedIds.length === 1 && (
        <p className="text-[#555] text-xs mt-2">
          Select at least 2 sessions to enable equity curve comparison.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Reports page
// ---------------------------------------------------------------------------

const TABS = ["ANALYTICS", "SESSION REPORT"];

export default function Reports() {
  const location = useLocation();
  const backtestResult = location.state?.backtestResult;
  const compareResult = location.state?.compareResult;

  const [activeTab, setActiveTab] = useState("ANALYTICS");

  // Session-report tab state
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [trades, setTrades] = useState([]);
  const [pnl, setPnl] = useState(null);
  const [equityCurve, setEquityCurve] = useState([]);
  const [exportingJournal, setExportingJournal] = useState(false);

  useEffect(() => {
    if (backtestResult) return;
    getSessions().then((r) => setSessions(r.data));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([
      getTrades(selectedId),
      getPnl(selectedId),
      getEquityCurve(selectedId),
    ]).then(([t, p, ec]) => {
      setTrades(t.data);
      setPnl(p.data.all_time);
      setEquityCurve(ec.data);
    });
  }, [selectedId]);

  const handleExportJournal = async () => {
    if (!selectedId) return;
    setExportingJournal(true);
    try {
      const r = await exportJournal(selectedId);
      const url = URL.createObjectURL(new Blob([r.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `journal_${selectedId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    } finally {
      setExportingJournal(false);
    }
  };

  const sessionIndex = sessions.findIndex((s) => s.id === selectedId);
  const hasPrev = sessionIndex > 0;
  const hasNext = sessionIndex >= 0 && sessionIndex < sessions.length - 1;
  const goToPrev = () => hasPrev && setSelectedId(sessions[sessionIndex - 1].id);
  const goToNext = () => hasNext && setSelectedId(sessions[sessionIndex + 1].id);

  // Session-report derived metrics
  const totalSessions = backtestResult ? 1 : sessions.length;
  const rawPnl =
    pnl?.total_pnl != null
      ? parseFloat(pnl.total_pnl)
      : backtestResult
      ? backtestResult.trades.reduce((sum, t) => sum + parseFloat(t.pnl ?? 0), 0)
      : null;
  const totalPnl = rawPnl != null ? `$${rawPnl.toFixed(2)}` : "—";
  const avgWinRate =
    pnl?.win_rate != null ? `${(parseFloat(pnl.win_rate) * 100).toFixed(0)}%` : "—";

  const fmt2 = (v) => (v != null ? v.toFixed(2) : "—");
  const sharpeDisplay = pnl?.sharpe_ratio != null ? fmt2(pnl.sharpe_ratio) : "—";
  const sortinoDisplay = pnl?.sortino_ratio != null ? fmt2(pnl.sortino_ratio) : "—";
  const maxDdDisplay =
    pnl?.max_drawdown_pct != null ? `${pnl.max_drawdown_pct.toFixed(2)}%` : "—";
  const calmarDisplay = pnl?.calmar_ratio != null ? fmt2(pnl.calmar_ratio) : "—";
  const pfDisplay = pnl?.profit_factor != null ? fmt2(pnl.profit_factor) : "—";

  // ---------- Early-exit routes (backtest / compare) ----------
  if (compareResult) {
    return (
      <div className="p-6">
        <PageHeader
          breadcrumb="HOME › REPORTS › COMPARE"
          title="Strategy Comparison"
          subtitle="Side-by-side performance across strategies"
        />
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <StrategyComparisonChart results={compareResult} />
        </div>
      </div>
    );
  }

  if (backtestResult) {
    const backtestStartingCapital = backtestResult.summary?.starting_capital ?? 1000;
    const backtestEquityCurve = (() => {
      const closed = backtestResult.trades
        .filter((t) => t.status === "closed" && t.pnl != null && t.timestamp_close)
        .sort((a, b) => new Date(a.timestamp_close) - new Date(b.timestamp_close));
      const points = [
        {
          timestamp: closed[0]?.timestamp_open ?? new Date().toISOString(),
          portfolio_value: backtestStartingCapital,
        },
      ];
      let cum = backtestStartingCapital;
      for (const t of closed) {
        cum += parseFloat(t.pnl);
        points.push({
          timestamp: t.timestamp_close,
          portfolio_value: Math.round(cum * 10000) / 10000,
        });
      }
      return points;
    })();

    return (
      <div className="p-6">
        <PageHeader
          breadcrumb="HOME › REPORTS › BACKTEST"
          title="Backtest Results"
          subtitle="Historical simulation output"
        />
        <div className="overflow-x-auto mb-8 -mx-6 px-6 sm:mx-0 sm:px-0">
          <div className="grid grid-cols-3 gap-4 min-w-[360px] sm:min-w-0">
            <MetricCard label="Total Sessions" value={totalSessions} />
            <MetricCard
              label="Total P&L"
              value={totalPnl}
              valueColor={rawPnl != null ? (rawPnl >= 0 ? "green" : "red") : undefined}
            />
            <MetricCard label="Avg Win Rate" value={avgWinRate} valueColor="green" />
          </div>
        </div>
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
            Equity Curve
          </h2>
          <EquityCurveChart
            points={backtestEquityCurve}
            startingCapital={backtestStartingCapital}
          />
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

  // ---------- Normal Reports view with tabs ----------
  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › REPORTS"
        title="Reports"
        subtitle="Review session history and performance"
      />

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-[#1e1e1e]">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-xs uppercase tracking-widest font-bold rounded-t transition-colors ${
              activeTab === tab
                ? "bg-[#00e676] text-[#0d0d0d]"
                : "text-[#666] hover:text-[#e0e0e0]"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab: Analytics */}
      {activeTab === "ANALYTICS" && <AnalyticsTab sessions={sessions} />}

      {/* Tab: Session Report (existing content, unchanged) */}
      {activeTab === "SESSION REPORT" && (
        <>
          <div className="overflow-x-auto mb-8 -mx-6 px-6 sm:mx-0 sm:px-0">
            <div className="grid grid-cols-3 gap-4 min-w-[360px] sm:min-w-0">
              <MetricCard
                label="Total Sessions"
                value={totalSessions > 0 ? totalSessions : "—"}
              />
              <MetricCard
                label="Total P&L"
                value={totalPnl}
                valueColor={rawPnl != null ? (rawPnl >= 0 ? "green" : "red") : undefined}
              />
              <MetricCard
                label="Avg Win Rate"
                value={avgWinRate}
                valueColor={avgWinRate !== "—" ? "green" : undefined}
              />
            </div>
          </div>

          {/* Session history list */}
          <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
              Session History
            </h2>
            <select
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors mb-4"
              value={selectedId || ""}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              <option value="">Select a session...</option>
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.symbol} — {s.strategy} ({s.mode}) —{" "}
                  {new Date(s.created_at).toLocaleDateString()}
                </option>
              ))}
            </select>

            {sessions.length > 0 && (
              <div className="flex flex-col gap-2">
                {sessions.map((s) => {
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
                      <span className="text-[#555] text-xs">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
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
                <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
                  Advanced Metrics
                </h2>
                <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
                <div className="grid grid-cols-5 gap-4 min-w-[540px] sm:min-w-0">
                  <MetricCard label="Sharpe Ratio" value={sharpeDisplay} />
                  <MetricCard label="Sortino Ratio" value={sortinoDisplay} />
                  <MetricCard
                    label="Max Drawdown"
                    value={maxDdDisplay}
                    valueColor={pnl.max_drawdown_pct > 0 ? "red" : undefined}
                  />
                  <MetricCard label="Calmar Ratio" value={calmarDisplay} />
                  <MetricCard
                    label="Profit Factor"
                    value={pfDisplay}
                    valueColor={
                      pnl.profit_factor != null
                        ? pnl.profit_factor >= 1
                          ? "green"
                          : "red"
                        : undefined
                    }
                  />
                </div>
                </div>
              </div>
              <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
                <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
                  Equity Curve
                </h2>
                <EquityCurveChart
                  points={equityCurve}
                  startingCapital={parseFloat(pnl.starting_capital)}
                />
              </div>
              <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
                <PnLChart trades={trades} />
                <ComparisonView trades={trades} summary={pnl} />
              </div>
              <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[#00e676] text-xs uppercase tracking-widest">Trade Log</h2>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={goToPrev}
                      disabled={!hasPrev}
                      className="text-xs px-2 py-1 border border-[#333] rounded text-[#888] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      ← Prev Session
                    </button>
                    <button
                      onClick={goToNext}
                      disabled={!hasNext}
                      className="text-xs px-2 py-1 border border-[#333] rounded text-[#888] hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      Next Session →
                    </button>
                    <button
                      onClick={handleExportJournal}
                      disabled={exportingJournal || !selectedId}
                      className="text-xs px-3 py-1 bg-[#00e676] text-[#0d0d0d] font-bold rounded hover:bg-[#00c853] disabled:opacity-50"
                    >
                      {exportingJournal ? "Exporting…" : "Export Journal"}
                    </button>
                  </div>
                </div>
                <TradeLog trades={trades} />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
