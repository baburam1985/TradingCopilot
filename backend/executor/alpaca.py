"""Alpaca Markets live broker connector.

Uses alpaca-py (alpaca.trading) for order submission.
Configure via environment variables:
    ALPACA_API_KEY     — Alpaca API key ID
    ALPACA_API_SECRET  — Alpaca API secret key
    ALPACA_PAPER       — "true" (default) for paper trading sandbox, "false" for live

The constructor accepts an optional ``trading_client`` injection point for testing.
When a client is injected, alpaca-py does not need to be installed.
"""

import logging
import os
from types import SimpleNamespace

from executor.base import ExecutorBase
from strategies.base import Signal

logger = logging.getLogger(__name__)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    _ALPACA_AVAILABLE = True
except ImportError:
    TradingClient = None  # type: ignore[assignment,misc]
    MarketOrderRequest = None  # type: ignore[assignment,misc]
    OrderSide = None  # type: ignore[assignment,misc]
    TimeInForce = None  # type: ignore[assignment,misc]
    _ALPACA_AVAILABLE = False


def _build_order_request(symbol: str, qty: float, side_str: str):
    """Build an Alpaca MarketOrderRequest, or a fallback namespace for testing."""
    if _ALPACA_AVAILABLE:
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL
        return MarketOrderRequest(
            symbol=symbol,
            qty=round(qty, 6),
            side=side,
            time_in_force=TimeInForce.DAY,
        )
    # Fallback: plain namespace accepted by injected mock clients in tests
    return SimpleNamespace(symbol=symbol, qty=round(qty, 6), side=side_str, time_in_force="day")


class AlpacaExecutor(ExecutorBase):
    """Live executor that submits market orders to Alpaca Markets."""

    def __init__(self, trading_client=None):
        if trading_client is not None:
            self._client = trading_client
        else:
            if not _ALPACA_AVAILABLE:
                raise ImportError(
                    "alpaca-py is not installed. Run: pip install alpaca-py"
                )
            api_key = os.environ["ALPACA_API_KEY"]
            secret_key = os.environ["ALPACA_API_SECRET"]
            paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
            self._client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper,
            )

    async def execute(self, session, signal: Signal, current_price: float, db=None):
        """Submit a market order to Alpaca for buy/sell signals; ignore hold."""
        if signal.action == "hold":
            return None

        qty = float(session.starting_capital) / current_price
        order_request = _build_order_request(
            symbol=session.symbol.upper(),
            qty=qty,
            side_str=signal.action,
        )

        logger.info(
            "[ALPACA] Submitting %s order: %s x%.4f @ ~$%.4f (session %s)",
            signal.action.upper(), session.symbol, qty, current_price, session.id,
        )

        order = self._client.submit_order(order_request)

        logger.info(
            "[ALPACA] Order submitted: id=%s status=%s", order.id, order.status
        )

        return {
            "order_id": str(order.id),
            "symbol": session.symbol,
            "side": signal.action,
            "qty": qty,
            "status": str(order.status),
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        }

    async def close_trade(self, trade, current_price: float, db=None):
        """Close the open position for this session's symbol on Alpaca."""
        symbol = (
            trade.session.symbol
            if hasattr(trade, "session") and trade.session
            else str(getattr(trade, "symbol", "UNKNOWN"))
        )
        logger.info("[ALPACA] Closing position for %s", symbol)
        order = self._client.close_position(symbol)
        logger.info("[ALPACA] Close order submitted: id=%s", order.id)
        return order
