"""Integration tests for GET /symbols/{symbol}/events."""

import pytest
from unittest.mock import patch
from datetime import date

pytestmark = pytest.mark.integration


async def test_events_endpoint_returns_200(client, clean_db):
    """Endpoint returns 200 with valid date range even when no earnings available."""
    with patch("services.events_calendar._fetch_earnings_date", return_value=None):
        resp = await client.get(
            "/symbols/AAPL/events",
            params={"from": "2025-01-01T00:00:00", "to": "2025-12-31T00:00:00"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


async def test_events_endpoint_includes_fomc_and_cpi(client, clean_db):
    """Macro events (FOMC, CPI) are returned for any symbol."""
    with patch("services.events_calendar._fetch_earnings_date", return_value=None):
        resp = await client.get(
            "/symbols/TSLA/events",
            params={"from": "2025-01-01T00:00:00", "to": "2025-12-31T00:00:00"},
        )
    assert resp.status_code == 200
    data = resp.json()
    event_types = {e["event_type"] for e in data}
    assert "fomc" in event_types
    assert "cpi" in event_types


async def test_events_endpoint_includes_earnings_when_available(client, clean_db):
    """Earnings event is returned for the symbol when yfinance provides a date."""
    earnings_date = date(2025, 10, 28)
    with patch(
        "services.events_calendar._fetch_earnings_date", return_value=earnings_date
    ):
        resp = await client.get(
            "/symbols/AAPL/events",
            params={"from": "2025-10-01T00:00:00", "to": "2025-10-31T00:00:00"},
        )
    assert resp.status_code == 200
    data = resp.json()
    earnings = [e for e in data if e["event_type"] == "earnings"]
    assert len(earnings) == 1
    assert earnings[0]["symbol"] == "AAPL"
    assert earnings[0]["event_date"] == "2025-10-28"


async def test_events_endpoint_date_filtering(client, clean_db):
    """Events outside the requested date range are excluded."""
    with patch("services.events_calendar._fetch_earnings_date", return_value=None):
        # Request a very narrow window
        resp = await client.get(
            "/symbols/AAPL/events",
            params={"from": "2025-01-29T00:00:00", "to": "2025-01-29T23:59:59"},
        )
    assert resp.status_code == 200
    data = resp.json()
    for e in data:
        assert e["event_date"] == "2025-01-29"


async def test_events_response_shape(client, clean_db):
    """Each event has the expected fields."""
    with patch("services.events_calendar._fetch_earnings_date", return_value=None):
        resp = await client.get(
            "/symbols/AAPL/events",
            params={"from": "2025-01-01T00:00:00", "to": "2025-06-30T00:00:00"},
        )
    assert resp.status_code == 200
    for event in resp.json():
        assert "id" in event
        assert "event_type" in event
        assert "event_date" in event
        assert "description" in event
        assert event["event_type"] in ("earnings", "fomc", "cpi")
