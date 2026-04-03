"""Interactive Brokers (IBKR) live broker connector.

Uses ib_insync (async-native IBKR client) for order submission.
Configure via environment variables:
    IBKR_HOST      — TWS/Gateway host (default: 127.0.0.1)
    IBKR_PORT      — TWS paper: 7497, Gateway: 4001 (default: 7497)
    IBKR_CLIENT_ID — Client ID for the connection (default: 1)
    IBKR_ACCOUNT   — Account ID (optional, auto-detected if omitted)

The constructor accepts an optional ``ib`` injection point for testing.
When an IB instance is injected, ib_insync does not need to be installed.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, List, Optional

from executor.base import ExecutorBase
from strategies.base import Signal

logger = logging.getLogger(__name__)

try:
    from ib_insync import IB, LimitOrder, MarketOrder, Stock
    _IB_AVAILABLE = True
except ImportError:
    IB = None  # type: ignore[assignment,misc]
    Stock = None  # type: ignore[assignment,misc]
    MarketOrder = None  # type: ignore[assignment,misc]
    LimitOrder = None  # type: ignore[assignment,misc]
    _IB_AVAILABLE = False

# Fill-polling defaults
_FILL_POLL_INTERVAL: float = 1.0
_FILL_POLL_TIMEOUT: float = 30.0

# Terminal IBKR order statuses
_TERMINAL_STATUSES = frozenset(
    {"Filled", "Cancelled", "ApiCancelled", "Inactive"}
)


def _make_contract(symbol: str) -> Any:
    """Build an ib_insync Stock contract, or a lightweight stub for tests."""
    if _IB_AVAILABLE:
        return Stock(symbol, "SMART", "USD")
    return SimpleNamespace(symbol=symbol, exchange="SMART", currency="USD")


def _make_market_order(side: str, qty: float) -> Any:
    """Build an ib_insync MarketOrder, or a stub for tests."""
    if _IB_AVAILABLE:
        return MarketOrder(side.upper(), round(qty, 6))
    return SimpleNamespace(
        action=side.upper(), totalQuantity=round(qty, 6), orderType="MKT"
    )


def _make_limit_order(side: str, qty: float, limit_price: float) -> Any:
    """Build an ib_insync LimitOrder, or a stub for tests."""
    if _IB_AVAILABLE:
        return LimitOrder(side.upper(), round(qty, 6), round(limit_price, 2))
    return SimpleNamespace(
        action=side.upper(),
        totalQuantity=round(qty, 6),
        orderType="LMT",
        lmtPrice=round(limit_price, 2),
    )


class IBKRConnector(ExecutorBase):
    """Live executor that submits orders to Interactive Brokers via ib_insync.

    Supports:
    - Market and limit orders (US equities via SMART routing)
    - Fill polling with configurable timeout
    - Position queries
    - Account balance retrieval
    - Fill history retrieval
    """

    def __init__(
        self,
        ib=None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_id: Optional[int] = None,
        account: Optional[str] = None,
    ):
        if ib is not None:
            self._ib = ib
        else:
            if not _IB_AVAILABLE:
                raise ImportError(
                    "ib_insync is not installed. Run: pip install 'ib_insync>=0.9.86'"
                )
            self._ib = IB()

        self._host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self._port = port or int(os.getenv("IBKR_PORT", "7497"))
        self._client_id = client_id or int(os.getenv("IBKR_CLIENT_ID", "1"))
        self._account = account or os.getenv("IBKR_ACCOUNT", "")

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to TWS or IB Gateway."""
        await self._ib.connectAsync(
            host=self._host,
            port=self._port,
            clientId=self._client_id,
        )
        logger.info(
            "[IBKR] Connected to %s:%d (clientId=%d)",
            self._host,
            self._port,
            self._client_id,
        )

    async def disconnect(self) -> None:
        """Disconnect from TWS/Gateway."""
        self._ib.disconnect()
        logger.info("[IBKR] Disconnected")

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
        """Submit a market or limit order to IBKR for buy/sell signals.

        Args:
            session: active TradingSession ORM object.
            signal: buy/sell/hold signal from the strategy.
            current_price: current market price used for quantity calculation.
            db: optional async DB session; when provided the trade is persisted.
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

        effective_limit = (
            limit_price if (order_type == "limit" and limit_price) else current_price
        )

        logger.info(
            "[IBKR] Submitting %s %s order: %s x%.4f @ ~$%.4f (session %s)",
            order_type.upper(),
            signal.action.upper(),
            symbol,
            qty,
            current_price,
            session.id,
        )

        trade = await self.submit_order(
            symbol=symbol,
            qty=qty,
            side=signal.action,
            order_type=order_type,
            limit_price=effective_limit if order_type == "limit" else None,
        )

        filled_price = await self._poll_for_fill(trade, fallback_price=current_price)

        if db is not None:
            await self._persist_trade(
                db=db,
                session=session,
                signal=signal,
                entry_price=filled_price if filled_price is not None else current_price,
                qty=qty,
            )

        return {
            "symbol": symbol,
            "side": signal.action,
            "qty": qty,
            "order_type": order_type,
            "filled_avg_price": filled_price,
        }

    async def close_trade(self, trade, current_price: float, db=None):
        """Close the open position for this session's symbol on IBKR."""
        symbol = (
            trade.session.symbol
            if hasattr(trade, "session") and trade.session
            else str(getattr(trade, "symbol", "UNKNOWN"))
        )
        logger.info("[IBKR] Closing position for %s", symbol)
        position = await self.get_position(symbol)
        if position is not None and getattr(position, "position", 0) != 0:
            side = "SELL" if position.position > 0 else "BUY"
            close_trade = await self.submit_order(
                symbol=symbol,
                qty=abs(float(position.position)),
                side=side,
            )
            logger.info("[IBKR] Close order submitted for %s", symbol)
            return close_trade
        return None

    # ------------------------------------------------------------------
    # Lower-level order and account methods
    # ------------------------------------------------------------------

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Any:
        """Place a market or limit order for a US equity.

        Returns the Trade object from ib_insync (or stub in tests).
        """
        contract = _make_contract(symbol)
        if order_type == "limit":
            effective_limit = limit_price if limit_price is not None else 0.0
            order = _make_limit_order(side, qty, effective_limit)
        else:
            order = _make_market_order(side, qty)

        trade = self._ib.placeOrder(contract, order)
        logger.info(
            "[IBKR] Order placed: %s %s x%.4f (type=%s)",
            side.upper(),
            symbol,
            qty,
            order_type,
        )
        return trade

    async def get_position(self, symbol: str) -> Optional[Any]:
        """Return the current open position for a symbol, or None."""
        try:
            positions = self._ib.positions(account=self._account or "")
            for pos in positions:
                if (
                    hasattr(pos, "contract")
                    and pos.contract.symbol == symbol.upper()
                ):
                    return pos
        except Exception as exc:
            logger.debug("[IBKR] No position for %s: %s", symbol, exc)
        return None

    async def get_account_balance(self) -> Optional[float]:
        """Return the net liquidation value (USD) of the IBKR account."""
        try:
            account_values = self._ib.accountValues(account=self._account or "")
            for av in account_values:
                if av.tag == "NetLiquidation" and av.currency == "USD":
                    return float(av.value)
        except Exception as exc:
            logger.error("[IBKR] Failed to fetch account balance: %s", exc)
        return None

    async def get_fills(self, since: Optional[datetime] = None) -> List[Any]:
        """Return execution fills, optionally filtered to those after *since*."""
        try:
            fills = self._ib.fills()
            if since is not None:
                fills = [
                    f
                    for f in fills
                    if hasattr(f, "time") and f.time and f.time >= since
                ]
            return list(fills)
        except Exception as exc:
            logger.error("[IBKR] Failed to fetch fills: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Fill polling
    # ------------------------------------------------------------------

    async def _poll_for_fill(
        self,
        trade: Any,
        fallback_price: float,
        timeout: float = _FILL_POLL_TIMEOUT,
        interval: float = _FILL_POLL_INTERVAL,
    ) -> Optional[float]:
        """Poll the ib_insync Trade object until it reaches a terminal status.

        Returns the average fill price on a fill, or ``None`` if the order
        does not fill within *timeout* seconds.
        """
        if trade is None or not hasattr(trade, "orderStatus"):
            return None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return None

        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                order_status = trade.orderStatus
                status = (
                    order_status.status
                    if hasattr(order_status, "status")
                    else str(order_status)
                )
                if status == "Filled":
                    avg_fill = getattr(order_status, "avgFillPrice", None)
                    price = float(avg_fill) if avg_fill else fallback_price
                    logger.info("[IBKR] Order filled @ $%.4f", price)
                    return price
                if status in _TERMINAL_STATUSES:
                    logger.warning("[IBKR] Order ended with status=%s", status)
                    return None
            except Exception as exc:
                logger.warning("[IBKR] Error polling trade status: %s", exc)
                return None
            await asyncio.sleep(interval)

        logger.warning("[IBKR] Order not filled within %.0fs", timeout)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _persist_trade(
        self,
        db,
        session,
        signal: Signal,
        entry_price: float,
        qty: float,
    ) -> None:
        """Write a PaperTrade row for the IBKR order."""
        from models.paper_trade import PaperTrade  # avoid circular import

        trade = PaperTrade(
            session_id=session.id,
            action=signal.action,
            signal_reason=signal.reason,
            price_at_signal=entry_price,
            quantity=qty,
            timestamp_open=datetime.now(timezone.utc),
            status="open",
        )
        db.add(trade)
        await db.commit()
        logger.info("[IBKR] Trade persisted: session=%s", session.id)
