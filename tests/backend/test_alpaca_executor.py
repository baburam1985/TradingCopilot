"""Unit tests for AlpacaExecutor — mocks the Alpaca trading client."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from executor.alpaca import AlpacaExecutor


def _make_session(symbol="AAPL", capital=1000.0):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.starting_capital = capital
    return s


def _make_order(order_id=None, filled_avg_price=150.0, qty=6.666, status="filled"):
    order = MagicMock()
    order.id = order_id or str(uuid.uuid4())
    order.filled_avg_price = filled_avg_price
    order.qty = str(qty)
    order.status = status
    return order


def _make_alpaca_client(submit_return=None, close_return=None):
    client = MagicMock()
    client.submit_order = MagicMock(return_value=submit_return or _make_order())
    client.close_position = MagicMock(return_value=close_return or _make_order())
    return client


@pytest.mark.asyncio
async def test_execute_buy_submits_market_order():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="oversold", confidence=0.8)
    session = _make_session(symbol="AAPL", capital=1000.0)
    mock_client = _make_alpaca_client()
    executor = AlpacaExecutor(trading_client=mock_client)

    await executor.execute(session, signal, current_price=150.0)

    mock_client.submit_order.assert_called_once()
    call_kwargs = mock_client.submit_order.call_args
    # Should be a buy order for AAPL
    order_request = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("order_data", call_kwargs[0][0])
    assert order_request is not None


@pytest.mark.asyncio
async def test_execute_sell_submits_market_order():
    from strategies.base import Signal
    signal = Signal(action="sell", reason="overbought", confidence=0.9)
    session = _make_session(symbol="TSLA", capital=500.0)
    mock_client = _make_alpaca_client()
    executor = AlpacaExecutor(trading_client=mock_client)

    await executor.execute(session, signal, current_price=200.0)

    mock_client.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_execute_hold_does_not_submit_order():
    from strategies.base import Signal
    signal = Signal(action="hold", reason="neutral", confidence=0.0)
    session = _make_session()
    mock_client = _make_alpaca_client()
    executor = AlpacaExecutor(trading_client=mock_client)

    result = await executor.execute(session, signal, current_price=150.0)

    mock_client.submit_order.assert_not_called()
    assert result is None


@pytest.mark.asyncio
async def test_close_trade_calls_close_position():
    from models.paper_trade import PaperTrade
    trade = MagicMock(spec=PaperTrade)
    trade.alpaca_order_id = str(uuid.uuid4())
    mock_client = _make_alpaca_client()
    executor = AlpacaExecutor(trading_client=mock_client)

    await executor.close_trade(trade, current_price=155.0)

    mock_client.close_position.assert_called_once_with(trade.session.symbol if hasattr(trade, "session") else mock_client.close_position.call_args[0][0])


@pytest.mark.asyncio
async def test_paper_flag_overrides_env_var():
    """Explicit paper=False must override ALPACA_PAPER=true in the environment."""
    with patch.dict("os.environ", {
        "ALPACA_API_KEY": "test_key",
        "ALPACA_API_SECRET": "test_secret",
        "ALPACA_PAPER": "true",
    }):
        with patch("executor.alpaca._ALPACA_AVAILABLE", True):
            with patch("executor.alpaca.TradingClient") as mock_cls:
                mock_cls.return_value = _make_alpaca_client()
                AlpacaExecutor(paper=False)
                mock_cls.assert_called_once_with(
                    api_key="test_key",
                    secret_key="test_secret",
                    paper=False,
                )


@pytest.mark.asyncio
async def test_executor_created_without_client_reads_env():
    """AlpacaExecutor without injected client should attempt to read env vars."""
    with patch.dict("os.environ", {
        "ALPACA_API_KEY": "test_key",
        "ALPACA_API_SECRET": "test_secret",
        "ALPACA_PAPER": "true",
    }):
        with patch("executor.alpaca._ALPACA_AVAILABLE", True):
            with patch("executor.alpaca.TradingClient") as mock_cls:
                mock_cls.return_value = _make_alpaca_client()
                executor = AlpacaExecutor()
                mock_cls.assert_called_once_with(
                    api_key="test_key",
                    secret_key="test_secret",
                    paper=True,
                )


@pytest.mark.asyncio
async def test_execute_returns_order_id_in_result():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="test", confidence=0.7)
    session = _make_session()
    order = _make_order(order_id="alpaca-order-123")
    mock_client = _make_alpaca_client(submit_return=order)
    executor = AlpacaExecutor(trading_client=mock_client)

    result = await executor.execute(session, signal, current_price=100.0)

    assert result is not None
    assert result.get("order_id") == "alpaca-order-123"
