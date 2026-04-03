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

async def _trigger_strategy(symbol: str, current_price: float):
    import logging
    from executor.paper import PaperExecutor
    from strategies.registry import STRATEGY_REGISTRY
    from database import AsyncSessionLocal
    from models.trading_session import TradingSession
    from models.price_history import PriceHistory
    from sqlalchemy import select

    logger = logging.getLogger(__name__)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.symbol == symbol,
                TradingSession.status == "active",
                TradingSession.mode == "paper",
            )
        )
        sessions = result.scalars().all()

    for session in sessions:
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
        if signal.action != "hold":
            executor = PaperExecutor()
            async with AsyncSessionLocal() as db:
                await executor.execute(session, signal, current_price, db)

def start_scheduler():
    scheduler.add_job(_scrape_all, "interval", minutes=1, id="scrape_all")
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()
