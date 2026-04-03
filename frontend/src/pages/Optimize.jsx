import { useState, useEffect } from "react";
import { getStrategies, runOptimize } from "../api/client";
import PageHeader from "../components/PageHeader";

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

export default function Optimize() {
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [form, setForm] = useState({
    symbol: "",
    strategy: "",
    start_date: "",
    end_date: "",
    starting_capital: 1000,
  });
  const [paramInputs, setParamInputs] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    getStrategies().then((r) => {
      const list = r.data;
      setStrategies(list);
      if (list.length > 0) {
        const first = list[0];
        setForm((f) => ({ ...f, strategy: first.name }));
        setSelectedStrategy(first);
        setParamInputs(buildDefaultRangeInputs(first.parameters));
      }
    });
  }, []);

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
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › OPTIMIZE"
        title="Strategy Parameter Optimizer"
        subtitle="Grid search across parameter combinations, ranked by Sharpe ratio"
      />

      <form onSubmit={handleSubmit} className="space-y-6 mb-8">
        {/* Core inputs */}
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Setup</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-[#888] text-xs mb-1 uppercase tracking-wider">Symbol</label>
              <input
                required
                type="text"
                placeholder="e.g. AAPL"
                value={form.symbol}
                onChange={(e) => setForm((f) => ({ ...f, symbol: e.target.value }))}
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors"
              />
            </div>

            <div>
              <label className="block text-[#888] text-xs mb-1 uppercase tracking-wider">Strategy</label>
              <select
                value={form.strategy}
                onChange={handleStrategyChange}
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors"
              >
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[#888] text-xs mb-1 uppercase tracking-wider">Starting Capital ($)</label>
              <input
                required
                type="number"
                min="1"
                step="any"
                value={form.starting_capital}
                onChange={(e) => setForm((f) => ({ ...f, starting_capital: e.target.value }))}
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors"
              />
            </div>

            <div>
              <label className="block text-[#888] text-xs mb-1 uppercase tracking-wider">Start Date</label>
              <input
                required
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors"
              />
            </div>

            <div>
              <label className="block text-[#888] text-xs mb-1 uppercase tracking-wider">End Date</label>
              <input
                required
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors"
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
                  <label className="block text-[#888] text-xs mb-1 uppercase tracking-wider">
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
                    className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors"
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

      {/* Loading spinner */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-[#00e676] border-t-transparent rounded-full animate-spin" />
          <span className="ml-3 text-[#888] text-sm">Running grid search…</span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[#00e676] text-xs uppercase tracking-widest">
              Results
            </h2>
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
