"""Unit tests for close summary generation (close_summary/generator.py).

Tests cover:
- _build_pattern_analysis groups trades by signal_reason correctly.
- _build_tomorrow_preview returns top patterns sorted by win_rate.
- _build_tomorrow_preview falls back to a generic entry when no patterns exist.
- generate_close_summaries is a no-op on non-trading days.
- generate_close_summaries skips if summary already exists (idempotent).
- generate_close_summaries creates a CloseSummary and updates UserStreak.
"""

import sys
import types
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Module stubs (mirror pattern from existing test_routers.py)
# ---------------------------------------------------------------------------

for mod_name in ["yfinance", "aiohttp", "finnhub", "apscheduler",
                 "apscheduler.schedulers", "apscheduler.schedulers.asyncio"]:
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        if mod_name == "apscheduler.schedulers.asyncio":
            m.AsyncIOScheduler = MagicMock
        sys.modules[mod_name] = m

if "pandas_market_calendars" not in sys.modules:
    stub = types.ModuleType("pandas_market_calendars")
    stub.get_calendar = lambda *a, **kw: (_ for _ in ()).throw(ImportError("stubbed"))
    sys.modules["pandas_market_calendars"] = stub

import pytest

from close_summary.generator import _build_pattern_analysis, _build_tomorrow_preview, generate_close_summaries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trade(signal_reason="rsi_oversold", pnl=10.0, status="closed"):
    t = MagicMock()
    t.signal_reason = signal_reason
    t.pnl = Decimal(str(pnl)) if pnl is not None else None
    t.status = status
    return t


def _make_session(strategy="rsi"):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.strategy = strategy
    s.starting_capital = Decimal("1000.00")
    return s


# ---------------------------------------------------------------------------
# _build_pattern_analysis
# ---------------------------------------------------------------------------

def test_pattern_analysis_empty_trades():
    result = _build_pattern_analysis([])
    assert result == []


def test_pattern_analysis_open_trades_excluded():
    """Open trades (not yet closed) must not affect the analysis."""
    trades = [_make_trade(pnl=5.0, status="open")]
    result = _build_pattern_analysis(trades)
    assert result == []


def test_pattern_analysis_groups_by_reason():
    trades = [
        _make_trade("rsi_oversold", pnl=5.0, status="closed"),
        _make_trade("rsi_oversold", pnl=-2.0, status="closed"),
        _make_trade("ma_crossover", pnl=3.0, status="closed"),
    ]
    result = _build_pattern_analysis(trades)
    by_pattern = {p["pattern"]: p for p in result}

    assert "rsi_oversold" in by_pattern
    rsi = by_pattern["rsi_oversold"]
    assert rsi["fired"] == 2
    assert rsi["wins"] == 1
    assert rsi["losses"] == 1
    assert rsi["win_rate"] == 0.5

    assert "ma_crossover" in by_pattern
    assert by_pattern["ma_crossover"]["wins"] == 1


def test_pattern_analysis_all_wins():
    trades = [_make_trade("vwap", pnl=10.0, status="closed")] * 4
    result = _build_pattern_analysis(trades)
    assert result[0]["win_rate"] == 1.0


def test_pattern_analysis_all_losses():
    trades = [_make_trade("breakout", pnl=-5.0, status="closed")] * 3
    result = _build_pattern_analysis(trades)
    assert result[0]["win_rate"] == 0.0


# ---------------------------------------------------------------------------
# _build_tomorrow_preview
# ---------------------------------------------------------------------------

def test_tomorrow_preview_top_3_sorted_by_win_rate():
    patterns = [
        {"pattern": "A", "fired": 5, "win_rate": 0.4},
        {"pattern": "B", "fired": 5, "win_rate": 0.9},
        {"pattern": "C", "fired": 5, "win_rate": 0.7},
        {"pattern": "D", "fired": 5, "win_rate": 0.2},
    ]
    session = _make_session("rsi")
    preview = _build_tomorrow_preview(session, patterns)
    assert len(preview) == 3
    assert preview[0]["signal"] == "B"
    assert preview[1]["signal"] == "C"
    assert preview[2]["signal"] == "A"


def test_tomorrow_preview_fallback_when_no_patterns():
    session = _make_session("rsi")
    preview = _build_tomorrow_preview(session, [])
    assert len(preview) == 1
    assert preview[0]["signal"] == "market_open_signal"
    assert preview[0]["strategy"] == "rsi"


