"""
Tests for IBKR session executor dispatch (AGEA-107).
TDD: Tests written before implementation.

Covers:
- sessions router: mode mapping from (mode, broker) to persisted mode
- scraper_job: IBKRConnector dispatched for ibkr_live sessions
- scraper_job: connect()/disconnect() lifecycle called around execute()
- scraper_job: non-IBKR sessions unaffected
"""

import sys
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))


# ---------------------------------------------------------------------------
# sessions router — mode mapping
# ---------------------------------------------------------------------------

class TestSessionModeMapping:
    """POST /sessions should map (mode, broker) → internal mode string."""

    def _make_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    def _make_request(self, mode, broker=None):
        from routers.sessions import CreateSessionRequest
        return CreateSessionRequest(
            symbol="AAPL",
            strategy="moving_average_crossover",
            strategy_params={"short_window": 5, "long_window": 20},
            starting_capital=1000.0,
            mode=mode,
            broker=broker,
        )

    @pytest.mark.asyncio
    async def test_live_ibkr_persists_ibkr_live_mode(self):
        """mode=live + broker=ibkr → stored as ibkr_live."""
        from routers.sessions import create_session

        req = self._make_request(mode="live", broker="ibkr")
        db = self._make_db()

        with patch("routers.sessions.register_symbol"):
            await create_session(req, db)

        stored = db.add.call_args[0][0]
        assert stored.mode == "ibkr_live"

    @pytest.mark.asyncio
    async def test_live_alpaca_persists_alpaca_live_mode(self):
        """mode=live + broker=alpaca → stored as alpaca_live."""
        from routers.sessions import create_session

        req = self._make_request(mode="live", broker="alpaca")
        db = self._make_db()

        with patch("routers.sessions.register_symbol"):
            await create_session(req, db)

        stored = db.add.call_args[0][0]
        assert stored.mode == "alpaca_live"

    @pytest.mark.asyncio
    async def test_paper_alpaca_persists_alpaca_paper_mode(self):
        """mode=paper + broker=alpaca → stored as alpaca_paper."""
        from routers.sessions import create_session

        req = self._make_request(mode="paper", broker="alpaca")
        db = self._make_db()

        with patch("routers.sessions.register_symbol"):
            await create_session(req, db)

        stored = db.add.call_args[0][0]
        assert stored.mode == "alpaca_paper"

    @pytest.mark.asyncio
    async def test_paper_no_broker_persists_paper_mode(self):
        """mode=paper + broker=None → stored as paper."""
        from routers.sessions import create_session

        req = self._make_request(mode="paper", broker=None)
        db = self._make_db()

        with patch("routers.sessions.register_symbol"):
            await create_session(req, db)

        stored = db.add.call_args[0][0]
        assert stored.mode == "paper"

    @pytest.mark.asyncio
    async def test_live_no_broker_raises_422(self):
        """mode=live with no broker → 400 (ambiguous executor)."""
        from fastapi import HTTPException
        from routers.sessions import create_session

        req = self._make_request(mode="live", broker=None)
        db = self._make_db()

        with patch("routers.sessions.register_symbol"):
            with pytest.raises(HTTPException) as exc_info:
                await create_session(req, db)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# scraper_job — IBKR dispatch
# ---------------------------------------------------------------------------

def _make_session(mode: str, symbol: str = "AAPL"):
    session = MagicMock()
    session.id = uuid.uuid4()
    session.symbol = symbol
    session.mode = mode
    session.strategy = "moving_average_crossover"
    session.strategy_params = {"short_window": 5, "long_window": 20}
    session.starting_capital = 1000.0
    session.status = "active"
    session.stop_loss_pct = None
    session.take_profit_pct = None
    session.max_position_pct = None
    session.daily_max_loss_pct = None
    session.notify_email = False
    session.email_address = None
    return session


def _make_db_with_sessions(sessions, open_trades=None, closes=None, price_bars=None):
    db = AsyncMock()
    db.add = MagicMock()

    result_sessions = MagicMock()
    result_sessions.scalars.return_value.all.return_value = sessions

    result_empty = MagicMock()
    result_empty.scalars.return_value.all.return_value = open_trades or []
    result_empty.scalar.return_value = 0

    result_bars = MagicMock()
    result_bars.scalars.return_value.all.return_value = price_bars or []

    db.execute = AsyncMock(side_effect=[
        result_sessions,   # initial session query
        result_empty,      # open_trades for stop-loss check
        result_bars,       # price history
        result_empty,      # opposing open trades
    ])
    return db


def _make_db_ctx(execute_results):
    """Return an async context-manager factory yielding a mock DB."""
    from contextlib import asynccontextmanager

    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(side_effect=execute_results)

    @asynccontextmanager
    async def _ctx():
        yield db

    return _ctx, db


