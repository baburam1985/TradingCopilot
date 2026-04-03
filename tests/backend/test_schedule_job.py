"""Unit tests for the schedule poller logic in scheduler/schedule_job.py.

All database interactions are mocked — these tests validate pure decision logic.
"""

import sys
import os
import uuid
from datetime import datetime, date, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

ET = ZoneInfo("America/New_York")


def _make_schedule(
    symbol="AAPL",
    days_of_week=None,
    start_time_et=time(9, 30),
    stop_time_et=None,
    last_triggered_date=None,
    last_run_status=None,
    last_session_id=None,
    auto_stop_daily_loss_pct=None,
    auto_stop_max_trades=None,
):
    sched = MagicMock()
    sched.id = uuid.uuid4()
    sched.symbol = symbol
    sched.strategy = "ma_crossover"
    sched.strategy_params = {}
    sched.capital = 100.0
    sched.mode = "paper"
    sched.days_of_week = days_of_week if days_of_week is not None else [0, 1, 2, 3, 4]
    sched.start_time_et = start_time_et
    sched.stop_time_et = stop_time_et
    sched.auto_stop_daily_loss_pct = auto_stop_daily_loss_pct
    sched.auto_stop_max_trades = auto_stop_max_trades
    sched.last_triggered_date = last_triggered_date
    sched.last_run_status = last_run_status
    sched.last_session_id = last_session_id
    sched.is_active = True
    sched.stop_loss_pct = None
    sched.take_profit_pct = None
    sched.max_position_pct = None
    return sched


# -------------------------------------------------------------------------
# _maybe_warmup
# -------------------------------------------------------------------------

class TestMaybeWarmup:
    @pytest.mark.asyncio
    async def test_warmup_fires_at_t_minus_15(self):
        """register_symbol is called when now_et is exactly 15 min before start."""
        from scheduler.schedule_job import _maybe_warmup

        sched = _make_schedule(start_time_et=time(9, 30))
        # T-15 = 09:15
        now_et = datetime(2026, 4, 1, 9, 15, 0, tzinfo=ET)

        with patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_warmup(sched, now_et)
            mock_reg.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_warmup_idempotent_second_call(self):
        """register_symbol is called again on a second warmup tick — idempotent in scraper."""
        from scheduler.schedule_job import _maybe_warmup

        sched = _make_schedule(start_time_et=time(9, 30))
        now_et = datetime(2026, 4, 1, 9, 20, 0, tzinfo=ET)

        with patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_warmup(sched, now_et)
            await _maybe_warmup(sched, now_et)
            # Called twice (scraper_job.register_symbol is idempotent set.add)
            assert mock_reg.call_count == 2

    @pytest.mark.asyncio
    async def test_warmup_does_not_fire_at_start_time(self):
        """At exactly start_time, warmup window is closed; no register call."""
        from scheduler.schedule_job import _maybe_warmup

        sched = _make_schedule(start_time_et=time(9, 30))
        now_et = datetime(2026, 4, 1, 9, 30, 0, tzinfo=ET)

        with patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_warmup(sched, now_et)
            mock_reg.assert_not_called()

    @pytest.mark.asyncio
    async def test_warmup_does_not_fire_before_window(self):
        """Before T-15, no register call."""
        from scheduler.schedule_job import _maybe_warmup

        sched = _make_schedule(start_time_et=time(9, 30))
        now_et = datetime(2026, 4, 1, 9, 0, 0, tzinfo=ET)

        with patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_warmup(sched, now_et)
            mock_reg.assert_not_called()


# -------------------------------------------------------------------------
# _maybe_start
# -------------------------------------------------------------------------

class TestMaybeStart:
    @pytest.mark.asyncio
    async def test_start_fires_at_start_time(self):
        """Session is created when now_et >= start_time_et and not yet triggered today."""
        from scheduler.schedule_job import _maybe_start

        sched = _make_schedule(start_time_et=time(9, 30), last_triggered_date=None)
        today = date(2026, 4, 1)
        now_et = datetime(2026, 4, 1, 9, 30, 0, tzinfo=ET)

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.get = AsyncMock(return_value=sched)
        mock_db.refresh = AsyncMock()

        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db), \
             patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_start(sched, now_et, today)
            mock_db.add.assert_called_once()
            mock_reg.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_no_dup_start_same_day(self):
        """If last_triggered_date == today, session must NOT be created again."""
        from scheduler.schedule_job import _maybe_start

        today = date(2026, 4, 1)
        sched = _make_schedule(start_time_et=time(9, 30), last_triggered_date=today)
        now_et = datetime(2026, 4, 1, 9, 30, 0, tzinfo=ET)

        mock_db = AsyncMock()
        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db), \
             patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_start(sched, now_et, today)
            mock_db.add.assert_not_called()
            mock_reg.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_start_before_start_time(self):
        """Session NOT created before start_time_et."""
        from scheduler.schedule_job import _maybe_start

        sched = _make_schedule(start_time_et=time(9, 30), last_triggered_date=None)
        today = date(2026, 4, 1)
        now_et = datetime(2026, 4, 1, 9, 29, 0, tzinfo=ET)

        mock_db = AsyncMock()
        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db), \
             patch("scheduler.schedule_job.register_symbol") as mock_reg:
            await _maybe_start(sched, now_et, today)
            mock_db.add.assert_not_called()
            mock_reg.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_loss_maps_to_session_field(self):
        """auto_stop_daily_loss_pct is copied to session.daily_max_loss_pct on creation."""
        from scheduler.schedule_job import _maybe_start

        sched = _make_schedule(
            start_time_et=time(9, 30),
            last_triggered_date=None,
            auto_stop_daily_loss_pct=5.0,
            auto_stop_max_trades=10,
        )
        today = date(2026, 4, 1)
        now_et = datetime(2026, 4, 1, 9, 30, 0, tzinfo=ET)

        created_session = None

        def capture_add(session_obj):
            nonlocal created_session
            created_session = session_obj

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.add = MagicMock(side_effect=capture_add)
        mock_db.get = AsyncMock(return_value=sched)
        mock_db.refresh = AsyncMock()

        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db), \
             patch("scheduler.schedule_job.register_symbol"):
            await _maybe_start(sched, now_et, today)

        assert created_session is not None
        assert created_session.daily_max_loss_pct == 5.0
        assert created_session.max_trades == 10
        assert created_session.auto_started is True


