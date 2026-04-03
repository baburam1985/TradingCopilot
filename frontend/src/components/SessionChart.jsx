import { useEffect, useRef, useState, useCallback } from "react";
import { createChart, CrosshairMode } from "lightweight-charts";
import { getChartData, getIndicators } from "../api/client";

const STRATEGY_INDICATORS = {
  rsi: ["rsi"],
  macd: ["macd"],
  bollinger_bands: ["bollinger"],
  moving_average_crossover: ["sma", "ema"],
  vwap: ["vwap"],
  breakout: ["breakout"],
  mean_reversion: ["mean_reversion"],
};

const ZOOM_OPTIONS = [
  { label: "Session", value: "session" },
  { label: "60 min", value: "60m" },
];

/**
 * Filter candles to last N minutes from the most recent candle.
 */
function filterLast60Minutes(candles) {
  if (!candles.length) return candles;
  const latest = candles[candles.length - 1].time;
  const cutoff = latest - 60 * 60;
  return candles.filter((c) => c.time >= cutoff);
}

/**
 * Filter indicator data points to match candle time range.
 */
function filterByTimeRange(points, minTime, maxTime) {
  return points.filter((p) => {
    const t = typeof p.time === "string" ? Math.floor(new Date(p.time).getTime() / 1000) : p.time;
    return t >= minTime && t <= maxTime;
  });
}

function normalizeTime(points) {
  return points.map((p) => ({
    ...p,
    time: typeof p.time === "string" ? Math.floor(new Date(p.time).getTime() / 1000) : p.time,
  }));
}

