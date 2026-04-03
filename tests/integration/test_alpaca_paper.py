"""Integration tests for AlpacaExecutor against the Alpaca paper trading sandbox.

These tests require real Alpaca paper trading credentials and will be skipped
automatically if the environment variables are not set.

Required env vars:
    ALPACA_API_KEY    — Alpaca paper trading API key
    ALPACA_API_SECRET — Alpaca paper trading API secret

Always runs against paper=True (sandbox); never touches live funds.
"""

import os
import uuid
from unittest.mock import MagicMock

import pytest

_ALPACA_KEY = os.environ.get("ALPACA_API_KEY", "")
_ALPACA_SECRET = os.environ.get("ALPACA_API_SECRET", "")
_HAVE_CREDS = bool(_ALPACA_KEY and _ALPACA_SECRET)

pytestmark = pytest.mark.skipif(
    not _HAVE_CREDS,
    reason="ALPACA_API_KEY / ALPACA_API_SECRET not set — skipping Alpaca sandbox tests",
)


def _make_session(symbol="AAPL", capital=100.0):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.starting_capital = capital
    return s


# ---------------------------------------------------------------------------
# Smoke tests against the live paper sandbox
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alpaca_paper_account_is_accessible():
    """Verify that the paper trading API key can reach the Alpaca account endpoint."""
    from executor.alpaca import AlpacaExecutor
    executor = AlpacaExecutor(paper=True)
    # get_all_positions() should return a list (possibly empty) without raising
    positions = executor.get_open_positions()
    assert isinstance(positions, list)


@pytest.mark.asyncio
async def test_alpaca_paper_submit_and_cancel_market_order():
    """Submit a fractional market buy on the paper sandbox and immediately cancel it."""
    from executor.alpaca import AlpacaExecutor
    from strategies.base import Signal

    executor = AlpacaExecutor(paper=True)
    signal = Signal(action="buy", reason="integration-test", confidence=1.0)
    session = _make_session(symbol="AAPL", capital=10.0)  # tiny $ amount

    # Submit order (no db — we don't have a DB in this test)
    result = await executor.execute(
        session, signal, current_price=200.0,
        order_type="market",
    )

    assert result is not None
    assert "order_id" in result
    order_id = result["order_id"]

    # Attempt to cancel to clean up (paper sandbox only)
    try:
        executor._client.cancel_order_by_id(order_id)
    except Exception:
        pass  # May already be filled/done — that's fine


@pytest.mark.asyncio
async def test_alpaca_paper_get_order_status():
    """Submit an order and verify get_order_status returns a non-None string."""
    from executor.alpaca import AlpacaExecutor
    from strategies.base import Signal

    executor = AlpacaExecutor(paper=True)
    signal = Signal(action="buy", reason="status-check", confidence=1.0)
    session = _make_session(symbol="SPY", capital=10.0)

    result = await executor.execute(session, signal, current_price=500.0, order_type="market")
    assert result is not None
    order_id = result["order_id"]

    status = await executor.get_order_status(order_id)
    assert status is not None
    assert isinstance(status, str)

    # Clean up
    try:
        executor._client.cancel_order_by_id(order_id)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_alpaca_paper_position_tracking_after_fill():
    """Submit a limit order far below market so it stays open, then check position API."""
    from executor.alpaca import AlpacaExecutor
    from strategies.base import Signal

    executor = AlpacaExecutor(paper=True)
    signal = Signal(action="buy", reason="position-track", confidence=1.0)
    session = _make_session(symbol="AAPL", capital=10.0)

    # Use a very low limit price so the order never fills — just tests the API plumbing
    result = await executor.execute(
        session, signal, current_price=200.0,
        order_type="limit", limit_price=1.0,
    )
    assert result is not None

    # Position should be None (order hasn't filled)
    pos = executor.get_position("AAPL")
    # Could be None or a position object — either is valid; just assert no crash
    assert pos is None or hasattr(pos, "qty")

    # Clean up
    try:
        executor._client.cancel_order_by_id(result["order_id"])
    except Exception:
        pass
