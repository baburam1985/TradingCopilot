import { useState, useEffect } from "react";
import {
  getSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
} from "../api/client";
import PageHeader from "../components/PageHeader";
import SchedulePicker from "../components/SchedulePicker";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDays(days) {
  if (!days || days.length === 0) return "—";
  if (days.length === 7) return "Every day";
  if (JSON.stringify(days) === JSON.stringify([0, 1, 2, 3, 4])) return "Weekdays";
  return days.map((d) => DAY_LABELS[d]).join(", ");
}

function StatusBadge({ status }) {
  if (!status) return <span className="text-[#555] text-xs">—</span>;
  const colors = {
    running: "bg-[#00e676]/10 text-[#00e676]",
    completed: "bg-[#1e1e1e] text-[#888]",
    failed: "bg-[#ff4444]/10 text-[#ff4444]",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${colors[status] ?? "text-[#888]"}`}>
      {status}
    </span>
  );
}

const BLANK_FORM = {
  symbol: "",
  strategy: "moving_average_crossover",
  strategy_params: {},
  capital: 1000,
  mode: "paper",
  days_of_week: [0, 1, 2, 3, 4],
  start_time_et: "09:30",
  stop_time_et: "",
  auto_stop_daily_loss_pct: null,
  auto_stop_max_trades: null,
};

export default function ScheduledSessions() {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(BLANK_FORM);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    getSchedules()
      .then((r) => setSchedules(r.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createSchedule({
        ...form,
        stop_time_et: form.stop_time_et || null,
        auto_stop_daily_loss_pct: form.auto_stop_daily_loss_pct || null,
        auto_stop_max_trades: form.auto_stop_max_trades || null,
      });
      setShowCreate(false);
      setForm(BLANK_FORM);
      load();
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (sched) => {
    try {
      await updateSchedule(sched.id, { is_active: !sched.is_active });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this schedule?")) return;
    try {
      await deleteSchedule(id);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const inputClass =
    "w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors";
  const labelClass = "block text-[#888] text-xs uppercase tracking-wider mb-1";

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › SCHEDULES"
        title="Scheduled Sessions"
        subtitle="Auto-start and stop trading sessions on a recurring schedule"
      />

      <div className="mb-4 flex justify-end">
        <button
          className="bg-[#00e676] text-black font-semibold text-sm px-4 py-2 rounded hover:bg-[#00c853] transition-colors"
          onClick={() => setShowCreate((o) => !o)}
        >
          {showCreate ? "Cancel" : "+ New Schedule"}
        </button>
      </div>

      {error && <p className="text-[#ff4444] text-sm mb-4">{error}</p>}

      {/* Create form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-[#141414] border border-[#1e1e1e] rounded p-5 mb-6 flex flex-col gap-4"
        >
          <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-1">New Schedule</h2>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Symbol</label>
              <input
                className={inputClass}
                value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                placeholder="AAPL"
                required
              />
            </div>
            <div>
              <label className={labelClass}>Mode</label>
              <select
                className={inputClass}
                value={form.mode}
                onChange={(e) => setForm({ ...form, mode: e.target.value })}
              >
                <option value="paper">Paper</option>
                <option value="alpaca_paper">Alpaca Paper</option>
                <option value="alpaca_live">Alpaca Live</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Strategy</label>
              <input
                className={inputClass}
                value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                placeholder="moving_average_crossover"
                required
              />
            </div>
            <div>
              <label className={labelClass}>Capital ($)</label>
              <input
                type="number"
                className={inputClass}
                value={form.capital}
                onChange={(e) => setForm({ ...form, capital: +e.target.value })}
                required
              />
            </div>
          </div>

          <SchedulePicker value={form} onChange={setForm} />

          <button
            type="submit"
            disabled={saving}
            className="bg-[#00e676] text-black font-semibold text-sm py-2 rounded hover:bg-[#00c853] transition-colors disabled:opacity-50"
          >
            {saving ? "Saving…" : "Create Schedule"}
          </button>
        </form>
      )}

      {/* Schedule table */}
      {loading ? (
        <p className="text-[#555] text-sm">Loading…</p>
      ) : schedules.length === 0 ? (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-10 text-center text-[#555]">
          <div className="text-3xl mb-3">🗓</div>
          <p className="text-sm">No schedules yet</p>
          <p className="text-xs mt-1">Create one above to auto-start sessions each trading day.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-[#555] text-xs uppercase tracking-wider border-b border-[#1e1e1e]">
                <th className="text-left py-2 pr-4">Symbol</th>
                <th className="text-left py-2 pr-4">Strategy</th>
                <th className="text-left py-2 pr-4">Capital</th>
                <th className="text-left py-2 pr-4">Days</th>
                <th className="text-left py-2 pr-4">Start ET</th>
                <th className="text-left py-2 pr-4">Stop ET</th>
                <th className="text-left py-2 pr-4">Next Run</th>
                <th className="text-left py-2 pr-4">Status</th>
                <th className="text-left py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} className="border-b border-[#1a1a1a] hover:bg-[#141414] transition-colors">
                  <td className="py-3 pr-4 text-white font-mono">{s.symbol}</td>
                  <td className="py-3 pr-4 text-[#888]">{s.strategy}</td>
                  <td className="py-3 pr-4 text-[#888]">${s.capital.toLocaleString()}</td>
                  <td className="py-3 pr-4 text-[#888]">{formatDays(s.days_of_week)}</td>
                  <td className="py-3 pr-4 text-[#888]">{s.start_time_et}</td>
                  <td className="py-3 pr-4 text-[#888]">{s.stop_time_et || "16:00"}</td>
                  <td className="py-3 pr-4 text-[#555] text-xs">
                    {s.next_run_at
                      ? new Date(s.next_run_at).toLocaleString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}
                  </td>
                  <td className="py-3 pr-4">
                    <StatusBadge status={s.last_run_status} />
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-3">
                      {/* Enable/disable toggle */}
                      <button
                        type="button"
                        onClick={() => handleToggle(s)}
                        className={`w-9 h-5 rounded-full transition-colors relative flex-shrink-0 ${
                          s.is_active ? "bg-[#00e676]" : "bg-[#333]"
                        }`}
                        title={s.is_active ? "Pause" : "Resume"}
                      >
                        <span
                          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${
                            s.is_active ? "left-4" : "left-0.5"
                          }`}
                        />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(s.id)}
                        className="text-[#555] hover:text-[#ff4444] text-xs transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
