import { createContext, useContext, useState, useCallback } from "react";
import { getAlerts, markAlertRead, markAllAlertsRead } from "../api/client";

const NotificationContext = createContext(null);

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  // Prepopulate from persisted API alerts for a session.
  // Maps API fields to the shape used by NotificationHistory (ts = created_at).
  const hydrate = useCallback(async (sessionId) => {
    try {
      const { data } = await getAlerts(sessionId, 20);
      const mapped = data.map((a) => ({
        id: a.id,
        session_id: a.session_id,
        level: a.level,
        title: a.title,
        message: a.message,
        read_at: a.read_at,
        ts: a.created_at,
      }));
      setNotifications(mapped);
    } catch {
      // Non-fatal: live WS events still work without hydration
    }
  }, []);

  // Append a live WebSocket notification (no read_at = unread).
  const addNotification = useCallback((notif) => {
    const entry = { ...notif, id: notif.id ?? crypto.randomUUID(), read_at: null };
    setNotifications((prev) => [entry, ...prev].slice(0, 100));
  }, []);

  const dismissNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  // Mark a single alert read on the backend and update local state.
  const markRead = useCallback(async (id) => {
    try {
      await markAlertRead(id);
      const now = new Date().toISOString();
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: now } : n))
      );
    } catch {
      // Best-effort
    }
  }, []);

  // Mark all alerts read for a session on the backend and update local state.
  const markAllRead = useCallback(async (sessionId) => {
    if (!sessionId) return;
    try {
      await markAllAlertsRead(sessionId);
      const now = new Date().toISOString();
      setNotifications((prev) =>
        prev.map((n) =>
          n.session_id === sessionId && !n.read_at ? { ...n, read_at: now } : n
        )
      );
    } catch {
      // Best-effort
    }
  }, []);

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        addNotification,
        dismissNotification,
        hydrate,
        markRead,
        markAllRead,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationProvider");
  return ctx;
}
