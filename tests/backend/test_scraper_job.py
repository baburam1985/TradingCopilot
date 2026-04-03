"""Additional tests for scheduler/scraper_job.py covering:
  - register_symbol / unregister_symbol
  - _scrape_all (market-hours gate, parallel dispatch)
  - _scrape_symbol (aggregate → save → trigger)
  - _trigger_strategy edge paths: stop-loss/take-profit close, daily max loss
    circuit breaker, max position size exceeded
  - start_scheduler / stop_scheduler
"""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scheduler.scraper_job import (
    _scrape_all,
    _scrape_symbol,
    _trigger_strategy,
    register_symbol,
    unregister_symbol,
)
from backend.strategies.base import Signal


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_scheduler_execution for self-containment)
# ---------------------------------------------------------------------------

def _make_session(strategy="rsi", daily_max_loss_pct=None, stop_loss_pct=None,
                  take_profit_pct=None, max_position_pct=None, starting_capital=1000.0):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = "AAPL"
    s.strategy = strategy
    s.strategy_params = {"period": 14, "oversold": 30, "overbought": 70}
    s.starting_capital = starting_capital
    s.mode = "paper"
    s.status = "active"
    s.stop_loss_pct = stop_loss_pct
    s.take_profit_pct = take_profit_pct
    s.max_position_pct = max_position_pct
    s.daily_max_loss_pct = daily_max_loss_pct
    return s


def _make_open_trade(action="buy", price_at_signal=140.0):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.action = action
    t.status = "open"
    t.price_at_signal = price_at_signal
    t.quantity = 6.0
    return t


def _db_result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _db_scalar(value):
    r = MagicMock()
    r.scalar.return_value = value
    return r


def _db_ctx(execute_results):
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_results)

    @asynccontextmanager
    async def _ctx():
        yield db

    return _ctx


def _alert_ctx():
    db = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield db

    return _ctx