export default function SessionChart({ sessionId, strategy, isActive = false }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const subChartRef = useRef(null);
  const refreshTimerRef = useRef(null);

  const [zoom, setZoom] = useState("session");
  const [tooltip, setTooltip] = useState(null);
  const [signals, setSignals] = useState([]);
  const [allCandles, setAllCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Build and render the chart
  const buildChart = useCallback((candles, sigs, indicators, currentZoom) => {
    if (!containerRef.current) return;

    // Destroy previous chart instance
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    }
    if (subChartRef.current) {
      subChartRef.current.remove();
      subChartRef.current = null;
    }

    if (!candles.length) return;

    const displayCandles =
      currentZoom === "60m" ? filterLast60Minutes(candles) : candles;

    if (!displayCandles.length) return;

    const minTime = displayCandles[0].time;
    const maxTime = displayCandles[displayCandles.length - 1].time;

    // Determine which sub-panel indicators are needed (RSI or MACD)
    const strategyIndicators = STRATEGY_INDICATORS[strategy] || [];
    const needsRsiPanel = strategyIndicators.includes("rsi") && indicators?.rsi?.length > 0;
    const needsMacdPanel = strategyIndicators.includes("macd") && indicators?.macd?.length > 0;
    const hasSubPanel = needsRsiPanel || needsMacdPanel;

    // --- Main price chart ---
    const mainHeight = hasSubPanel ? 260 : 320;
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: mainHeight,
      layout: { background: { color: "#141414" }, textColor: "#aaa" },
      grid: {
        vertLines: { color: "#1e1e1e" },
        hLines: { color: "#1e1e1e" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#333" },
      timeScale: { borderColor: "#333", timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });
    candleSeries.setData(displayCandles);
    candleSeriesRef.current = candleSeries;

    // --- Strategy indicator overlays on main chart ---
    if (indicators) {
      if (strategyIndicators.includes("sma") && indicators.sma?.length > 0) {
        const smaSeries = chart.addLineSeries({ color: "#9ca3af", lineWidth: 1, lineStyle: 2 });
        const smaData = normalizeTime(filterByTimeRange(indicators.sma, minTime, maxTime));
        smaSeries.setData(smaData.map((p) => ({ time: p.time, value: p.value })));
      }
      if (strategyIndicators.includes("ema") && indicators.ema?.length > 0) {
        const emaSeries = chart.addLineSeries({ color: "#f97316", lineWidth: 1, lineStyle: 2 });
        const emaData = normalizeTime(filterByTimeRange(indicators.ema, minTime, maxTime));
        emaSeries.setData(emaData.map((p) => ({ time: p.time, value: p.value })));
      }
      if (strategyIndicators.includes("bollinger") && indicators.bollinger?.length > 0) {
        const bbData = normalizeTime(filterByTimeRange(indicators.bollinger, minTime, maxTime));
        const bbUpper = chart.addLineSeries({ color: "#7c3aed", lineWidth: 1, lineStyle: 2 });
        const bbMiddle = chart.addLineSeries({ color: "#7c3aed", lineWidth: 1, lineStyle: 2 });
        const bbLower = chart.addLineSeries({ color: "#7c3aed", lineWidth: 1, lineStyle: 2 });
        bbUpper.setData(bbData.map((p) => ({ time: p.time, value: p.upper })));
        bbMiddle.setData(bbData.map((p) => ({ time: p.time, value: p.middle })));
        bbLower.setData(bbData.map((p) => ({ time: p.time, value: p.lower })));
      }
      if (strategyIndicators.includes("vwap") && indicators.vwap?.length > 0) {
        const vwapSeries = chart.addLineSeries({ color: "#38bdf8", lineWidth: 1.5 });
        const vwapData = normalizeTime(filterByTimeRange(indicators.vwap, minTime, maxTime));
        vwapSeries.setData(vwapData.map((p) => ({ time: p.time, value: p.value })));
      }
      if (strategyIndicators.includes("breakout") && indicators.breakout?.length > 0) {
        const boData = normalizeTime(filterByTimeRange(indicators.breakout, minTime, maxTime));
        const boHigh = chart.addLineSeries({ color: "#22c55e", lineWidth: 1, lineStyle: 1 });
        const boLow = chart.addLineSeries({ color: "#ef4444", lineWidth: 1, lineStyle: 1 });
        boHigh.setData(boData.map((p) => ({ time: p.time, value: p.high })));
        boLow.setData(boData.map((p) => ({ time: p.time, value: p.low })));
      }
      if (strategyIndicators.includes("mean_reversion") && indicators.mean_reversion?.length > 0) {
        const mrData = normalizeTime(filterByTimeRange(indicators.mean_reversion, minTime, maxTime));
        const mrMean = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1.5 });
        const mrUpper = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1, lineStyle: 2 });
        const mrLower = chart.addLineSeries({ color: "#a78bfa", lineWidth: 1, lineStyle: 2 });
        mrMean.setData(mrData.map((p) => ({ time: p.time, value: p.mean })));
        mrUpper.setData(mrData.map((p) => ({ time: p.time, value: p.upper })));
        mrLower.setData(mrData.map((p) => ({ time: p.time, value: p.lower })));
      }
    }

    // --- Signal markers (buy/sell arrows) ---
    const displaySigs = sigs.filter((s) => s.time >= minTime && s.time <= maxTime);
    const markers = displaySigs.map((s) => ({
      time: s.time,
      position: s.action === "buy" ? "belowBar" : "aboveBar",
      color: s.action === "buy" ? "#22c55e" : "#ef4444",
      shape: s.action === "buy" ? "arrowUp" : "arrowDown",
      text: s.pnl_pct != null ? `${s.pnl_pct > 0 ? "+" : ""}${s.pnl_pct}%` : "",
    }));
    if (markers.length > 0) {
      candleSeries.setMarkers(markers);
    }

    // Crosshair move → show reasoning tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!param.point || !param.time) {
        setTooltip(null);
        return;
      }
      const sig = displaySigs.find((s) => s.time === param.time);
      if (sig?.reasoning_text) {
        setTooltip({
          x: param.point.x,
          y: param.point.y,
          text: sig.reasoning_text,
          action: sig.action,
          price: sig.price,
          pnl_pct: sig.pnl_pct,
        });
      } else {
        setTooltip(null);
      }
    });

    chart.timeScale().fitContent();

    // --- Sub-panel (RSI or MACD) ---
    if (hasSubPanel && containerRef.current.parentElement) {
      // Find or create the sub-panel container
      let subContainer = containerRef.current.parentElement.querySelector("[data-sub-chart]");
      if (!subContainer) {
        subContainer = document.createElement("div");
        subContainer.setAttribute("data-sub-chart", "true");
        containerRef.current.parentElement.appendChild(subContainer);
      }

      const subChart = createChart(subContainer, {
        width: containerRef.current.clientWidth,
        height: 80,
        layout: { background: { color: "#141414" }, textColor: "#888" },
        grid: { vertLines: { color: "#1e1e1e" }, hLines: { color: "#1e1e1e" } },
        crosshair: { mode: CrosshairMode.Normal },
        rightPriceScale: { borderColor: "#333" },
        timeScale: { borderColor: "#333", timeVisible: true, secondsVisible: false, visible: false },
      });
      subChartRef.current = subChart;

      if (needsRsiPanel) {
        const rsiSeries = subChart.addLineSeries({ color: "#a78bfa", lineWidth: 1.5 });
        const rsiData = normalizeTime(filterByTimeRange(indicators.rsi, minTime, maxTime));
        rsiSeries.setData(rsiData.map((p) => ({ time: p.time, value: p.value })));
        // Overbought/oversold reference lines
        subChart.addLineSeries({ color: "#ef4444", lineWidth: 1, lineStyle: 2 }).setData(
          rsiData.map((p) => ({ time: p.time, value: 70 }))
        );
        subChart.addLineSeries({ color: "#22c55e", lineWidth: 1, lineStyle: 2 }).setData(
          rsiData.map((p) => ({ time: p.time, value: 30 }))
        );
        subChart.timeScale().fitContent();
      } else if (needsMacdPanel) {
        const macdData = normalizeTime(filterByTimeRange(indicators.macd, minTime, maxTime));
        const macdLine = subChart.addLineSeries({ color: "#38bdf8", lineWidth: 1.5 });
        const signalLine = subChart.addLineSeries({ color: "#fb923c", lineWidth: 1.5 });
        const histSeries = subChart.addHistogramSeries({
          color: "#64748b",
          priceFormat: { type: "price", precision: 4 },
        });
        macdLine.setData(macdData.map((p) => ({ time: p.time, value: p.macd })));
        signalLine.setData(macdData.map((p) => ({ time: p.time, value: p.signal })));
        histSeries.setData(
          macdData.map((p) => ({
            time: p.time,
            value: p.histogram,
            color: p.histogram >= 0 ? "#26a69a" : "#ef5350",
          }))
        );
        subChart.timeScale().fitContent();
      }

      // Sync time scales
      chart.timeScale().subscribeVisibleTimeRangeChange(() => {
        const range = chart.timeScale().getVisibleRange();
        if (range) subChart.timeScale().setVisibleRange(range);
      });
    }

    // Handle resize
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [strategy]);

  const loadData = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [chartResp, indResp] = await Promise.all([
        getChartData(sessionId),
        getIndicators(sessionId).catch(() => ({ data: null })),
      ]);
      const { candles, signals: sigs } = chartResp.data;
      setAllCandles(candles);
      setSignals(sigs);
      buildChart(candles, sigs, indResp.data, zoom);
    } catch (e) {
      setError("Failed to load chart data");
    } finally {
      setLoading(false);
    }
  }, [sessionId, buildChart, zoom]);

  // Initial load
  useEffect(() => {
    loadData();
  }, [sessionId]);

  // Auto-refresh every 30s for active sessions
  useEffect(() => {
    if (!isActive) return;
    refreshTimerRef.current = setInterval(loadData, 30_000);
    return () => clearInterval(refreshTimerRef.current);
  }, [isActive, loadData]);

  // Re-render chart when zoom changes
  useEffect(() => {
    if (!allCandles.length) return;
    getIndicators(sessionId)
      .then((r) => buildChart(allCandles, signals, r.data, zoom))
      .catch(() => buildChart(allCandles, signals, null, zoom));
  }, [zoom]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
      if (subChartRef.current) { subChartRef.current.remove(); subChartRef.current = null; }
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
      // Remove any orphaned sub-panel DOM nodes
      if (containerRef.current?.parentElement) {
        const sub = containerRef.current.parentElement.querySelector("[data-sub-chart]");
        if (sub) sub.remove();
      }
    };
  }, []);

  return (
    <div className="w-full" data-testid="session-chart">
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[#00e676] text-xs uppercase tracking-widest">Price Chart</span>
        <div className="flex gap-1">
          {ZOOM_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setZoom(opt.value)}
              data-testid={`zoom-${opt.value}`}
              className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                zoom === opt.value
                  ? "bg-[#00e676] text-black border-[#00e676]"
                  : "bg-transparent text-[#aaa] border-[#444] hover:border-[#888]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-[#888] text-xs z-10">
            Loading chart…
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-[#ef4444] text-xs z-10">
            {error}
          </div>
        )}

        {/* Reasoning tooltip */}
        {tooltip && (
          <div
            data-testid="signal-tooltip"
            className="absolute z-20 bg-[#1e1e1e] border border-[#333] rounded p-2 text-xs max-w-[220px] pointer-events-none"
            style={{ left: tooltip.x + 12, top: tooltip.y - 40 }}
          >
            <div className={`font-bold mb-1 ${tooltip.action === "buy" ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
              {tooltip.action.toUpperCase()} @ ${tooltip.price?.toFixed(2)}
              {tooltip.pnl_pct != null && (
                <span className={`ml-2 ${tooltip.pnl_pct >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
                  {tooltip.pnl_pct > 0 ? "+" : ""}{tooltip.pnl_pct}%
                </span>
              )}
            </div>
            <div className="text-[#ccc]">{tooltip.text}</div>
          </div>
        )}

        <div ref={containerRef} className="w-full" style={{ minHeight: 260 }} />
      </div>
    </div>
  );
}
