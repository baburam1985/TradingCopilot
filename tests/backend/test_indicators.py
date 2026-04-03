"""Tests for indicators router and rolling series computation."""

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
with patch("scheduler.scraper_job.AsyncIOScheduler", MagicMock):
    from main import app  # noqa: E402

from database import get_db
from routers.indicators import (
    _compute_sma_series,
    _compute_ema_series,
    _compute_bollinger_series,
    _compute_rsi_series,
    _compute_macd_series,
)
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Unit tests for rolling series helpers
# ---------------------------------------------------------------------------

class TestSMASeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 5
        result = _compute_sma_series(closes, period=20)
        assert all(v is None for v in result)

    def test_correct_values_after_period(self):
        closes = list(range(1, 22))  # 1..21
        result = _compute_sma_series(closes, period=20)
        # First 19 should be None
        assert all(v is None for v in result[:19])
        # Index 19: average of 1..20 = 10.5
        assert result[19] == pytest.approx(10.5)
        # Index 20: average of 2..21 = 11.5
        assert result[20] == pytest.approx(11.5)

    def test_length_matches_input(self):
        closes = [100.0 + i for i in range(30)]
        result = _compute_sma_series(closes, period=20)
        assert len(result) == 30


class TestEMASeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 5
        result = _compute_ema_series(closes, period=20)
        assert all(v is None for v in result[:19])

    def test_emits_value_at_period(self):
        closes = [100.0] * 25
        result = _compute_ema_series(closes, period=20)
        # From index 19 onward should have float values (EMA of constant = same value)
        assert result[19] == pytest.approx(100.0)
        assert result[24] == pytest.approx(100.0)

    def test_ema_trends_toward_new_price(self):
        closes = [100.0] * 20 + [200.0] * 20
        result = _compute_ema_series(closes, period=20)
        # After sustained higher prices, EMA should be trending up
        non_none = [v for v in result if v is not None]
        assert non_none[-1] > non_none[0]

    def test_length_matches_input(self):
        closes = [50.0 + i * 0.5 for i in range(40)]
        result = _compute_ema_series(closes, period=20)
        assert len(result) == 40


class TestBollingerSeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 15
        result = _compute_bollinger_series(closes, period=20, multiplier=2.0)
        assert all(v is None for v in result)

    def test_bands_structure(self):
        closes = [100.0 + i for i in range(25)]
        result = _compute_bollinger_series(closes, period=20, multiplier=2.0)
        val = result[19]
        assert val is not None
        assert "upper" in val and "middle" in val and "lower" in val
        assert val["upper"] > val["middle"] > val["lower"]

    def test_constant_series_has_zero_width(self):
        closes = [100.0] * 25
        result = _compute_bollinger_series(closes, period=20, multiplier=2.0)
        val = result[19]
        assert val is not None
        assert val["upper"] == pytest.approx(val["middle"])
        assert val["lower"] == pytest.approx(val["middle"])

    def test_length_matches_input(self):
        closes = [100.0] * 30
        result = _compute_bollinger_series(closes, period=20, multiplier=2.0)
        assert len(result) == 30


class TestRSISeries:
    def test_returns_none_before_period(self):
        closes = [100.0] * 10
        result = _compute_rsi_series(closes, period=14)
        assert all(v is None for v in result)

    def test_emits_value_at_period_plus_one(self):
        closes = [100.0 + i * 0.5 for i in range(20)]
        result = _compute_rsi_series(closes, period=14)
        assert result[14] is not None

    def test_rsi_bounds(self):
        closes = [100.0 + i * 0.5 for i in range(30)]
        result = _compute_rsi_series(closes, period=14)
        for v in result:
            if v is not None:
                assert 0 <= v <= 100

    def test_length_matches_input(self):
        closes = [100.0] * 30
        result = _compute_rsi_series(closes, period=14)
        assert len(result) == 30


