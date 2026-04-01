import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategies, createSession, runBacktest } from "../api/client";

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

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>New Trading Session</h1>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <label>Symbol<input value={form.symbol} onChange={e => setForm({...form, symbol: e.target.value})} placeholder="AAPL" required /></label>
        <label>Strategy
          <select value={form.strategy} onChange={e => setForm({...form, strategy: e.target.value})}>
            {strategies.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label>Short Window<input type="number" value={form.short_window} onChange={e => setForm({...form, short_window: e.target.value})} /></label>
        <label>Long Window<input type="number" value={form.long_window} onChange={e => setForm({...form, long_window: e.target.value})} /></label>
        <label>Capital ($)<input type="number" value={form.starting_capital} onChange={e => setForm({...form, starting_capital: e.target.value})} /></label>
        <label>Mode
          <select value={form.mode} onChange={e => setForm({...form, mode: e.target.value})}>
            <option value="paper">Paper Trading (Real-time)</option>
            <option value="backtest">Backtest (Historical)</option>
            <option value="live">Live (Stubbed)</option>
          </select>
        </label>
        {form.mode === "backtest" && (<>
          <label>From<input type="datetime-local" value={form.from_dt} onChange={e => setForm({...form, from_dt: e.target.value})} required /></label>
          <label>To<input type="datetime-local" value={form.to_dt} onChange={e => setForm({...form, to_dt: e.target.value})} required /></label>
        </>)}
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={loading}>{loading ? "Starting..." : "Start Session"}</button>
      </form>
    </div>
  );
}
