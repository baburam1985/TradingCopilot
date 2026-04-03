import { useState } from "react";

/**
 * Renders a 2D heatmap from optimization results.
 *
 * Props:
 *   results  — array of { parameters, sharpe_ratio, total_pnl, win_rate, num_trades }
 *   metric   — "sharpe" | "pnl" | "win_rate" (which value drives the color)
 */

const METRIC_LABELS = {
  sharpe: "Sharpe Ratio",
  pnl: "Total P&L",
  win_rate: "Win Rate",
};

function metricValue(row, metric) {
  if (metric === "sharpe") return row.sharpe_ratio ?? -Infinity;
  if (metric === "pnl") return row.total_pnl;
  if (metric === "win_rate") return row.win_rate;
  return 0;
}

/** Map a 0–1 normalized value to an HSL color: red (0) → yellow (0.5) → green (1) */
function metricColor(norm) {
  // hue: 0 = red, 60 = yellow, 120 = green
  const hue = Math.round(norm * 120);
  return `hsl(${hue}, 60%, 35%)`;
}

/**
 * Given results, pick two parameter keys that have multiple unique values.
 * Falls back to the first two keys if all params are single-valued.
 */
function pickAxes(results) {
  if (!results.length) return [null, null];
  const allKeys = Object.keys(results[0].parameters);
  if (allKeys.length < 2) return [allKeys[0] ?? null, null];

  const multiValueKeys = allKeys.filter((k) => {
    const vals = new Set(results.map((r) => r.parameters[k]));
    return vals.size > 1;
  });

  if (multiValueKeys.length >= 2) return [multiValueKeys[0], multiValueKeys[1]];
  if (multiValueKeys.length === 1) return [multiValueKeys[0], allKeys.find((k) => k !== multiValueKeys[0])];
  return [allKeys[0], allKeys[1]];
}

