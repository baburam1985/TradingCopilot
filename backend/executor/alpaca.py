"""Alpaca Markets live broker connector.

Uses alpaca-py (alpaca.trading) for order submission.
Configure via environment variables:
    ALPACA_API_KEY     — Alpaca API key ID
    ALPACA_API_SECRET  — Alpaca API secret key
    ALPACA_PAPER       — "true" (default) for paper trading sandbox, "false" for live

The constructor accepts an optional ``trading_client`` injection point for testing.
When a client is injected, alpaca-py does not need to be installed.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable, List, Optional

from executor.base import ExecutorBase
from strategies.base import Signal

logger = logging.getLogger(__name__)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.stream import TradingStream
    _ALPACA_AVAILABLE = True
except ImportError:
    TradingClient = None  # type: ignore[assignment,misc]
    MarketOrderRequest = None  # type: ignore[assignment,misc]
    LimitOrderRequest = None  # type: ignore[assignment,misc]
    OrderSide = None  # type: ignore[assignment,misc]
    TimeInForce = None  # type: ignore[assignment,misc]
    TradingStream = None  # type: ignore[assignment,misc]
    _ALPACA_AVAILABLE = False

# Fill-polling defaults
_FILL_POLL_INTERVAL: float = 1.0   # seconds between polls
_FILL_POLL_TIMEOUT: float = 30.0   # give up after this many seconds

# Terminal order statuses — no point polling further
_TERMINAL_STATUSES = frozenset(
    {"filled", "canceled", "expired", "rejected", "done_for_day"}
)


def _build_market_order(symbol: str, qty: float, side_str: str) -> Any:
    """Build an Alpaca MarketOrderRequest, or a fallback namespace for tests."""
    if _ALPACA_AVAILABLE:
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL
        return MarketOrderRequest(
            symbol=symbol,
            qty=round(qty, 6),
            side=side,
            time_in_force=TimeInForce.DAY,
        )
    return SimpleNamespace(
        symbol=symbol, qty=round(qty, 6), side=side_str,
        time_in_force="day", type="market",
    )


def _build_limit_order(symbol: str, qty: float, side_str: str, limit_price: float) -> Any:
    """Build an Alpaca LimitOrderRequest, or a fallback namespace for tests."""
    if _ALPACA_AVAILABLE:
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL
        return LimitOrderRequest(
            symbol=symbol,
            qty=round(qty, 6),
            side=side,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
        )
    return SimpleNamespace(
        symbol=symbol, qty=round(qty, 6), side=side_str,
        time_in_force="day", type="limit", limit_price=round(limit_price, 2),
    )


class AlpacaExecutor(ExecutorBase):
    """Live executor that submits orders to Alpaca Markets.

    Supports:
    - Market and limit orders
    - Fill polling with configurable timeout
    - Order status queries
    - Position tracking (all open positions or by symbol)
    - Optional WebSocket TradingStream for real-time order/fill events
    - Alpaca order-id persistence to the paper_trades table for reconciliation
    """

    def __init__(
        self,
        trading_client=None,
        stream_client=None,
        paper: Optional[bool] = None,
    ):
        if trading_client is not None:
            self._client = trading_client
        else:
            if not _ALPACA_AVAILABLE:
                raise ImportError(
                    "alpaca-py is not installed. Run: pip install alpaca-py"
                )
            api_key = os.environ["ALPACA_API_KEY"]
            secret_key = os.environ["ALPACA_API_SECRET"]
            if paper is None:
                paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
            self._client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=paper,
            )
        # Optional TradingStream; can be injected for tests or lazy-created in start_stream()
        self._stream = stream_client

    # ------------------------------------------------------------------
    # ExecutorBase interface
    # ------------------------------------------------------------------

    async def execute(
        self,
        session,
        signal: Signal,
        current_price: float,
        db=None,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ):
        """Submit a market or limit order to Alpaca for buy/sell signals.

        Args:
            session: active TradingSession ORM object.
            signal: buy/sell/hold signal from the strategy.
            current_price: current market price used for quantity calculation.
            db: optional async DB session; when provided the order is persisted.
            order_type: ``"market"`` (default) or ``"limit"``.
            limit_price: price cap for limit orders; falls back to
                *current_price* if not supplied.

        Returns:
            dict with order details, or ``None`` for hold signals.
        """
        if signal.action == "hold":
            return None

        qty = float(session.starting_capital) / current_price
        symbol = session.symbol.upper()

        if order_type == "limit":
            effective_limit = limit_price if limit_price is not None else current_price
            order_request = _build_limit_order(symbol, qty, signal.action, effective_limit)
        else:
            order_request = _build_market_order(symbol, qty, signal.action)

        logger.info(
            "[ALPACA] Submitting %s %s order: %s x%.4f @ ~$%.4f (session %s)",
            order_type.upper(), signal.action.upper(), symbol, qty, current_price, session.id,
        )

        order = self._client.submit_order(order_request)
        order_id = str(order.id)

        logger.info("[ALPACA] Order submitted: id=%s status=%s", order_id, order.status)

        # Poll REST until filled (or timeout) to capture actual fill price
        filled_price = await self._poll_for_fill(order_id, fallback_price=current_price)

        if db is not None:
            await self._persist_trade(
                db=db,
                session=session,
                signal=signal,
                order_id=order_id,
                entry_price=filled_price if filled_price is not None else current_price,
                qty=qty,
            )

        return {
            "order_id": order_id,
            "symbol": symbol,
            "side": signal.action,
            "qty": qty,
            "order_type": order_type,
            "status": str(order.status),
            "filled_avg_price": filled_price,
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

    # ------------------------------------------------------------------
    # Fill polling & order status
    # ------------------------------------------------------------------

    async def _poll_for_fill(
        self,
        order_id: str,
        fallback_price: float,
        timeout: float = _FILL_POLL_TIMEOUT,
        interval: float = _FILL_POLL_INTERVAL,
    ) -> Optional[float]:
        """Poll the Alpaca REST API until the order reaches a terminal status.

        Returns the ``filled_avg_price`` on a fill, or ``None`` if the order
        does not fill within *timeout* seconds (e.g. an open limit order).
        """
        if not hasattr(self._client, "get_order_by_id"):
            # Injected test mock without polling support — skip gracefully
            return None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return None

        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                order = self._client.get_order_by_id(order_id)
                status = str(order.status) if order.status else ""
                if status == "filled":
                    price = (
                        float(order.filled_avg_price)
                        if order.filled_avg_price
                        else fallback_price
                    )
                    logger.info("[ALPACA] Order %s filled @ $%.4f", order_id, price)
                    return price
                if status in _TERMINAL_STATUSES:
                    logger.warning(
                        "[ALPACA] Order %s ended with non-fill status=%s", order_id, status
                    )
                    return None
            except Exception as exc:
                logger.warning("[ALPACA] Error polling order %s: %s", order_id, exc)
                return None
            await asyncio.sleep(interval)

        logger.warning("[ALPACA] Order %s not filled within %.0fs", order_id, timeout)
        return None

    async def get_order_status(self, order_id: str) -> Optional[str]:
        """Return the current status string of an Alpaca order, or ``None``."""
        try:
            order = self._client.get_order_by_id(order_id)
            return str(order.status)
        except Exception as exc:
            logger.error("[ALPACA] Could not fetch order %s: %s", order_id, exc)
            return None

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------

    def get_open_positions(self) -> List[Any]:
        """Return all open positions from Alpaca (empty list on error)."""
        try:
            return self._client.get_all_positions()
        except Exception as exc:
            logger.error("[ALPACA] Failed to fetch positions: %s", exc)
            return []

    def get_position(self, symbol: str) -> Optional[Any]:
        """Return the open position for a single symbol, or ``None``."""
        try:
            return self._client.get_open_position(symbol.upper())
        except Exception as exc:
            logger.debug("[ALPACA] No open position for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # WebSocket TradingStream
    # ------------------------------------------------------------------

    async def start_stream(
        self, on_order_update: Optional[Callable] = None
    ) -> None:
        """Subscribe to real-time order/fill events via the Alpaca TradingStream.

        *on_order_update* is an async callable invoked with each trade-update
        payload.  Run this in a background task and cancel it (or call
        ``stop_stream()``) when the session ends.
        """
        if self._stream is None:
            if not _ALPACA_AVAILABLE or TradingStream is None:
                logger.warning(
                    "[ALPACA] TradingStream unavailable — skipping real-time stream"
                )
                return
            api_key = os.environ.get("ALPACA_API_KEY", "")
            secret_key = os.environ.get("ALPACA_API_SECRET", "")
            paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
            self._stream = TradingStream(api_key, secret_key, paper=paper)

        async def _handler(data: Any) -> None:
            logger.info("[ALPACA STREAM] Order update: %s", data)
            if on_order_update is not None:
                await on_order_update(data)

        self._stream.subscribe_trade_updates(_handler)
        logger.info("[ALPACA] Starting trading stream…")
        await self._stream._run_forever()  # blocks until stopped

    async def stop_stream(self) -> None:
        """Disconnect the TradingStream if one is running."""
        if self._stream is not None:
            try:
                await self._stream.stop_ws()
                logger.info("[ALPACA] Trading stream stopped")
            except Exception as exc:
                logger.warning("[ALPACA] Error stopping stream: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _persist_trade(
        self,
        db,
        session,
        signal: Signal,
        order_id: str,
        entry_price: float,
        qty: float,
    ) -> None:
        """Write a PaperTrade row tagged with the live Alpaca order id."""
        from models.paper_trade import PaperTrade  # avoid circular import at module level

        trade = PaperTrade(
            session_id=session.id,
            action=signal.action,
            signal_reason=signal.reason,
            price_at_signal=entry_price,
            quantity=qty,
            timestamp_open=datetime.now(timezone.utc),
            status="open",
            alpaca_order_id=order_id,
        )
        db.add(trade)
        await db.commit()
        logger.info(
            "[ALPACA] Trade persisted: order_id=%s session=%s", order_id, session.id
        )
