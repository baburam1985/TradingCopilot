"""Tests for FastAPI routers: sessions, trades, market_data.

Uses dependency overrides to avoid a real database connection.
"""

import sys
import types
import uuid
from datetime import datetime, timezone, timedelta
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

# Import app after stubs are in place
with patch("scheduler.scraper_job.AsyncIOScheduler", MagicMock):
    from main import app  # noqa: E402

from database import get_db


def _make_mock_session(
    symbol="AAPL",
    strategy="rsi",
    status="active",
    starting_capital=1000.0,
    mode="paper",
):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.strategy = strategy
    s.strategy_params = {"period": 14}
    s.starting_capital = starting_capital
    s.mode = mode
    s.status = status
    s.created_at = datetime.now(timezone.utc)
    s.closed_at = None
    s.stop_loss_pct = None
    s.take_profit_pct = None
    s.max_position_pct = None
    s.daily_max_loss_pct = None
    s.notify_email = False
    s.email_address = None
    return s


def _make_mock_trade(session_id=None, action="buy", status="closed", pnl=10.0):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.session_id = session_id or uuid.uuid4()
    t.action = action
    t.status = status
    t.pnl = pnl
    t.price_at_signal = 150.0
    t.quantity = 6.0
    t.signal_reason = "oversold"
    t.timestamp_open = datetime.now(timezone.utc) - timedelta(hours=2)
    t.timestamp_close = datetime.now(timezone.utc) - timedelta(hours=1)
    t.alpaca_order_id = None
    t.reasoning = None
    return t


def _make_mock_db():
    db = AsyncMock()
    return db


def _override_get_db(db_mock):
    async def _get_db_override():
        yield db_mock
    return _get_db_override


# ---------------------------------------------------------------------------
# Sessions router
# ---------------------------------------------------------------------------

