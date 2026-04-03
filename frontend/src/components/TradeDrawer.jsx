import { useEffect, useRef, useState } from "react";
import { getNotes, createNote, deleteNote } from "../api/client";

const TAGS = ["FOMO", "Missed Signal", "Correct Entry", "Late Entry", "Rule Violation"];

export default function TradeDrawer({ trade, isOpen, onClose }) {
  const [notes, setNotes] = useState([]);
  const [body, setBody] = useState("");
  const [selectedTags, setSelectedTags] = useState([]);
  const [saving, setSaving] = useState(false);
  const drawerRef = useRef(null);

  // Load notes when trade changes
  useEffect(() => {
    if (!trade) return;
    getNotes(trade.id)
      .then((r) => setNotes(r.data))
      .catch(() => setNotes([]));
  }, [trade]);

  // ESC to close
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  if (!isOpen || !trade) return null;

  const toggleTag = (tag) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await createNote(trade.id, body, selectedTags);
      const r = await getNotes(trade.id);
      setNotes(r.data);
      setBody("");
      setSelectedTags([]);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (noteId) => {
    try {
      await deleteNote(trade.id, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch {
      // ignore
    }
  };

  const pnlColor =
    trade.pnl > 0 ? "#00e676" : trade.pnl < 0 ? "#ef5350" : "#888";

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed top-0 right-0 h-full w-full max-w-md bg-[#0d0d0d] border-l border-[#1e1e1e] z-50 flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e1e1e]">
          <div className="flex items-center gap-3">
            <span
              className="text-xs font-bold px-2 py-0.5 rounded"
              style={{ background: trade.action === "buy" ? "#00e676" : "#ef5350", color: "#0d0d0d" }}
            >
              {trade.action?.toUpperCase()}
            </span>
            <span className="text-white text-sm font-semibold">Trade Detail</span>
          </div>
          <button
            onClick={onClose}
            className="text-[#666] hover:text-white text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Trade summary */}
        <div className="px-5 py-4 border-b border-[#1e1e1e] grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-[#555] text-xs uppercase">Entry</div>
            <div className="text-white">
              {trade.price_at_signal != null ? `$${parseFloat(trade.price_at_signal).toFixed(2)}` : "—"}
            </div>
          </div>
          <div>
            <div className="text-[#555] text-xs uppercase">Exit</div>
            <div className="text-white">
              {trade.price_at_close != null ? `$${parseFloat(trade.price_at_close).toFixed(2)}` : "—"}
            </div>
          </div>
          <div>
            <div className="text-[#555] text-xs uppercase">P&L</div>
            <div style={{ color: pnlColor }} className="font-semibold">
              {trade.pnl != null
                ? `${trade.pnl > 0 ? "+" : ""}$${parseFloat(trade.pnl).toFixed(2)}`
                : "—"}
            </div>
          </div>
          <div>
            <div className="text-[#555] text-xs uppercase">Status</div>
            <div className="text-[#e0e0e0]">{trade.status}</div>
          </div>
          {(trade.reasoning_text || trade.signal_reason) && (
            <div className="col-span-2">
              <div className="text-[#555] text-xs uppercase mb-1">Reasoning</div>
              <div className="text-[#b0b0b0] text-xs leading-relaxed">
                {trade.reasoning_text || trade.signal_reason}
              </div>
            </div>
          )}
        </div>

        {/* Notes list */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="text-[#00e676] text-xs uppercase tracking-widest mb-3">Notes</div>
          {notes.length === 0 && (
            <p className="text-[#555] text-sm">No notes yet.</p>
          )}
          {notes.map((note) => (
            <div
              key={note.id}
              className="mb-3 p-3 bg-[#141414] border border-[#1e1e1e] rounded"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-[#e0e0e0] text-sm whitespace-pre-wrap flex-1">{note.body}</p>
                <button
                  onClick={() => handleDelete(note.id)}
                  className="text-[#555] hover:text-[#ef5350] text-xs shrink-0"
                >
                  ✕
                </button>
              </div>
              {note.tags && note.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {note.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-2 py-0.5 rounded bg-[#1e1e1e] text-[#00e676]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
              <div className="text-[#444] text-[10px] mt-1">
                {new Date(note.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>

        {/* Add note form */}
        <div className="px-5 py-4 border-t border-[#1e1e1e]">
          <textarea
            className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676] resize-none mb-3"
            rows={3}
            placeholder="Add a note..."
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="flex flex-wrap gap-2 mb-3">
            {TAGS.map((tag) => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`text-[11px] px-2 py-1 rounded border transition-colors ${
                  selectedTags.includes(tag)
                    ? "border-[#00e676] bg-[#00e676] text-[#0d0d0d] font-semibold"
                    : "border-[#333] text-[#888] hover:border-[#666]"
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full bg-[#00e676] text-[#0d0d0d] font-bold text-sm py-2 rounded hover:bg-[#00c853] disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : "Save Note"}
          </button>
        </div>
      </div>
    </>
  );
}
