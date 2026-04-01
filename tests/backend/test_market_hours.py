from datetime import datetime, timezone
import pytest
from backend.scheduler.market_hours import is_market_open

def test_market_open_on_weekday_during_hours():
    # Tuesday 10:00 AM ET = 14:00 UTC
    dt = datetime(2026, 3, 17, 14, 0, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is True

def test_market_closed_before_open():
    # Tuesday 9:00 AM ET = 13:00 UTC
    dt = datetime(2026, 3, 17, 13, 0, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is False

def test_market_closed_after_close():
    # Tuesday 4:30 PM ET = 20:30 UTC
    dt = datetime(2026, 3, 17, 20, 30, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is False

def test_market_closed_on_saturday():
    dt = datetime(2026, 3, 14, 15, 0, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is False
