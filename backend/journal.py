"""Trade journal CSV export logic, extracted for testability."""
import csv
import io


JOURNAL_HEADERS = [
    "trade_id", "action", "price_at_signal", "price_at_close",
    "pnl", "timestamp_open", "timestamp_close", "status",
    "note_body", "tags",
]


def build_journal_csv(trades, notes_by_trade_id: dict) -> str:
    """Return a CSV string for the given trades and their notes.

    Args:
        trades: iterable of trade objects (or dicts) with the standard PaperTrade fields.
        notes_by_trade_id: mapping of trade_id -> list of note objects sorted by created_at.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(JOURNAL_HEADERS)

    for trade in trades:
        trade_id = _attr(trade, "id")
        notes = notes_by_trade_id.get(trade_id, [])
        note_body = " | ".join(_attr(n, "body") for n in notes)
        note_tags = ";".join(",".join(_attr(n, "tags") or []) for n in notes)
        writer.writerow([
            str(trade_id),
            _attr(trade, "action"),
            _float_or_empty(_attr(trade, "price_at_signal")),
            _float_or_empty(_attr(trade, "price_at_close")),
            _float_or_empty(_attr(trade, "pnl")),
            _isoformat_or_empty(_attr(trade, "timestamp_open")),
            _isoformat_or_empty(_attr(trade, "timestamp_close")),
            _attr(trade, "status"),
            note_body,
            note_tags,
        ])

    return output.getvalue()


def _attr(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _float_or_empty(v):
    return float(v) if v is not None else ""


def _isoformat_or_empty(v):
    return v.isoformat() if v is not None else ""
