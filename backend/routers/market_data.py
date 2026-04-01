from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from database import get_db
from models.price_history import PriceHistory

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
