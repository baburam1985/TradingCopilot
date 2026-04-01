import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import { getTrades, getLatestPrice } from "../api/client";
import { createSessionSocket } from "../api/client";
import PriceChart from "../components/PriceChart";
import TradeLog from "../components/TradeLog";

export default function LiveDashboard() {
  const { sessionId } = useParams();
  const [bars, setBars] = useState([]);
  const [trades, setTrades] = useState([]);
  const [latestPrice, setLatestPrice] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    getTrades(sessionId).then(r => setTrades(r.data));

    wsRef.current = createSessionSocket(sessionId, (msg) => {
      if (msg.type === "price_update") {
        setLatestPrice(msg.close);
        setBars(prev => [...prev.slice(-199), { timestamp: msg.timestamp, close: msg.close }]);
        getTrades(sessionId).then(r => setTrades(r.data));
      }
    });

    return () => wsRef.current?.close();
  }, [sessionId]);

  const openTrade = trades.find(t => t.status === "open");
  const unrealizedPnl = openTrade && latestPrice
    ? ((latestPrice - parseFloat(openTrade.price_at_signal)) * parseFloat(openTrade.quantity)).toFixed(2)
    : null;

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Live Dashboard</h2>
      {latestPrice && <p>Current Price: <strong>${latestPrice.toFixed(2)}</strong></p>}
      {openTrade && (
        <div style={{ padding: "0.5rem", background: "#f0f9ff", borderRadius: 4, marginBottom: "1rem" }}>
          <strong>Open Position</strong> — Entry: ${parseFloat(openTrade.price_at_signal).toFixed(2)} |
          Unrealized P&L: <span style={{ color: unrealizedPnl > 0 ? "green" : "red" }}>${unrealizedPnl}</span>
        </div>
      )}
      <PriceChart bars={bars} trades={trades} />
      <h3>Trade Log</h3>
      <TradeLog trades={trades} />
    </div>
  );
}