class TestMACDSeries:
    def test_returns_none_before_min_bars(self):
        # MACD needs slow + signal bars = 26 + 9 = 35
        closes = [100.0] * 30
        result = _compute_macd_series(closes, fast=12, slow=26, signal=9)
        assert all(v is None for v in result)

    def test_emits_dict_at_min_bars(self):
        closes = [100.0 + i * 0.1 for i in range(40)]
        result = _compute_macd_series(closes, fast=12, slow=26, signal=9)
        val = result[34]
        assert val is not None
        assert "macd" in val and "signal" in val and "histogram" in val

    def test_histogram_equals_macd_minus_signal(self):
        closes = [100.0 + i * 0.1 for i in range(40)]
        result = _compute_macd_series(closes, fast=12, slow=26, signal=9)
        for v in result:
            if v is not None:
                assert v["histogram"] == pytest.approx(v["macd"] - v["signal"])

    def test_length_matches_input(self):
        closes = [100.0] * 50
        result = _compute_macd_series(closes, fast=12, slow=26, signal=9)
        assert len(result) == 50


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

def _make_mock_session(symbol="AAPL"):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.strategy = "rsi"
    s.strategy_params = {}
    s.starting_capital = 1000.0
    s.mode = "paper"
    s.status = "active"
    s.created_at = datetime.now(timezone.utc)
    s.closed_at = None
    return s


def _make_mock_price_rows(symbol="AAPL", n=50):
    rows = []
    base_time = datetime.now(timezone.utc) - timedelta(minutes=n)
    for i in range(n):
        row = MagicMock()
        row.symbol = symbol
        row.timestamp = base_time + timedelta(minutes=i)
        row.close = 100.0 + i * 0.5
        rows.append(row)
    return rows


def _make_mock_db():
    return AsyncMock()


def _override_get_db(db_mock):
    async def _get_db_override():
        yield db_mock
    return _get_db_override


class TestIndicatorsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_all_indicators_by_default(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        mock_rows = _make_mock_price_rows(n=50)

        db.get = AsyncMock(return_value=mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators")
            assert resp.status_code == 200
            data = resp.json()
            assert "sma" in data
            assert "ema" in data
            assert "bollinger" in data
            assert "rsi" in data
            assert "macd" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_returns_only_requested_indicators(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        mock_rows = _make_mock_price_rows(n=50)

        db.get = AsyncMock(return_value=mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators?indicators=sma,rsi")
            assert resp.status_code == 200
            data = resp.json()
            assert "sma" in data
            assert "rsi" in data
            assert "ema" not in data
            assert "bollinger" not in data
            assert "macd" not in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_sma_entries_have_time_and_value(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        mock_rows = _make_mock_price_rows(n=30)

        db.get = AsyncMock(return_value=mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators?indicators=sma")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["sma"]) > 0
            entry = data["sma"][0]
            assert "time" in entry
            assert "value" in entry
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_bollinger_entries_have_upper_middle_lower(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        mock_rows = _make_mock_price_rows(n=30)

        db.get = AsyncMock(return_value=mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators?indicators=bollinger")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["bollinger"]) > 0
            entry = data["bollinger"][0]
            assert "time" in entry
            assert "upper" in entry
            assert "middle" in entry
            assert "lower" in entry
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_macd_entries_have_macd_signal_histogram(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        mock_rows = _make_mock_price_rows(n=50)

        db.get = AsyncMock(return_value=mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_rows
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators?indicators=macd")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["macd"]) > 0
            entry = data["macd"][0]
            assert "time" in entry
            assert "macd" in entry
            assert "signal" in entry
            assert "histogram" in entry
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_session_not_found_returns_404(self):
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
    async def test_unknown_indicator_returns_400(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()
        db.get = AsyncMock(return_value=mock_session)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators?indicators=unknown")
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_empty_price_history_returns_empty_lists(self):
        db = _make_mock_db()
        mock_session = _make_mock_session()

        db.get = AsyncMock(return_value=mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/sessions/{mock_session.id}/indicators?indicators=sma,rsi")
            assert resp.status_code == 200
            data = resp.json()
            assert data["sma"] == []
            assert data["rsi"] == []
        finally:
            app.dependency_overrides.clear()
