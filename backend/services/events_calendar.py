"""EventsCalendar service.

Fetches earnings dates (via yfinance), FOMC meeting dates, and CPI release
dates. All results are cached in the `events_calendar` DB table.

Event types:
  earnings  — company-specific; keyed by symbol
  fomc      — Fed meeting dates; symbol is NULL
  cpi       — CPI release dates; symbol is NULL
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone, timedelta
from typing import List

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.events_calendar import EventsCalendar

# ---------------------------------------------------------------------------
# Known macro event dates (2025-2026)
# Source: Federal Reserve (FOMC) and BLS (CPI)
# ---------------------------------------------------------------------------

_FOMC_DATES: List[str] = [
    "2025-01-29",
    "2025-03-19",
    "2025-05-07",
    "2025-06-18",
    "2025-07-30",
    "2025-09-17",
    "2025-10-29",
    "2025-12-10",
    "2026-01-28",
    "2026-03-18",
    "2026-04-29",
    "2026-06-17",
    "2026-07-29",
    "2026-09-16",
    "2026-10-28",
    "2026-12-09",
]

_CPI_DATES: List[str] = [
    "2025-01-15",
    "2025-02-12",
    "2025-03-12",
    "2025-04-10",
    "2025-05-13",
    "2025-06-11",
    "2025-07-11",
    "2025-08-12",
    "2025-09-11",
    "2025-10-14",
    "2025-11-13",
    "2025-12-10",
    "2026-01-14",
    "2026-02-11",
    "2026-03-11",
    "2026-04-10",
    "2026-05-13",
    "2026-06-10",
    "2026-07-10",
    "2026-08-12",
    "2026-09-11",
    "2026-10-14",
    "2026-11-12",
    "2026-12-10",
]

# Cache TTL: re-fetch earnings if the cached row is older than this
_EARNINGS_CACHE_TTL = timedelta(hours=6)


async def get_events(
    symbol: str,
    from_date: date,
    to_date: date,
    db: AsyncSession,
) -> List[EventsCalendar]:
    """Return all calendar events for *symbol* between *from_date* and *to_date*.

    Macro events (FOMC, CPI) are seeded from static data on first call.
    Earnings dates are fetched from yfinance and cached in DB.
    """
    await _ensure_macro_events(db)
    await _ensure_earnings(symbol, db)

    result = await db.execute(
        select(EventsCalendar).where(
            and_(
                EventsCalendar.event_date >= from_date,
                EventsCalendar.event_date <= to_date,
                or_(
                    EventsCalendar.symbol == symbol.upper(),
                    EventsCalendar.symbol.is_(None),
                ),
            )
        ).order_by(EventsCalendar.event_date.asc())
    )
    return result.scalars().all()


async def _ensure_macro_events(db: AsyncSession) -> None:
    """Seed FOMC and CPI rows if they do not already exist."""
    # Check whether any macro events are present
    result = await db.execute(
        select(EventsCalendar).where(
            EventsCalendar.event_type.in_(["fomc", "cpi"])
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return  # already seeded

    now = datetime.now(timezone.utc)
    rows = []
    for ds in _FOMC_DATES:
        rows.append(EventsCalendar(
            id=uuid.uuid4(),
            event_type="fomc",
            symbol=None,
            event_date=date.fromisoformat(ds),
            description="FOMC Meeting",
            fetched_at=now,
        ))
    for ds in _CPI_DATES:
        rows.append(EventsCalendar(
            id=uuid.uuid4(),
            event_type="cpi",
            symbol=None,
            event_date=date.fromisoformat(ds),
            description="CPI Release",
            fetched_at=now,
        ))
    db.add_all(rows)
    await db.commit()


async def _ensure_earnings(symbol: str, db: AsyncSession) -> None:
    """Fetch and cache the next earnings date for *symbol* from yfinance."""
    sym = symbol.upper()

    # Check if we have a fresh earnings row for this symbol
    result = await db.execute(
        select(EventsCalendar).where(
            and_(
                EventsCalendar.event_type == "earnings",
                EventsCalendar.symbol == sym,
            )
        ).order_by(EventsCalendar.fetched_at.desc()).limit(1)
    )
    existing = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is not None and (now - existing.fetched_at) < _EARNINGS_CACHE_TTL:
        return  # cache still fresh

    earnings_date = _fetch_earnings_date(sym)
    if earnings_date is None:
        return

    row = EventsCalendar(
        id=uuid.uuid4(),
        event_type="earnings",
        symbol=sym,
        event_date=earnings_date,
        description=f"{sym} Earnings",
        fetched_at=now,
    )
    db.add(row)
    await db.commit()


def _fetch_earnings_date(symbol: str) -> date | None:
    """Return the next earnings date for *symbol* via yfinance, or None."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        cal = ticker.calendar
        if cal is None:
            return None
        # calendar may be a dict or DataFrame depending on yfinance version
        if hasattr(cal, "get"):
            # dict-style: {"Earnings Date": [datetime, ...], ...}
            earnings_list = cal.get("Earnings Date", [])
            if earnings_list:
                first = earnings_list[0]
                if hasattr(first, "date"):
                    return first.date()
                return date.fromisoformat(str(first)[:10])
        elif hasattr(cal, "columns"):
            # DataFrame style
            col = "Earnings Date"
            if col in cal.columns and len(cal[col]) > 0:
                val = cal[col].iloc[0]
                if hasattr(val, "date"):
                    return val.date()
        return None
    except Exception:
        return None
