"""Unit tests for TradeNote model and journal CSV formatter."""
import csv
import io
import sys
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from models.trade_note import TradeNote
from journal import build_journal_csv, JOURNAL_HEADERS


def _make_note(**overrides) -> TradeNote:
    defaults = dict(
        id=uuid.uuid4(),
        trade_id=uuid.uuid4(),
        body="",
        tags=[],
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return TradeNote(**defaults)


def _make_trade(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        action="buy",
        price_at_signal=150.0,
        price_at_close=152.0,
        pnl=2.0,
        timestamp_open=datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc),
        timestamp_close=datetime(2025, 1, 1, 15, 0, tzinfo=timezone.utc),
        status="closed",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _parse_csv(csv_str: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_str))
    return list(reader)


# ── Model tests ────────────────────────────────────────────────────────────


def test_trade_note_defaults():
    note = _make_note()
    assert note.tags == []
    assert note.body == ""
    assert note.created_at is not None
    assert note.__tablename__ == "trade_notes"


def test_trade_note_tags_round_trip():
    tags = ["FOMO", "Late Entry"]
    note = _make_note(tags=tags)
    assert note.tags == ["FOMO", "Late Entry"]


# ── CSV formatter tests ────────────────────────────────────────────────────


def test_csv_formatter_single_note():
    trade = _make_trade()
    note = _make_note(trade_id=trade.id, body="Entered too early", tags=["FOMO"])
    csv_str = build_journal_csv([trade], {trade.id: [note]})
    rows = _parse_csv(csv_str)
    assert rows[0]["note_body"] == "Entered too early"
    assert rows[0]["tags"] == "FOMO"
    assert rows[0]["action"] == "buy"
    assert rows[0]["status"] == "closed"


def test_csv_formatter_multi_note_concatenation():
    trade = _make_trade()
    note1 = _make_note(trade_id=trade.id, body="First note", tags=["FOMO"])
    note2 = _make_note(trade_id=trade.id, body="Second note", tags=["Late Entry", "Rule Violation"])
    csv_str = build_journal_csv([trade], {trade.id: [note1, note2]})
    rows = _parse_csv(csv_str)
    assert rows[0]["note_body"] == "First note | Second note"
    assert rows[0]["tags"] == "FOMO;Late Entry,Rule Violation"


def test_csv_formatter_no_notes():
    trade = _make_trade()
    csv_str = build_journal_csv([trade], {})
    rows = _parse_csv(csv_str)
    assert len(rows) == 1
    assert rows[0]["note_body"] == ""
    assert rows[0]["tags"] == ""


def test_csv_formatter_commas_in_body():
    trade = _make_trade()
    body = 'Entered at 150, exited at 152, good trade'
    note = _make_note(trade_id=trade.id, body=body, tags=[])
    csv_str = build_journal_csv([trade], {trade.id: [note]})
    rows = _parse_csv(csv_str)
    assert rows[0]["note_body"] == body


def test_csv_formatter_no_trades():
    csv_str = build_journal_csv([], {})
    reader = csv.reader(io.StringIO(csv_str))
    header = next(reader)
    assert header == JOURNAL_HEADERS
    rows = list(reader)
    assert rows == []
