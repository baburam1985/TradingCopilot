import { useNotifications } from "../context/NotificationContext";

const LEVEL_DOT = {
  info:    "bg-[#00e676]",
  warning: "bg-[#ffb300]",
  danger:  "bg-[#ff4444]",
};

export default function NotificationHistory({ open, onClose }) {
  const { notifications, dismissNotification } = useNotifications();

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed top-12 right-0 w-80 h-[calc(100vh-3rem)] bg-[#111] border-l border-[#1e1e1e] z-50 flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e1e]">
          <span className="text-[#00e676] text-xs uppercase tracking-widest">Notifications</span>
          <button
            onClick={onClose}
            className="text-[#555] hover:text-white text-xs"
            aria-label="Close"
          >✕</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {notifications.length === 0 ? (
            <p className="text-[#555] text-xs text-center mt-8 px-4">No notifications yet.</p>
          ) : (
            notifications.map((n) => (
              <div key={n.id} className="flex items-start gap-3 px-4 py-3 border-b border-[#1a1a1a] hover:bg-[#141414]">
                <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${LEVEL_DOT[n.level] ?? LEVEL_DOT.info}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-white text-xs font-semibold">{n.title}</p>
                  <p className="text-[#666] text-xs mt-0.5 break-words">{n.message}</p>
                  <p className="text-[#444] text-xs mt-1">{new Date(n.ts).toLocaleTimeString()}</p>
                </div>
                <button
                  onClick={() => dismissNotification(n.id)}
                  className="text-[#555] hover:text-white text-xs flex-shrink-0"
                  aria-label="Dismiss"
                >✕</button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
