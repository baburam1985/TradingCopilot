"""Tests for _trigger_strategy — the autonomous paper trade execution loop.

Validates that paper sessions generate trades from price ticks without any
manual trigger, and that opposing open trades are closed on reversal signals.
"""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scheduler.scraper_job import _trigger_strategy
from backend.strategies.base import Signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(strategy="rsi", strategy_params=None, starting_capital=1000.0):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.strategy = strategy
    s.strategy_params = strategy_params or {"period": 14, "oversold": 30, "overbought": 70}
    s.starting_capital = starting_capital
    # Risk params default to None (all guardrails disabled)
    s.stop_loss_pct = None
    s.take_profit_pct = None
    s.max_position_pct = None
    s.daily_max_loss_pct = None
    return s


def _make_price_bar(close=150.0):
    bar = MagicMock()
    bar.close = close
    return bar


def _make_open_trade(action="buy"):
    trade = MagicMock()
    trade.action = action
    trade.status = "open"
    trade.price_at_signal = 140.0
    trade.quantity = 6.666
    return trade


def _db_result(items):
    """Return a mock query result whose .scalars().all() yields *items*."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _db_ctx(execute_results):
    """
    Return an async context-manager factory whose db.execute() side_effect
    cycles through *execute_results* in order.
    """
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_results)

    @asynccontextmanager
    async def _ctx():
        yield db

    return _ctx


def _chained_db_factory(*db_ctx_factories):
    """
    Build a mock for AsyncSessionLocal whose __call__ side_effect cycles
    through the supplied async-context-manager factories.
    """
    call_count = [0]

    def _factory(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return db_ctx_factories[idx]()

    return _factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_buy_signal_creates_trade_autonomously():
    """A buy signal from a strategy must produce a PaperTrade without manual intervention."""
    session = _make_session()
    bars = [_make_price_bar(150.0)] * 20

    mock_signal = Signal(action="buy", reason="oversold", confidence=0.8)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session])])
    # second db: risk scan for open SL/TP trades (none)
    risk_check_db = _db_ctx([_db_result([])])
    history_db = _db_ctx([_db_result(bars)])
    # fourth db: open opposing trades (none) + execute
    exec_db_inner = AsyncMock()
    exec_db_inner.execute = AsyncMock(return_value=_db_result([]))

    @asynccontextmanager
    async def exec_ctx():
        yield exec_db_inner

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    factory = _chained_db_factory(sessions_db, risk_check_db, history_db, exec_ctx)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 150.0)

    mock_strategy.analyze.assert_called_once()
    mock_executor.execute.assert_called_once_with(session, mock_signal, 150.0, exec_db_inner)


@pytest.mark.asyncio
async def test_hold_signal_creates_no_trade():
    """A hold signal must not invoke PaperExecutor at all."""
    session = _make_session()
    bars = [_make_price_bar()] * 20

    mock_signal = Signal(action="hold", reason="neutral", confidence=0.5)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session])])
    # second db: risk scan for open SL/TP trades (none)
    risk_check_db = _db_ctx([_db_result([])])
    history_db = _db_ctx([_db_result(bars)])
    factory = _chained_db_factory(sessions_db, risk_check_db, history_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 150.0)

    mock_executor.execute.assert_not_called()
    mock_executor.close_trade.assert_not_called()


@pytest.mark.asyncio
async def test_sell_signal_closes_open_buy_trade():
    """A sell signal must close an existing open buy trade before creating a sell trade."""
    session = _make_session()
    bars = [_make_price_bar(160.0)] * 20
    open_buy_trade = _make_open_trade(action="buy")

    sell_signal = Signal(action="sell", reason="overbought", confidence=0.9)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = sell_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session])])
    # second db: risk scan for open SL/TP trades (none, risk params disabled)
    risk_check_db = _db_ctx([_db_result([])])
    history_db = _db_ctx([_db_result(bars)])

    exec_db_inner = AsyncMock()
    exec_db_inner.execute = AsyncMock(return_value=_db_result([open_buy_trade]))

    @asynccontextmanager
    async def exec_ctx():
        yield exec_db_inner

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    factory = _chained_db_factory(sessions_db, risk_check_db, history_db, exec_ctx)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 160.0)

    mock_executor.close_trade.assert_called_once_with(open_buy_trade, 160.0, exec_db_inner)
    mock_executor.execute.assert_called_once_with(session, sell_signal, 160.0, exec_db_inner)


@pytest.mark.asyncio
async def test_buy_signal_closes_open_sell_trade():
    """A buy signal must close an existing open sell trade before creating a buy trade."""
    session = _make_session()
    bars = [_make_price_bar(140.0)] * 20
    open_sell_trade = _make_open_trade(action="sell")

    buy_signal = Signal(action="buy", reason="oversold", confidence=0.85)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = buy_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session])])
    # second db: risk scan for open SL/TP trades (none, risk params disabled)
    risk_check_db = _db_ctx([_db_result([])])
    history_db = _db_ctx([_db_result(bars)])

    exec_db_inner = AsyncMock()
    exec_db_inner.execute = AsyncMock(return_value=_db_result([open_sell_trade]))

    @asynccontextmanager
    async def exec_ctx():
        yield exec_db_inner

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    factory = _chained_db_factory(sessions_db, risk_check_db, history_db, exec_ctx)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 140.0)

    mock_executor.close_trade.assert_called_once_with(open_sell_trade, 140.0, exec_db_inner)
    mock_executor.execute.assert_called_once_with(session, buy_signal, 140.0, exec_db_inner)


@pytest.mark.asyncio
async def test_unknown_strategy_skipped_without_crash():
    """Sessions with an unknown strategy must be skipped cleanly (no exception raised)."""
    session = _make_session(strategy="nonexistent_strategy")

    sessions_db = _db_ctx([_db_result([session])])
    # second db: risk scan for open SL/TP trades (none, risk params disabled)
    risk_check_db = _db_ctx([_db_result([])])
    factory = _chained_db_factory(sessions_db, risk_check_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {}, clear=True), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 150.0)  # Must not raise

    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_no_active_sessions_no_execution():
    """When no active paper sessions exist for a symbol, no trades are executed."""
    sessions_db = _db_ctx([_db_result([])])
    factory = _chained_db_factory(sessions_db)

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 150.0)

    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_sessions_all_executed():
    """Each active session receives an independent strategy evaluation and trade execution."""
    session_a = _make_session(strategy="rsi")
    session_b = _make_session(strategy="rsi")
    bars = [_make_price_bar(155.0)] * 20

    buy_signal = Signal(action="buy", reason="oversold", confidence=0.75)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = buy_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session_a, session_b])])

    # Two sessions → two price-history lookups + two exec db contexts
    history_db_a = _db_ctx([_db_result(bars)])
    history_db_b = _db_ctx([_db_result(bars)])

    exec_db_a = AsyncMock()
    exec_db_a.execute = AsyncMock(return_value=_db_result([]))
    exec_db_b = AsyncMock()
    exec_db_b.execute = AsyncMock(return_value=_db_result([]))

    @asynccontextmanager
    async def exec_ctx_a():
        yield exec_db_a

    @asynccontextmanager
    async def exec_ctx_b():
        yield exec_db_b

    mock_executor = AsyncMock()
    mock_executor_cls = MagicMock(return_value=mock_executor)

    risk_check_db_a = _db_ctx([_db_result([])])
    risk_check_db_b = _db_ctx([_db_result([])])
    factory = _chained_db_factory(sessions_db, risk_check_db_a, history_db_a, exec_ctx_a, risk_check_db_b, history_db_b, exec_ctx_b)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.paper.PaperExecutor", mock_executor_cls):
        await _trigger_strategy("AAPL", 155.0)

    assert mock_executor.execute.call_count == 2


@pytest.mark.asyncio
async def test_alpaca_paper_session_uses_alpaca_executor():
    """A session with mode='alpaca_paper' must use AlpacaExecutor(paper=True)."""
    session = _make_session()
    session.mode = "alpaca_paper"
    bars = [_make_price_bar(150.0)] * 20

    mock_signal = Signal(action="buy", reason="oversold", confidence=0.8)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session])])
    risk_check_db = _db_ctx([_db_result([])])
    history_db = _db_ctx([_db_result(bars)])

    exec_db_inner = AsyncMock()
    exec_db_inner.execute = AsyncMock(return_value=_db_result([]))
    exec_db_inner.add = MagicMock()

    @asynccontextmanager
    async def exec_ctx():
        yield exec_db_inner

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value={
        "order_id": "alpaca-order-456",
        "symbol": "AAPL",
        "side": "buy",
        "qty": 6.666,
        "status": "accepted",
        "filled_avg_price": None,
    })
    mock_alpaca_cls = MagicMock(return_value=mock_executor)

    factory = _chained_db_factory(sessions_db, risk_check_db, history_db, exec_ctx)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.alpaca.AlpacaExecutor", mock_alpaca_cls):
        await _trigger_strategy("AAPL", 150.0)

    mock_alpaca_cls.assert_called_once_with(paper=True)
    mock_executor.execute.assert_called_once()


@pytest.mark.asyncio
async def test_alpaca_live_session_uses_alpaca_executor_paper_false():
    """A session with mode='alpaca_live' must use AlpacaExecutor(paper=False)."""
    session = _make_session()
    session.mode = "alpaca_live"
    bars = [_make_price_bar(200.0)] * 20

    mock_signal = Signal(action="sell", reason="overbought", confidence=0.9)
    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    sessions_db = _db_ctx([_db_result([session])])
    risk_check_db = _db_ctx([_db_result([])])
    history_db = _db_ctx([_db_result(bars)])

    exec_db_inner = AsyncMock()
    exec_db_inner.execute = AsyncMock(return_value=_db_result([]))
    exec_db_inner.add = MagicMock()

    @asynccontextmanager
    async def exec_ctx():
        yield exec_db_inner

    mock_executor = AsyncMock()
    mock_executor.execute = AsyncMock(return_value={
        "order_id": "alpaca-order-789",
        "symbol": "AAPL",
        "side": "sell",
        "qty": 5.0,
        "status": "accepted",
        "filled_avg_price": None,
    })
    mock_alpaca_cls = MagicMock(return_value=mock_executor)

    factory = _chained_db_factory(sessions_db, risk_check_db, history_db, exec_ctx)

    with patch("database.AsyncSessionLocal", new=factory), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"rsi": mock_strategy_cls}), \
         patch("executor.alpaca.AlpacaExecutor", mock_alpaca_cls):
        await _trigger_strategy("AAPL", 200.0)

    mock_alpaca_cls.assert_called_once_with(paper=False)
    mock_executor.execute.assert_called_once()
