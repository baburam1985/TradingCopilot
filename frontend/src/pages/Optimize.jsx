import { useState, useEffect } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Cell,
} from "recharts";
import { getStrategies, runOptimize, runWalkForward } from "../api/client";
import PageHeader from "../components/PageHeader";
import OptimizeHeatmap from "../components/OptimizeHeatmap";

// ---------------------------------------------------------------------------
// Optimizer helpers
// ---------------------------------------------------------------------------

const MAX_COMBINATIONS = 100;

function countCombinations(paramRanges) {
  return Object.values(paramRanges).reduce((acc, vals) => acc * (vals.length || 1), 1);
}

function parseRangeInput(raw) {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s !== "")
    .map((s) => {
      const n = Number(s);
      return isNaN(n) ? s : n;
    });
}

// ---------------------------------------------------------------------------
// Shared field styles
// ---------------------------------------------------------------------------

const inputCls =
  "w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors";
const labelCls = "block text-[#888] text-xs mb-1 uppercase tracking-wider";

// ---------------------------------------------------------------------------
// Walk-Forward tab
// ---------------------------------------------------------------------------

function WalkForwardTab({ strategies }) {
  const [selectedStrategy, setSelectedStrategy] = useState(strategies[0] || null);
  const [form, setForm] = useState({
    symbol: "",
    strategy: strategies[0]?.name ?? "",
    start_date: "",
    end_date: "",
    starting_capital: 1000,
    train_window_days: 60,
    test_window_days: 20,
    step_days: 10,
  });
  // param grid: key → comma-separated string
  const [paramGrid, setParamGrid] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // keep paramGrid keys in sync when strategy changes
  useEffect(() => {
    if (!selectedStrategy) return;
    setParamGrid(
      Object.fromEntries(
        Object.entries(selectedStrategy.parameters).map(([k, spec]) => [k, String(spec.default)])
      )
    );
  }, [selectedStrategy]);

  const handleStrategyChange = (e) => {
    const name = e.target.value;
    const strat = strategies.find((s) => s.name === name);
    setForm((f) => ({ ...f, strategy: name }));
    setSelectedStrategy(strat || null);
    setResult(null);
    setError(null);
  };

  const buildParamGridPayload = () => {
    if (!selectedStrategy) return {};
    const grid = {};
    for (const [key, raw] of Object.entries(paramGrid)) {
      const vals = parseRangeInput(raw);
      if (vals.length > 1) grid[key] = vals;
    }
    return grid;
  };

  const buildStrategyParams = () => {
    if (!selectedStrategy) return {};
    const params = {};
    for (const [key, raw] of Object.entries(paramGrid)) {
      const vals = parseRangeInput(raw);
      params[key] = vals[0] ?? null;
    }
    return params;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await runWalkForward({
        symbol: form.symbol.trim().toUpperCase(),
        strategy: form.strategy,
        strategy_params: buildStrategyParams(),
        param_grid: buildParamGridPayload(),
        start_date: form.start_date,
        end_date: form.end_date,
        starting_capital: Number(form.starting_capital),
        train_window_days: Number(form.train_window_days),
        test_window_days: Number(form.test_window_days),
        step_days: Number(form.step_days),
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Walk-forward analysis failed. Check inputs and try again.");
    } finally {
      setLoading(false);
    }
  };

  const fmt = (v, d = 2) => (v != null ? Number(v).toFixed(d) : "—");

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-6 mb-8">
        {/* Core inputs */}
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Setup</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className={labelCls}>Symbol</label>
              <input
                required
                type="text"
                placeholder="e.g. AAPL"
                value={form.symbol}
                onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Strategy</label>
              <select
                value={form.strategy}
                onChange={handleStrategyChange}
                className={inputCls}
              >
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelCls}>Starting Capital ($)</label>
              <input
                required
                type="number"
                min="1"
                step="any"
                value={form.starting_capital}
                onChange={(e) => setForm((f) => ({ ...f, starting_capital: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Start Date</label>
              <input
                required
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>End Date</label>
              <input
                required
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                className={inputCls}
              />
            </div>
          </div>
        </div>

        {/* Window configuration */}
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-1">Window Configuration</h2>
          <p className="text-[#555] text-xs mb-4">
            Rolling train/test split to detect overfitting across time.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelCls}>Train Window (days)</label>
              <input
                required
                type="number"
                min="5"
                max="1825"
                value={form.train_window_days}
                onChange={(e) => setForm((f) => ({ ...f, train_window_days: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Test Window (days)</label>
              <input
                required
                type="number"
                min="1"
                max="365"
                value={form.test_window_days}
                onChange={(e) => setForm((f) => ({ ...f, test_window_days: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Step Size (days)</label>
              <input
                required
                type="number"
                min="1"
                max="365"
                value={form.step_days}
                onChange={(e) => setForm((f) => ({ ...f, step_days: e.target.value }))}
                className={inputCls}
              />
            </div>
          </div>
        </div>

        {/* Optional param grid */}
        {selectedStrategy && Object.keys(selectedStrategy.parameters).length > 0 && (
          <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-1">
              Parameter Grid (optional)
            </h2>
            <p className="text-[#555] text-xs mb-4">
              Comma-separated values = optimize on train window. Single value = fixed.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(selectedStrategy.parameters).map(([key, spec]) => (
                <div key={key}>
                  <label className={labelCls}>
                    {key}{" "}
                    <span className="normal-case text-[#444] ml-1">({spec.type})</span>
                  </label>
                  <input
                    type="text"
                    value={paramGrid[key] ?? ""}
                    onChange={(e) =>
                      setParamGrid((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                    placeholder={String(spec.default)}
                    className={inputCls}
                  />
                  {spec.description && (
                    <p className="text-[#444] text-xs mt-0.5">{spec.description}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="bg-[#00e676] text-black font-bold px-6 py-2.5 rounded text-sm uppercase tracking-widest hover:bg-[#00c853] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Running…" : "Run Walk-Forward Analysis"}
        </button>
      </form>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-[#00e676] border-t-transparent rounded-full animate-spin" />
          <span className="ml-3 text-[#888] text-sm">Running walk-forward analysis…</span>
        </div>
      )}

      {result && !loading && (
        <>
          {/* Aggregate summary */}
          <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
              Out-of-Sample Aggregate
            </h2>
            {result.windows.length === 0 ? (
              <p className="text-[#555] text-sm">No windows generated. Try a wider date range or smaller window sizes.</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                {[
                  { label: "Windows", value: result.aggregate.num_windows },
                  {
                    label: "Avg Sharpe",
                    value: fmt(result.aggregate.avg_test_sharpe),
                    color:
                      result.aggregate.avg_test_sharpe != null
                        ? result.aggregate.avg_test_sharpe >= 1
                          ? "text-[#00e676]"
                          : result.aggregate.avg_test_sharpe >= 0
                          ? "text-[#e0e0e0]"
                          : "text-red-400"
                        : "text-[#555]",
                  },
                  {
                    label: "Avg P&L",
                    value:
                      result.aggregate.avg_test_pnl != null
                        ? `${result.aggregate.avg_test_pnl >= 0 ? "+" : ""}$${fmt(result.aggregate.avg_test_pnl)}`
                        : "—",
                    color:
                      result.aggregate.avg_test_pnl != null
                        ? result.aggregate.avg_test_pnl >= 0
                          ? "text-[#00e676]"
                          : "text-red-400"
                        : "text-[#555]",
                  },
                  {
                    label: "Avg Win Rate",
                    value:
                      result.aggregate.avg_test_win_rate != null
                        ? `${(result.aggregate.avg_test_win_rate * 100).toFixed(0)}%`
                        : "—",
                  },
                  {
                    label: "Consistency",
                    value:
                      result.aggregate.consistency_score != null
                        ? `${(result.aggregate.consistency_score * 100).toFixed(0)}%`
                        : "—",
                    color:
                      result.aggregate.consistency_score != null
                        ? result.aggregate.consistency_score >= 0.6
                          ? "text-[#00e676]"
                          : "text-[#888]"
                        : "text-[#555]",
                  },
                  {
                    label: "Train vs Test",
                    value:
                      result.aggregate.avg_train_sharpe != null && result.aggregate.avg_test_sharpe != null
                        ? `${fmt(result.aggregate.avg_train_sharpe)} / ${fmt(result.aggregate.avg_test_sharpe)}`
                        : "—",
                  },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-[#0a0a0a] border border-[#1e1e1e] rounded p-3">
                    <div className="text-[#666] text-xs uppercase tracking-wider mb-1">{label}</div>
                    <div className={`text-lg font-bold ${color ?? "text-[#e0e0e0]"}`}>{value}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Out-of-sample P&L bar chart across windows */}
          {result.windows.length > 0 && (
            <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
              <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
                Out-of-Sample P&L by Window
              </h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={result.windows.map((w) => ({
                    name: `W${w.window_index + 1}`,
                    pnl: w.test_pnl,
                    label: `${w.test_start} → ${w.test_end}`,
                  }))}
                  margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
                >
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10, fill: "#666" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#666" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `$${v.toFixed(0)}`}
                    width={60}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-xs">
                          <div className="text-[#888] mb-1">{d.label}</div>
                          <div className={`font-semibold ${d.pnl >= 0 ? "text-[#00e676]" : "text-red-400"}`}>
                            {d.pnl >= 0 ? "+" : ""}${d.pnl.toFixed(2)}
                          </div>
                        </div>
                      );
                    }}
                  />
                  <ReferenceLine y={0} stroke="#333" strokeWidth={1} />
                  <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                    {result.windows.map((w, i) => (
                      <Cell key={i} fill={w.test_pnl >= 0 ? "#00e676" : "#dc2626"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Per-window table */}
          {result.windows.length > 0 && (
            <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
              <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">
                Per-Window Results
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#1e1e1e]">
                      {[
                        ["#", "text-left"],
                        ["Test Period", "text-left"],
                        ["Best Params", "text-left"],
                        ["Train Sharpe", "text-right"],
                        ["Test Sharpe", "text-right"],
                        ["Test P&L", "text-right"],
                        ["Win Rate", "text-right"],
                        ["Max DD", "text-right"],
                        ["Trades", "text-right"],
                      ].map(([h, align]) => (
                        <th
                          key={h}
                          className={`text-[#666] text-xs uppercase tracking-wider py-2 px-3 ${align} whitespace-nowrap`}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.windows.map((w) => (
                      <tr
                        key={w.window_index}
                        className="border-b border-[#1e1e1e] hover:bg-[#1a1a1a] transition-colors"
                      >
                        <td className="py-2 px-3 text-[#666]">{w.window_index + 1}</td>
                        <td className="py-2 px-3 text-[#888] text-xs whitespace-nowrap">
                          {w.test_start} → {w.test_end}
                        </td>
                        <td className="py-2 px-3">
                          <span className="bg-[#1e1e1e] text-[#e0e0e0] text-xs font-mono px-2 py-1 rounded">
                            {JSON.stringify(w.best_params)}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-[#888]">
                          {fmt(w.train_sharpe)}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          {w.test_sharpe != null ? (
                            <span
                              className={
                                w.test_sharpe >= 1
                                  ? "text-[#00e676]"
                                  : w.test_sharpe >= 0
                                  ? "text-[#e0e0e0]"
                                  : "text-red-400"
                              }
                            >
                              {fmt(w.test_sharpe)}
                            </span>
                          ) : (
                            <span className="text-[#555]">—</span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          <span className={w.test_pnl >= 0 ? "text-[#00e676]" : "text-red-400"}>
                            {w.test_pnl >= 0 ? "+" : ""}${fmt(w.test_pnl)}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-[#e0e0e0]">
                          {(w.test_win_rate * 100).toFixed(0)}%
                        </td>
                        <td className="py-2 px-3 text-right text-[#e0e0e0]">
                          {w.test_max_drawdown_pct != null ? `${fmt(w.test_max_drawdown_pct)}%` : "—"}
                        </td>
                        <td className="py-2 px-3 text-right text-[#e0e0e0]">
                          {w.test_num_trades}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Optimizer tab (original content, unchanged logic)
// ---------------------------------------------------------------------------

function OptimizerTab({ strategies }) {
  const [selectedStrategy, setSelectedStrategy] = useState(strategies[0] || null);
  const [form, setForm] = useState({
    symbol: "",
    strategy: strategies[0]?.name ?? "",
    start_date: "",
    end_date: "",
    starting_capital: 1000,
  });
  const [paramInputs, setParamInputs] = useState(
    strategies[0] ? buildDefaultRangeInputs(strategies[0].parameters) : {}
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  function buildDefaultRangeInputs(parameters) {
    return Object.fromEntries(
      Object.entries(parameters).map(([key, spec]) => [key, String(spec.default)])
    );
  }

  const handleStrategyChange = (e) => {
    const name = e.target.value;
    const strat = strategies.find((s) => s.name === name);
    setForm((f) => ({ ...f, strategy: name }));
    setSelectedStrategy(strat || null);
    setParamInputs(strat ? buildDefaultRangeInputs(strat.parameters) : {});
    setResult(null);
    setError(null);
  };

  const buildParameterRanges = () => {
    if (!selectedStrategy) return {};
    return Object.fromEntries(
      Object.entries(paramInputs).map(([key, raw]) => [key, parseRangeInput(raw)])
    );
  };

  const combinationCount = countCombinations(buildParameterRanges());
  const tooManyCombinations = combinationCount > MAX_COMBINATIONS;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (tooManyCombinations) {
      setError(`Too many combinations (${combinationCount}). Reduce parameter values to ≤ ${MAX_COMBINATIONS} total.`);
      return;
    }

    setLoading(true);
    try {
      const res = await runOptimize({
        symbol: form.symbol.trim().toUpperCase(),
        start_date: form.start_date,
        end_date: form.end_date,
        starting_capital: Number(form.starting_capital),
        strategy: form.strategy,
        parameter_ranges: buildParameterRanges(),
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Optimization failed. Check inputs and try again.");
    } finally {
      setLoading(false);
    }
  };

  const fmt = (v, decimals = 2) => (v != null ? v.toFixed(decimals) : "—");

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-6 mb-8">
        {/* Core inputs */}
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Setup</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className={labelCls}>Symbol</label>
              <input
                required
                type="text"
                placeholder="e.g. AAPL"
                value={form.symbol}
                onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Strategy</label>
              <select
                value={form.strategy}
                onChange={handleStrategyChange}
                className={inputCls}
              >
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelCls}>Starting Capital ($)</label>
              <input
                required
                type="number"
                min="1"
                step="any"
                value={form.starting_capital}
                onChange={(e) => setForm((f) => ({ ...f, starting_capital: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>Start Date</label>
              <input
                required
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                className={inputCls}
              />
            </div>

            <div>
              <label className={labelCls}>End Date</label>
              <input
                required
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                className={inputCls}
              />
            </div>
          </div>
        </div>

        {/* Parameter ranges */}
        {selectedStrategy && Object.keys(selectedStrategy.parameters).length > 0 && (
          <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-1">Parameter Ranges</h2>
            <p className="text-[#555] text-xs mb-4">
              Enter comma-separated values per parameter (e.g. <span className="text-[#888]">7,9,14</span>).
              Single value = fixed.{" "}
              <span className={tooManyCombinations ? "text-red-400 font-semibold" : "text-[#888]"}>
                {combinationCount} combination{combinationCount !== 1 ? "s" : ""} / {MAX_COMBINATIONS} max
              </span>
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(selectedStrategy.parameters).map(([key, spec]) => (
                <div key={key}>
                  <label className={labelCls}>
                    {key}{" "}
                    <span className="normal-case text-[#444] ml-1">({spec.type})</span>
                  </label>
                  <input
                    type="text"
                    value={paramInputs[key] ?? ""}
                    onChange={(e) =>
                      setParamInputs((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                    placeholder={String(spec.default)}
                    className={inputCls}
                  />
                  {spec.description && (
                    <p className="text-[#444] text-xs mt-0.5">{spec.description}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || tooManyCombinations}
          className="bg-[#00e676] text-black font-bold px-6 py-2.5 rounded text-sm uppercase tracking-widest hover:bg-[#00c853] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Running…" : "Run Optimization"}
        </button>
      </form>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-[#00e676] border-t-transparent rounded-full animate-spin" />
          <span className="ml-3 text-[#888] text-sm">Running grid search…</span>
        </div>
      )}

      {result && !loading && (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Heatmap</h2>
          <OptimizeHeatmap results={result.results} metric="sharpe" />
        </div>
      )}

      {result && !loading && (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest">Results</h2>
            <span className="text-[#888] text-xs">
              {result.combinations_tested} combination{result.combinations_tested !== 1 ? "s" : ""} tested
            </span>
          </div>

          {result.results.length === 0 ? (
            <p className="text-[#555] text-sm">No results returned.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1e1e1e]">
                    <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-left">Rank</th>
                    <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-left">Parameters</th>
                    <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-right">Sharpe</th>
                    <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-right">Total P&L</th>
                    <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-right">Win Rate</th>
                    <th className="text-[#666] text-xs uppercase tracking-wider py-2 px-3 text-right"># Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {result.results.map((row, idx) => {
                    const isTop = idx === 0;
                    return (
                      <tr
                        key={idx}
                        className={`border-b border-[#1e1e1e] transition-colors ${
                          isTop
                            ? "bg-[#1a2a1a] border-l-2 border-l-[#00e676]"
                            : "hover:bg-[#1a1a1a]"
                        }`}
                      >
                        <td className="py-2 px-3">
                          {isTop ? (
                            <span className="bg-[#ffd700] text-black text-xs font-bold px-2 py-0.5 rounded">
                              #1
                            </span>
                          ) : (
                            <span className="text-[#666]">#{idx + 1}</span>
                          )}
                        </td>
                        <td className="py-2 px-3">
                          <span className="bg-[#1e1e1e] text-[#e0e0e0] text-xs font-mono px-2 py-1 rounded">
                            {JSON.stringify(row.parameters)}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          {row.sharpe_ratio != null ? (
                            <span className={row.sharpe_ratio >= 1 ? "text-[#00e676]" : row.sharpe_ratio >= 0 ? "text-[#e0e0e0]" : "text-red-400"}>
                              {fmt(row.sharpe_ratio)}
                            </span>
                          ) : (
                            <span className="text-[#555]">—</span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          <span className={row.total_pnl >= 0 ? "text-[#00e676]" : "text-red-400"}>
                            {row.total_pnl >= 0 ? "+" : ""}${fmt(row.total_pnl)}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right text-[#e0e0e0]">
                          {(row.win_rate * 100).toFixed(0)}%
                        </td>
                        <td className="py-2 px-3 text-right text-[#e0e0e0]">
                          {row.num_trades}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page shell with tab switcher
// ---------------------------------------------------------------------------

const PAGE_TABS = ["OPTIMIZE", "WALK-FORWARD"];

export default function Optimize() {
  const [activeTab, setActiveTab] = useState("OPTIMIZE");
  const [strategies, setStrategies] = useState([]);

  useEffect(() => {
    getStrategies().then((r) => setStrategies(r.data));
  }, []);

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb={`HOME › OPTIMIZE › ${activeTab}`}
        title="Strategy Optimizer"
        subtitle={
          activeTab === "OPTIMIZE"
            ? "Grid search across parameter combinations, ranked by Sharpe ratio"
            : "Rolling train/test windows to detect overfitting across time"
        }
      />

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-[#1e1e1e]">
        {PAGE_TABS.map((tab) => (
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

      {strategies.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-[#00e676] border-t-transparent rounded-full animate-spin" />
          <span className="ml-3 text-[#888] text-sm">Loading strategies…</span>
        </div>
      ) : (
        <>
          {activeTab === "OPTIMIZE" && <OptimizerTab strategies={strategies} />}
          {activeTab === "WALK-FORWARD" && <WalkForwardTab strategies={strategies} />}
        </>
      )}
    </div>
  );
}
