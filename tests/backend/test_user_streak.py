"""Unit tests for streak calculation logic (close_summary/streak.py).

Tests cover:
- First trading day initialises streak to 1.
- Consecutive trading days increment the streak.
- Weekends between two trading days do NOT break the streak (gap == 0 business days).
- A missed trading day (gap >= 1 business day) resets the streak to 1.
- Streak is idempotent when called twice on the same date.
- Milestone badges are awarded at 5, 10, 30, 60.
- Badges are not double-awarded.
- Longest streak is updated correctly.
"""

import sys
import types

# Stub out pandas_market_calendars so the test never touches the network.
# The streak module falls back to Mon-Fri when the package raises an exception.
if "pandas_market_calendars" not in sys.modules:
    stub = types.ModuleType("pandas_market_calendars")
    stub.get_calendar = lambda *a, **kw: (_ for _ in ()).throw(ImportError("stubbed"))
    sys.modules["pandas_market_calendars"] = stub

from datetime import date

import pytest

from close_summary.streak import update_streak, business_days_between, _is_market_day


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update(current=0, longest=0, last_date=None, badges=None, today_iso="2026-04-01"):
    return update_streak(
        current_streak=current,
        longest_streak=longest,
        last_trading_date=last_date,
        milestone_badges=badges,
        today=date.fromisoformat(today_iso),
    )


# ---------------------------------------------------------------------------
# _is_market_day fallback (Mon-Fri only since pandas_market_calendars is stubbed)
# ---------------------------------------------------------------------------

def test_is_market_day_weekday():
    assert _is_market_day(date(2026, 4, 1)) is True   # Wednesday


def test_is_market_day_saturday():
    assert _is_market_day(date(2026, 4, 4)) is False  # Saturday


def test_is_market_day_sunday():
    assert _is_market_day(date(2026, 4, 5)) is False  # Sunday


# ---------------------------------------------------------------------------
# business_days_between
# ---------------------------------------------------------------------------

def test_business_days_same_day_is_zero():
    d = date(2026, 4, 1)
    assert business_days_between(d, d) == 0


def test_business_days_consecutive_trading_days():
    # Mon → Tue: no days strictly in between
    assert business_days_between(date(2026, 3, 30), date(2026, 3, 31)) == 0


def test_business_days_fri_to_mon():
    # Friday → Monday: Sat/Sun in between, both not market days → gap == 0
    assert business_days_between(date(2026, 4, 3), date(2026, 4, 6)) == 0


def test_business_days_one_missed_day():
    # Monday → Wednesday: Tuesday is strictly between, and is a market day → gap == 1
    assert business_days_between(date(2026, 3, 30), date(2026, 4, 1)) == 1


def test_business_days_two_missed_days():
    # Monday → Thursday: Tue and Wed are between → gap == 2
    assert business_days_between(date(2026, 3, 30), date(2026, 4, 2)) == 2


# ---------------------------------------------------------------------------
# update_streak — first day
# ---------------------------------------------------------------------------

def test_first_trading_day_starts_streak_at_one():
    result = _update(today_iso="2026-04-01")
    assert result["current_streak"] == 1
    assert result["longest_streak"] == 1
    assert result["last_trading_date"] == "2026-04-01"


# ---------------------------------------------------------------------------
# update_streak — consecutive days
# ---------------------------------------------------------------------------

def test_consecutive_trading_days_increment():
    result = _update(current=1, longest=1, last_date="2026-03-31", today_iso="2026-04-01")
    assert result["current_streak"] == 2
    assert result["longest_streak"] == 2


def test_friday_to_monday_not_broken():
    """Friday last day, Monday today — weekend must not break the streak."""
    result = _update(current=3, longest=3, last_date="2026-04-03", today_iso="2026-04-06")
    assert result["current_streak"] == 4


# ---------------------------------------------------------------------------
# update_streak — gap resets
# ---------------------------------------------------------------------------

def test_one_missed_business_day_resets_streak():
    """Missed Tuesday: last=Monday, today=Wednesday → gap=1 → reset to 1."""
    result = _update(current=10, longest=10, last_date="2026-03-30", today_iso="2026-04-01")
    assert result["current_streak"] == 1


def test_two_missed_business_days_resets_streak():
    result = _update(current=5, longest=5, last_date="2026-03-30", today_iso="2026-04-02")
    assert result["current_streak"] == 1


# ---------------------------------------------------------------------------
# update_streak — idempotency
# ---------------------------------------------------------------------------

def test_same_day_is_idempotent():
    result = _update(current=7, longest=7, last_date="2026-04-01", today_iso="2026-04-01")
    assert result["current_streak"] == 7
    assert result["new_badges"] == []


# ---------------------------------------------------------------------------
# update_streak — longest streak tracking
# ---------------------------------------------------------------------------

def test_longest_streak_updated():
    result = _update(current=9, longest=9, last_date="2026-04-01", today_iso="2026-04-02")
    assert result["current_streak"] == 10
    assert result["longest_streak"] == 10


def test_longest_streak_preserved_after_reset():
    result = _update(current=1, longest=20, last_date="2026-03-30", today_iso="2026-04-02")
    assert result["current_streak"] == 1
    assert result["longest_streak"] == 20  # unchanged


# ---------------------------------------------------------------------------
# update_streak — milestone badges
# ---------------------------------------------------------------------------

def test_milestone_badge_at_5():
    result = _update(current=4, longest=4, last_date="2026-04-01", today_iso="2026-04-02")
    assert result["current_streak"] == 5
    assert len(result["new_badges"]) == 1
    assert result["new_badges"][0]["badge"] == "5-day streak"
    assert result["new_badges"][0]["streak"] == 5


def test_milestone_badge_at_10():
    result = _update(current=9, longest=9, last_date="2026-04-01", today_iso="2026-04-02")
    assert result["current_streak"] == 10
    assert any(b["streak"] == 10 for b in result["new_badges"])


def test_milestone_badge_at_30():
    result = _update(current=29, longest=29, last_date="2026-04-01", today_iso="2026-04-02")
    assert result["current_streak"] == 30
    assert any(b["streak"] == 30 for b in result["new_badges"])


def test_milestone_badge_at_60():
    result = _update(current=59, longest=59, last_date="2026-04-01", today_iso="2026-04-02")
    assert result["current_streak"] == 60
    assert any(b["streak"] == 60 for b in result["new_badges"])


def test_milestone_badge_not_double_awarded():
    existing_badge = {"badge": "5-day streak", "earned_at": "2026-01-01T00:00:00+00:00", "streak": 5}
    # Simulate streak reaching 5 again (e.g. after a reset)
    result = _update(current=4, longest=5, last_date="2026-04-01",
                     badges=[existing_badge], today_iso="2026-04-02")
    assert result["current_streak"] == 5
    # No NEW badge should be added
    assert result["new_badges"] == []


def test_non_milestone_day_no_badge():
    result = _update(current=6, longest=6, last_date="2026-04-01", today_iso="2026-04-02")
    assert result["current_streak"] == 7
    assert result["new_badges"] == []
