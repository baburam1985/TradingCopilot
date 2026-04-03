"""Tests for the notes router, sessions journal export, and indicators router."""

import sys
import types
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# Stub third-party modules before importing main
for _mod in ["yfinance", "aiohttp", "finnhub"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

for _full in ["scrapers.yahoo", "scrapers.alpha_vantage", "scrapers.finnhub"]:
    if _full not in sys.modules:
        _m = types.ModuleType(_full)
        async def _noop(*a, **kw): return None
        _m.fetch_yahoo = _noop
        _m.fetch_alpha_vantage = _noop
        _m.fetch_finnhub = _noop
        sys.modules[_full] = _m

from main import app  # noqa: E402
from database import get_db


def _make_mock_db():
    return AsyncMock()


def _override_get_db(db_mock):
    async def _get_db_override():
        yield db_mock
    return _get_db_override


def _mock_trade(session_id=None):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.session_id = session_id or uuid.uuid4()
    t.action = "buy"
    t.price_at_signal = 150.0
    t.price_at_close = 155.0
    t.pnl = 5.0
    t.quantity = 6.0
    t.status = "closed"
    t.timestamp_open = datetime.now(timezone.utc) - timedelta(hours=2)
    t.timestamp_close = datetime.now(timezone.utc) - timedelta(hours=1)
    return t


def _mock_note(trade_id=None):
    n = MagicMock()
    n.id = uuid.uuid4()
    n.trade_id = trade_id or uuid.uuid4()
    n.body = "Good entry"
    n.tags = ["momentum"]
    n.created_at = datetime.now(timezone.utc)
    return n


# ---------------------------------------------------------------------------
# Notes router (/trades/{trade_id}/notes)
# ---------------------------------------------------------------------------

class TestNotesRouter:
    @pytest.mark.asyncio
    async def test_create_note_returns_201(self):
        db = _make_mock_db()
        trade = _mock_trade()
        db.get = AsyncMock(return_value=trade)
        db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/trades/{trade.id}/notes", json={
                    "body": "Good entry signal",
                    "tags": ["momentum", "rsi"],
                })
            assert resp.status_code == 201
            db.add.assert_called_once()
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_note_returns_404_when_trade_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/trades/{uuid.uuid4()}/notes", json={"body": "x", "tags": []})
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_notes_returns_notes(self):
        db = _make_mock_db()
        trade = _mock_trade()
        notes = [_mock_note(trade_id=trade.id), _mock_note(trade_id=trade.id)]
        db.get = AsyncMock(return_value=trade)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = notes
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/trades/{trade.id}/notes")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_notes_returns_404_when_trade_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/trades/{uuid.uuid4()}/notes")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_note_returns_204(self):
        db = _make_mock_db()
        trade = _mock_trade()
        note = _mock_note(trade_id=trade.id)
        db.get = AsyncMock(return_value=note)
        db.delete = AsyncMock()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/trades/{note.trade_id}/notes/{note.id}")
            assert resp.status_code == 204
            db.delete.assert_awaited_once_with(note)
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_note_returns_404_when_note_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/trades/{uuid.uuid4()}/notes/{uuid.uuid4()}")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_note_returns_404_when_trade_id_mismatch(self):
        db = _make_mock_db()
        note = _mock_note()
        db.get = AsyncMock(return_value=note)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            # Use a different trade_id than the note's trade_id
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.delete(f"/trades/{uuid.uuid4()}/notes/{note.id}")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sessions journal export (/sessions/{session_id}/journal)
# ---------------------------------------------------------------------------

class TestSessionsJournalExport:
    def _make_session(self, session_id=None):
        s = MagicMock()
        s.id = session_id or uuid.uuid4()
        s.symbol = "AAPL"
        s.strategy = "rsi"
        s.starting_capital = 1000.0
        s.mode = "paper"
        s.status = "active"
        s.created_at = datetime.now(timezone.utc)
        return s

    @pytest.mark.asyncio
    async def test_journal_export_returns_csv(self):
        db = _make_mock_db()
        session = self._make_session()
        trade = _mock_trade(session_id=session.id)
        db.get = AsyncMock(return_value=session)

        # trades query result
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = [trade]
        # notes query result
        notes_result = MagicMock()
        notes_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[trades_result, notes_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/journal?format=csv")
            assert resp.status_code == 200
            assert "text/csv" in resp.headers["content-type"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_journal_export_returns_400_for_unsupported_format(self):
        db = _make_mock_db()
        session = self._make_session()
        db.get = AsyncMock(return_value=session)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/journal?format=json")
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_journal_export_returns_404_when_session_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{uuid.uuid4()}/journal")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_journal_includes_notes_when_present(self):
        """Journal CSV includes note body and tags for each trade."""
        db = _make_mock_db()
        session = self._make_session()
        trade = _mock_trade(session_id=session.id)
        note = _mock_note(trade_id=trade.id)
        note.body = "Strong momentum"
        note.tags = ["momentum"]
        db.get = AsyncMock(return_value=session)

        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = [trade]
        notes_result = MagicMock()
        notes_result.scalars.return_value.all.return_value = [note]
        db.execute = AsyncMock(side_effect=[trades_result, notes_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/journal")
            assert resp.status_code == 200
            content = resp.text
            assert "Strong momentum" in content
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Indicators router (/sessions/{session_id}/indicators)
# ---------------------------------------------------------------------------

class TestIndicatorsRouter:
    def _make_price_bars(self, n=50, start_close=100.0):
        bars = []
        for i in range(n):
            b = MagicMock()
            b.close = start_close + i * 0.5
            b.open = b.close - 0.3
            b.high = b.close + 0.5
            b.low = b.close - 0.5
            b.volume = 100000
            b.timestamp = datetime.now(timezone.utc) - timedelta(minutes=n - i)
            bars.append(b)
        return bars

    @pytest.mark.asyncio
    async def test_get_indicators_returns_all_by_default(self):
        db = _make_mock_db()
        session_id = uuid.uuid4()
        session = MagicMock()
        session.id = session_id
        session.symbol = "AAPL"
        bars = self._make_price_bars(n=50)

        db.get = AsyncMock(return_value=session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = bars
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session_id}/indicators")
            assert resp.status_code == 200
            data = resp.json()
            # Response contains at least one of the standard indicator keys
            assert any(k in data for k in ("sma", "ema", "rsi", "macd", "bollinger"))
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_indicators_returns_404_when_session_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{uuid.uuid4()}/indicators")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_indicators_filters_to_requested_set(self):
        db = _make_mock_db()
        session_id = uuid.uuid4()
        session = MagicMock()
        session.id = session_id
        session.symbol = "AAPL"
        bars = self._make_price_bars(n=50)

        db.get = AsyncMock(return_value=session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = bars
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session_id}/indicators?indicators=rsi,sma")
            assert resp.status_code == 200
            data = resp.json()
            assert "rsi" in data
            assert "sma" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_indicators_returns_400_for_invalid_indicator(self):
        db = _make_mock_db()
        session = MagicMock()
        session.id = uuid.uuid4()
        db.get = AsyncMock(return_value=session)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/indicators?indicators=invalid_indicator")
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()
