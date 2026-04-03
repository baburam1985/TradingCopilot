import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useState } from "react";

// Event type colours and labels (mirrors PriceChart)
const EVENT_COLORS = {
  earnings: "#f97316",
  fomc: "#3b82f6",
  cpi: "#ef4444",
};

const EVENT_LABELS = {
  earnings: "Earnings",
  fomc: "FOMC",
  cpi: "CPI",
};

const ALL_EVENT_TYPES = Object.keys(EVENT_LABELS);

function formatTimestamp(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Build a map from date string (YYYY-MM-DD) → formatted label ("Apr 1").
 * Used to match event dates to equity curve x-axis labels.
 */
function buildDateToLabelMap(points) {
  const map = {};
  for (const p of points) {
    const dateKey = new Date(p.timestamp).toISOString().slice(0, 10);
    if (!(dateKey in map)) {
      map[dateKey] = formatTimestamp(p.timestamp);
    }
  }
  return map;
}

function CustomTooltip({ active, payload, label, visibleEvents, dateToLabel }) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  // Find event whose label matches this x-axis tick
  const matchedEvent = visibleEvents.find((e) => dateToLabel[e.event_date] === label);
  return (
    <div className="bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-xs">
      <div className="text-[#888] mb-1">{label}</div>
      <div className="text-white font-semibold">${value.toFixed(2)}</div>
      {matchedEvent && (
        <div className="mt-1 font-semibold" style={{ color: EVENT_COLORS[matchedEvent.event_type] }}>
          {matchedEvent.description}
        </div>
      )}
    </div>
  );
}

function EventLabel({ viewBox, event }) {
  const { x, y } = viewBox;
  return (
    <text
      x={x + 4}
      y={y + 12}
      fill={EVENT_COLORS[event.event_type] ?? "#fff"}
      fontSize={9}
      fontWeight="bold"
    >
      {EVENT_LABELS[event.event_type]?.[0] ?? "E"}
    </text>
  );
}

function EventToggle({ activeEventTypes, onToggle }) {
  return (
    <div className="flex flex-wrap gap-2 mb-3" data-testid="equity-event-toggles">
      {ALL_EVENT_TYPES.map((key) => {
        const active = activeEventTypes.has(key);
        const color = EVENT_COLORS[key];
        return (
          <button
            key={key}
            onClick={() => onToggle(key)}
            data-testid={`toggle-equity-event-${key}`}
            className="px-2 py-0.5 text-xs rounded border transition-colors"
            style={
              active
                ? { backgroundColor: color, color: "#000", borderColor: color }
                : { backgroundColor: "transparent", color: "#aaa", borderColor: "#444" }
            }
          >
            {EVENT_LABELS[key]}
          </button>
        );
      })}
    </div>
  );
}

export default function EquityCurveChart({ points, startingCapital, events = [] }) {
  const [activeEventTypes, setActiveEventTypes] = useState(new Set(ALL_EVENT_TYPES));

  if (!points || points.length < 2) {
    return (
      <p className="text-[#555] text-xs text-center py-8">
        Not enough closed trades to render equity curve.
      </p>
    );
  }

  const data = points.map((p) => ({
    timestamp: formatTimestamp(p.timestamp),
    portfolio_value: p.portfolio_value,
  }));

  const values = points.map((p) => p.portfolio_value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const lastVal = values[values.length - 1];
  const isProfit = lastVal >= startingCapital;

  const dateToLabel = buildDateToLabelMap(points);
  const visibleEvents = events.filter(
    (e) => activeEventTypes.has(e.event_type) && dateToLabel[e.event_date]
  );

  function handleEventToggle(key) {
    setActiveEventTypes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="w-full" style={{ touchAction: "pan-y" }}>
      {events.length > 0 && (
        <EventToggle activeEventTypes={activeEventTypes} onToggle={handleEventToggle} />
      )}
      <ResponsiveContainer width="100%" height={220} minHeight={160}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="5%"
                stopColor={isProfit ? "#00e676" : "#dc2626"}
                stopOpacity={0.25}
              />
              <stop
                offset="95%"
                stopColor={isProfit ? "#00e676" : "#dc2626"}
                stopOpacity={0}
              />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="timestamp"
            tick={{ fontSize: 10, fill: "#666" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[minVal * 0.995, maxVal * 1.005]}
            tick={{ fontSize: 10, fill: "#666" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            width={60}
          />
          <Tooltip
            content={
              <CustomTooltip
                visibleEvents={visibleEvents}
                dateToLabel={dateToLabel}
              />
            }
          />
          <ReferenceLine
            y={startingCapital}
            stroke="#444"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
          <Area
            type="monotone"
            dataKey="portfolio_value"
            stroke={isProfit ? "#00e676" : "#dc2626"}
            strokeWidth={2}
            fill="url(#equityGradient)"
            dot={false}
            activeDot={{ r: 4, fill: isProfit ? "#00e676" : "#dc2626" }}
          />

          {/* Event calendar markers */}
          {visibleEvents.map((e) => (
            <ReferenceLine
              key={`evt-${e.id}`}
              x={dateToLabel[e.event_date]}
              stroke={EVENT_COLORS[e.event_type]}
              strokeDasharray="4 2"
              strokeWidth={1.5}
              label={<EventLabel event={e} />}
              data-testid={`equity-event-line-${e.event_type}`}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