def _chained_factory(*ctx_factories):
    """Build a mock for AsyncSessionLocal that cycles through factories."""
    call_count = [0]

    def _factory(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return ctx_factories[idx]()

    return _factory


def _db_result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    r.scalar.return_value = 0
    return r


@pytest.mark.asyncio
async def test_ibkr_live_session_dispatches_ibkr_connector():
    """_trigger_strategy dispatches to IBKRConnector for ibkr_live sessions."""
    session = _make_session(mode="ibkr_live")
    session.mode = "ibkr_live"

    mock_signal = MagicMock()
    mock_signal.action = "buy"
    mock_signal.reason = "MA crossover"
    mock_signal.reasoning = None

    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    bar = MagicMock()
    bar.close = 150.0

    mock_connector = AsyncMock()
    mock_connector.execute = AsyncMock(return_value=None)
    mock_connector.connect = AsyncMock()
    mock_connector.disconnect = AsyncMock()
    mock_connector.close_trade = AsyncMock()
    mock_connector_cls = MagicMock(return_value=mock_connector)

    sessions_ctx, _ = _make_db_ctx([_db_result([session])])
    risk_ctx, _ = _make_db_ctx([_db_result([])])
    history_ctx, _ = _make_db_ctx([_db_result([bar] * 50)])
    exec_ctx, exec_db = _make_db_ctx([_db_result([])])
    alert_ctx, alert_db = _make_db_ctx([])

    factory = _chained_factory(sessions_ctx, risk_ctx, history_ctx, exec_ctx, alert_ctx)

    from scheduler.scraper_job import _trigger_strategy
    with patch("database.AsyncSessionLocal", new=factory), \
         patch("executor.ibkr.IBKRConnector", mock_connector_cls), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"moving_average_crossover": mock_strategy_cls}), \
         patch("notifications.alert_engine.AlertEngine") as mock_alert_cls:
        mock_alert_cls.return_value.fire = AsyncMock()
        await _trigger_strategy("AAPL", 150.0)

    mock_connector_cls.assert_called_once()
    mock_connector.connect.assert_called_once()
    mock_connector.execute.assert_called_once()
    mock_connector.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_ibkr_connector_disconnect_called_even_on_execute_failure():
    """disconnect() must be called even if execute() raises."""
    session = _make_session(mode="ibkr_live")
    session.mode = "ibkr_live"

    mock_signal = MagicMock()
    mock_signal.action = "buy"
    mock_signal.reason = "MA crossover"
    mock_signal.reasoning = None

    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    bar = MagicMock()
    bar.close = 150.0

    mock_connector = AsyncMock()
    mock_connector.connect = AsyncMock()
    mock_connector.execute = AsyncMock(side_effect=RuntimeError("IB connection lost"))
    mock_connector.disconnect = AsyncMock()
    mock_connector_cls = MagicMock(return_value=mock_connector)

    sessions_ctx, _ = _make_db_ctx([_db_result([session])])
    risk_ctx, _ = _make_db_ctx([_db_result([])])
    history_ctx, _ = _make_db_ctx([_db_result([bar] * 50)])
    exec_ctx, _ = _make_db_ctx([_db_result([])])
    alert_ctx, _ = _make_db_ctx([])

    factory = _chained_factory(sessions_ctx, risk_ctx, history_ctx, exec_ctx, alert_ctx)

    from scheduler.scraper_job import _trigger_strategy
    with patch("database.AsyncSessionLocal", new=factory), \
         patch("executor.ibkr.IBKRConnector", mock_connector_cls), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"moving_average_crossover": mock_strategy_cls}), \
         patch("notifications.alert_engine.AlertEngine") as mock_alert_cls:
        mock_alert_cls.return_value.fire = AsyncMock()
        # Must not propagate RuntimeError
        await _trigger_strategy("AAPL", 150.0)

    mock_connector.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_paper_session_still_dispatches_paper_executor():
    """paper sessions still use PaperExecutor, not IBKRConnector."""
    session = _make_session(mode="paper")
    session.mode = "paper"

    mock_signal = MagicMock()
    mock_signal.action = "buy"
    mock_signal.reason = "MA crossover"
    mock_signal.reasoning = None

    mock_strategy = MagicMock()
    mock_strategy.analyze.return_value = mock_signal
    mock_strategy_cls = MagicMock(return_value=mock_strategy)

    bar = MagicMock()
    bar.close = 150.0

    mock_paper_executor = AsyncMock()
    mock_paper_executor.execute = AsyncMock()
    mock_paper_executor.close_trade = AsyncMock()
    mock_paper_executor_cls = MagicMock(return_value=mock_paper_executor)

    mock_ibkr_connector_cls = MagicMock()

    sessions_ctx, _ = _make_db_ctx([_db_result([session])])
    risk_ctx, _ = _make_db_ctx([_db_result([])])
    history_ctx, _ = _make_db_ctx([_db_result([bar] * 50)])
    exec_ctx, _ = _make_db_ctx([_db_result([])])
    alert_ctx, _ = _make_db_ctx([])

    factory = _chained_factory(sessions_ctx, risk_ctx, history_ctx, exec_ctx, alert_ctx)

    from scheduler.scraper_job import _trigger_strategy
    with patch("database.AsyncSessionLocal", new=factory), \
         patch("executor.paper.PaperExecutor", mock_paper_executor_cls), \
         patch("executor.ibkr.IBKRConnector", mock_ibkr_connector_cls), \
         patch.dict("strategies.registry.STRATEGY_REGISTRY", {"moving_average_crossover": mock_strategy_cls}), \
         patch("notifications.alert_engine.AlertEngine") as mock_alert_cls:
        mock_alert_cls.return_value.fire = AsyncMock()
        await _trigger_strategy("AAPL", 150.0)

    mock_ibkr_connector_cls.assert_not_called()
    mock_paper_executor.execute.assert_called_once()


def test_ibkr_live_mode_included_in_session_filter():
    """_trigger_strategy session filter must include ibkr_live."""
    import ast
    import inspect
    import scheduler.scraper_job as sj

    source = inspect.getsource(sj._trigger_strategy)
    assert "ibkr_live" in source, (
        "ibkr_live must be included in the session mode filter in _trigger_strategy"
    )