def _chained(*db_ctx_factories):
    call_count = [0]

    def _factory(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return db_ctx_factories[idx]()

    return _factory


# ---------------------------------------------------------------------------
# register_symbol / unregister_symbol
# ---------------------------------------------------------------------------

def test_register_symbol_adds_uppercase():
    from backend.scheduler.scraper_job import _active_symbols
    _active_symbols.discard("AAPL")
    register_symbol("aapl")
    assert "AAPL" in _active_symbols
    _active_symbols.discard("AAPL")


def test_unregister_symbol_removes_uppercase():
    from backend.scheduler.scraper_job import _active_symbols
    _active_symbols.add("TSLA")
    unregister_symbol("tsla")
    assert "TSLA" not in _active_symbols


def test_unregister_symbol_noop_when_not_present():
    """Calling unregister on a symbol not in the set must not raise."""
    unregister_symbol("NOTEXIST")  # Should not raise


# ---------------------------------------------------------------------------
# _scrape_all
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_all_skips_when_market_closed():
    with patch("backend.scheduler.scraper_job.is_market_open", return_value=False), \
         patch("backend.scheduler.scraper_job._scrape_symbol", new=AsyncMock()) as mock_scrape:
        await _scrape_all()
    mock_scrape.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_all_dispatches_active_symbols():
    from backend.scheduler import scraper_job as job

    original = set(job._active_symbols)
    job._active_symbols.clear()
    job._active_symbols.update(["AAPL", "TSLA"])

    try:
        with patch("backend.scheduler.scraper_job.is_market_open", return_value=True), \
             patch("backend.scheduler.scraper_job._scrape_symbol", new=AsyncMock()) as mock_scrape:
            await _scrape_all()

        assert mock_scrape.call_count == 2
    finally:
        job._active_symbols.clear()
        job._active_symbols.update(original)


# ---------------------------------------------------------------------------
# _scrape_symbol
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_symbol_skips_when_all_sources_fail():
    """When aggregate raises ValueError, _scrape_symbol returns without saving or triggering."""
    from backend.scrapers.base import FetchResult
    fail = FetchResult(source="x", open=0, high=0, low=0, close=0, volume=0, success=False)

    with patch("backend.scheduler.scraper_job.fetch_yahoo", AsyncMock(return_value=fail)), \
         patch("backend.scheduler.scraper_job.fetch_alpha_vantage", AsyncMock(return_value=fail)), \
         patch("backend.scheduler.scraper_job.fetch_finnhub", AsyncMock(return_value=fail)), \
         patch("backend.scheduler.scraper_job.aggregate", side_effect=ValueError("all failed")), \
         patch("backend.scheduler.scraper_job._trigger_strategy", new=AsyncMock()) as mock_trigger:
        await _scrape_symbol("AAPL")

    mock_trigger.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_symbol_saves_record_and_triggers_strategy():
    """When aggregate succeeds, the bar is saved and _trigger_strategy is called."""
    from backend.scrapers.base import FetchResult
    from backend.scrapers.base import ConsensusBar

    good = FetchResult(source="yahoo", open=100.0, high=105.0, low=99.0, close=102.0,
                       volume=500000, success=True)
    bar = ConsensusBar(
        open=100.0, high=105.0, low=99.0, close=102.0, volume=500000,
        yahoo_close=102.0, alphavantage_close=None, finnhub_close=None,
        outlier_flags={}, sources_available=["yahoo"]
    )

    mock_db = AsyncMock()

    @asynccontextmanager
    async def _db_ctx_save():
        yield mock_db

    with patch("backend.scheduler.scraper_job.fetch_yahoo", AsyncMock(return_value=good)), \
         patch("backend.scheduler.scraper_job.fetch_alpha_vantage", AsyncMock(return_value=good)), \
         patch("backend.scheduler.scraper_job.fetch_finnhub", AsyncMock(return_value=good)), \
         patch("backend.scheduler.scraper_job.aggregate", return_value=bar), \
         patch("database.AsyncSessionLocal", _db_ctx_save), \
         patch("backend.scheduler.scraper_job._trigger_strategy", new=AsyncMock()) as mock_trigger:
        await _scrape_symbol("AAPL")

    mock_trigger.assert_called_once_with("AAPL", 102.0)


# ---------------------------------------------------------------------------
# _trigger_strategy — stop-loss / take-profit close path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_loss_triggers_close_trade():
    """An open trade that hits stop-loss must be closed via executor."""
    session = _make_session(stop_loss_pct=5.0, take_profit_pct=None)
    open_trade = _make_open_trade(action="buy", price_at_signal=150.0)
    current_price = 140.0  # 6.7% drop → stop-loss hit

    # DB contexts: sessions, risk-check (returns the open trade)
    sessions_db = _db_ctx([_db_result([session])])
    risk_db_inner = AsyncMock()
    risk_db_inner.execute = AsyncMock(return_value=_db_result([open_trade]))

    @asynccontextmanager
    async def risk_ctx():
        yield risk_db_inner

    # alert ctx for the SL alert (inside risk check block) — uses the same db
    # The SL alert fires inside the same `async with` as the risk check:
    # no extra DB context needed for alert here since AlertEngine is mocked.
    # After risk check, strategy runs: hold signal → no exec or trade alert.
    hold_signal = Signal(action="hold", reason="neutral", confidence=0.5)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = hold_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)
    history_db = _db_ctx([_db_result([MagicMock(close=140.0)] * 20)])

    factory = _chained(sessions_db, risk_ctx, history_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    mock_alert_engine = AsyncMock()
    mock_alert_cls = MagicMock(return_value=mock_alert_engine)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls), \
         patch("notifications.alert_engine.AlertEngine", mock_alert_cls), \
         patch("risk.engine.should_stop_loss", return_value=True), \
         patch("risk.engine.should_take_profit", return_value=False):
        await _trigger_strategy("AAPL", current_price)

    mock_executor.close_trade.assert_called_once_with(open_trade, current_price, risk_db_inner)
    mock_alert_engine.fire.assert_called()


@pytest.mark.asyncio
async def test_take_profit_triggers_close_trade():
    """An open trade that hits take-profit must be closed via executor."""
    session = _make_session(stop_loss_pct=None, take_profit_pct=10.0)
    open_trade = _make_open_trade(action="buy", price_at_signal=140.0)
    current_price = 160.0  # 14% gain → take-profit hit

    sessions_db = _db_ctx([_db_result([session])])
    risk_db_inner = AsyncMock()
    risk_db_inner.execute = AsyncMock(return_value=_db_result([open_trade]))

    @asynccontextmanager
    async def risk_ctx():
        yield risk_db_inner

    hold_signal = Signal(action="hold", reason="neutral", confidence=0.5)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = hold_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)
    history_db = _db_ctx([_db_result([MagicMock(close=160.0)] * 20)])

    factory = _chained(sessions_db, risk_ctx, history_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)
    mock_alert_engine = AsyncMock()
    mock_alert_cls = MagicMock(return_value=mock_alert_engine)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls), \
         patch("notifications.alert_engine.AlertEngine", mock_alert_cls), \
         patch("risk.engine.should_stop_loss", return_value=False), \
         patch("risk.engine.should_take_profit", return_value=True):
        await _trigger_strategy("AAPL", current_price)

    mock_executor.close_trade.assert_called_once_with(open_trade, current_price, risk_db_inner)


