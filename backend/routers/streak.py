"""Streak router — exposes current trading discipline streak for the user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user_streak import UserStreak

router = APIRouter()


@router.get("/{user_id}/streak")
async def get_user_streak(user_id: str, db: AsyncSession = Depends(get_db)):
    """Return the current streak and milestone history.

    In this single-user app, ``user_id`` is accepted for API compatibility but
    is not used as a filter — the singleton UserStreak record is always returned.
    """
    result = await db.execute(select(UserStreak).limit(1))
    streak = result.scalars().first()

    if not streak:
        # No trading days recorded yet
        raise HTTPException(status_code=404, detail="No streak data found. Start a trading session to begin your streak.")

    return {
        "user_id": user_id,
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "last_trading_date": streak.last_trading_date,
        "milestone_badges": streak.milestone_badges or [],
        "updated_at": streak.updated_at.isoformat(),
    }
