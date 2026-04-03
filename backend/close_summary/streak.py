"""Streak calculation logic for the discipline streak tracker.

Rules:
- A trading day counts toward the streak if at least one active TradingSession
  existed on that calendar date (regardless of outcomes).
- Weekends and NYSE holidays do NOT break the streak — gaps on non-trading days
  are simply skipped when determining whether the streak is continuous.
- A multi-business-day gap (missing one or more weekdays that are market days)
  resets the streak to 1 (current day).
- Milestones: 5, 10, 30, 60 consecutive trading days.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

MILESTONE_THRESHOLDS = (5, 10, 30, 60)

# ---- market-day helpers -------------------------------------------------------


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


def business_days_between(start: date, end: date) -> int:
    """Return number of NYSE trading days strictly between start and end (exclusive on both ends)."""
    if start >= end:
        return 0
    current = start
    count = 0
    from datetime import timedelta
    current = start + timedelta(days=1)
    while current < end:
        if _is_market_day(current):
            count += 1
        from datetime import timedelta
        current = current + timedelta(days=1)
    return count


# ---- milestone helpers --------------------------------------------------------


def _milestone_label(streak: int) -> Optional[str]:
    """Return badge label if streak hits a milestone threshold, else None."""
    if streak in MILESTONE_THRESHOLDS:
        return f"{streak}-day streak"
    return None


# ---- streak update ------------------------------------------------------------


def update_streak(current_streak: int, longest_streak: int,
                  last_trading_date: Optional[str],
                  milestone_badges: Optional[list],
                  today: date) -> dict:
    """Compute new streak state given current state and today's trading date.

    Args:
        current_streak: Existing streak count.
        longest_streak: All-time best streak count.
        last_trading_date: ISO date string of last counted day, or None.
        milestone_badges: Existing list of earned badge dicts.
        today: The trading date to incorporate (must be a market day).

    Returns:
        dict with keys: current_streak, longest_streak, last_trading_date,
        milestone_badges (list), new_badges (list of newly earned badges).
    """
    badges = list(milestone_badges) if milestone_badges else []
    today_str = today.isoformat()

    if last_trading_date is None:
        # First ever trading day
        new_streak = 1
    else:
        last_date = date.fromisoformat(last_trading_date)

        if last_date == today:
            # Already counted today — idempotent, no change
            return {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "last_trading_date": last_trading_date,
                "milestone_badges": badges,
                "new_badges": [],
            }

        gap = business_days_between(last_date, today)
        # gap == 0 → consecutive trading days (no market days in between)
        # gap > 0 → at least one missed trading day → reset
        if gap == 0:
            new_streak = current_streak + 1
        else:
            new_streak = 1

    new_longest = max(longest_streak, new_streak)

    # Check for newly earned milestones
    new_badges: list[dict] = []
    label = _milestone_label(new_streak)
    if label:
        already_earned = any(b.get("streak") == new_streak for b in badges)
        if not already_earned:
            badge = {
                "badge": label,
                "earned_at": datetime.now(timezone.utc).isoformat(),
                "streak": new_streak,
            }
            badges.append(badge)
            new_badges.append(badge)

    return {
        "current_streak": new_streak,
        "longest_streak": new_longest,
        "last_trading_date": today_str,
        "milestone_badges": badges,
        "new_badges": new_badges,
    }
