"""Tests for individual scraper modules: yahoo, finnhub, alpha_vantage.

All external HTTP/SDK calls are mocked so no real network access is required.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Yahoo Finance scraper
# ---------------------------------------------------------------------------

class TestFetchYahoo:
    @pytest.mark.asyncio
    async def test_returns_correct_ohlcv_on_success(self):
        import pandas as pd
        from backend.scrapers.yahoo import fetch_yahoo

        df = pd.DataFrame({
            "Open": [100.0],
            "High": [105.0],
            "Low": [99.0],
            "Close": [102.0],
            "Volume": [500000],
        })

        with patch("backend.scrapers.yahoo.yf") as mock_yf:
            mock_yf.download.return_value = df
            result = await fetch_yahoo("AAPL")

        assert result.success is True
        assert result.source == "yahoo"
        assert result.open == pytest.approx(100.0)
        assert result.high == pytest.approx(105.0)
        assert result.low == pytest.approx(99.0)
        assert result.close == pytest.approx(102.0)
        assert result.volume == 500000

    @pytest.mark.asyncio
    async def test_returns_failure_on_empty_dataframe(self):
        from backend.scrapers.yahoo import fetch_yahoo

        with patch("backend.scrapers.yahoo.yf") as mock_yf:
            mock_yf.download.return_value = pd.DataFrame()
            result = await fetch_yahoo("UNKNOWN")

        assert result.success is False
        assert result.error == "Empty response"

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self):
        from backend.scrapers.yahoo import fetch_yahoo

        with patch("backend.scrapers.yahoo.yf") as mock_yf:
            mock_yf.download.side_effect = RuntimeError("network error")
            result = await fetch_yahoo("AAPL")

        assert result.success is False
        assert "network error" in result.error

    @pytest.mark.asyncio
    async def test_flattens_multiindex_columns(self):
        """yfinance 0.2+ returns MultiIndex columns — they should be flattened."""
        from backend.scrapers.yahoo import fetch_yahoo

        arrays = [["Open", "High", "Low", "Close", "Volume"], ["AAPL"] * 5]
        index = pd.MultiIndex.from_arrays(arrays)
        df = pd.DataFrame([[101.0, 106.0, 100.0, 103.0, 1000000]], columns=index)

        with patch("backend.scrapers.yahoo.yf") as mock_yf:
            mock_yf.download.return_value = df
            result = await fetch_yahoo("AAPL")

        assert result.success is True
        assert result.open == pytest.approx(101.0)


# ---------------------------------------------------------------------------
# Finnhub scraper
#
# We patch `asyncio.to_thread` rather than `finnhub.Client` directly because
# the stub modules injected by other test files (test_api.py, test_routers.py)
# may replace the real `finnhub` package in sys.modules before this module
# loads, making Client-level patching unreliable across the full test suite.
# ---------------------------------------------------------------------------

def _make_finnhub_module_mock(quote_return_value):
    """Build a mock finnhub module whose Client().quote() returns *quote_return_value*."""
    mock_mod = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.quote.return_value = quote_return_value
    mock_mod.Client.return_value = mock_client_instance
    return mock_mod


class TestFetchFinnhub:
    @pytest.mark.asyncio
    async def test_returns_correct_ohlc_on_success(self):
        from backend.scrapers.finnhub import fetch_finnhub

        quote = {"o": 150.0, "h": 155.0, "l": 149.0, "c": 152.5}
        mock_mod = _make_finnhub_module_mock(quote)

        with patch("backend.scrapers.finnhub.FINNHUB_API_KEY", "test-key"), \
             patch("backend.scrapers.finnhub.finnhub", mock_mod), \
             patch("asyncio.to_thread", AsyncMock(return_value=quote)):
            result = await fetch_finnhub("AAPL")

        assert result.success is True
        assert result.source == "finnhub"
        assert result.open == pytest.approx(150.0)
        assert result.high == pytest.approx(155.0)
        assert result.low == pytest.approx(149.0)
        assert result.close == pytest.approx(152.5)

    @pytest.mark.asyncio
    async def test_returns_failure_when_no_api_key(self):
        from backend.scrapers.finnhub import fetch_finnhub

        with patch("backend.scrapers.finnhub.FINNHUB_API_KEY", ""):
            result = await fetch_finnhub("AAPL")

        assert result.success is False
        assert "No API key" in result.error

    @pytest.mark.asyncio
    async def test_returns_failure_on_empty_quote(self):
        from backend.scrapers.finnhub import fetch_finnhub

        empty_quote = {"c": 0}
        mock_mod = _make_finnhub_module_mock(empty_quote)

        with patch("backend.scrapers.finnhub.FINNHUB_API_KEY", "test-key"), \
             patch("backend.scrapers.finnhub.finnhub", mock_mod), \
             patch("asyncio.to_thread", AsyncMock(return_value=empty_quote)):
            result = await fetch_finnhub("AAPL")

        assert result.success is False
        assert "Empty quote" in result.error

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self):
        from backend.scrapers.finnhub import fetch_finnhub

        mock_mod = MagicMock()
        mock_mod.Client.return_value = MagicMock()

        with patch("backend.scrapers.finnhub.FINNHUB_API_KEY", "test-key"), \
             patch("backend.scrapers.finnhub.finnhub", mock_mod), \
             patch("asyncio.to_thread", AsyncMock(side_effect=Exception("API error"))):
            result = await fetch_finnhub("AAPL")

        assert result.success is False
        assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_returns_failure_on_none_quote(self):
        from backend.scrapers.finnhub import fetch_finnhub

        mock_mod = _make_finnhub_module_mock(None)

        with patch("backend.scrapers.finnhub.FINNHUB_API_KEY", "test-key"), \
             patch("backend.scrapers.finnhub.finnhub", mock_mod), \
             patch("asyncio.to_thread", AsyncMock(return_value=None)):
            result = await fetch_finnhub("AAPL")

        assert result.success is False


# ---------------------------------------------------------------------------
# Alpha Vantage scraper
# ---------------------------------------------------------------------------

class TestFetchAlphaVantage:
    @pytest.mark.asyncio
    async def test_returns_correct_ohlcv_on_success(self):
        from backend.scrapers.alpha_vantage import fetch_alpha_vantage

        ts_data = {
            "2024-01-15 15:59:00": {
                "1. open": "145.0",
                "2. high": "146.5",
                "3. low": "144.5",
                "4. close": "145.8",
                "5. volume": "123456",
            }
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {"Time Series (1min)": ts_data}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.scrapers.alpha_vantage.ALPHA_VANTAGE_API_KEY", "test-key"), \
             patch("backend.scrapers.alpha_vantage.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_alpha_vantage("AAPL")

        assert result.success is True
        assert result.source == "alphavantage"
        assert result.open == pytest.approx(145.0)
        assert result.close == pytest.approx(145.8)
        assert result.volume == 123456

    @pytest.mark.asyncio
    async def test_returns_failure_when_no_api_key(self):
        from backend.scrapers.alpha_vantage import fetch_alpha_vantage

        with patch("backend.scrapers.alpha_vantage.ALPHA_VANTAGE_API_KEY", ""):
            result = await fetch_alpha_vantage("AAPL")

        assert result.success is False
        assert "No API key" in result.error

    @pytest.mark.asyncio
    async def test_returns_failure_when_no_time_series(self):
        from backend.scrapers.alpha_vantage import fetch_alpha_vantage

        mock_response = MagicMock()
        mock_response.json.return_value = {"Note": "API rate limit"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.scrapers.alpha_vantage.ALPHA_VANTAGE_API_KEY", "test-key"), \
             patch("backend.scrapers.alpha_vantage.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_alpha_vantage("AAPL")

        assert result.success is False
        assert "No time series" in result.error

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self):
        from backend.scrapers.alpha_vantage import fetch_alpha_vantage

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.scrapers.alpha_vantage.ALPHA_VANTAGE_API_KEY", "test-key"), \
             patch("backend.scrapers.alpha_vantage.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_alpha_vantage("AAPL")

        assert result.success is False
        assert "Connection refused" in result.error
