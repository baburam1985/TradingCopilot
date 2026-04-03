import React, { useState } from "react";
import {
  ComposedChart,
  Line,
  Bar,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

const INDICATOR_LABELS = {
  sma: "SMA",
  ema: "EMA",
  bollinger: "Bollinger",
  rsi: "RSI",
  macd: "MACD",
};

const ALL_INDICATORS = Object.keys(INDICATOR_LABELS);

// Event type colours and labels
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

/**
 * Merge indicator arrays (indexed by position) into the base data array.
 */
function mergeIndicators(baseData, indicators) {
  if (!indicators) return baseData;
  return baseData.map((d, i) => ({
    ...d,
    sma: indicators.sma?.[i] ?? null,
    ema: indicators.ema?.[i] ?? null,
    bbUpper: indicators.bollinger?.upper?.[i] ?? null,
    bbLower: indicators.bollinger?.lower?.[i] ?? null,
    bbMiddle: indicators.bollinger?.middle?.[i] ?? null,
    rsi: indicators.rsi?.[i] ?? null,
    macd: indicators.macd?.macd?.[i] ?? null,
    macdSignal: indicators.macd?.signal?.[i] ?? null,
    macdHistogram: indicators.macd?.histogram?.[i] ?? null,
  }));
}

function IndicatorToggle({ activeIndicators, onToggle }) {
  return (
    <div className="flex flex-wrap gap-2 mb-3" data-testid="indicator-toggles">
      {ALL_INDICATORS.map((key) => {
        const active = activeIndicators.has(key);
        return (
          <button
            key={key}
            onClick={() => onToggle(key)}
            data-testid={`toggle-${key}`}
            className={`px-2 py-0.5 text-xs rounded border transition-colors ${
              active
                ? "bg-[#00e676] text-black border-[#00e676]"
                : "bg-transparent text-[#aaa] border-[#444] hover:border-[#888]"
            }`}
          >
            {INDICATOR_LABELS[key]}
          </button>
        );
      })}
    </div>
  );
}

function EventToggle({ activeEventTypes, onToggle }) {
  return (
    <div className="flex flex-wrap gap-2 mb-3" data-testid="event-toggles">
      {ALL_EVENT_TYPES.map((key) => {
        const active = activeEventTypes.has(key);
        const color = EVENT_COLORS[key];
        return (
          <button
            key={key}
            onClick={() => onToggle(key)}
            data-testid={`toggle-event-${key}`}
            className={`px-2 py-0.5 text-xs rounded border transition-colors`}
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

/**
 * Build a map from date string (YYYY-MM-DD) → time string ("HH:MM:SS") for the
 * first bar on that date. Used to position event reference lines.
 */
function buildDateToTimeMap(bars) {
  const map = {};
  for (const b of bars) {
    const d = new Date(b.timestamp);
    const dateKey = d.toISOString().slice(0, 10);
    if (!(dateKey in map)) {
      map[dateKey] = d.toLocaleTimeString();
    }
  }
  return map;
}

/**
 * Custom label for event reference lines shown inside the chart.
 */
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

export default function PriceChart({
  bars,
  trades,
  indicators = null,
  activeIndicators: externalActive = null,
  onToggleIndicator = null,
  events = [],
}) {
  const [localActive, setLocalActive] = useState(new Set());
  const [activeEventTypes, setActiveEventTypes] = useState(new Set(ALL_EVENT_TYPES));

  const activeIndicators = externalActive !== null ? externalActive : localActive;

  function handleToggle(key) {
    if (onToggleIndicator) {
      onToggleIndicator(key);
    } else {
      setLocalActive((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
    }
  }

  function handleEventToggle(key) {
    setActiveEventTypes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const baseData = bars.map((b) => ({
    time: new Date(b.timestamp).toLocaleTimeString(),
    price: parseFloat(b.close),
  }));

  const data = mergeIndicators(baseData, indicators);

  const buyTimes = new Set(
    trades.filter((t) => t.action === "buy").map((t) =>
      new Date(t.timestamp_open).toLocaleTimeString()
    )
  );
  const sellTimes = new Set(
    trades.filter((t) => t.action === "sell").map((t) =>
      new Date(t.timestamp_open).toLocaleTimeString()
    )
  );

  // Map event dates to bar time strings for positioning reference lines
  const dateToTime = buildDateToTimeMap(bars);
  const visibleEvents = events.filter(
    (e) => activeEventTypes.has(e.event_type) && dateToTime[e.event_date]
  );

  const showSma = activeIndicators.has("sma");
  const showEma = activeIndicators.has("ema");
  const showBollinger = activeIndicators.has("bollinger");
  const showRsi = activeIndicators.has("rsi");
  const showMacd = activeIndicators.has("macd");
  const hasEvents = events.length > 0;

  return (
    <div className="w-full" style={{ touchAction: "pan-y" }} data-testid="price-chart">
      <IndicatorToggle activeIndicators={activeIndicators} onToggle={handleToggle} />
      {hasEvents && (
        <EventToggle activeEventTypes={activeEventTypes} onToggle={handleEventToggle} />
      )}

      {/* Main price + overlay chart */}
      <ResponsiveContainer width="100%" height={240} minHeight={180}>
        <ComposedChart data={data}>
          <XAxis dataKey="time" tick={{ fontSize: 10 }} />
          <YAxis domain={["auto", "auto"]} />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const matchedEvent = visibleEvents.find(
                (e) => dateToTime[e.event_date] === label
              );
              return (
                <div className="bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-xs">
                  <div className="text-[#888] mb-1">{label}</div>
                  {payload.map((p) => (
                    <div key={p.dataKey} style={{ color: p.color }}>
                      {p.name}: {p.value?.toFixed ? p.value.toFixed(2) : p.value}
                    </div>
                  ))}
                  {matchedEvent && (
                    <div
                      className="mt-1 font-semibold"
                      style={{ color: EVENT_COLORS[matchedEvent.event_type] }}
                    >
                      {matchedEvent.description}
                    </div>
                  )}
                </div>
              );
            }}
          />

          {showBollinger && (
            <Area
              type="monotone"
              dataKey="bbUpper"
              stroke="#7c3aed"
              strokeDasharray="3 3"
              strokeWidth={1}
              fill="#7c3aed"
              fillOpacity={0.08}
              dot={false}
              activeDot={false}
              legendType="none"
            />
          )}
          {showBollinger && (
            <Area
              type="monotone"
              dataKey="bbLower"
              stroke="#7c3aed"
              strokeDasharray="3 3"
              strokeWidth={1}
              fill="#7c3aed"
              fillOpacity={0.08}
              dot={false}
              activeDot={false}
              legendType="none"
            />
          )}
          {showBollinger && (
            <Line
              type="monotone"
              dataKey="bbMiddle"
              stroke="#7c3aed"
              strokeDasharray="3 3"
              strokeWidth={1}
              dot={false}
            />
          )}

          <Line
            type="monotone"
            dataKey="price"
            dot={false}
            stroke="#2563eb"
            strokeWidth={2}
            activeDot={{ r: 5 }}
          />

          {showSma && (
            <Line
              type="monotone"
              dataKey="sma"
              stroke="#9ca3af"
              strokeDasharray="5 3"
              strokeWidth={1.5}
              dot={false}
              activeDot={false}
            />
          )}

          {showEma && (
            <Line
              type="monotone"
              dataKey="ema"
              stroke="#f97316"
              strokeDasharray="5 3"
              strokeWidth={1.5}
              dot={false}
              activeDot={false}
            />
          )}

          {data.map((d, i) =>
            buyTimes.has(d.time) ? (
              <ReferenceLine key={`b${i}`} x={d.time} stroke="green" label="B" />
            ) : null
          )}
          {data.map((d, i) =>
            sellTimes.has(d.time) ? (
              <ReferenceLine key={`s${i}`} x={d.time} stroke="red" label="S" />
            ) : null
          )}

          {/* Event calendar markers */}
          {visibleEvents.map((e) => (
            <ReferenceLine
              key={`evt-${e.id}`}
              x={dateToTime[e.event_date]}
              stroke={EVENT_COLORS[e.event_type]}
              strokeDasharray="4 2"
              strokeWidth={1.5}
              label={<EventLabel event={e} />}
              data-testid={`event-line-${e.event_type}`}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* RSI sub-chart */}
      {showRsi && (
        <div className="mt-2" data-testid="rsi-panel">
          <p className="text-[10px] text-[#888] uppercase tracking-widest mb-1">RSI</p>
          <ResponsiveContainer width="100%" height={80}>
            <ComposedChart data={data}>
              <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} width={24} />
              <Tooltip formatter={(v) => v?.toFixed(2)} />
              <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" />
              <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="rsi"
                stroke="#a78bfa"
                strokeWidth={1.5}
                dot={false}
                activeDot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* MACD sub-chart */}
      {showMacd && (
        <div className="mt-2" data-testid="macd-panel">
          <p className="text-[10px] text-[#888] uppercase tracking-widest mb-1">MACD</p>
          <ResponsiveContainer width="100%" height={80}>
            <ComposedChart data={data}>
              <XAxis dataKey="time" tick={false} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9 }} width={24} />
              <Tooltip formatter={(v) => v?.toFixed(4)} />
              <Bar dataKey="macdHistogram" fill="#64748b" opacity={0.7} />
              <Line
                type="monotone"
                dataKey="macd"
                stroke="#38bdf8"
                strokeWidth={1.5}
                dot={false}
                activeDot={false}
              />
              <Line
                type="monotone"
                dataKey="macdSignal"
                stroke="#fb923c"
                strokeWidth={1.5}
                dot={false}
                activeDot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
