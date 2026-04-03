from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from database import get_db
from models.price_history import PriceHistory
from services.events_calendar import get_events
import scrapers.yahoo as _yahoo_scraper

router = APIRouter()

@router.get("/{symbol}/history")
async def get_history(
    symbol: str,
    from_dt: datetime = Query(alias="from"),
    to_dt: datetime = Query(alias="to"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == symbol.upper(),
            PriceHistory.timestamp >= from_dt,
            PriceHistory.timestamp <= to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    return result.scalars().all()

@router.get("/{symbol}/latest")
async def get_latest(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.symbol == symbol.upper())
        .order_by(PriceHistory.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/{symbol}/scrape")
async def scrape_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await _yahoo_scraper.fetch_yahoo(symbol.upper())
    if not result.success:
        raise HTTPException(status_code=422, detail=f"Yahoo Finance returned no data: {result.error}")
    row = PriceHistory(
        symbol=symbol.upper(),
        timestamp=datetime.now(timezone.utc),
        open=result.open,
        high=result.high,
        low=result.low,
        close=result.close,
        volume=result.volume,
        yahoo_close=result.close,
        alphavantage_close=None,
        finnhub_close=None,
        outlier_flags={},
        sources_available=["yahoo"],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/{symbol}/events")
async def get_symbol_events(
    symbol: str,
    from_dt: datetime = Query(alias="from"),
    to_dt: datetime = Query(alias="to"),
    db: AsyncSession = Depends(get_db),
):
    """Return earnings, FOMC, and CPI events for a date range.

    Macro events (fomc, cpi) are included regardless of symbol.
    Earnings events are symbol-specific and fetched via yfinance with DB caching.
    """
    events = await get_events(
        symbol=symbol.upper(),
        from_date=from_dt.date(),
        to_date=to_dt.date(),
        db=db,
    )
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "symbol": e.symbol,
            "event_date": e.event_date.isoformat(),
            "description": e.description,
        }
        for e in events
    ]
