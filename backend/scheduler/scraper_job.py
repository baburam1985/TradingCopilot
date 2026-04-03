import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scrapers.yahoo import fetch_yahoo
from scrapers.alpha_vantage import fetch_alpha_vantage
from scrapers.finnhub import fetch_finnhub
from scrapers.aggregator import aggregate
from scheduler.market_hours import is_market_open
from database import AsyncSessionLocal
from strategies.registry import STRATEGY_REGISTRY
from notifications.broadcaster import notification_broadcaster, build_notification_payload

scheduler = AsyncIOScheduler()
_active_symbols: set[str] = set()

def register_symbol(symbol: str):
    _active_symbols.add(symbol.upper())

def unregister_symbol(symbol: str):
    _active_symbols.discard(symbol.upper())

_watchlist_symbols: set[str] = set()


def register_watchlist_symbol(symbol: str) -> None:
    sym = symbol.upper()
    _watchlist_symbols.add(sym)
    _active_symbols.add(sym)  # ensure price is scraped


def unregister_watchlist_symbol(symbol: str) -> None:
    sym = symbol.upper()
    _watchlist_symbols.discard(sym)
    # Do NOT remove from _active_symbols — sessions manage that set themselves.
    # If no session uses this symbol, it stays in _active_symbols but
    # _trigger_watchlist_signals will find no items and be a no-op.

async def _scrape_all():
    if not is_market_open():
        return
    tasks = [_scrape_symbol(sym) for sym in list(_active_symbols)]
    await asyncio.gather(*tasks)

async def _scrape_symbol(symbol: str):
    from database import AsyncSessionLocal
    from models.price_history import PriceHistory

    results = await asyncio.gather(
        fetch_yahoo(symbol),
        fetch_alpha_vantage(symbol),
        fetch_finnhub(symbol),
    )
    try:
        bar = aggregate(results)
    except ValueError:
        return  # All sources failed — skip this tick

    record = PriceHistory(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        yahoo_close=bar.yahoo_close,
        alphavantage_close=bar.alphavantage_close,
        finnhub_close=bar.finnhub_close,
        outlier_flags=bar.outlier_flags,
        sources_available=bar.sources_available,
    )
    async with AsyncSessionLocal() as db:
        db.add(record)
        await db.commit()

    await _trigger_strategy(symbol, bar.close)

    if symbol in _watchlist_symbols:
        await _trigger_watchlist_signals(symbol, bar.close)

_ALPACA_MODES = ("alpaca_paper", "alpaca_live")
_IBKR_MODES = ("ibkr_live",)


