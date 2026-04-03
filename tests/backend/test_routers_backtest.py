"""Tests for the backtest router endpoints.

All DB and yfinance calls are mocked via dependency overrides.
"""

import sys
import types
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from httpx import AsyncClient, ASGITransport

# Ensure third-party stubs exist before importing main
for _mod in ["yfinance", "aiohttp", "finnhub"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

for _full in ["scrapers.yahoo", "scrapers.alpha_vantage", "scrapers.finnhub"]:
    if _full not in sys.modules:
        _m = types.ModuleType(_full)
        async def _stub(*a, **kw):
            return None
        _m.fetch_yahoo = _stub
        _m.fetch_alpha_vantage = _stub
        _m.fetch_finnhub = _stub
        sys.modules[_full] = _m

from main import app  # noqa: E402
from database import get_db


def _make_price_bar(close=150.0, ts=None):
    bar = MagicMock()
    bar.close = close
    bar.open = close - 1
    bar.high = close + 1
    bar.low = close - 2
    bar.volume = 100000
    bar.timestamp = ts or datetime.now(timezone.utc)
    bar.symbol = "AAPL"
    return bar


def _make_mock_db():
    return AsyncMock()


def _override_get_db(db_mock):
    async def _get_db_override():
        yield db_mock
    return _get_db_override


def _mock_execute(db, items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    db.execute = AsyncMock(return_value=result)
    return result


# ---------------------------------------------------------------------------
# /backtest/seed/{symbol}
# ---------------------------------------------------------------------------

class TestSeedPriceHistory:
    @pytest.mark.asyncio
    async def test_seed_inserts_rows(self):
        db = _make_mock_db()

        import pandas as pd
        from datetime import date
        idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
        df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 100.0],
            "Close": [102.0, 103.0],
            "Volume": [500000, 600000],
        }, index=idx)

        # existing timestamps query
        existing_result = MagicMock()
        existing_result.fetchall.return_value = []
        db.execute = AsyncMock(return_value=existing_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("asyncio.to_thread", AsyncMock(return_value=df)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/backtest/seed/AAPL?days=30")
            assert resp.status_code == 200
            data = resp.json()
            assert data["inserted"] == 2
            assert data["skipped"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_seed_skips_existing_rows(self):
        db = _make_mock_db()

        import pandas as pd
        idx = pd.to_datetime(["2024-01-02"])
        df = pd.DataFrame({
            "Open": [100.0], "High": [105.0], "Low": [99.0], "Close": [102.0], "Volume": [500000],
        }, index=idx)

        existing_ts = datetime(2024, 1, 2, tzinfo=timezone.utc)
        existing_result = MagicMock()
        existing_result.fetchall.return_value = [(existing_ts,)]
        db.execute = AsyncMock(return_value=existing_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("asyncio.to_thread", AsyncMock(return_value=df)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/backtest/seed/AAPL")
            assert resp.status_code == 200
            data = resp.json()
            assert data["skipped"] == 1
            assert data["inserted"] == 0
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_seed_returns_422_when_yahoo_empty(self):
        db = _make_mock_db()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("asyncio.to_thread", AsyncMock(return_value=pd.DataFrame())):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/backtest/seed/FAKE")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_seed_flattens_multiindex_columns(self):
        db = _make_mock_db()

        import pandas as pd
        idx = pd.to_datetime(["2024-01-02"])
        arrays = [["Open", "High", "Low", "Close", "Volume"], ["AAPL"] * 5]
        mi = pd.MultiIndex.from_arrays(arrays)
        df = pd.DataFrame([[100.0, 105.0, 99.0, 102.0, 500000]], index=idx, columns=mi)

        existing_result = MagicMock()
        existing_result.fetchall.return_value = []
        db.execute = AsyncMock(return_value=existing_result)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            with patch("asyncio.to_thread", AsyncMock(return_value=df)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/backtest/seed/AAPL")
            assert resp.status_code == 200
            assert resp.json()["inserted"] == 1
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /backtest
# ---------------------------------------------------------------------------

class TestRunBacktest:
    @pytest.mark.asyncio
    async def test_run_backtest_returns_trades_and_summary(self):
        db = _make_mock_db()
        bars = [_make_price_bar(close=100.0 + i) for i in range(50)]
        _mock_execute(db, bars)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest", json={
                    "symbol": "AAPL",
                    "strategy": "rsi",
                    "strategy_params": {"period": 14, "oversold": 30, "overbought": 70},
                    "starting_capital": 1000.0,
                    "from_dt": "2024-01-01T00:00:00Z",
                    "to_dt": "2024-06-01T00:00:00Z",
                })
            assert resp.status_code == 200
            data = resp.json()
            assert "trades" in data
            assert "summary" in data
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_run_backtest_returns_400_for_unknown_strategy(self):
        db = _make_mock_db()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest", json={
                    "symbol": "AAPL",
                    "strategy": "nonexistent_strategy",
                    "strategy_params": {},
                    "starting_capital": 1000.0,
                    "from_dt": "2024-01-01T00:00:00Z",
                    "to_dt": "2024-06-01T00:00:00Z",
                })
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /backtest/compare
# ---------------------------------------------------------------------------

class TestRunBacktestCompare:
    @pytest.mark.asyncio
    async def test_compare_returns_results(self):
        db = _make_mock_db()
        bars = [_make_price_bar(close=100.0 + i) for i in range(50)]
        _mock_execute(db, bars)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest/compare", json={
                    "symbol": "AAPL",
                    "strategies": [
                        {"name": "rsi", "params": {"period": 14, "oversold": 30, "overbought": 70}},
                        {"name": "macd", "params": {}},
                    ],
                    "starting_capital": 1000.0,
                    "from_dt": "2024-01-01T00:00:00Z",
                    "to_dt": "2024-06-01T00:00:00Z",
                })
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_compare_returns_400_for_unknown_strategy(self):
        db = _make_mock_db()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest/compare", json={
                    "symbol": "AAPL",
                    "strategies": [{"name": "fake_strategy", "params": {}}],
                    "starting_capital": 1000.0,
                    "from_dt": "2024-01-01T00:00:00Z",
                    "to_dt": "2024-06-01T00:00:00Z",
                })
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /backtest/optimize
# ---------------------------------------------------------------------------

