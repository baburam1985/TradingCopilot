import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.watchlist_item import WatchlistItem
from scheduler.scraper_job import register_watchlist_symbol, unregister_watchlist_symbol

router = APIRouter()


class CreateWatchlistItemRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict = {}
    alert_threshold: Optional[float] = None
    notify_email: bool = False
    email_address: Optional[str] = None


class UpdateWatchlistItemRequest(BaseModel):
    strategy: Optional[str] = None
    strategy_params: Optional[dict] = None
    alert_threshold: Optional[float] = None
    notify_email: Optional[bool] = None
    email_address: Optional[str] = None


@router.get("")
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WatchlistItem).order_by(WatchlistItem.created_at.desc())
    )
    return result.scalars().all()


@router.post("")
async def create_watchlist_item(
    req: CreateWatchlistItemRequest, db: AsyncSession = Depends(get_db)
):
    item = WatchlistItem(
        symbol=req.symbol.upper(),
        strategy=req.strategy,
        strategy_params=req.strategy_params,
        alert_threshold=req.alert_threshold,
        notify_email=req.notify_email,
        email_address=req.email_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    register_watchlist_symbol(item.symbol)
    return item


@router.get("/{item_id}")
async def get_watchlist_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@router.patch("/{item_id}")
async def update_watchlist_item(
    item_id: uuid.UUID,
    req: UpdateWatchlistItemRequest,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    if req.strategy is not None:
        item.strategy = req.strategy
    if req.strategy_params is not None:
        item.strategy_params = req.strategy_params
    if req.alert_threshold is not None:
        item.alert_threshold = req.alert_threshold
    if req.notify_email is not None:
        item.notify_email = req.notify_email
    if req.email_address is not None:
        item.email_address = req.email_address
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}")
async def delete_watchlist_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    symbol = item.symbol
    db.delete(item)
    await db.commit()
    unregister_watchlist_symbol(symbol)
    return {"deleted": True, "symbol": symbol}