export default function OptimizeHeatmap({ results, metric = "sharpe" }) {
  const [hoveredCell, setHoveredCell] = useState(null);

  if (!results || results.length === 0) {
    return (
      <div data-testid="optimize-heatmap">
        <p className="text-[#555] text-sm">No results to display.</p>
      </div>
    );
  }

  const [xKey, yKey] = pickAxes(results);

  // Determine unique sorted values for each axis
  const xVals = xKey
    ? [...new Set(results.map((r) => r.parameters[xKey]))].sort((a, b) => a - b)
    : [null];
  const yVals = yKey
    ? [...new Set(results.map((r) => r.parameters[yKey]))].sort((a, b) => a - b)
    : [null];

  // Index results into a map for O(1) lookup
  const cellMap = new Map();
  const rawValues = [];
  results.forEach((r) => {
    const x = xKey ? r.parameters[xKey] : null;
    const y = yKey ? r.parameters[yKey] : null;
    cellMap.set(`${x}::${y}`, r);
    rawValues.push(metricValue(r, metric));
  });

  const minVal = Math.min(...rawValues);
  const maxVal = Math.max(...rawValues);
  const range = maxVal - minVal || 1;

  // Best result by metric
  const bestResult = results.reduce(
    (best, r) => (metricValue(r, metric) > metricValue(best, metric) ? r : best),
    results[0]
  );
  const bestKey = `${xKey ? bestResult.parameters[xKey] : null}::${yKey ? bestResult.parameters[yKey] : null}`;

  const fmt = (v, d = 2) => (v != null && isFinite(v) ? Number(v).toFixed(d) : "—");

  const singleAxis = !xKey || !yKey;

  return (
    <div data-testid="optimize-heatmap" className="space-y-4">
      {/* Metric selector row */}
      <div className="flex items-center gap-4">
        <span className="text-[#888] text-xs uppercase tracking-wider">Color by:</span>
        {Object.entries(METRIC_LABELS).map(([key, label]) => (
          <span key={key} className={`text-xs px-2 py-0.5 rounded cursor-default ${metric === key ? "bg-[#00e676]/20 text-[#00e676] font-semibold" : "text-[#666]"}`}>
            {label}
          </span>
        ))}
      </div>

      {singleAxis ? (
        <p className="text-[#555] text-xs">
          Heatmap requires at least two parameters with multiple values. Showing table only.
        </p>
      ) : (
        <div className="overflow-x-auto">
          {/* Axis labels */}
          <div className="mb-1 text-[#555] text-xs">
            Y: <span className="text-[#888]">{yKey}</span> &nbsp;/&nbsp; X:{" "}
            <span className="text-[#888]">{xKey}</span>
          </div>

          <table className="border-collapse" data-testid="heatmap-grid">
            <thead>
              <tr>
                {/* corner */}
                <th className="w-16 text-[#444] text-[10px] pr-2 text-right">{yKey} ╲ {xKey}</th>
                {xVals.map((xv) => (
                  <th
                    key={xv}
                    className="text-[#888] text-[10px] font-normal px-2 pb-1 text-center min-w-[52px]"
                  >
                    {xv}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {yVals.map((yv) => (
                <tr key={yv}>
                  <td className="text-[#888] text-[10px] pr-2 text-right whitespace-nowrap">
                    {yv}
                  </td>
                  {xVals.map((xv) => {
                    const cellKey = `${xv}::${yv}`;
                    const row = cellMap.get(cellKey);
                    const val = row ? metricValue(row, metric) : null;
                    const norm = val != null && isFinite(val) ? (val - minVal) / range : 0;
                    const isBest = cellKey === bestKey;

                    return (
                      <td
                        key={xv}
                        data-testid={`heatmap-cell-${xv}-${yv}`}
                        data-norm={row ? norm.toFixed(4) : null}
                        data-metric={row ? metricValue(row, metric) : null}
                        className={`relative w-14 h-10 text-center text-[10px] font-semibold cursor-default transition-opacity ${
                          isBest ? "ring-2 ring-[#ffd700] ring-inset" : ""
                        }`}
                        style={{
                          backgroundColor: row ? metricColor(norm) : "#111",
                          color: norm > 0.45 ? "#fff" : "#ccc",
                        }}
                        onMouseEnter={() => setHoveredCell(cellKey)}
                        onMouseLeave={() => setHoveredCell(null)}
                      >
                        {row ? (
                          <>
                            {isBest && (
                              <span className="absolute top-0.5 right-0.5 text-[#ffd700] text-[8px]">★</span>
                            )}
                            {fmt(val)}
                            {hoveredCell === cellKey && row && (
                              <div
                                data-testid="heatmap-tooltip"
                                className="absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-1 bg-[#0d0d0d] border border-[#333] rounded px-2 py-1 text-[9px] text-left whitespace-nowrap shadow-lg pointer-events-none"
                              >
                                <div className="text-[#888] mb-0.5">
                                  {xKey}: {xv} / {yKey}: {yv}
                                </div>
                                <div>Sharpe: {fmt(row.sharpe_ratio)}</div>
                                <div>P&amp;L: ${fmt(row.total_pnl)}</div>
                                <div>Win Rate: {(row.win_rate * 100).toFixed(0)}%</div>
                                <div>Trades: {row.num_trades}</div>
                              </div>
                            )}
                          </>
                        ) : (
                          <span className="text-[#333]">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>

          {/* Color scale legend */}
          <div className="flex items-center gap-2 mt-3">
            <span className="text-[#555] text-[10px]">Low</span>
            <div
              className="h-2 w-24 rounded"
              style={{
                background: "linear-gradient(to right, hsl(0,60%,35%), hsl(60,60%,35%), hsl(120,60%,35%))",
              }}
            />
            <span className="text-[#555] text-[10px]">High</span>
          </div>
        </div>
      )}

      {/* Best parameters summary card */}
      <div
        data-testid="best-params-card"
        className="bg-[#1a2a1a] border border-[#00e676]/30 rounded p-4 mt-4"
      >
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[#ffd700] text-sm">★</span>
          <h3 className="text-[#00e676] text-xs uppercase tracking-widest">
            Best Parameters Found
          </h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          {Object.entries(bestResult.parameters).map(([k, v]) => (
            <div key={k} className="flex flex-col gap-0.5">
              <span className="text-[#555] text-[10px] uppercase">{k}</span>
              <span className="text-white text-sm font-semibold font-mono">{v}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3 text-xs text-[#888] border-t border-[#1e3a2e] pt-3">
          <div>
            Sharpe:{" "}
            <span className={bestResult.sharpe_ratio >= 1 ? "text-[#00e676]" : "text-white"}>
              {fmt(bestResult.sharpe_ratio)}
            </span>
          </div>
          <div>
            P&amp;L:{" "}
            <span className={bestResult.total_pnl >= 0 ? "text-[#00e676]" : "text-[#ff4444]"}>
              {bestResult.total_pnl >= 0 ? "+" : ""}${fmt(bestResult.total_pnl)}
            </span>
          </div>
          <div>
            Win Rate:{" "}
            <span className="text-white">{(bestResult.win_rate * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
