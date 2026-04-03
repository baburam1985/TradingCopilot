import { useState, useEffect, useRef } from "react";
import { getRegime } from "../api/client";

const REGIME_LABELS = {
  TRENDING_UP: "Trending Up",
  TRENDING_DOWN: "Trending Down",
  SIDEWAYS_HIGH_VOL: "Sideways (High Vol)",
  SIDEWAYS_LOW_VOL: "Sideways (Low Vol)",
};

function scoreColor(score) {
  if (score >= 70) return { bg: "#00e676", text: "#000" };
  if (score >= 40) return { bg: "#ffb300", text: "#000" };
  return { bg: "#ff4444", text: "#fff" };
}

/**
 * FitnessBadge — shows strategy fitness score for the current market regime.
 *
 * Props:
 *   symbol   string  — ticker symbol
 *   strategy string  — strategy name
 */
export default function FitnessBadge({ symbol, strategy }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (!symbol || !strategy) {
      setData(null);
      return;
    }

    // 800ms debounce to avoid hammering the API while the user is typing
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      getRegime(symbol)
        .then((r) => setData(r.data))
        .catch(() => setData(null))
        .finally(() => setLoading(false));
    }, 800);

    return () => clearTimeout(debounceRef.current);
  }, [symbol, strategy]);

  if (!symbol || !strategy) return null;

  if (loading) {
    return (
      <div className="flex items-center gap-1.5 mt-1">
        <div className="w-2 h-2 rounded-full bg-[#333] animate-pulse" />
        <span className="text-[#555] text-xs">Checking regime…</span>
      </div>
    );
  }

  if (!data) return null;

  const score = data.fitness_scores?.[strategy] ?? 50;
  const { bg, text } = scoreColor(score);
  const regimeLabel = REGIME_LABELS[data.regime] ?? data.regime;

  return (
    <div className="relative inline-flex items-center gap-2 mt-1">
      {/* Score badge */}
      <span
        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold cursor-default select-none"
        style={{ background: bg, color: text }}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        Fitness {score}/100
      </span>

      {/* Regime label */}
      <span className="text-[#666] text-xs">{regimeLabel}</span>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute left-0 top-full mt-1.5 z-50 w-56 bg-[#1e1e1e] border border-[#333] rounded p-3 shadow-xl text-xs text-[#ccc]">
          <p className="font-semibold text-white mb-1">{strategy}</p>
          <p className="mb-1">
            Regime: <span className="text-[#00e676]">{regimeLabel}</span>
          </p>
          <p className="mb-1">
            ADX: <span className="text-white">{data.adx}</span>
            <span className="ml-2">ATR%: {data.atr_pct}%</span>
          </p>
          <p className="mb-1">
            Confidence: <span className="text-white">{data.confidence}%</span>
          </p>
          <p className="text-[#888] mt-1 leading-snug">
            Score reflects how well this strategy historically performs in the
            current market regime.
          </p>
        </div>
      )}
    </div>
  );
}
