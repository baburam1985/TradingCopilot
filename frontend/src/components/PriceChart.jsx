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

export default function PriceChart({
  bars,
  trades,
  indicators = null,
  activeIndicators: externalActive = null,
  onToggleIndicator = null,
}) {
  const [localActive, setLocalActive] = useState(new Set());

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

  const showSma = activeIndicators.has("sma");
  const showEma = activeIndicators.has("ema");
  const showBollinger = activeIndicators.has("bollinger");
  const showRsi = activeIndicators.has("rsi");
  const showMacd = activeIndicators.has("macd");

  return (
    <div className="w-full" style={{ touchAction: "pan-y" }} data-testid="price-chart">
      <IndicatorToggle activeIndicators={activeIndicators} onToggle={handleToggle} />

      {/* Main price + overlay chart */}
      <ResponsiveContainer width="100%" height={240} minHeight={180}>
        <ComposedChart data={data}>
          <XAxis dataKey="time" tick={{ fontSize: 10 }} />
          <YAxis domain={["auto", "auto"]} />
          <Tooltip />

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