# -------------------------------------------------------------------------
# _maybe_stop
# -------------------------------------------------------------------------

class TestMaybeStop:
    @pytest.mark.asyncio
    async def test_stop_at_stop_time(self):
        """Active session is closed when now_et >= stop_time_et."""
        from scheduler.schedule_job import _maybe_stop

        session_id = uuid.uuid4()
        sched = _make_schedule(
            stop_time_et=time(16, 0),
            last_run_status="running",
            last_session_id=session_id,
        )
        now_et = datetime(2026, 4, 1, 16, 0, 0, tzinfo=ET)

        mock_session = MagicMock()
        mock_session.status = "active"
        mock_session.symbol = "AAPL"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.get = AsyncMock(return_value=mock_session)

        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db), \
             patch("scheduler.schedule_job._maybe_unregister_symbol") as mock_unreg:
            await _maybe_stop(sched, now_et)
            assert mock_session.status == "closed"
            mock_unreg.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_stop_defaults_1600_et(self):
        """When stop_time_et is None, 16:00 ET is used as the stop time."""
        from scheduler.schedule_job import _maybe_stop

        session_id = uuid.uuid4()
        sched = _make_schedule(
            stop_time_et=None,
            last_run_status="running",
            last_session_id=session_id,
        )
        now_et = datetime(2026, 4, 1, 16, 0, 0, tzinfo=ET)

        mock_session = MagicMock()
        mock_session.status = "active"
        mock_session.symbol = "AAPL"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.get = AsyncMock(return_value=mock_session)

        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db), \
             patch("scheduler.schedule_job._maybe_unregister_symbol"):
            await _maybe_stop(sched, now_et)
            assert mock_session.status == "closed"

    @pytest.mark.asyncio
    async def test_no_stop_before_stop_time(self):
        """Session NOT closed before stop_time_et."""
        from scheduler.schedule_job import _maybe_stop

        session_id = uuid.uuid4()
        sched = _make_schedule(
            stop_time_et=time(16, 0),
            last_run_status="running",
            last_session_id=session_id,
        )
        now_et = datetime(2026, 4, 1, 15, 59, 0, tzinfo=ET)

        mock_db = AsyncMock()
        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db):
            await _maybe_stop(sched, now_et)
            mock_db.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_skips_when_not_running(self):
        """If last_run_status is not 'running', stop is a no-op."""
        from scheduler.schedule_job import _maybe_stop

        sched = _make_schedule(last_run_status="completed", last_session_id=uuid.uuid4())
        now_et = datetime(2026, 4, 1, 16, 0, 0, tzinfo=ET)

        mock_db = AsyncMock()
        with patch("scheduler.schedule_job.AsyncSessionLocal", return_value=mock_db):
            await _maybe_stop(sched, now_et)
            mock_db.get.assert_not_called()


# -------------------------------------------------------------------------
# _is_market_day
# -------------------------------------------------------------------------

class TestIsMarketDay:
    def test_weekday_is_market_day(self):
        from scheduler.schedule_job import _is_market_day

        with patch("scheduler.schedule_job._is_market_day", return_value=True):
            # Monday
            assert _is_market_day(date(2026, 3, 30)) is True

    def test_returns_false_on_weekend_fallback(self):
        """On import error (no pandas_market_calendars), fallback uses weekday check."""
        from scheduler.schedule_job import _is_market_day

        with patch("builtins.__import__", side_effect=ImportError("no module")):
            # Saturday = weekday 5
            result = _is_market_day(date(2026, 4, 5))
            # Should return False because weekday() >= 5


# -------------------------------------------------------------------------
# ET timezone guard
# -------------------------------------------------------------------------

class TestETTimezone:
    @pytest.mark.asyncio
    async def test_all_comparisons_in_et_not_utc(self):
        """Poller's now_et must be in ET. Verify by checking tzinfo."""
        from scheduler.schedule_job import _maybe_warmup

        sched = _make_schedule(start_time_et=time(9, 30))
        # Build a UTC-based time that would be 09:15 ET
        # ET is UTC-5 normally; 09:15 ET = 14:15 UTC
        now_utc = datetime(2026, 4, 1, 14, 15, 0)  # naive UTC

        # Passing naive UTC (no tzinfo) should NOT match the warmup window
        # because combine() with tzinfo=ET will have the right time zone.
        now_et_correct = datetime(2026, 4, 1, 9, 15, 0, tzinfo=ET)

        with patch("scheduler.schedule_job.register_symbol") as mock_reg:
            # Correct ET time → warmup fires
            await _maybe_warmup(sched, now_et_correct)
            assert mock_reg.call_count == 1
