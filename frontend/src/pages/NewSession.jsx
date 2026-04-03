import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategies, createSession, runBacktest, runBacktestCompare } from "../api/client";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";

function buildDefaultParams(parameters) {
  return Object.fromEntries(
    Object.entries(parameters).map(([key, spec]) => [key, spec.default])
  );
}

function coerceParam(value, type) {
  if (type === "int") return parseInt(value, 10);
  if (type === "float") return parseFloat(value);
  return value;
}

export default function NewSession() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [strategyParamValues, setStrategyParamValues] = useState({});
  const [form, setForm] = useState({
    symbol: "",
    strategy: "moving_average_crossover",
    starting_capital: 1000,
    mode: "paper",
    from_dt: "",
    to_dt: "",
    stop_loss_pct: "",
    take_profit_pct: "",
    max_position_pct: "",
    daily_max_loss_pct: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareStrategies, setCompareStrategies] = useState([]);

  useEffect(() => {
    getStrategies().then((r) => {
      const list = r.data;
      setStrategies(list);
      const initial = list.find(s => s.name === form.strategy) || list[0];
      if (initial) {
        setSelectedStrategy(initial);
        setStrategyParamValues(buildDefaultParams(initial.parameters));
      }
    });
  }, []);

  const handleStrategyChange = (e) => {
    const name = e.target.value;
    const strat = strategies.find(s => s.name === name);
    setForm({ ...form, strategy: name });
    setSelectedStrategy(strat || null);
    setStrategyParamValues(strat ? buildDefaultParams(strat.parameters) : {});
  };

  const buildStrategyParams = () => {
    if (!selectedStrategy) return {};
    return Object.fromEntries(
      Object.entries(strategyParamValues).map(([key, val]) => [
        key,
        coerceParam(val, selectedStrategy.parameters[key]?.type),
      ])
    );
  };

  const addCompareStrategy = () => {
    if (!selectedStrategy) return;
    setCompareStrategies([
      ...compareStrategies,
      { name: form.strategy, params: buildStrategyParams() },
    ]);
  };

  const removeCompareStrategy = (idx) => {
    setCompareStrategies(compareStrategies.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const strategy_params = buildStrategyParams();
    try {
      if (form.mode === "backtest" && compareMode) {
        const allSpecs = [
          { name: form.strategy, params: strategy_params },
          ...compareStrategies,
        ];
        const result = await runBacktestCompare({
          symbol: form.symbol,
          strategies: allSpecs,
          starting_capital: +form.starting_capital,
          from_dt: form.from_dt,
          to_dt: form.to_dt,
        });
        navigate("/reports", { state: { compareResult: result.data } });
      } else if (form.mode === "backtest") {
        const result = await runBacktest({
          symbol: form.symbol,
          strategy: form.strategy,
          strategy_params,
          starting_capital: +form.starting_capital,
          from_dt: form.from_dt,
          to_dt: form.to_dt,
        });
        navigate("/reports", { state: { backtestResult: result.data } });
      } else {
        const session = await createSession({
          symbol: form.symbol,
          strategy: form.strategy,
          strategy_params,
          starting_capital: +form.starting_capital,
          mode: form.mode,
          stop_loss_pct: form.stop_loss_pct !== "" ? +form.stop_loss_pct : null,
          take_profit_pct: form.take_profit_pct !== "" ? +form.take_profit_pct : null,
          max_position_pct: form.max_position_pct !== "" ? +form.max_position_pct : null,
          daily_max_loss_pct: form.daily_max_loss_pct !== "" ? +form.daily_max_loss_pct : null,
        });
        navigate(`/dashboard/${session.data.id}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors";
  const labelClass = "block text-[#888] text-xs uppercase tracking-wider mb-1";

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › NEW SESSION"
        title="New Trading Session"
        subtitle="Configure your strategy and launch a session"
      />

      {/* Metrics row — horizontal scroll on mobile */}
      <div className="overflow-x-auto mb-8 -mx-6 px-6 sm:mx-0 sm:px-0">
        <div className="grid grid-cols-3 gap-4 min-w-[420px] sm:min-w-0">
          <MetricCard label="Expected Volatility" value="—" />
          <MetricCard label="Market Liquidity" value="—" />
          <MetricCard label="Backtest Win-Rate" value="—" />
        </div>
      </div>

      {/* Body: stacked on mobile, two-column on md+ */}
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left panel — form */}
        <div className="w-full md:flex-1 md:max-w-md">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {/* Asset Selection */}
            <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
              <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Asset Selection</h2>
              <div className="flex flex-col gap-3">
                <div>
                  <label className={labelClass}>Symbol</label>
                  <input
                    className={inputClass}
                    value={form.symbol}
                    onChange={e => setForm({ ...form, symbol: e.target.value })}
                    placeholder="AAPL"
                    required
                  />
                </div>
                <div>
                  <label className={labelClass}>Mode</label>
                  <select
                    className={inputClass}
                    value={form.mode}
                    onChange={e => setForm({ ...form, mode: e.target.value })}
                  >
                    <option value="paper">Paper Trading (Internal)</option>
                    <option value="alpaca_paper">Alpaca Paper Trading</option>
                    <option value="alpaca_live">Alpaca Live Trading</option>
                    <option value="backtest">Backtest (Historical)</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Capital ($)</label>
                  <input
                    type="number"
                    className={inputClass}
                    value={form.starting_capital}
                    onChange={e => setForm({ ...form, starting_capital: e.target.value })}
                  />
                </div>
              </div>
            </div>

            {/* Algorithm Parameters */}
            <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
              <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Algorithm Parameters</h2>
              <div className="flex flex-col gap-3">
                <div>
                  <label className={labelClass}>Strategy</label>
                  <select
                    className={inputClass}
                    value={form.strategy}
                    onChange={handleStrategyChange}
                  >
                    {strategies.map(s => (
                      <option key={s.name} value={s.name}>{s.name}</option>
                    ))}
                  </select>
                  {selectedStrategy?.description && (
                    <p className="text-[#555] text-xs mt-1">{selectedStrategy.description}</p>
                  )}
                </div>
                {selectedStrategy && Object.entries(selectedStrategy.parameters).map(([key, spec]) => (
                  <div key={key}>
                    <label className={labelClass}>{key.replace(/_/g, " ")}</label>
                    <input
                      type={spec.type === "int" || spec.type === "float" ? "number" : "text"}
                      className={inputClass}
                      value={strategyParamValues[key] ?? spec.default}
                      onChange={e => setStrategyParamValues({ ...strategyParamValues, [key]: e.target.value })}
                      title={spec.description}
                      placeholder={String(spec.default)}
                    />
                    {spec.description && (
                      <p className="text-[#444] text-xs mt-0.5">{spec.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Risk Management */}
            <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
              <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-1">Risk Management</h2>
              <p className="text-[#444] text-xs mb-4">All fields optional. Leave blank to disable that guardrail.</p>
              <div className="flex flex-col gap-3">
                <div>
                  <label className={labelClass}>Stop-Loss (%)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    className={inputClass}
                    value={form.stop_loss_pct}
                    onChange={e => setForm({ ...form, stop_loss_pct: e.target.value })}
                    placeholder="e.g. 5"
                  />
                  <p className="text-[#444] text-xs mt-0.5">Exit if unrealised loss reaches this %</p>
                </div>
                <div>
                  <label className={labelClass}>Take-Profit (%)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    className={inputClass}
                    value={form.take_profit_pct}
                    onChange={e => setForm({ ...form, take_profit_pct: e.target.value })}
                    placeholder="e.g. 15"
                  />
                  <p className="text-[#444] text-xs mt-0.5">Exit if unrealised gain reaches this %</p>
                </div>
                <div>
                  <label className={labelClass}>Max Position Size (% of capital)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    className={inputClass}
                    value={form.max_position_pct}
                    onChange={e => setForm({ ...form, max_position_pct: e.target.value })}
                    placeholder="e.g. 50"
                  />
                  <p className="text-[#444] text-xs mt-0.5">Skip trades that would exceed this % of capital</p>
                </div>
                <div>
                  <label className={labelClass}>Daily Max Loss (% of capital)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    className={inputClass}
                    value={form.daily_max_loss_pct}
                    onChange={e => setForm({ ...form, daily_max_loss_pct: e.target.value })}
                    placeholder="e.g. 3"
                  />
                  <p className="text-[#444] text-xs mt-0.5">Close session if daily P&L loss exceeds this %</p>
                </div>
              </div>
            </div>

            {/* Execution Logic (backtest date range) */}
            {form.mode === "backtest" && (
              <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
                <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Execution Logic</h2>
                <div className="flex flex-col gap-3">
                  <div>
                    <label className={labelClass}>From</label>
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={form.from_dt}
                      onChange={e => setForm({ ...form, from_dt: e.target.value })}
                      required
                    />
                  </div>
                  <div>
                    <label className={labelClass}>To</label>
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={form.to_dt}
                      onChange={e => setForm({ ...form, to_dt: e.target.value })}
                      required
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Strategy Comparison (backtest only) */}
            {form.mode === "backtest" && (
              <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-[#00e676] text-xs uppercase tracking-widest">Compare Strategies</h2>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <div
                      onClick={() => setCompareMode(!compareMode)}
                      className={`w-9 h-5 rounded-full transition-colors ${compareMode ? "bg-[#00e676]" : "bg-[#333]"} relative`}
                    >
                      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${compareMode ? "left-4" : "left-0.5"}`} />
                    </div>
                    <span className="text-[#555] text-xs">{compareMode ? "On" : "Off"}</span>
                  </label>
                </div>
                {compareMode && (
                  <div className="flex flex-col gap-2">
                    <p className="text-[#555] text-xs mb-2">
                      Current strategy is included automatically. Add more to compare.
                    </p>
                    {compareStrategies.map((s, i) => (
                      <div key={i} className="flex items-center justify-between bg-[#0a0a0a] rounded px-3 py-2">
                        <span className="text-white text-xs">{s.name}</span>
                        <button
                          type="button"
                          onClick={() => removeCompareStrategy(i)}
                          className="text-[#555] hover:text-[#ff4444] text-xs transition-colors"
                        >remove</button>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={addCompareStrategy}
                      className="text-[#00e676] text-xs border border-[#1e1e1e] rounded px-3 py-1.5 hover:border-[#00e676] transition-colors mt-1"
                    >
                      + Add current strategy config
                    </button>
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-[#ff4444] text-sm">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="bg-[#00e676] text-black font-semibold text-sm py-2.5 rounded hover:bg-[#00c853] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading
                ? "Running..."
                : form.mode === "backtest" && compareMode
                ? "Run Comparison"
                : form.mode === "backtest"
                ? "Run Backtest"
                : "Start Session"}
            </button>
          </form>
        </div>

        {/* Right panel — session preview */}
        <div className="w-full md:flex-1 bg-[#141414] border border-[#1e1e1e] rounded p-6 flex items-center justify-center min-h-[180px]">
          <div className="text-center text-[#555]">
            <div className="text-4xl mb-3">⏳</div>
            <p className="text-sm">Awaiting session launch</p>
            <p className="text-xs mt-1">Configure the form and start a session to see a live preview.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
