"""Schedule poller — checks active SessionSchedule rows every minute and
auto-starts/stops TradingSession instances at the configured ET times."""

import logging
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from database import AsyncSessionLocal
from models.session_schedule import SessionSchedule
from models.trading_session import TradingSession
from scheduler.scraper_job import register_symbol, unregister_symbol

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
_DEFAULT_STOP = time(16, 0)
_WARMUP_MINUTES = 15


def _is_market_day(check_date: date) -> bool:
    """Return True when check_date is a NYSE trading day (no holiday, Mon-Fri)."""
    try:
        import pandas_market_calendars as mcal  # type: ignore

        nyse = mcal.get_calendar("NYSE")
        schedule = nyse.schedule(
            start_date=check_date.isoformat(),
            end_date=check_date.isoformat(),
        )
        return not schedule.empty
    except Exception:
        # Fallback: Mon-Fri only (ignores holidays)
        return check_date.weekday() < 5


async def _maybe_warmup(sched: SessionSchedule, now_et: datetime) -> None:
    """Register the symbol for scraping 15 min before start_time so price history accumulates."""
    start_dt = datetime.combine(now_et.date(), sched.start_time_et, tzinfo=ET)
    warmup_dt = start_dt - timedelta(minutes=_WARMUP_MINUTES)
    if warmup_dt <= now_et < start_dt:
        register_symbol(sched.symbol)
        logger.info("Schedule %s: warmup — registered symbol %s", sched.id, sched.symbol)


async def _maybe_start(
    sched: SessionSchedule, now_et: datetime, today: date
) -> None:
    """Create a TradingSession when start_time_et is reached (once per day)."""
    if sched.last_triggered_date == today:
        return  # Already started today

    start_dt = datetime.combine(today, sched.start_time_et, tzinfo=ET)
    if now_et < start_dt:
        return  # Not time yet

    async with AsyncSessionLocal() as db:
        session = TradingSession(
            symbol=sched.symbol.upper(),
            strategy=sched.strategy,
            strategy_params=sched.strategy_params,
            starting_capital=sched.capital,
            mode=sched.mode,
            status="active",
            created_at=datetime.now(timezone.utc),
            stop_loss_pct=sched.stop_loss_pct,
            take_profit_pct=sched.take_profit_pct,
            max_position_pct=sched.max_position_pct,
            daily_max_loss_pct=sched.auto_stop_daily_loss_pct,
            notify_email=False,
            schedule_id=sched.id,
            auto_started=True,
            max_trades=sched.auto_stop_max_trades,
        )
        db.add(session)

        # Update schedule state
        sched_row = await db.get(SessionSchedule, sched.id)
        if sched_row:
            sched_row.last_triggered_date = today
            sched_row.last_session_id = session.id
            sched_row.last_run_status = "running"
            sched_row.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(session)

    register_symbol(sched.symbol)
    logger.info(
        "Schedule %s: auto-started session %s for %s at %s",
        sched.id, session.id, sched.symbol, now_et.isoformat(),
    )


async def _maybe_stop(sched: SessionSchedule, now_et: datetime) -> None:
    """Close the active session when stop_time_et is reached."""
    if sched.last_run_status != "running":
        return
    if not sched.last_session_id:
        return

    stop_time = sched.stop_time_et or _DEFAULT_STOP
    stop_dt = datetime.combine(now_et.date(), stop_time, tzinfo=ET)
    if now_et < stop_dt:
        return

    async with AsyncSessionLocal() as db:
        sess = await db.get(TradingSession, sched.last_session_id)
        if sess is None or sess.status != "active":
            # Session already closed by risk manager — just reconcile
            sched_row = await db.get(SessionSchedule, sched.id)
            if sched_row:
                sched_row.last_run_status = "completed"
                sched_row.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return

        sess.status = "closed"
        sess.closed_at = datetime.now(timezone.utc)

        sched_row = await db.get(SessionSchedule, sched.id)
        if sched_row:
            sched_row.last_run_status = "completed"
            sched_row.updated_at = datetime.now(timezone.utc)

        await db.commit()

    await _maybe_unregister_symbol(sched.symbol)
    logger.info(
        "Schedule %s: auto-stopped session %s for %s at %s",
        sched.id, sched.last_session_id, sched.symbol, now_et.isoformat(),
    )


async def _maybe_unregister_symbol(symbol: str) -> None:
    """Unregister symbol from scraper only if no other active sessions reference it."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.symbol == symbol.upper(),
                TradingSession.status == "active",
            )
        )
        active_sessions = result.scalars().all()

    if not active_sessions:
        unregister_symbol(symbol)
        logger.info("Unregistered symbol %s — no active sessions remain", symbol)


async def _schedule_poller() -> None:
    """Main 1-minute job: evaluate all active schedules for warmup/start/stop."""
    now_et = datetime.now(ET)
    today = now_et.date()

    if not _is_market_day(today):
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionSchedule).where(SessionSchedule.is_active == True)  # noqa: E712
        )
        schedules = result.scalars().all()

    for sched in schedules:
        # Check day-of-week filter
        if today.weekday() not in sched.days_of_week:
            continue

        try:
            await _maybe_warmup(sched, now_et)
            await _maybe_start(sched, now_et, today)
            await _maybe_stop(sched, now_et)
        except Exception:
            logger.exception("Error processing schedule %s", sched.id)
