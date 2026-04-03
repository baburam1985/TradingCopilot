import { useEffect, useState } from "react";
import { getSessions } from "../api/client";
import PageHeader from "../components/PageHeader";
import AlertSettings from "../components/AlertSettings";

export default function AlertPreferences() {
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    getSessions().then((r) => setSessions(r.data));
  }, []);

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › ALERTS"
        title="Alert Preferences"
        subtitle="Configure notifications per trading session"
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
              <div className="flex items-center justify-between mb-4">
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

              <AlertSettings session={s} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
