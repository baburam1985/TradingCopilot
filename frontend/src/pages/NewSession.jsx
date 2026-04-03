import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategies, createSession, runBacktest } from "../api/client";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";

export default function NewSession() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState([]);
  const [form, setForm] = useState({
    symbol: "",
    strategy: "moving_average_crossover",
    short_window: 50,
    long_window: 200,
    starting_capital: 1000,
    mode: "paper",
    from_dt: "",
    to_dt: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStrategies().then((r) => setStrategies(r.data));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (form.mode === "backtest") {
        const result = await runBacktest({
          symbol: form.symbol,
          strategy: form.strategy,
          strategy_params: { short_window: +form.short_window, long_window: +form.long_window },
          starting_capital: +form.starting_capital,
          from_dt: form.from_dt,
          to_dt: form.to_dt,
        });
        navigate("/reports", { state: { backtestResult: result.data } });
      } else {
        const session = await createSession({
          symbol: form.symbol,
          strategy: form.strategy,
          strategy_params: { short_window: +form.short_window, long_window: +form.long_window },
          starting_capital: +form.starting_capital,
          mode: form.mode,
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

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <MetricCard label="Expected Volatility" value="—" />
        <MetricCard label="Market Liquidity" value="—" />
        <MetricCard label="Backtest Win-Rate" value="—" />
      </div>

      {/* Body: two-column layout */}
      <div className="flex gap-6">
        {/* Left panel — form */}
        <div className="flex-1 max-w-md">
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
                    <option value="paper">Paper Trading (Real-time)</option>
                    <option value="backtest">Backtest (Historical)</option>
                    <option value="live">Live (Stubbed)</option>
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
                    onChange={e => setForm({ ...form, strategy: e.target.value })}
                  >
                    {strategies.map(s => (
                      <option key={s.name} value={s.name}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Short Window</label>
                  <input
                    type="number"
                    className={inputClass}
                    value={form.short_window}
                    onChange={e => setForm({ ...form, short_window: e.target.value })}
                  />
                </div>
                <div>
                  <label className={labelClass}>Long Window</label>
                  <input
                    type="number"
                    className={inputClass}
                    value={form.long_window}
                    onChange={e => setForm({ ...form, long_window: e.target.value })}
                  />
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

            {error && <p className="text-[#ff4444] text-sm">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="bg-[#00e676] text-black font-semibold text-sm py-2.5 rounded hover:bg-[#00c853] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Starting..." : "Start Session"}
            </button>
          </form>
        </div>

        {/* Right panel — session preview */}
        <div className="flex-1 bg-[#141414] border border-[#1e1e1e] rounded p-6 flex items-center justify-center">
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
