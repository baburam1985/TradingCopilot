import { useEffect, useState } from "react";
import { getSessions, updateSession } from "../api/client";
import PageHeader from "../components/PageHeader";

export default function AlertPreferences() {
  const [sessions, setSessions] = useState([]);
  const [saving, setSaving] = useState({});
  const [saved, setSaved] = useState({});

  useEffect(() => {
    getSessions().then((r) => setSessions(r.data));
  }, []);

  function handleToggle(sessionId, field, value) {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, [field]: value } : s))
    );
  }

  async function handleSave(session) {
    setSaving((prev) => ({ ...prev, [session.id]: true }));
    try {
      await updateSession(session.id, {
        notify_email: session.notify_email,
        email_address: session.email_address || null,
      });
      setSaved((prev) => ({ ...prev, [session.id]: true }));
      setTimeout(() => setSaved((prev) => ({ ...prev, [session.id]: false })), 2000);
    } finally {
      setSaving((prev) => ({ ...prev, [session.id]: false }));
    }
  }

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › ALERTS"
        title="Alert Preferences"
        subtitle="Configure email notifications per trading session"
      />

      {sessions.length === 0 ? (
        <p className="text-[#555] text-sm mt-8">No active sessions found.</p>
      ) : (
        <div className="space-y-4 mt-6">
          {sessions.map((s) => (
            <div
              key={s.id}
              className="bg-[#141414] border border-[#1e1e1e] rounded p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <span className="text-white text-sm font-semibold">{s.symbol}</span>
                  <span className="text-[#555] text-xs ml-2">{s.strategy}</span>
                </div>
                <span
                  className={`text-xs font-bold px-2 py-0.5 rounded ${
                    s.status === "active"
                      ? "bg-[#00e676] text-black"
                      : "bg-[#333] text-[#888]"
                  }`}
                >
                  {s.status.toUpperCase()}
                </span>
              </div>

              <div className="flex items-center gap-3 mb-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!s.notify_email}
                    onChange={(e) => handleToggle(s.id, "notify_email", e.target.checked)}
                    className="accent-[#00e676]"
                  />
                  <span className="text-[#888] text-xs">Email alerts</span>
                </label>
              </div>

              {s.notify_email && (
                <div className="mb-3">
                  <input
                    type="email"
                    placeholder="Email address"
                    value={s.email_address ?? ""}
                    onChange={(e) => handleToggle(s.id, "email_address", e.target.value)}
                    className="w-full max-w-xs bg-[#0a0a0a] border border-[#333] text-white text-xs px-3 py-2 rounded focus:outline-none focus:border-[#00e676]"
                  />
                </div>
              )}

              <button
                onClick={() => handleSave(s)}
                disabled={saving[s.id]}
                className="text-xs bg-[#00e676] text-black font-bold px-3 py-1.5 rounded hover:bg-[#00c853] disabled:opacity-50 transition-colors"
              >
                {saving[s.id] ? "Saving…" : saved[s.id] ? "Saved ✓" : "Save"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