async def _trigger_strategy(symbol: str, current_price: float):
    import logging
    from datetime import datetime, timezone
    from executor.paper import PaperExecutor
    from executor.alpaca import AlpacaExecutor
    from executor.ibkr import IBKRConnector
    from risk.engine import (
        should_stop_loss,
        should_take_profit,
        exceeds_max_position,
        daily_loss_limit_breached,
    )
    from database import AsyncSessionLocal
    from models.trading_session import TradingSession
    from models.paper_trade import PaperTrade
    from models.price_history import PriceHistory
    from sqlalchemy import select, func
    from notifications.alert_engine import AlertEngine

    logger = logging.getLogger(__name__)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.symbol == symbol,
                TradingSession.status == "active",
                TradingSession.mode.in_(["paper", "alpaca_paper", "alpaca_live", "ibkr_live"]),
            )
        )
        sessions = result.scalars().all()

    for session in sessions:
        if session.mode in _ALPACA_MODES:
            executor = AlpacaExecutor(paper=(session.mode == "alpaca_paper"))
        elif session.mode in _IBKR_MODES:
            executor = None  # IBKRConnector created per-trade with connect/disconnect lifecycle
        else:
            executor = PaperExecutor()

        # --- Risk: close any open trades that hit stop-loss or take-profit ---
        async with AsyncSessionLocal() as db:
            open_result = await db.execute(
                select(PaperTrade).where(
                    PaperTrade.session_id == session.id,
                    PaperTrade.status == "open",
                )
            )
            open_trades = open_result.scalars().all()
            for trade in open_trades:
                entry = float(trade.price_at_signal)
                hit_sl = should_stop_loss(entry, current_price, trade.action, session.stop_loss_pct)
                hit_tp = should_take_profit(entry, current_price, trade.action, session.take_profit_pct)
                if hit_sl or hit_tp:
                    reason = "stop-loss" if hit_sl else "take-profit"
                    await executor.close_trade(trade, current_price, db)
                    logger.info(
                        "Session %s: closed trade %s via %s at %.4f",
                        session.id,
                        trade.id,
                        reason,
                        current_price,
                    )
                    event_type = "stop_loss" if hit_sl else "take_profit"
                    await AlertEngine().fire(
                        session=session,
                        event_type=event_type,
                        level="warning",
                        title=f"{reason.replace('-', ' ').title()} Triggered",
                        message=f"{symbol}: trade closed at ${current_price:.2f} ({reason})",
                        db=db,
                    )

        # --- Risk: daily max loss circuit breaker ---
        if session.daily_max_loss_pct is not None:
            async with AsyncSessionLocal() as db:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                daily_result = await db.execute(
                    select(func.coalesce(func.sum(PaperTrade.pnl), 0)).where(
                        PaperTrade.session_id == session.id,
                        PaperTrade.status == "closed",
                        PaperTrade.timestamp_close >= today_start,
                    )
                )
                daily_pnl = float(daily_result.scalar())

            if daily_loss_limit_breached(daily_pnl, float(session.starting_capital), session.daily_max_loss_pct):
                async with AsyncSessionLocal() as db:
                    sess = await db.get(TradingSession, session.id)
                    if sess and sess.status == "active":
                        sess.status = "closed"
                        sess.closed_at = datetime.now(timezone.utc)
                        await db.commit()
                unregister_symbol(symbol)
                logger.warning(
                    "Session %s: daily max loss circuit breaker triggered (%.2f P&L, limit %.1f%%)",
                    session.id,
                    daily_pnl,
                    session.daily_max_loss_pct,
                )
                async with AsyncSessionLocal() as db:
                    await AlertEngine().fire(
                        session=session,
                        event_type="daily_loss_limit",
                        level="danger",
                        title="Daily Loss Limit Hit",
                        message=f"{symbol}: session closed — daily loss limit reached (P&L: ${daily_pnl:.2f})",
                        db=db,
                    )
                continue

        # --- Strategy signal ---
        strategy_cls = STRATEGY_REGISTRY.get(session.strategy)
        if strategy_cls is None:
            logger.warning(
                "Unknown strategy '%s' for session %s — skipping",
                session.strategy,
                session.id,
            )
            continue

        strategy = strategy_cls(**session.strategy_params)

        async with AsyncSessionLocal() as db:
            ph_result = await db.execute(
                select(PriceHistory)
                .where(PriceHistory.symbol == symbol)
                .order_by(PriceHistory.timestamp.desc())
                .limit(500)
            )
            bars = ph_result.scalars().all()

        closes = [float(b.close) for b in reversed(bars)]
        signal = strategy.analyze(closes)
        if signal.action == "hold":
            continue

        # --- Risk: max position size check ---
        capital = float(session.starting_capital)
        quantity = capital / current_price
        if exceeds_max_position(quantity, current_price, capital, session.max_position_pct):
            logger.info(
                "Session %s: skipping %s — exceeds max position size (%.1f%%)",
                session.id,
                signal.action,
                session.max_position_pct,
            )
            continue

        opposing = "buy" if signal.action == "sell" else "sell"
        async with AsyncSessionLocal() as db:
            open_result = await db.execute(
                select(PaperTrade).where(
                    PaperTrade.session_id == session.id,
                    PaperTrade.status == "open",
                    PaperTrade.action == opposing,
                )
            )
            for open_trade in open_result.scalars().all():
                if executor is not None:
                    await executor.close_trade(open_trade, current_price, db)

            if session.mode in _ALPACA_MODES:
                order_result = await executor.execute(session, signal, current_price, db)
                if order_result:
                    trade = PaperTrade(
                        session_id=session.id,
                        action=signal.action,
                        signal_reason=signal.reason,
                        price_at_signal=current_price,
                        quantity=order_result["qty"],
                        timestamp_open=datetime.now(timezone.utc),
                        status="open",
                        alpaca_order_id=order_result["order_id"],
                        reasoning=signal.reasoning,
                    )
                    db.add(trade)
                    await db.commit()
            elif session.mode in _IBKR_MODES:
                # IBKRConnector self-persists trade via _persist_trade(); requires
                # explicit connect/disconnect lifecycle around each execution.
                connector = IBKRConnector()
                try:
                    await connector.connect()
                    await connector.execute(session, signal, current_price, db)
                except Exception as exc:
                    logger.warning(
                        "Session %s: IBKR execution error: %s", session.id, exc
                    )
                finally:
                    await connector.disconnect()
            else:
                await executor.execute(session, signal, current_price, db)
        logger.info(
            "Session %s: %s at %.4f (%s)",
            session.id,
            signal.action,
            current_price,
            signal.reason,
        )
        async with AsyncSessionLocal() as db:
            await AlertEngine().fire(
                session=session,
                event_type="trade_executed",
                level="info",
                title=f"{'Buy' if signal.action == 'buy' else 'Sell'} Signal",
                message=f"{symbol}: {signal.action} at ${current_price:.2f} — {signal.reason}",
                db=db,
            )