# ---------------------------------------------------------------------------
# _trigger_strategy — daily max loss circuit breaker path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_loss_limit_closes_session_and_continues():
    """When daily P&L breaches the limit, the session is closed and the loop continues."""
    session = _make_session(daily_max_loss_pct=5.0, starting_capital=1000.0)
    session.daily_max_loss_pct = 5.0

    sessions_db = _db_ctx([_db_result([session])])
    risk_db = _db_ctx([_db_result([])])  # no SL/TP trades

    # daily P&L query — session hits -6% loss
    daily_pnl_db_inner = AsyncMock()
    daily_pnl_db_inner.execute = AsyncMock(return_value=_db_scalar(-60.0))  # -6% of 1000

    @asynccontextmanager
    async def daily_pnl_ctx():
        yield daily_pnl_db_inner

    # close session DB
    close_sess_db_inner = AsyncMock()
    active_session = MagicMock()
    active_session.status = "active"
    close_sess_db_inner.get = AsyncMock(return_value=active_session)

    @asynccontextmanager
    async def close_sess_ctx():
        yield close_sess_db_inner

    alert_db = AsyncMock()

    @asynccontextmanager
    async def alert_ctx():
        yield alert_db

    factory = _chained(sessions_db, risk_db, daily_pnl_ctx, close_sess_ctx, alert_ctx)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)
    mock_alert_engine = AsyncMock()
    mock_alert_cls = MagicMock(return_value=mock_alert_engine)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch("executor.paper.PaperExecutor", mock_executor_cls), \
         patch("notifications.alert_engine.AlertEngine", mock_alert_cls), \
         patch("risk.engine.daily_loss_limit_breached", return_value=True), \
         patch("backend.scheduler.scraper_job.unregister_symbol") as mock_unreg:
        await _trigger_strategy("AAPL", 940.0)

    mock_unreg.assert_called_once_with("AAPL")
    assert active_session.status == "closed"
    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_daily_loss_limit_not_breached_continues_to_strategy():
    """When daily P&L is within limits, strategy evaluation proceeds normally."""
    session = _make_session(daily_max_loss_pct=5.0, starting_capital=1000.0)

    sessions_db = _db_ctx([_db_result([session])])
    risk_db = _db_ctx([_db_result([])])

    daily_pnl_db_inner = AsyncMock()
    daily_pnl_db_inner.execute = AsyncMock(return_value=_db_scalar(-10.0))  # only -1%

    @asynccontextmanager
    async def daily_pnl_ctx():
        yield daily_pnl_db_inner

    hold_signal = Signal(action="hold", reason="neutral", confidence=0.5)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = hold_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)
    history_db = _db_ctx([_db_result([MagicMock(close=990.0)] * 20)])

    factory = _chained(sessions_db, risk_db, daily_pnl_ctx, history_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls), \
         patch("risk.engine.daily_loss_limit_breached", return_value=False):
        await _trigger_strategy("AAPL", 990.0)

    mock_strategy.analyze.assert_called_once()
    mock_executor.execute.assert_not_called()  # hold signal


# ---------------------------------------------------------------------------
# _trigger_strategy — max position size exceeded path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_position_size_exceeded_skips_execution():
    """When max_position_pct is breached, the signal is skipped."""
    session = _make_session(max_position_pct=10.0, starting_capital=1000.0)

    sessions_db = _db_ctx([_db_result([session])])
    risk_db = _db_ctx([_db_result([])])

    buy_signal = Signal(action="buy", reason="oversold", confidence=0.8)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = buy_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)
    history_db = _db_ctx([_db_result([MagicMock(close=150.0)] * 20)])

    factory = _chained(sessions_db, risk_db, history_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls), \
         patch("risk.engine.exceeds_max_position", return_value=True):
        await _trigger_strategy("AAPL", 150.0)

    mock_executor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# start_scheduler / stop_scheduler
# ---------------------------------------------------------------------------

def test_start_scheduler_adds_job_and_starts():
    from backend.scheduler import scraper_job as job

    mock_scheduler = MagicMock()
    original = job.scheduler
    job.scheduler = mock_scheduler
    try:
        from backend.scheduler.scraper_job import start_scheduler
        start_scheduler()
        mock_scheduler.add_job.assert_called_once()
        mock_scheduler.start.assert_called_once()
    finally:
        job.scheduler = original


def test_stop_scheduler_calls_shutdown():
    from backend.scheduler import scraper_job as job

    mock_scheduler = MagicMock()
    original = job.scheduler
    job.scheduler = mock_scheduler
    try:
        from backend.scheduler.scraper_job import stop_scheduler
        stop_scheduler()
        mock_scheduler.shutdown.assert_called_once()
    finally:
        job.scheduler = original