class TestSessionsRouter:
    @pytest.mark.asyncio
    async def test_create_session_returns_201(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("routers.sessions.register_symbol"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/sessions", json={
                        "symbol": "AAPL",
                        "strategy": "rsi",
                        "strategy_params": {"period": 14},
                        "starting_capital": 1000.0,
                        "mode": "paper",
                    })
            assert resp.status_code == 200
            db.add.assert_called_once()
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_session_with_risk_params(self):
        db = _make_mock_db()
        db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("routers.sessions.register_symbol"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/sessions", json={
                        "symbol": "TSLA",
                        "strategy": "macd",
                        "strategy_params": {},
                        "starting_capital": 500.0,
                        "mode": "paper",
                        "stop_loss_pct": 5.0,
                        "take_profit_pct": 10.0,
                        "max_position_pct": 50.0,
                        "daily_max_loss_pct": 3.0,
                        "notify_email": True,
                        "email_address": "trader@example.com",
                    })
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_sessions_returns_list(self):
        db = _make_mock_db()
        sessions = [_make_mock_session(), _make_mock_session(symbol="TSLA")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sessions
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sessions")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session_returns_session(self):
        db = _make_mock_db()
        session = _make_mock_session()
        db.get = AsyncMock(return_value=session)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{uuid.uuid4()}")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_stop_session_closes_it(self):
        db = _make_mock_db()
        session = _make_mock_session()
        db.get = AsyncMock(return_value=session)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("routers.sessions.unregister_symbol"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.patch(f"/sessions/{session.id}/stop")
            assert resp.status_code == 200
            assert session.status == "closed"
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_stop_session_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(f"/sessions/{uuid.uuid4()}/stop")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_session_patches_notification_prefs(self):
        db = _make_mock_db()
        session = _make_mock_session()
        session.notify_email = False
        session.email_address = None
        db.get = AsyncMock(return_value=session)
        db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(f"/sessions/{session.id}", json={
                    "notify_email": True,
                    "email_address": "trader@example.com",
                })
            assert resp.status_code == 200
            assert session.notify_email is True
            assert session.email_address == "trader@example.com"
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_session_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.patch(f"/sessions/{uuid.uuid4()}", json={"notify_email": True})
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_strategy(self):
        db = _make_mock_db()
        sessions = [_make_mock_session(strategy="rsi")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sessions
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sessions?strategy=rsi")
            assert resp.status_code == 200
            db.execute.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_symbol(self):
        db = _make_mock_db()
        sessions = [_make_mock_session(symbol="TSLA")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sessions
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sessions?symbol=TSLA")
            assert resp.status_code == 200
            db.execute.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_status(self):
        db = _make_mock_db()
        sessions = [_make_mock_session(status="closed")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sessions
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sessions?status=closed")
            assert resp.status_code == 200
            db.execute.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_date_range(self):
        db = _make_mock_db()
        sessions = [_make_mock_session()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sessions
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sessions?from_date=2024-01-01&to_date=2024-12-31")
            assert resp.status_code == 200
            db.execute.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session_summary_returns_metrics(self):
        db = _make_mock_db()
        session = _make_mock_session(starting_capital=1000.0)
        session.closed_at = datetime.now(timezone.utc)
        db.get = AsyncMock(return_value=session)

        trade1 = _make_mock_trade(session_id=session.id, action="buy", status="closed", pnl=25.0)
        trade2 = _make_mock_trade(session_id=session.id, action="buy", status="closed", pnl=-10.0)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [trade1, trade2]
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/summary")
            assert resp.status_code == 200
            data = resp.json()
            assert data["num_trades"] == 2
            assert data["num_wins"] == 1
            assert data["symbol"] == "AAPL"
            assert data["strategy"] == "rsi"
            assert "duration_seconds" in data
            assert "win_rate" in data
            assert "total_pnl" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session_summary_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{uuid.uuid4()}/summary")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Trades router
# ---------------------------------------------------------------------------

class TestTradesRouter:
    @pytest.mark.asyncio
    async def test_get_trades_returns_list(self):
        db = _make_mock_db()
        session_id = uuid.uuid4()
        trades = [_make_mock_trade(session_id=session_id)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = trades
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session_id}/trades")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_equity_curve_returns_data(self):
        db = _make_mock_db()
        session_id = uuid.uuid4()
        session = _make_mock_session(starting_capital=1000.0)
        session.created_at = datetime.now(timezone.utc) - timedelta(days=30)

        trade = _make_mock_trade(session_id=session_id, status="closed", pnl=50.0)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [trade]

        db.get = AsyncMock(return_value=session)
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session_id}/equity-curve")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_pnl_returns_summary(self):
        db = _make_mock_db()
        session_id = uuid.uuid4()
        session = _make_mock_session(starting_capital=1000.0)

        trade = _make_mock_trade(session_id=session_id, status="closed", pnl=25.0)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [trade]

        db.get = AsyncMock(return_value=session)
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session_id}/pnl")
            assert resp.status_code == 200
            data = resp.json()
            assert "all_time" in data
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Market data router
# ---------------------------------------------------------------------------

class TestMarketDataRouter:
    def _make_price_history_row(self, symbol="AAPL", close=150.0):
        row = MagicMock()
        row.symbol = symbol
        row.close = close
        row.open = 148.0
        row.high = 152.0
        row.low = 147.0
        row.volume = 1000000
        row.timestamp = datetime.now(timezone.utc)
        row.yahoo_close = close
        row.alphavantage_close = close
        row.finnhub_close = close
        row.outlier_flags = {}
        row.sources_available = ["yahoo"]
        return row

    @pytest.mark.asyncio
    async def test_get_history_returns_rows(self):
        db = _make_mock_db()
        rows = [self._make_price_history_row()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            now = datetime.now(timezone.utc)
            from_dt = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
            to_dt = now.strftime("%Y-%m-%dT%H:%M:%S")
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/symbols/AAPL/history?from={from_dt}&to={to_dt}")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_latest_returns_row(self):
        db = _make_mock_db()
        row = self._make_price_history_row()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/symbols/AAPL/latest")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_latest_returns_null_when_no_data(self):
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/symbols/AAPL/latest")
            assert resp.status_code == 200
            assert resp.json() is None
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_scrape_symbol_success(self):
        from backend.scrapers.base import FetchResult

        db = _make_mock_db()
        db.refresh = AsyncMock()

        fake_result = FetchResult(
            source="yahoo", open=100.0, high=105.0, low=99.0, close=102.0,
            volume=500000, success=True
        )

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            import scrapers.yahoo as yahoo_mod
            with patch.object(yahoo_mod, "fetch_yahoo", AsyncMock(return_value=fake_result)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/symbols/AAPL/scrape")
            assert resp.status_code == 200
            db.add.assert_called_once()
            db.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_scrape_symbol_returns_422_on_failure(self):
        from backend.scrapers.base import FetchResult

        db = _make_mock_db()
        fake_result = FetchResult(
            source="yahoo", open=0, high=0, low=0, close=0,
            volume=0, success=False, error="No data"
        )

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            import scrapers.yahoo as yahoo_mod
            with patch.object(yahoo_mod, "fetch_yahoo", AsyncMock(return_value=fake_result)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/symbols/FAKE/scrape")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Live executor stub
# ---------------------------------------------------------------------------

class TestLiveExecutorStub:
    @pytest.mark.asyncio
    async def test_execute_returns_none(self):
        from backend.executor.live_stub import LiveExecutorStub
        from backend.strategies.base import Signal

        stub = LiveExecutorStub()
        session = MagicMock()
        session.symbol = "AAPL"
        session.id = uuid.uuid4()
        signal = Signal(action="buy", reason="test", confidence=0.9)

        result = await stub.execute(session, signal, 150.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_with_db_arg_still_returns_none(self):
        from backend.executor.live_stub import LiveExecutorStub
        from backend.strategies.base import Signal

        stub = LiveExecutorStub()
        session = MagicMock()
        session.symbol = "TSLA"
        session.id = uuid.uuid4()
        signal = Signal(action="sell", reason="overbought", confidence=0.7)
        mock_db = AsyncMock()

        result = await stub.execute(session, signal, 300.0, db=mock_db)
        assert result is None
