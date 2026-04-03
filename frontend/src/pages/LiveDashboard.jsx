import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import { getTrades, getLatestPrice } from "../api/client";
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
  const wsRef = useRef(null);
  const { addNotification } = useNotifications();

  useEffect(() => {
    getTrades(sessionId).then(r => setTrades(r.data));

    wsRef.current = createSessionSocket(sessionId, (msg) => {
      if (msg.type === "price_update") {
        setLatestPrice(msg.close);
        setBars(prev => [...prev.slice(-199), { timestamp: msg.timestamp, close: msg.close }]);
        getTrades(sessionId).then(r => setTrades(r.data));
      } else if (msg.type === "notification") {
        addNotification(msg);
      }
    });

    return () => wsRef.current?.close();
  }, [sessionId]);

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
        <PriceChart bars={bars} trades={trades} />
      </div>

      {/* Trade Log */}
      <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
        <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Trade Log</h2>
        <TradeLog trades={trades} />
      </div>
    </div>
  );
}
