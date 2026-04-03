"""Tests for EventsCalendar service and the GET /symbols/{symbol}/events endpoint."""

import sys
import types
import uuid
from datetime import date, datetime, timezone
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

        async def _noop(*a, **kw):
            return None

        _m.fetch_yahoo = _noop
        _m.fetch_alpha_vantage = _noop
        _m.fetch_finnhub = _noop
        sys.modules[_full] = _m

from main import app  # noqa: E402
from database import get_db  # noqa: E402


def _make_mock_db():
    return AsyncMock()


def _override_get_db(db_mock):
    async def _get_db_override():
        yield db_mock

    return _get_db_override


def _mock_event(event_type="earnings", symbol="AAPL", event_date_str="2026-04-15"):
    e = MagicMock()
    e.id = uuid.uuid4()
    e.event_type = event_type
    e.symbol = symbol if event_type == "earnings" else None
    e.event_date = date.fromisoformat(event_date_str)
    e.description = f"{symbol} {event_type.title()}" if event_type == "earnings" else event_type.upper()
    e.fetched_at = datetime.now(timezone.utc)
    return e


# ---------------------------------------------------------------------------
# Router tests — GET /symbols/{symbol}/events
# ---------------------------------------------------------------------------


class TestSymbolEventsRouter:
    @pytest.mark.asyncio
    async def test_returns_200_with_empty_list(self):
        db = _make_mock_db()
        with patch("routers.market_data.get_events", new=AsyncMock(return_value=[])):
            app.dependency_overrides[get_db] = _override_get_db(db)
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.get(
                        "/symbols/AAPL/events",
                        params={"from": "2026-04-01T00:00:00", "to": "2026-04-30T00:00:00"},
                    )
                assert resp.status_code == 200
                assert resp.json() == []
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_events_list(self):
        db = _make_mock_db()
        earnings_event = _mock_event("earnings", "AAPL", "2026-04-15")
        fomc_event = _mock_event("fomc", None, "2026-04-29")

        with patch(
            "routers.market_data.get_events",
            new=AsyncMock(return_value=[earnings_event, fomc_event]),
        ):
            app.dependency_overrides[get_db] = _override_get_db(db)
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.get(
                        "/symbols/AAPL/events",
                        params={"from": "2026-04-01T00:00:00", "to": "2026-04-30T00:00:00"},
                    )
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 2
                assert data[0]["event_type"] == "earnings"
                assert data[0]["symbol"] == "AAPL"
                assert data[0]["event_date"] == "2026-04-15"
                assert data[1]["event_type"] == "fomc"
                assert data[1]["symbol"] is None
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_uppercases_symbol(self):
        db = _make_mock_db()
        captured = {}

        async def mock_get_events(symbol, from_date, to_date, db):
            captured["symbol"] = symbol
            return []

        with patch("routers.market_data.get_events", new=mock_get_events):
            app.dependency_overrides[get_db] = _override_get_db(db)
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    await client.get(
                        "/symbols/aapl/events",
                        params={"from": "2026-04-01T00:00:00", "to": "2026-04-30T00:00:00"},
                    )
                assert captured["symbol"] == "AAPL"
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_missing_params_returns_422(self):
        db = _make_mock_db()
        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/symbols/AAPL/events")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Service unit tests — _fetch_earnings_date
# ---------------------------------------------------------------------------


class TestFetchEarningsDate:
    def test_returns_none_when_yfinance_raises(self):
        from services.events_calendar import _fetch_earnings_date

        with patch.dict(sys.modules, {"yfinance": None}):
            # Without yfinance, should return None gracefully
            result = _fetch_earnings_date("AAPL")
            assert result is None

    def test_returns_date_from_dict_style_calendar(self):
        from services.events_calendar import _fetch_earnings_date

        mock_yf = types.ModuleType("yfinance")
        mock_ticker = MagicMock()
        mock_ticker.calendar = {"Earnings Date": [datetime(2026, 7, 28)]}
        mock_yf.Ticker = MagicMock(return_value=mock_ticker)

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            result = _fetch_earnings_date("AAPL")
        assert result == date(2026, 7, 28)

    def test_returns_none_when_calendar_is_none(self):
        from services.events_calendar import _fetch_earnings_date

        mock_yf = types.ModuleType("yfinance")
        mock_ticker = MagicMock()
        mock_ticker.calendar = None
        mock_yf.Ticker = MagicMock(return_value=mock_ticker)

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            result = _fetch_earnings_date("AAPL")
        assert result is None

    def test_returns_none_when_earnings_list_empty(self):
        from services.events_calendar import _fetch_earnings_date

        mock_yf = types.ModuleType("yfinance")
        mock_ticker = MagicMock()
        mock_ticker.calendar = {"Earnings Date": []}
        mock_yf.Ticker = MagicMock(return_value=mock_ticker)

        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            result = _fetch_earnings_date("AAPL")
        assert result is None


# ---------------------------------------------------------------------------
# Service unit tests — _ensure_macro_events
# ---------------------------------------------------------------------------


class TestEnsureMacroEvents:
    @pytest.mark.asyncio
    async def test_seeds_fomc_and_cpi_when_empty(self):
        from services.events_calendar import _ensure_macro_events

        db = AsyncMock()
        # Simulate no existing macro events
        empty_result = MagicMock()
        empty_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=empty_result)
        db.add_all = MagicMock()
        db.commit = AsyncMock()

        await _ensure_macro_events(db)

        db.add_all.assert_called_once()
        rows = db.add_all.call_args[0][0]
        event_types = {r.event_type for r in rows}
        assert "fomc" in event_types
        assert "cpi" in event_types
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_seeding_when_already_present(self):
        from services.events_calendar import _ensure_macro_events

        db = AsyncMock()
        existing = MagicMock()
        existing.scalar_one_or_none = MagicMock(return_value=MagicMock())
        db.execute = AsyncMock(return_value=existing)
        db.add_all = MagicMock()
        db.commit = AsyncMock()

        await _ensure_macro_events(db)

        db.add_all.assert_not_called()
        db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Service unit tests — _ensure_earnings
# ---------------------------------------------------------------------------


class TestEnsureEarnings:
    @pytest.mark.asyncio
    async def test_skips_when_cache_is_fresh(self):
        from services.events_calendar import _ensure_earnings

        db = AsyncMock()
        fresh_event = MagicMock()
        fresh_event.fetched_at = datetime.now(timezone.utc)
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=fresh_event)
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock()
        db.commit = AsyncMock()

        await _ensure_earnings("AAPL", db)

        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_and_caches_when_no_existing_row(self):
        from services.events_calendar import _ensure_earnings

        db = AsyncMock()
        empty_result = MagicMock()
        empty_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=empty_result)
        db.add = MagicMock()
        db.commit = AsyncMock()

        with patch(
            "services.events_calendar._fetch_earnings_date",
            return_value=date(2026, 7, 28),
        ):
            await _ensure_earnings("AAPL", db)

        db.add.assert_called_once()
        row = db.add.call_args[0][0]
        assert row.event_type == "earnings"
        assert row.symbol == "AAPL"
        assert row.event_date == date(2026, 7, 28)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_earnings_date_not_available(self):
        from services.events_calendar import _ensure_earnings

        db = AsyncMock()
        empty_result = MagicMock()
        empty_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=empty_result)
        db.add = MagicMock()
        db.commit = AsyncMock()

        with patch("services.events_calendar._fetch_earnings_date", return_value=None):
            await _ensure_earnings("AAPL", db)

        db.add.assert_not_called()
        db.commit.assert_not_called()