class TestOptimizeStrategy:
    @pytest.mark.asyncio
    async def test_optimize_returns_results(self):
        db = _make_mock_db()
        bars = [_make_price_bar(close=100.0 + i) for i in range(50)]
        _mock_execute(db, bars)

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest/optimize", json={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-01",
                    "starting_capital": 1000.0,
                    "strategy": "rsi",
                    "parameter_ranges": {
                        "period": [14, 21],
                        "oversold": [30],
                        "overbought": [70],
                    },
                })
            assert resp.status_code == 200
            data = resp.json()
            assert "combinations_tested" in data
            assert "results" in data
            assert data["combinations_tested"] == 2
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_optimize_returns_400_for_unknown_strategy(self):
        db = _make_mock_db()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest/optimize", json={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-01",
                    "starting_capital": 1000.0,
                    "strategy": "nonexistent",
                    "parameter_ranges": {"period": [14]},
                })
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_optimize_returns_400_when_too_many_combinations(self):
        db = _make_mock_db()

        app.dependency_overrides[get_db] = _override_get_db(db)
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/backtest/optimize", json={
                    "symbol": "AAPL",
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-01",
                    "starting_capital": 1000.0,
                    "strategy": "rsi",
                    "parameter_ranges": {
                        "period": list(range(1, 52)),  # 51 values
                        "oversold": list(range(20, 45)),  # 25 values → 51×25 = 1275 > 100
                        "overbought": [70],
                    },
                })
            assert resp.status_code == 400
            assert "Too many" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()