async def _trigger_watchlist_signals(symbol: str, current_price: float):
    import logging
    from models.watchlist_item import WatchlistItem
    from models.price_history import PriceHistory
    from sqlalchemy import select
    from notifications.email import send_trade_email

    logger = logging.getLogger(__name__)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WatchlistItem).where(WatchlistItem.symbol == symbol)
        )
        items = result.scalars().all()

    for item in items:
        strategy_cls = STRATEGY_REGISTRY.get(item.strategy)
        if strategy_cls is None:
            logger.warning("Watchlist item %s: unknown strategy '%s'", item.id, item.strategy)
            continue

        strategy = strategy_cls(**(item.strategy_params or {}))

        async with AsyncSessionLocal() as db:
            ph_result = await db.execute(
                select(PriceHistory)
                .where(PriceHistory.symbol == symbol)
                .order_by(PriceHistory.timestamp.desc())
                .limit(500)
            )
            bars = ph_result.scalars().all()

        closes = [float(b.close) for b in reversed(bars)]
        signal = strategy.analyze(closes)

        # Detect price-threshold crossing
        threshold_crossed = False
        if item.alert_threshold is not None and item.last_price is not None:
            prev = float(item.last_price)
            threshold = float(item.alert_threshold)
            if (prev < threshold <= current_price) or (prev > threshold >= current_price):
                threshold_crossed = True

        # Persist updated state
        async with AsyncSessionLocal() as db:
            db_item = await db.get(WatchlistItem, item.id)
            if db_item:
                db_item.last_signal = signal.action
                db_item.last_price = current_price
                db_item.last_evaluated_at = datetime.now(timezone.utc)
                await db.commit()

        # Broadcast signal alert on buy or sell
        if signal.action in ("buy", "sell"):
            level = "info"
            title = f"Watchlist Signal: {symbol}"
            message = (
                f"{item.strategy} generated a {signal.action.upper()} signal "
                f"at ${current_price:.2f} — {signal.reason}"
            )
            payload = build_notification_payload(level=level, title=title, message=message)
            payload["watchlist_item_id"] = str(item.id)
            await notification_broadcaster.broadcast_watchlist(payload)
            if item.notify_email and item.email_address:
                try:
                    send_trade_email(
                        item.email_address,
                        f"TradingCopilot: {title}",
                        message,
                    )
                except Exception as exc:
                    logger.warning("Watchlist email delivery failed: %s", exc)

        # Broadcast price-threshold alert
        if threshold_crossed:
            level = "warning"
            title = f"Watchlist Alert: {symbol}"
            message = (
                f"{symbol} crossed alert threshold ${item.alert_threshold:.2f} "
                f"(current: ${current_price:.2f})"
            )
            payload = build_notification_payload(level=level, title=title, message=message)
            payload["watchlist_item_id"] = str(item.id)
            await notification_broadcaster.broadcast_watchlist(payload)
            if item.notify_email and item.email_address and signal.action not in ("buy", "sell"):
                try:
                    send_trade_email(
                        item.email_address,
                        f"TradingCopilot: {title}",
                        message,
                    )
                except Exception as exc:
                    logger.warning("Watchlist threshold email delivery failed: %s", exc)


def start_scheduler():
    from scheduler.schedule_job import _schedule_poller
    scheduler.add_job(_scrape_all, "interval", minutes=1, id="scrape_all")
    scheduler.add_job(_schedule_poller, "interval", minutes=1, id="schedule_poller")
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()
