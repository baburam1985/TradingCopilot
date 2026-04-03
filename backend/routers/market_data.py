from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from database import get_db
from models.price_history import PriceHistory
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


@router.get("/{symbol}/sparkline")
async def get_sparkline(symbol: str, db: AsyncSession = Depends(get_db)):
    """Return the last 7 close prices for a symbol (oldest first)."""
    result = await db.execute(
        select(PriceHistory.timestamp, PriceHistory.close)
        .where(PriceHistory.symbol == symbol.upper())
        .order_by(PriceHistory.timestamp.desc())
        .limit(7)
    )
    rows = result.all()
    # Reverse to chronological order
    return [{"timestamp": r.timestamp.isoformat(), "close": float(r.close)} for r in reversed(rows)]


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
