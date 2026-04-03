import { useState } from "react";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const inputClass =
  "w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] transition-colors";
const labelClass = "block text-[#888] text-xs uppercase tracking-wider mb-1";

export default function SchedulePicker({ value, onChange }) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const toggleDay = (dayIndex) => {
    const next = value.days_of_week.includes(dayIndex)
      ? value.days_of_week.filter((d) => d !== dayIndex)
      : [...value.days_of_week, dayIndex].sort((a, b) => a - b);
    onChange({ ...value, days_of_week: next });
  };

  return (
    <div className="flex flex-col gap-3">
      {/* Days of week */}
      <div>
        <label className={labelClass}>Days</label>
        <div className="flex gap-1.5 flex-wrap">
          {DAY_LABELS.map((label, i) => (
            <button
              key={i}
              type="button"
              onClick={() => toggleDay(i)}
              className={`px-2.5 py-1 text-xs rounded border transition-colors ${
                value.days_of_week.includes(i)
                  ? "bg-[#00e676] text-black border-[#00e676]"
                  : "bg-[#0a0a0a] text-[#888] border-[#1e1e1e] hover:border-[#555]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Start time */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Start Time (ET)</label>
          <input
            type="time"
            className={inputClass}
            value={value.start_time_et}
            onChange={(e) => onChange({ ...value, start_time_et: e.target.value })}
            required
          />
        </div>
        <div>
          <label className={labelClass}>Stop Time (ET)</label>
          <input
            type="time"
            className={inputClass}
            value={value.stop_time_et}
            onChange={(e) => onChange({ ...value, stop_time_et: e.target.value })}
            placeholder="16:00 (market close)"
          />
          <p className="text-[#444] text-xs mt-0.5">Leave blank = 16:00 market close</p>
        </div>
      </div>

      {/* Advanced */}
      <div>
        <button
          type="button"
          className="text-[#555] text-xs hover:text-[#888] transition-colors"
          onClick={() => setAdvancedOpen((o) => !o)}
        >
          {advancedOpen ? "▲ Hide" : "▼ Show"} advanced auto-stop conditions
        </button>
        {advancedOpen && (
          <div className="mt-3 flex flex-col gap-3">
            <div>
              <label className={labelClass}>Daily Loss Stop (%)</label>
              <input
                type="number"
                min="0"
                step="0.1"
                className={inputClass}
                value={value.auto_stop_daily_loss_pct ?? ""}
                onChange={(e) =>
                  onChange({
                    ...value,
                    auto_stop_daily_loss_pct: e.target.value !== "" ? +e.target.value : null,
                  })
                }
                placeholder="e.g. 5"
              />
              <p className="text-[#444] text-xs mt-0.5">Stop session if daily loss exceeds this %</p>
            </div>
            <div>
              <label className={labelClass}>Max Trades</label>
              <input
                type="number"
                min="1"
                step="1"
                className={inputClass}
                value={value.auto_stop_max_trades ?? ""}
                onChange={(e) =>
                  onChange({
                    ...value,
                    auto_stop_max_trades: e.target.value !== "" ? parseInt(e.target.value, 10) : null,
                  })
                }
                placeholder="e.g. 10"
              />
              <p className="text-[#444] text-xs mt-0.5">Stop after this many trades per day</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
