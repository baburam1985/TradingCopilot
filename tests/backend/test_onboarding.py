"""Tests for onboarding-related endpoints:
  - GET /strategies (with avg_win_rate enrichment)
  - GET /symbols/{symbol}/sparkline
  - Session auto-creation (POST /sessions) — simulates what the wizard does
"""

import sys
import types
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


def _stub_scraper_modules():
    for mod_name in ["yfinance", "aiohttp", "finnhub", "apscheduler",
                     "apscheduler.schedulers", "apscheduler.schedulers.asyncio"]:
        if mod_name not in sys.modules:
            m = types.ModuleType(mod_name)
            if mod_name == "apscheduler.schedulers.asyncio":
                m.AsyncIOScheduler = MagicMock
            sys.modules[mod_name] = m

    for full in ["scrapers.yahoo", "scrapers.alpha_vantage", "scrapers.finnhub"]:
        if full not in sys.modules:
            mod = types.ModuleType(full)
            async def _stub(*a, **kw):
                return None
            mod.fetch_yahoo = _stub
            mod.fetch_alpha_vantage = _stub
            mod.fetch_finnhub = _stub
            sys.modules[full] = mod


_stub_scraper_modules()

import pytest
from httpx import AsyncClient, ASGITransport

with patch("scheduler.scraper_job.AsyncIOScheduler", MagicMock):
    from main import app  # noqa: E402

from database import get_db


def _make_db_override(execute_return=None):
    """Return a get_db override whose session.execute returns execute_return."""
    mock_db = AsyncMock()
    if execute_return is not None:
        mock_db.execute = AsyncMock(return_value=execute_return)
    return mock_db


# ---------------------------------------------------------------------------
# GET /strategies
# ---------------------------------------------------------------------------

class TestListStrategies:
    @pytest.mark.asyncio
    async def test_returns_all_strategies(self):
        """All registry strategies are returned with required fields."""
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([]))  # no win-rate rows

        async def mock_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/strategies")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0
            for item in data:
                assert "name" in item
                assert "description" in item
                assert "parameters" in item
                assert "avg_win_rate" in item
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_avg_win_rate_populated_from_db(self):
        """avg_win_rate is set for strategies that have aggregated pnl data."""
        # Simulate one DB row: rsi strategy has 0.65 avg win rate
        win_rate_row = MagicMock()
        win_rate_row.strategy = "rsi"
        win_rate_row.avg_win_rate = 0.65

        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([win_rate_row]))

        async def mock_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/strategies")
            assert resp.status_code == 200
            data = resp.json()
            rsi_item = next((s for s in data if s["name"] == "rsi"), None)
            assert rsi_item is not None
            assert abs(rsi_item["avg_win_rate"] - 0.65) < 1e-6
            # Strategies with no data have null win rate
            no_data = [s for s in data if s["name"] != "rsi"]
            for s in no_data:
                assert s["avg_win_rate"] is None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /symbols/{symbol}/sparkline
# ---------------------------------------------------------------------------

class TestSparkline:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_data(self):
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[])

        async def mock_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/symbols/AAPL/sparkline")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_up_to_7_data_points(self):
        rows = []
        for i in range(5):
            row = MagicMock()
            row.timestamp = datetime(2026, 3, i + 1, tzinfo=timezone.utc)
            row.close = 150.0 + i
            rows.append(row)

        # DB returns rows in DESC order (newest first); endpoint reverses to get ASC
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=list(reversed(rows)))

        async def mock_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/symbols/AAPL/sparkline")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 5
            # After reversal: oldest (i=0, close=150.0) is first, newest (i=4, close=154.0) is last
            assert data[0]["close"] == pytest.approx(150.0)
            assert data[-1]["close"] == pytest.approx(154.0)
            for pt in data:
                assert "timestamp" in pt
                assert "close" in pt
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_symbol_uppercased(self):
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[])

        async def mock_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=result_mock)
            yield db

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/symbols/aapl/sparkline")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Session auto-creation (wizard completion)
# ---------------------------------------------------------------------------

class TestOnboardingSessionCreation:
    """The wizard's final step calls POST /sessions — validate that flow."""

    def _make_mock_session(self, symbol="AAPL", strategy="rsi", capital=100.0):
        s = MagicMock()
        s.id = uuid.uuid4()
        s.symbol = symbol
        s.strategy = strategy
        s.strategy_params = {}
        s.starting_capital = capital
        s.mode = "paper"
        s.status = "active"
        s.created_at = datetime.now(timezone.utc)
        s.closed_at = None
        s.stop_loss_pct = None
        s.take_profit_pct = None
        s.max_position_pct = None
        s.daily_max_loss_pct = None
        s.notify_email = False
        s.email_address = None
        return s

    @pytest.mark.asyncio
    async def test_wizard_creates_paper_session(self):
        """Completing the wizard POSTs a paper session and returns a session id."""
        mock_session = self._make_mock_session(symbol="AAPL", strategy="rsi", capital=100.0)

        async def mock_get_db():
            db = AsyncMock()
            db.add = MagicMock()
            db.commit = AsyncMock()
            db.refresh = AsyncMock(side_effect=lambda obj: None)

            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=mock_session)
            db.execute = AsyncMock(return_value=result)
            yield db

        with patch("routers.sessions.register_symbol", MagicMock()):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/sessions", json={
                        "symbol": "AAPL",
                        "strategy": "rsi",
                        "strategy_params": {},
                        "starting_capital": 100.0,
                        "mode": "paper",
                    })
                assert resp.status_code == 200
            finally:
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_wizard_requires_symbol(self):
        """Missing symbol should result in a 422 validation error."""
        async def mock_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/sessions", json={
                    "strategy": "rsi",
                    "strategy_params": {},
                    "starting_capital": 100.0,
                    "mode": "paper",
                })
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_wizard_requires_strategy(self):
        """Missing strategy should result in a 422 validation error."""
        async def mock_get_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = mock_get_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/sessions", json={
                    "symbol": "AAPL",
                    "strategy_params": {},
                    "starting_capital": 100.0,
                    "mode": "paper",
                })
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()
