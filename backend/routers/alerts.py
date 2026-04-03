import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db
from models.alert_event import AlertEvent

router = APIRouter()


@router.get("")
async def list_alerts(
    session_id: Optional[uuid.UUID] = None,
    limit: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AlertEvent)
    if session_id is not None:
        stmt = stmt.where(AlertEvent.session_id == session_id)
    if unread_only:
        stmt = stmt.where(AlertEvent.read_at.is_(None))
    stmt = stmt.order_by(AlertEvent.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/{event_id}/read")
async def mark_read(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    event = await db.get(AlertEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Alert event not found")
    if event.read_at is None:
        event.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(event)
    return event


@router.post("/mark-all-read")
async def mark_all_read(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    stmt = (
        update(AlertEvent)
        .where(AlertEvent.session_id == session_id, AlertEvent.read_at.is_(None))
        .values(read_at=now)
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}
