"""Unit tests for GET /sessions/{session_id}/chart-data endpoint
and new indicator series (VWAP, breakout, mean_reversion).
"""

import sys
import types
import uuid
import math
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def _stub_scraper_modules():
    for mod_name in [
        "yfinance", "aiohttp", "finnhub",
        "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    ]:
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
from routers.indicators import (
    _compute_vwap_series,
    _compute_breakout_series,
    _compute_mean_reversion_series,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_session(symbol="AAPL", strategy="rsi", status="active", starting_capital=1000.0):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.strategy = strategy
    s.starting_capital = starting_capital
    s.mode = "paper"
    s.status = status
    s.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    s.closed_at = None
    return s


def _make_mock_price_row(symbol="AAPL", offset_minutes=0):
    row = MagicMock()
    row.symbol = symbol
    row.timestamp = datetime.now(timezone.utc) - timedelta(minutes=120 - offset_minutes)
    row.open = 149.5 + offset_minutes * 0.01
    row.high = 151.0 + offset_minutes * 0.01
    row.low = 148.5 + offset_minutes * 0.01
    row.close = 150.0 + offset_minutes * 0.01
    row.volume = 100000
    return row


def _make_mock_trade(session_id=None, action="buy", pnl=None):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.session_id = session_id or uuid.uuid4()
    t.action = action
    t.price_at_signal = 150.0
    t.quantity = 5.0
    t.timestamp_open = datetime.now(timezone.utc) - timedelta(hours=1)
    t.timestamp_close = None
    t.pnl = pnl
    t.signal_reason = "test signal"
    t.reasoning = None
    t.status = "open" if pnl is None else "closed"
    return t


def _make_mock_db():
    return AsyncMock()


def _override_get_db(db_mock):
    async def _get_db_override():
        yield db_mock
    return _get_db_override


# ---------------------------------------------------------------------------
# Unit tests: VWAP series
# ---------------------------------------------------------------------------

class TestVWAPSeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 5
        highs = [101.0] * 5
        lows = [99.0] * 5
        volumes = [1000.0] * 5
        result = _compute_vwap_series(closes, highs, lows, volumes, period=20)
        assert all(v is None for v in result)

    def test_emits_value_at_period(self):
        closes = [100.0] * 25
        highs = [101.0] * 25
        lows = [99.0] * 25
        volumes = [1000.0] * 25
        result = _compute_vwap_series(closes, highs, lows, volumes, period=20)
        # Index 19 onward should have a value
        assert result[19] is not None

    def test_vwap_equals_price_for_constant_series(self):
        closes = [100.0] * 25
        highs = [102.0] * 25
        lows = [98.0] * 25
        volumes = [500.0] * 25
        result = _compute_vwap_series(closes, highs, lows, volumes, period=20)
        # typical = (102 + 98 + 100) / 3 = 100.0
        assert result[19] == pytest.approx(100.0)

    def test_zero_volume_falls_back_to_mean(self):
        closes = [100.0] * 25
        highs = [102.0] * 25
        lows = [98.0] * 25
        volumes = [0.0] * 25
        result = _compute_vwap_series(closes, highs, lows, volumes, period=20)
        assert result[19] == pytest.approx(100.0)

    def test_length_matches_input(self):
        closes = [100.0 + i for i in range(30)]
        highs = [101.0 + i for i in range(30)]
        lows = [99.0 + i for i in range(30)]
        volumes = [1000.0] * 30
        result = _compute_vwap_series(closes, highs, lows, volumes, period=20)
        assert len(result) == 30


# ---------------------------------------------------------------------------
# Unit tests: Breakout channel series
# ---------------------------------------------------------------------------

class TestBreakoutSeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 15
        result = _compute_breakout_series(closes, period=20)
        assert all(v is None for v in result)

    def test_high_low_structure(self):
        closes = [float(i) for i in range(1, 26)]  # 1..25
        result = _compute_breakout_series(closes, period=20)
        entry = result[19]
        assert entry is not None
        assert "high" in entry and "low" in entry
        assert entry["high"] > entry["low"]

    def test_correct_channel_values(self):
        closes = list(range(1, 26))  # 1..25
        result = _compute_breakout_series(closes, period=20)
        # Index 19: window is closes[0..19] = 1..20
        assert result[19]["high"] == pytest.approx(20)
        assert result[19]["low"] == pytest.approx(1)

    def test_length_matches_input(self):
        closes = [100.0] * 30
        result = _compute_breakout_series(closes, period=20)
        assert len(result) == 30


# ---------------------------------------------------------------------------
# Unit tests: Mean Reversion band series
# ---------------------------------------------------------------------------

class TestMeanReversionSeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 15
        result = _compute_mean_reversion_series(closes, period=20)
        assert all(v is None for v in result)

    def test_band_structure(self):
        closes = [100.0 + i for i in range(25)]
        result = _compute_mean_reversion_series(closes, period=20)
        entry = result[19]
        assert entry is not None
        assert "mean" in entry and "upper" in entry and "lower" in entry

    def test_upper_above_mean_above_lower(self):
        closes = [100.0 + i * 0.5 for i in range(25)]
        result = _compute_mean_reversion_series(closes, period=20)
        entry = result[19]
        assert entry["upper"] >= entry["mean"] >= entry["lower"]

    def test_constant_series_zero_width(self):
        closes = [100.0] * 25
        result = _compute_mean_reversion_series(closes, period=20)
        entry = result[19]
        assert entry["upper"] == pytest.approx(entry["mean"])
        assert entry["lower"] == pytest.approx(entry["mean"])

    def test_length_matches_input(self):
        closes = [100.0] * 30
        result = _compute_mean_reversion_series(closes, period=20)
        assert len(result) == 30


# ---------------------------------------------------------------------------
# Endpoint tests: /sessions/{id}/chart-data
# ---------------------------------------------------------------------------

class TestChartDataEndpoint:
    @pytest.mark.asyncio
    async def test_returns_candles_and_signals(self):
        db = _make_mock_db()
        session = _make_mock_session()
        price_rows = [_make_mock_price_row(offset_minutes=i * 5) for i in range(10)]
        trade = _make_mock_trade(session_id=session.id)

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = price_rows
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = [trade]
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            assert resp.status_code == 200
            data = resp.json()
            assert "candles" in data
            assert "signals" in data
            assert "symbol" in data
            assert "strategy" in data
            assert len(data["candles"]) == 10
            assert len(data["signals"]) == 1
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_candle_has_ohlcv_fields(self):
        db = _make_mock_db()
        session = _make_mock_session()
        price_rows = [_make_mock_price_row()]

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = price_rows
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            assert resp.status_code == 200
            candle = resp.json()["candles"][0]
            for field in ("time", "open", "high", "low", "close", "volume"):
                assert field in candle
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_signal_has_required_fields(self):
        db = _make_mock_db()
        session = _make_mock_session()
        trade = _make_mock_trade(session_id=session.id, action="buy", pnl=12.5)
        trade.quantity = 5.0
        trade.price_at_signal = 150.0

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = []
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = [trade]
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            assert resp.status_code == 200
            sig = resp.json()["signals"][0]
            assert sig["action"] == "buy"
            assert sig["price"] == pytest.approx(150.0)
            assert "reasoning_text" in sig
            assert "time" in sig
            assert "pnl_pct" in sig
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_pnl_pct_computed_correctly(self):
        db = _make_mock_db()
        session = _make_mock_session()
        trade = _make_mock_trade(session_id=session.id, action="buy", pnl=15.0)
        trade.quantity = 10.0
        trade.price_at_signal = 100.0  # cost_basis = 1000, pnl_pct = 15/1000 * 100 = 1.5

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = []
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = [trade]
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            sig = resp.json()["signals"][0]
            assert sig["pnl_pct"] == pytest.approx(1.5)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_session_not_found_returns_404(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{uuid.uuid4()}/chart-data")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_empty_price_history_returns_empty_candles(self):
        db = _make_mock_db()
        session = _make_mock_session()

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = []
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            assert resp.status_code == 200
            data = resp.json()
            assert data["candles"] == []
            assert data["signals"] == []
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_candle_time_is_unix_epoch(self):
        db = _make_mock_db()
        session = _make_mock_session()
        row = _make_mock_price_row()

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = [row]
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            candle = resp.json()["candles"][0]
            # Epoch seconds should be a reasonable value (after year 2020)
            assert candle["time"] > 1577836800  # 2020-01-01 in epoch
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_includes_symbol_and_strategy(self):
        db = _make_mock_db()
        session = _make_mock_session(symbol="TSLA", strategy="macd")

        db.get = AsyncMock(return_value=session)
        price_result = MagicMock()
        price_result.scalars.return_value.all.return_value = []
        trades_result = MagicMock()
        trades_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[price_result, trades_result])

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/chart-data")
            data = resp.json()
            assert data["symbol"] == "TSLA"
            assert data["strategy"] == "macd"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint tests: new indicators via /sessions/{id}/indicators
# ---------------------------------------------------------------------------

class TestNewIndicatorsEndpoint:
    def _make_mock_session_obj(self, symbol="AAPL"):
        s = MagicMock()
        s.id = uuid.uuid4()
        s.symbol = symbol
        s.strategy = "vwap"
        s.starting_capital = 1000.0
        s.mode = "paper"
        s.status = "active"
        s.created_at = datetime.now(timezone.utc)
        s.closed_at = None
        return s

    def _make_price_rows(self, n=30):
        rows = []
        base = datetime.now(timezone.utc) - timedelta(minutes=n)
        for i in range(n):
            r = MagicMock()
            r.symbol = "AAPL"
            r.timestamp = base + timedelta(minutes=i)
            r.close = 100.0 + i * 0.5
            r.open = 99.5 + i * 0.5
            r.high = 101.0 + i * 0.5
            r.low = 99.0 + i * 0.5
            r.volume = 50000
            rows.append(r)
        return rows

    @pytest.mark.asyncio
    async def test_vwap_entries_have_time_and_value(self):
        db = _make_mock_db()
        session = self._make_mock_session_obj()
        rows = self._make_price_rows(30)

        db.get = AsyncMock(return_value=session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/indicators?indicators=vwap")
            assert resp.status_code == 200
            data = resp.json()
            assert "vwap" in data
            assert len(data["vwap"]) > 0
            entry = data["vwap"][0]
            assert "time" in entry and "value" in entry
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_breakout_entries_have_high_and_low(self):
        db = _make_mock_db()
        session = self._make_mock_session_obj()
        rows = self._make_price_rows(30)

        db.get = AsyncMock(return_value=session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/indicators?indicators=breakout")
            assert resp.status_code == 200
            data = resp.json()
            assert "breakout" in data
            assert len(data["breakout"]) > 0
            entry = data["breakout"][0]
            assert "time" in entry and "high" in entry and "low" in entry
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_mean_reversion_entries_have_mean_upper_lower(self):
        db = _make_mock_db()
        session = self._make_mock_session_obj()
        rows = self._make_price_rows(30)

        db.get = AsyncMock(return_value=session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{session.id}/indicators?indicators=mean_reversion")
            assert resp.status_code == 200
            data = resp.json()
            assert "mean_reversion" in data
            assert len(data["mean_reversion"]) > 0
            entry = data["mean_reversion"][0]
            assert "time" in entry and "mean" in entry and "upper" in entry and "lower" in entry
        finally:
            app.dependency_overrides.clear()
