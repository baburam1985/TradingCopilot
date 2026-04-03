"""Integration tests for Trade Journal notes API."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

SESSION_PAYLOAD = {
    "symbol": "AAPL",
    "strategy": "rsi",
    "strategy_params": {"period": 14},
    "starting_capital": 1000.0,
    "mode": "paper",
}


async def _create_session(client) -> str:
    resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    assert resp.status_code == 200
    return resp.json()["id"]


async def _insert_trade(db_session, session_id: str) -> str:
    trade_id = str(uuid.uuid4())
    await db_session.execute(
        text("""
            INSERT INTO paper_trades
              (id, session_id, action, signal_reason, price_at_signal, quantity,
               timestamp_open, status)
            VALUES
              (:id, :session_id, 'buy', 'RSI oversold', 150.00, 1.0,
               :ts, 'open')
        """),
        {"id": trade_id, "session_id": session_id, "ts": datetime.now(timezone.utc)},
    )
    await db_session.commit()
    return trade_id


async def test_post_get_note_round_trip(client, db_session, clean_db):
    session_id = await _create_session(client)
    trade_id = await _insert_trade(db_session, session_id)

    # Create note
    resp = await client.post(
        f"/trades/{trade_id}/notes",
        json={"body": "Entered too early", "tags": ["FOMO", "Late Entry"]},
    )
    assert resp.status_code == 201
    note = resp.json()
    assert note["body"] == "Entered too early"
    assert note["tags"] == ["FOMO", "Late Entry"]

    # List notes
    list_resp = await client.get(f"/trades/{trade_id}/notes")
    assert list_resp.status_code == 200
    notes = list_resp.json()
    assert len(notes) == 1
    assert notes[0]["id"] == note["id"]


async def test_delete_removes_note(client, db_session, clean_db):
    session_id = await _create_session(client)
    trade_id = await _insert_trade(db_session, session_id)

    # Create then delete
    create_resp = await client.post(
        f"/trades/{trade_id}/notes",
        json={"body": "Test note", "tags": []},
    )
    note_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/trades/{trade_id}/notes/{note_id}")
    assert del_resp.status_code == 204

    # Verify gone
    list_resp = await client.get(f"/trades/{trade_id}/notes")
    assert list_resp.json() == []


async def test_404_unknown_trade_on_post(client, clean_db):
    fake_trade_id = str(uuid.uuid4())
    resp = await client.post(
        f"/trades/{fake_trade_id}/notes",
        json={"body": "ghost note", "tags": []},
    )
    assert resp.status_code == 404
    assert "Trade not found" in resp.json()["detail"]


async def test_404_unknown_note_on_delete(client, db_session, clean_db):
    session_id = await _create_session(client)
    trade_id = await _insert_trade(db_session, session_id)
    fake_note_id = str(uuid.uuid4())
    resp = await client.delete(f"/trades/{trade_id}/notes/{fake_note_id}")
    assert resp.status_code == 404
    assert "Note not found" in resp.json()["detail"]


async def test_export_journal_includes_note(client, db_session, clean_db):
    session_id = await _create_session(client)
    trade_id = await _insert_trade(db_session, session_id)

    await client.post(
        f"/trades/{trade_id}/notes",
        json={"body": "Correct entry", "tags": ["Correct Entry"]},
    )

    resp = await client.get(f"/sessions/{session_id}/journal?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "note_body" in content  # header row
    assert "Correct entry" in content
    assert "Correct Entry" in content


async def test_export_journal_no_notes_returns_header_only(client, db_session, clean_db):
    session_id = await _create_session(client)
    await _insert_trade(db_session, session_id)

    resp = await client.get(f"/sessions/{session_id}/journal?format=csv")
    assert resp.status_code == 200
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    # Header + 1 trade row = 2 lines
    assert len(lines) == 2
    assert "note_body" in lines[0]
    # Note columns should be empty
    assert lines[1].endswith('""')