def test_tomorrow_preview_fewer_than_3_patterns():
    patterns = [{"pattern": "X", "fired": 2, "win_rate": 0.6}]
    session = _make_session("ma_crossover")
    preview = _build_tomorrow_preview(session, patterns)
    assert len(preview) == 1
    assert preview[0]["signal"] == "X"


# ---------------------------------------------------------------------------
# generate_close_summaries — no-op on non-trading day
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_skips_non_trading_day():
    with patch("close_summary.generator._is_market_day", return_value=False), \
         patch("close_summary.generator.AsyncSessionLocal") as mock_session_cls:
        await generate_close_summaries()
        # DB session should never be opened
        mock_session_cls.assert_not_called()


# ---------------------------------------------------------------------------
# generate_close_summaries — creates summary and updates streak
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_creates_summary_for_active_session():
    session = _make_session("rsi")

    # Trades: 2 closed wins, 1 closed loss
    trades = [
        _make_trade("rsi_oversold", pnl=10.0, status="closed"),
        _make_trade("rsi_oversold", pnl=5.0, status="closed"),
        _make_trade("rsi_overbought", pnl=-3.0, status="closed"),
    ]

    async_ctx = AsyncMock()
    mock_db = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    async_ctx.__aexit__ = AsyncMock(return_value=False)

    # Simulate: no existing summary, active sessions = [session], trades, no streak record
    mock_db.execute = AsyncMock(side_effect=[
        _make_scalars_result([session]),    # active sessions query
        _make_scalars_result(None),         # existing summary check (none)
        _make_scalars_result(trades),       # trades query
        _make_scalars_result(None),         # streak query (no record yet)
    ])

    added_objects = []
    mock_db.add = lambda obj: added_objects.append(obj)
    mock_db.commit = AsyncMock()

    from models.close_summary import CloseSummary
    from models.user_streak import UserStreak

    with patch("close_summary.generator._is_market_day", return_value=True), \
         patch("close_summary.generator.AsyncSessionLocal", return_value=async_ctx):
        await generate_close_summaries()

    # Should have added a CloseSummary and a UserStreak
    types_added = [type(o).__name__ for o in added_objects]
    assert "CloseSummary" in types_added
    assert "UserStreak" in types_added

    close = next(o for o in added_objects if isinstance(o, CloseSummary))
    assert close.session_id == session.id
    assert float(close.total_pnl) == pytest.approx(12.0)
    assert close.trade_count == 3


@pytest.mark.asyncio
async def test_generate_is_idempotent_when_summary_exists():
    """If a summary already exists for today, no new one should be created."""
    session = _make_session("rsi")
    existing_summary = MagicMock()

    async_ctx = AsyncMock()
    mock_db = AsyncMock()
    async_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    async_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_db.execute = AsyncMock(side_effect=[
        _make_scalars_result([session]),       # active sessions query
        _make_scalars_result(existing_summary),  # existing summary found
        _make_scalars_result(None),              # streak query
    ])

    added_objects = []
    mock_db.add = lambda obj: added_objects.append(obj)
    mock_db.commit = AsyncMock()

    from models.close_summary import CloseSummary

    with patch("close_summary.generator._is_market_day", return_value=True), \
         patch("close_summary.generator.AsyncSessionLocal", return_value=async_ctx):
        await generate_close_summaries()

    # No CloseSummary should be added (already exists)
    assert not any(isinstance(o, CloseSummary) for o in added_objects)


# ---------------------------------------------------------------------------
# Helpers for mocking scalars().first() / scalars().all()
# ---------------------------------------------------------------------------

def _make_scalars_result(value):
    """Return a mock that simulates ``await db.execute(...)``.

    If value is None → scalars().first() returns None AND scalars().all() returns [].
    If value is a list → scalars().first() returns first item, scalars().all() returns list.
    Else (single object) → scalars().first() returns value, scalars().all() returns [value].
    """
    mock_result = MagicMock()
    if value is None:
        mock_result.scalars.return_value.first.return_value = None
        mock_result.scalars.return_value.all.return_value = []
    elif isinstance(value, list):
        mock_result.scalars.return_value.first.return_value = value[0] if value else None
        mock_result.scalars.return_value.all.return_value = value
    else:
        mock_result.scalars.return_value.first.return_value = value
        mock_result.scalars.return_value.all.return_value = [value]
    return mock_result
