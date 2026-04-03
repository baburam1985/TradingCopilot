export default function MetricCard({ label, value, valueColor }) {
  const colorClass = valueColor === "green"
    ? "text-[#00e676]"
    : valueColor === "red"
    ? "text-[#ff4444]"
    : "text-white";

  return (
    <div className="bg-[#141414] border border-[#1e1e1e] rounded px-4 py-3 flex flex-col gap-1">
      <span className="text-[#888] text-xs uppercase tracking-wider">{label}</span>
      <span className={`text-lg font-semibold ${colorClass}`}>{value ?? "—"}</span>
    </div>
  );
}
