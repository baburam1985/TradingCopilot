import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from backend.executor.paper import PaperExecutor
from backend.strategies.base import Signal

@pytest.fixture
def mock_session():
    s = MagicMock()
    s.id = uuid.uuid4()
    s.starting_capital = 1000.0
    s.strategy_params = {"short_window": 3, "long_window": 5}
    return s

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_buy_signal_creates_open_trade(mock_session, mock_db):
    executor = PaperExecutor()
    signal = Signal(action="buy", reason="Golden cross", confidence=0.7)
    trade = await executor.execute(mock_session, signal, current_price=150.0, db=mock_db)
    assert trade.action == "buy"
    assert trade.status == "open"
    assert float(trade.price_at_signal) == 150.0
    assert float(trade.quantity) > 0

@pytest.mark.asyncio
async def test_sell_signal_closes_open_trade(mock_session, mock_db):
    executor = PaperExecutor()
    buy_signal = Signal(action="buy", reason="Golden cross", confidence=0.7)
    open_trade = await executor.execute(mock_session, buy_signal, current_price=150.0, db=mock_db)

    sell_signal = Signal(action="sell", reason="Death cross", confidence=0.7)
    closed_trade = await executor.close_trade(open_trade, current_price=160.0, db=mock_db)
    assert closed_trade.status == "closed"
    assert float(closed_trade.price_at_close) == 160.0
    assert float(closed_trade.pnl) == pytest.approx(
        (160.0 - 150.0) * float(closed_trade.quantity), abs=0.01
    )

@pytest.mark.asyncio
async def test_pnl_is_negative_on_losing_trade(mock_session, mock_db):
    executor = PaperExecutor()
    buy_signal = Signal(action="buy", reason="Golden cross", confidence=0.7)
    open_trade = await executor.execute(mock_session, buy_signal, current_price=150.0, db=mock_db)
    closed_trade = await executor.close_trade(open_trade, current_price=140.0, db=mock_db)
    assert float(closed_trade.pnl) < 0
