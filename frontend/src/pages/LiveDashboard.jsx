import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import { getTrades, getLatestPrice, getIndicators, getRegime, getSessions } from "../api/client";
import { createSessionSocket } from "../api/client";
import PriceChart from "../components/PriceChart";
import TradeLog from "../components/TradeLog";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";
import { useNotifications } from "../context/NotificationContext";

export default function LiveDashboard() {
  const { sessionId } = useParams();
  const [bars, setBars] = useState([]);
  const [trades, setTrades] = useState([]);
  const [latestPrice, setLatestPrice] = useState(null);
  const [indicators, setIndicators] = useState(null);
  const [activeIndicators, setActiveIndicators] = useState(new Set());
  const [regime, setRegime] = useState(null);
  const wsRef = useRef(null);
  const { addNotification, hydrate } = useNotifications();

  useEffect(() => {
    getTrades(sessionId).then(r => setTrades(r.data));
    getIndicators(sessionId).then(r => setIndicators(r.data)).catch(() => {});

    wsRef.current = createSessionSocket(sessionId, (msg) => {
      if (msg.type === "price_update") {
        setLatestPrice(msg.close);
        setBars(prev => [...prev.slice(-199), { timestamp: msg.timestamp, close: msg.close }]);
        getTrades(sessionId).then(r => setTrades(r.data));
        getIndicators(sessionId).then(r => setIndicators(r.data)).catch(() => {});
      } else if (msg.type === "notification") {
        addNotification(msg);
      }
    });

    // Hydrate notification history from persisted alerts once WS is set up.
    hydrate(sessionId);

    // Fetch session symbol then poll regime every 5 minutes
    let regimeInterval = null;
    getSessions().then((r) => {
      const session = r.data.find((s) => s.id === sessionId);
      if (!session?.symbol) return;
      const fetchRegime = () =>
        getRegime(session.symbol)
          .then((res) => setRegime(res.data))
          .catch(() => {});
      fetchRegime();
      regimeInterval = setInterval(fetchRegime, 5 * 60 * 1000);
    }).catch(() => {});

    return () => {
      wsRef.current?.close();
      clearInterval(regimeInterval);
    };
  }, [sessionId]);

  function handleToggleIndicator(key) {
    setActiveIndicators(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const openTrade = trades.find(t => t.status === "open");
  const unrealizedPnl = openTrade && latestPrice
    ? ((latestPrice - parseFloat(openTrade.price_at_signal)) * parseFloat(openTrade.quantity)).toFixed(2)
    : null;

  const totalTrades = trades.length;
  const closedTrades = trades.filter(t => t.status === "closed");
  const winners = closedTrades.filter(t => parseFloat(t.pnl ?? 0) > 0);
  const winRate = closedTrades.length > 0
    ? `${((winners.length / closedTrades.length) * 100).toFixed(0)}%`
    : "—";

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › DASHBOARD"
        title="Live Dashboard"
        subtitle={sessionId ? `Session ${sessionId}` : "Monitoring active session"}
      />
      {regime && (
        <div className="mb-4 flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold"
            style={{
              background:
                regime.regime === "TRENDING_UP" ? "#00e676" :
                regime.regime === "TRENDING_DOWN" ? "#ff4444" :
                regime.regime === "SIDEWAYS_HIGH_VOL" ? "#ffb300" : "#888",
              color: regime.regime === "TRENDING_DOWN" ? "#fff" : "#000",
            }}
          >
            Market:{" "}
            {{
              TRENDING_UP: "Trending Up",
              TRENDING_DOWN: "Trending Down",
              SIDEWAYS_HIGH_VOL: "Sideways (High Vol)",
              SIDEWAYS_LOW_VOL: "Sideways (Low Vol)",
            }[regime.regime] ?? regime.regime}
          </span>
          <span className="text-[#555] text-xs">ADX {regime.adx}</span>
        </div>
      )}

      {/* Metrics row — horizontal scroll on mobile */}
      <div className="overflow-x-auto mb-8 -mx-6 px-6 sm:mx-0 sm:px-0">
      <div className="grid grid-cols-4 gap-4 min-w-[480px] sm:min-w-0">
        <MetricCard
          label="Current Price"
          value={latestPrice ? `$${latestPrice.toFixed(2)}` : "—"}
          valueColor="green"
        />
        <MetricCard
          label="Open P&L"
          value={unrealizedPnl !== null ? `$${unrealizedPnl}` : "—"}
          valueColor={unrealizedPnl !== null ? (unrealizedPnl > 0 ? "green" : "red") : undefined}
        />
        <MetricCard label="Total Trades" value={totalTrades > 0 ? totalTrades : "—"} />
        <MetricCard label="Win Rate" value={winRate} valueColor={winRate !== "—" ? "green" : undefined} />
      </div>
      </div>

      {/* Charts */}
      <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4 mb-4">
        <PriceChart
          bars={bars}
          trades={trades}
          indicators={indicators}
          activeIndicators={activeIndicators}
          onToggleIndicator={handleToggleIndicator}
        />
      </div>

      {/* Trade Log */}
      <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
        <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Trade Log</h2>
        <TradeLog trades={trades} />
      </div>
    </div>
  );
}
