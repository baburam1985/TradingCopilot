import sys
import types
import unittest.mock
import pytest
from httpx import AsyncClient, ASGITransport


def _stub_scraper_modules():
    """Stub out third-party scraper dependencies so main.py can be imported without yfinance etc."""
    for mod_name in [
        "yfinance",
        "aiohttp",
        "finnhub",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    # scrapers.yahoo needs yfinance; provide a minimal fetch_yahoo stub
    for full in ["scrapers.yahoo", "scrapers.alpha_vantage", "scrapers.finnhub"]:
        if full not in sys.modules:
            mod = types.ModuleType(full)
            async def _stub(*args, **kwargs):
                return None
            mod.fetch_yahoo = _stub
            mod.fetch_alpha_vantage = _stub
            mod.fetch_finnhub = _stub
            sys.modules[full] = mod


_stub_scraper_modules()

# Now it is safe to import main
from main import app  # noqa: E402  (must come after stubs)


@pytest.mark.asyncio
async def test_list_strategies_returns_moving_average():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "moving_average_crossover"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live PostgreSQL database connection")
async def test_list_sessions_returns_empty_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/sessions")
    assert resp.status_code == 200
    assert resp.json() == []
