import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scrapers.yahoo import fetch_yahoo
from scrapers.alpha_vantage import fetch_alpha_vantage
from scrapers.finnhub import fetch_finnhub
from scrapers.aggregator import aggregate
from scheduler.market_hours import is_market_open

scheduler = AsyncIOScheduler()
_active_symbols: set[str] = set()

def register_symbol(symbol: str):
    _active_symbols.add(symbol.upper())

def unregister_symbol(symbol: str):
    _active_symbols.discard(symbol.upper())

# Aliases used by the watchlist router (Task 5 will expand these to also
# schedule per-symbol evaluation jobs)
def register_watchlist_symbol(symbol: str):
    _active_symbols.add(symbol.upper())

def unregister_watchlist_symbol(symbol: str):
    _active_symbols.discard(symbol.upper())

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

_ALPACA_MODES = ("alpaca_paper", "alpaca_live")


async def _trigger_strategy(symbol: str, current_price: float):
    import logging
    from datetime import datetime, timezone
    from executor.paper import PaperExecutor
    from executor.alpaca import AlpacaExecutor
    from strategies.registry import STRATEGY_REGISTRY
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
                TradingSession.mode.in_(["paper", "alpaca_paper", "alpaca_live"]),
            )
        )
        sessions = result.scalars().all()

    for session in sessions:
        if session.mode in _ALPACA_MODES:
            executor = AlpacaExecutor(paper=(session.mode == "alpaca_paper"))
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
                    )
                    db.add(trade)
                    await db.commit()
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

def start_scheduler():
    scheduler.add_job(_scrape_all, "interval", minutes=1, id="scrape_all")
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()
