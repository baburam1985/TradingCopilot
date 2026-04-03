"""CRUD router for SessionSchedule — /sessions/schedules"""

import uuid
from datetime import datetime, timezone, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator

from database import get_db
from models.session_schedule import SessionSchedule

router = APIRouter()

_ET_OFFSET = -5  # hours; approximate — poller uses zoneinfo for precise comparison


# ---- Pydantic schemas ----

class CreateScheduleRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict = {}
    capital: float
    mode: str  # "paper" | "alpaca_paper" | "alpaca_live"
    days_of_week: list[int] = [0, 1, 2, 3, 4]  # 0=Mon … 6=Sun
    start_time_et: str  # "HH:MM"
    stop_time_et: Optional[str] = None  # "HH:MM" or null → 16:00 default
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_position_pct: Optional[float] = None
    auto_stop_daily_loss_pct: Optional[float] = None
    auto_stop_max_trades: Optional[int] = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("days_of_week must not be empty")
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("days_of_week values must be 0–6")
        return v

    @field_validator("start_time_et", "stop_time_et", mode="before")
    @classmethod
    def validate_time_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Time must be in HH:MM format")
        return v


class UpdateScheduleRequest(BaseModel):
    is_active: Optional[bool] = None
    stop_time_et: Optional[str] = None
    auto_stop_daily_loss_pct: Optional[float] = None
    auto_stop_max_trades: Optional[int] = None
    # Symbol/strategy/capital changes only take effect from next run.
    # Allow patching them freely (guard is on the running-state restriction above).
    symbol: Optional[str] = None
    strategy: Optional[str] = None
    strategy_params: Optional[dict] = None
    capital: Optional[float] = None
    days_of_week: Optional[list[int]] = None
    start_time_et: Optional[str] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_position_pct: Optional[float] = None


def _parse_time(t: Optional[str]) -> Optional[time]:
    if t is None:
        return None
    return datetime.strptime(t, "%H:%M").time()


def _next_run_at(sched: SessionSchedule) -> Optional[str]:
    """Compute next scheduled run datetime in ET (ISO 8601). Returns None if not determinable."""
    try:
        from datetime import date, timedelta
        from zoneinfo import ZoneInfo

        ET = ZoneInfo("America/New_York")
        now_et = datetime.now(ET)
        today = now_et.date()

        for offset in range(8):  # Check up to 7 days ahead
            candidate = today + timedelta(days=offset)
            if candidate.weekday() not in sched.days_of_week:
                continue
            candidate_dt = datetime.combine(candidate, sched.start_time_et, tzinfo=ET)
            if candidate_dt > now_et:
                return candidate_dt.isoformat()

        return None
    except Exception:
        return None


def _schedule_to_dict(sched: SessionSchedule) -> dict:
    return {
        "id": str(sched.id),
        "symbol": sched.symbol,
        "strategy": sched.strategy,
        "strategy_params": sched.strategy_params,
        "capital": float(sched.capital),
        "mode": sched.mode,
        "days_of_week": sched.days_of_week,
        "start_time_et": sched.start_time_et.strftime("%H:%M") if sched.start_time_et else None,
        "stop_time_et": sched.stop_time_et.strftime("%H:%M") if sched.stop_time_et else None,
        "stop_loss_pct": float(sched.stop_loss_pct) if sched.stop_loss_pct is not None else None,
        "take_profit_pct": float(sched.take_profit_pct) if sched.take_profit_pct is not None else None,
        "max_position_pct": float(sched.max_position_pct) if sched.max_position_pct is not None else None,
        "auto_stop_daily_loss_pct": float(sched.auto_stop_daily_loss_pct) if sched.auto_stop_daily_loss_pct is not None else None,
        "auto_stop_max_trades": sched.auto_stop_max_trades,
        "is_active": sched.is_active,
        "last_triggered_date": sched.last_triggered_date.isoformat() if sched.last_triggered_date else None,
        "last_session_id": str(sched.last_session_id) if sched.last_session_id else None,
        "last_run_status": sched.last_run_status,
        "next_run_at": _next_run_at(sched),
        "created_at": sched.created_at.isoformat(),
        "updated_at": sched.updated_at.isoformat(),
    }


# ---- Endpoints ----

@router.post("", status_code=201)
async def create_schedule(req: CreateScheduleRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    sched = SessionSchedule(
        symbol=req.symbol.upper(),
        strategy=req.strategy,
        strategy_params=req.strategy_params,
        capital=req.capital,
        mode=req.mode,
        days_of_week=req.days_of_week,
        start_time_et=_parse_time(req.start_time_et),
        stop_time_et=_parse_time(req.stop_time_et),
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        max_position_pct=req.max_position_pct,
        auto_stop_daily_loss_pct=req.auto_stop_daily_loss_pct,
        auto_stop_max_trades=req.auto_stop_max_trades,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(sched)
    await db.commit()
    await db.refresh(sched)
    return _schedule_to_dict(sched)


@router.get("")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SessionSchedule).order_by(SessionSchedule.created_at.desc())
    )
    return [_schedule_to_dict(s) for s in result.scalars().all()]


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    sched = await db.get(SessionSchedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _schedule_to_dict(sched)


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: uuid.UUID, req: UpdateScheduleRequest, db: AsyncSession = Depends(get_db)
):
    sched = await db.get(SessionSchedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # While running, only allow safe fields to be patched
    running = sched.last_run_status == "running"
    restricted = {"symbol", "strategy", "strategy_params", "capital", "days_of_week", "start_time_et"}
    if running:
        payload = req.model_dump(exclude_none=True)
        blocked = restricted & set(payload.keys())
        if blocked:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot modify {blocked} while session is running",
            )

    if req.is_active is not None:
        sched.is_active = req.is_active
    if req.stop_time_et is not None:
        sched.stop_time_et = _parse_time(req.stop_time_et)
    if req.auto_stop_daily_loss_pct is not None:
        sched.auto_stop_daily_loss_pct = req.auto_stop_daily_loss_pct
    if req.auto_stop_max_trades is not None:
        sched.auto_stop_max_trades = req.auto_stop_max_trades
    if not running:
        if req.symbol is not None:
            sched.symbol = req.symbol.upper()
        if req.strategy is not None:
            sched.strategy = req.strategy
        if req.strategy_params is not None:
            sched.strategy_params = req.strategy_params
        if req.capital is not None:
            sched.capital = req.capital
        if req.days_of_week is not None:
            sched.days_of_week = req.days_of_week
        if req.start_time_et is not None:
            sched.start_time_et = _parse_time(req.start_time_et)
        if req.stop_loss_pct is not None:
            sched.stop_loss_pct = req.stop_loss_pct
        if req.take_profit_pct is not None:
            sched.take_profit_pct = req.take_profit_pct
        if req.max_position_pct is not None:
            sched.max_position_pct = req.max_position_pct

    sched.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(sched)
    return _schedule_to_dict(sched)


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    sched = await db.get(SessionSchedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(sched)
    await db.commit()
    return {"deleted": True, "id": str(schedule_id)}
