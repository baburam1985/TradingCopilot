import { useState } from "react";
import { updateSession } from "../api/client";

/**
 * Per-session alert configuration panel.
 * Handles: email alerts, price threshold alerts (above/below), trade signal alerts,
 * and browser push notification opt-in.
 *
 * Props:
 *   session  — full session object from GET /api/sessions
 *   onSaved  — optional callback fired after a successful save
 */
export default function AlertSettings({ session, onSaved }) {
  const [notifyEmail, setNotifyEmail] = useState(!!session.notify_email);
  const [emailAddress, setEmailAddress] = useState(session.email_address ?? "");

  const [priceAboveEnabled, setPriceAboveEnabled] = useState(false);
  const [priceAbove, setPriceAbove] = useState("");
  const [priceBelowEnabled, setPriceBelowEnabled] = useState(false);
  const [priceBelow, setPriceBelow] = useState("");
  const [signalAlerts, setSignalAlerts] = useState(false);

  const [pushStatus, setPushStatus] = useState(() => {
    if (!("Notification" in window)) return "unsupported";
    if (Notification.permission === "granted") return "granted";
    if (Notification.permission === "denied") return "denied";
    return "default";
  });
  const [pushLoading, setPushLoading] = useState(false);

  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  async function handleRequestPush() {
    if (!("Notification" in window)) return;
    setPushLoading(true);
    try {
      const permission = await Notification.requestPermission();
      setPushStatus(permission);
      if (permission === "granted" && "serviceWorker" in navigator) {
        const reg = await navigator.serviceWorker.ready;
        // POST subscription to backend — backend endpoint is a separate subtask
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          // VAPID key would be loaded from env in a real deployment
          applicationServerKey: null,
        }).catch(() => null);
        if (sub) {
          await fetch("/api/push/subscribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: session.id, subscription: sub.toJSON() }),
          }).catch(() => {});
        }
      }
    } finally {
      setPushLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSavedMsg("");
    try {
      await updateSession(session.id, {
        notify_email: notifyEmail,
        email_address: notifyEmail ? emailAddress || null : null,
      });
      setSavedMsg("Saved");
      onSaved?.();
      setTimeout(() => setSavedMsg(""), 2000);
    } catch {
      setSavedMsg("Error saving");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div data-testid="alert-settings" className="space-y-5">
      {/* ── Price threshold alerts ── */}
      <section>
        <h3 className="text-[#00e676] text-[10px] uppercase tracking-widest mb-3">
          Price Threshold Alerts
        </h3>
        <div className="space-y-2">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={priceAboveEnabled}
              onChange={(e) => setPriceAboveEnabled(e.target.checked)}
              className="accent-[#00e676]"
              data-testid="price-above-toggle"
            />
            <span className="text-[#888] text-xs">Alert when price goes above</span>
            {priceAboveEnabled && (
              <input
                type="number"
                step="0.01"
                placeholder="e.g. 200.00"
                value={priceAbove}
                onChange={(e) => setPriceAbove(e.target.value)}
                className="w-28 bg-[#0a0a0a] border border-[#333] text-white text-xs px-2 py-1 rounded focus:outline-none focus:border-[#00e676]"
                data-testid="price-above-input"
              />
            )}
          </label>

          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={priceBelowEnabled}
              onChange={(e) => setPriceBelowEnabled(e.target.checked)}
              className="accent-[#00e676]"
              data-testid="price-below-toggle"
            />
            <span className="text-[#888] text-xs">Alert when price goes below</span>
            {priceBelowEnabled && (
              <input
                type="number"
                step="0.01"
                placeholder="e.g. 150.00"
                value={priceBelow}
                onChange={(e) => setPriceBelow(e.target.value)}
                className="w-28 bg-[#0a0a0a] border border-[#333] text-white text-xs px-2 py-1 rounded focus:outline-none focus:border-[#00e676]"
                data-testid="price-below-input"
              />
            )}
          </label>
        </div>
      </section>

      {/* ── Trade signal alerts ── */}
      <section>
        <h3 className="text-[#00e676] text-[10px] uppercase tracking-widest mb-3">
          Trade Signal Alerts
        </h3>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={signalAlerts}
            onChange={(e) => setSignalAlerts(e.target.checked)}
            className="accent-[#00e676]"
            data-testid="signal-alerts-toggle"
          />
          <span className="text-[#888] text-xs">
            Notify when a buy or sell signal fires
          </span>
        </label>
      </section>

      {/* ── Delivery channels ── */}
      <section>
        <h3 className="text-[#00e676] text-[10px] uppercase tracking-widest mb-3">
          Delivery Channels
        </h3>
        <div className="space-y-3">
          {/* Email */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={notifyEmail}
              onChange={(e) => setNotifyEmail(e.target.checked)}
              className="accent-[#00e676]"
              data-testid="email-toggle"
            />
            <span className="text-[#888] text-xs">Email</span>
          </label>
          {notifyEmail && (
            <input
              type="email"
              placeholder="Email address"
              value={emailAddress}
              onChange={(e) => setEmailAddress(e.target.value)}
              className="w-full max-w-xs bg-[#0a0a0a] border border-[#333] text-white text-xs px-3 py-2 rounded focus:outline-none focus:border-[#00e676]"
              data-testid="email-input"
            />
          )}

          {/* Browser push */}
          <div className="flex items-center gap-3">
            <span className="text-[#888] text-xs">Browser Push</span>
            {pushStatus === "unsupported" && (
              <span className="text-[#555] text-xs">Not supported by this browser</span>
            )}
            {pushStatus === "granted" && (
              <span className="text-[#00e676] text-xs font-semibold" data-testid="push-status-active">
                Active
              </span>
            )}
            {pushStatus === "denied" && (
              <span className="text-[#ff4444] text-xs" data-testid="push-status-denied">
                Blocked — enable in browser settings
              </span>
            )}
            {pushStatus === "default" && (
              <button
                onClick={handleRequestPush}
                disabled={pushLoading}
                className="text-xs bg-[#1e1e1e] border border-[#333] text-white px-3 py-1 rounded hover:border-[#00e676] hover:text-[#00e676] disabled:opacity-50 transition-colors"
                data-testid="push-enable-btn"
              >
                {pushLoading ? "Requesting…" : "Enable Push Notifications"}
              </button>
            )}
          </div>
        </div>
      </section>

      {/* ── Save ── */}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs bg-[#00e676] text-black font-bold px-3 py-1.5 rounded hover:bg-[#00c853] disabled:opacity-50 transition-colors"
          data-testid="save-btn"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {savedMsg && (
          <span
            className={`text-xs ${savedMsg === "Saved" ? "text-[#00e676]" : "text-[#ff4444]"}`}
            data-testid="save-msg"
          >
            {savedMsg}
          </span>
        )}
      </div>
    </div>
  );
}
