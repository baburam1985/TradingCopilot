import { useState, useEffect, useRef } from "react";
import {
  getWatchlist,
  createWatchlistItem,
  deleteWatchlistItem,
  createWatchlistSocket,
} from "../api/client";
import PageHeader from "../components/PageHeader";
import { useNotifications } from "../context/NotificationContext";

const SIGNAL_BADGE = {
  buy:  "bg-[#00e676]/10 text-[#00e676] border border-[#00e676]/30",
  sell: "bg-red-500/10 text-red-400 border border-red-500/30",
  hold: "bg-[#1e1e1e] text-[#888] border border-[#333]",
};

function AddItemModal({ onClose, onAdd }) {
  const [form, setForm] = useState({
    symbol: "",
    strategy: "rsi",
    alert_threshold: "",
    notify_email: false,
    email_address: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        symbol: form.symbol.trim().toUpperCase(),
        strategy: form.strategy,
        strategy_params: {},
        alert_threshold: form.alert_threshold ? parseFloat(form.alert_threshold) : null,
        notify_email: form.notify_email,
        email_address: form.notify_email ? form.email_address : null,
      };
      const resp = await createWatchlistItem(payload);
      onAdd(resp.data);
      onClose();
    } catch (err) {
      setError(err?.response?.data?.detail ?? "Failed to add symbol");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#141414] border border-[#1e1e1e] rounded-lg p-6 w-full max-w-md">
        <h2 className="text-[#00e676] text-sm uppercase tracking-widest mb-4">Add Symbol to Watchlist</h2>
        {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Symbol</label>
            <input
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              placeholder="AAPL"
              required
            />
          </div>
          <div>
            <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Strategy</label>
            <select
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
              value={form.strategy}
              onChange={(e) => setForm({ ...form, strategy: e.target.value })}
            >
              <option value="rsi">RSI</option>
              <option value="moving_average_crossover">Moving Average Crossover</option>
              <option value="bollinger_bands">Bollinger Bands</option>
              <option value="macd">MACD</option>
            </select>
          </div>
          <div>
            <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Alert Threshold (price, optional)</label>
            <input
              type="number"
              step="0.01"
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
              value={form.alert_threshold}
              onChange={(e) => setForm({ ...form, alert_threshold: e.target.value })}
              placeholder="e.g. 180.00"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="notify_email"
              checked={form.notify_email}
              onChange={(e) => setForm({ ...form, notify_email: e.target.checked })}
            />
            <label htmlFor="notify_email" className="text-[#888] text-xs uppercase tracking-wide">Email Alerts</label>
          </div>
          {form.notify_email && (
            <div>
              <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Email Address</label>
              <input
                type="email"
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
                value={form.email_address}
                onChange={(e) => setForm({ ...form, email_address: e.target.value })}
                required={form.notify_email}
              />
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#00e676] text-black text-sm font-bold py-2 rounded hover:bg-[#00c853] disabled:opacity-50 transition-colors"
            >
              {loading ? "Adding..." : "Add to Watchlist"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-[#1e1e1e] text-[#888] text-sm py-2 rounded hover:text-white transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Watchlist() {
  const [items, setItems] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const wsRef = useRef(null);
  const { addNotification } = useNotifications();

  useEffect(() => {
    getWatchlist().then((r) => setItems(r.data));

    wsRef.current = createWatchlistSocket((msg) => {
      if (msg.type === "notification") {
        addNotification(msg);
        // Update signal badge for the relevant item
        if (msg.watchlist_item_id) {
          setItems((prev) =>
            prev.map((item) =>
              String(item.id) === msg.watchlist_item_id
                ? {
                    ...item,
                    last_signal: msg.message.includes("BUY")
                      ? "buy"
                      : msg.message.includes("SELL")
                      ? "sell"
                      : item.last_signal,
                  }
                : item
            )
          );
        }
      }
    });

    return () => wsRef.current?.close();
  }, []);

  const handleAdd = (newItem) => {
    setItems((prev) => [newItem, ...prev]);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Remove this symbol from your watchlist?")) return;
    await deleteWatchlistItem(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › WATCHLIST"
        title="Watchlist"
        subtitle="Monitor signals across multiple symbols without committing capital"
      />

      <div className="flex justify-between items-center mb-4">
        <span className="text-[#888] text-xs uppercase tracking-wide">{items.length} symbols monitored</span>
        <button
          onClick={() => setShowModal(true)}
          className="bg-[#00e676] text-black text-xs font-bold px-4 py-2 rounded hover:bg-[#00c853] transition-colors uppercase tracking-wide"
        >
          + Add Symbol
        </button>
      </div>

      {items.length === 0 ? (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-8 text-center text-[#555] text-sm">
          No symbols on your watchlist. Add one to start monitoring signals.
        </div>
      ) : (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e1e]">
                {["Symbol", "Strategy", "Signal", "Last Price", "Alert Threshold", "Added", ""].map((h) => (
                  <th key={h} className="text-left text-[#555] text-xs uppercase tracking-widest px-4 py-3 font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-[#1a1a1a] hover:bg-[#111] transition-colors">
                  <td className="px-4 py-3 font-bold text-white">{item.symbol}</td>
                  <td className="px-4 py-3 text-[#888]">{item.strategy}</td>
                  <td className="px-4 py-3">
                    {item.last_signal ? (
                      <span className={`text-xs font-bold px-2 py-0.5 rounded uppercase ${SIGNAL_BADGE[item.last_signal] ?? SIGNAL_BADGE.hold}`}>
                        {item.last_signal}
                      </span>
                    ) : (
                      <span className="text-[#555] text-xs">Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[#ccc]">
                    {item.last_price != null ? `$${parseFloat(item.last_price).toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-[#888]">
                    {item.alert_threshold != null ? `$${parseFloat(item.alert_threshold).toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-[#555] text-xs">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="text-[#555] hover:text-red-400 text-xs transition-colors"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <AddItemModal onClose={() => setShowModal(false)} onAdd={handleAdd} />
      )}
    </div>
  );
}
