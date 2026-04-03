import { useEffect, useState } from "react";
import { useNotifications } from "../context/NotificationContext";

const LEVEL_STYLES = {
  info:    "border-[#00e676] text-[#00e676]",
  warning: "border-[#ffb300] text-[#ffb300]",
  danger:  "border-[#ff4444] text-[#ff4444]",
};

function ToastItem({ notif, onDismiss }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(notif.id), 300); // allow fade-out
    }, 5000);
    return () => clearTimeout(timer);
  }, [notif.id, onDismiss]);

  return (
    <div
      className={`flex items-start gap-3 bg-[#141414] border-l-4 rounded px-4 py-3 shadow-lg w-80 transition-opacity duration-300 ${LEVEL_STYLES[notif.level] ?? LEVEL_STYLES.info} ${visible ? "opacity-100" : "opacity-0"}`}
    >
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-semibold leading-tight">{notif.title}</p>
        <p className="text-[#888] text-xs mt-0.5 break-words">{notif.message}</p>
      </div>
      <button
        onClick={() => onDismiss(notif.id)}
        className="text-[#555] hover:text-white text-xs ml-2 flex-shrink-0"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export default function Toast() {
  const { notifications, dismissNotification } = useNotifications();
  // Show only the 3 most recent toasts
  const visible = notifications.slice(0, 3);

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 items-end">
      {visible.map((n) => (
        <ToastItem key={n.id} notif={n} onDismiss={dismissNotification} />
      ))}
    </div>
  );
}
