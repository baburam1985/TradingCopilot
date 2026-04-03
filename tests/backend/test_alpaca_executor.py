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
    # Pre-configure get_order_by_id so fill polling resolves immediately
    client.get_order_by_id = MagicMock(return_value=_make_order(status="filled"))
    return client


# ---------------------------------------------------------------------------
# Market order — basic path
# ---------------------------------------------------------------------------

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

    mock_client.close_position.assert_called_once_with(
        trade.session.symbol if hasattr(trade, "session") else mock_client.close_position.call_args[0][0]
    )


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


# ---------------------------------------------------------------------------
# Limit orders
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_limit_order_uses_limit_price():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="dip", confidence=0.85)
    session = _make_session(symbol="MSFT", capital=2000.0)
    order = _make_order(order_id="limit-order-abc", status="new")
    mock_client = _make_alpaca_client(submit_return=order)
    executor = AlpacaExecutor(trading_client=mock_client)

    result = await executor.execute(
        session, signal, current_price=300.0,
        order_type="limit", limit_price=295.0,
    )

    mock_client.submit_order.assert_called_once()
    assert result["order_type"] == "limit"
    assert result["order_id"] == "limit-order-abc"


@pytest.mark.asyncio
async def test_execute_limit_order_falls_back_to_current_price_when_no_limit_supplied():
    from strategies.base import Signal
    signal = Signal(action="sell", reason="target", confidence=0.9)
    session = _make_session(symbol="NVDA", capital=500.0)
    order = _make_order(order_id="limit-fallback", status="new")
    mock_client = _make_alpaca_client(submit_return=order)
    executor = AlpacaExecutor(trading_client=mock_client)

    result = await executor.execute(
        session, signal, current_price=500.0, order_type="limit"
    )

    mock_client.submit_order.assert_called_once()
    assert result["order_type"] == "limit"


@pytest.mark.asyncio
async def test_execute_result_includes_order_type_market():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="test", confidence=0.7)
    session = _make_session()
    mock_client = _make_alpaca_client()
    executor = AlpacaExecutor(trading_client=mock_client)

    result = await executor.execute(session, signal, current_price=100.0)

    assert result["order_type"] == "market"


# ---------------------------------------------------------------------------
# Fill polling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_for_fill_returns_filled_price_immediately():
    executor = AlpacaExecutor(trading_client=MagicMock())
    filled_order = _make_order(filled_avg_price=151.25, status="filled")
    executor._client.get_order_by_id = MagicMock(return_value=filled_order)

    price = await executor._poll_for_fill("some-id", fallback_price=150.0, timeout=5.0)

    assert price == 151.25


@pytest.mark.asyncio
async def test_poll_for_fill_returns_none_on_canceled():
    executor = AlpacaExecutor(trading_client=MagicMock())
    canceled_order = _make_order(status="canceled")
    canceled_order.filled_avg_price = None
    executor._client.get_order_by_id = MagicMock(return_value=canceled_order)

    price = await executor._poll_for_fill("some-id", fallback_price=150.0, timeout=5.0)

    assert price is None


@pytest.mark.asyncio
async def test_poll_for_fill_returns_none_when_get_order_by_id_absent():
    """Injected mock without get_order_by_id should skip polling gracefully."""
    mock_client = MagicMock(spec=[])  # empty spec — no attributes
    executor = AlpacaExecutor(trading_client=mock_client)

    price = await executor._poll_for_fill("some-id", fallback_price=200.0)

    assert price is None


@pytest.mark.asyncio
async def test_poll_for_fill_returns_none_on_exception():
    executor = AlpacaExecutor(trading_client=MagicMock())
    executor._client.get_order_by_id = MagicMock(side_effect=RuntimeError("network"))

    price = await executor._poll_for_fill("bad-id", fallback_price=100.0, timeout=2.0)

    assert price is None


# ---------------------------------------------------------------------------
# Order status tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_order_status_returns_status_string():
    executor = AlpacaExecutor(trading_client=MagicMock())
    order = _make_order(status="partially_filled")
    executor._client.get_order_by_id = MagicMock(return_value=order)

    status = await executor.get_order_status("order-xyz")

    assert status == "partially_filled"


@pytest.mark.asyncio
async def test_get_order_status_returns_none_on_error():
    executor = AlpacaExecutor(trading_client=MagicMock())
    executor._client.get_order_by_id = MagicMock(side_effect=Exception("not found"))

    status = await executor.get_order_status("missing-order")

    assert status is None


# ---------------------------------------------------------------------------
# Position tracking
# ---------------------------------------------------------------------------

def test_get_open_positions_returns_list():
    mock_positions = [MagicMock(), MagicMock()]
    mock_client = MagicMock()
    mock_client.get_all_positions = MagicMock(return_value=mock_positions)
    executor = AlpacaExecutor(trading_client=mock_client)

    positions = executor.get_open_positions()

    assert positions == mock_positions
    mock_client.get_all_positions.assert_called_once()


def test_get_open_positions_returns_empty_list_on_error():
    mock_client = MagicMock()
    mock_client.get_all_positions = MagicMock(side_effect=Exception("API error"))
    executor = AlpacaExecutor(trading_client=mock_client)

    positions = executor.get_open_positions()

    assert positions == []


def test_get_position_returns_position_for_symbol():
    mock_pos = MagicMock()
    mock_client = MagicMock()
    mock_client.get_open_position = MagicMock(return_value=mock_pos)
    executor = AlpacaExecutor(trading_client=mock_client)

    pos = executor.get_position("aapl")

    mock_client.get_open_position.assert_called_once_with("AAPL")
    assert pos == mock_pos


def test_get_position_returns_none_when_no_open_position():
    mock_client = MagicMock()
    mock_client.get_open_position = MagicMock(side_effect=Exception("no position"))
    executor = AlpacaExecutor(trading_client=mock_client)

    pos = executor.get_position("GOOG")

    assert pos is None


# ---------------------------------------------------------------------------
# WebSocket stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_stream_calls_subscribe_and_run():
    mock_stream = MagicMock()
    mock_stream.subscribe_trade_updates = MagicMock()
    mock_stream._run_forever = AsyncMock()

    executor = AlpacaExecutor(trading_client=MagicMock(), stream_client=mock_stream)
    await executor.start_stream()

    mock_stream.subscribe_trade_updates.assert_called_once()
    mock_stream._run_forever.assert_called_once()


@pytest.mark.asyncio
async def test_start_stream_invokes_callback_on_update():
    received = []

    async def _cb(data):
        received.append(data)

    mock_stream = MagicMock()
    captured_handler = []

    def _subscribe(handler):
        captured_handler.append(handler)

    mock_stream.subscribe_trade_updates = _subscribe

    async def _run():
        await captured_handler[0]({"event": "fill", "order": {"id": "abc"}})

    mock_stream._run_forever = _run

    executor = AlpacaExecutor(trading_client=MagicMock(), stream_client=mock_stream)
    await executor.start_stream(on_order_update=_cb)

    assert len(received) == 1
    assert received[0]["event"] == "fill"


@pytest.mark.asyncio
async def test_stop_stream_calls_stop_ws():
    mock_stream = MagicMock()
    mock_stream.stop_ws = AsyncMock()
    executor = AlpacaExecutor(trading_client=MagicMock(), stream_client=mock_stream)

    await executor.stop_stream()

    mock_stream.stop_ws.assert_called_once()


@pytest.mark.asyncio
async def test_stop_stream_noop_when_no_stream():
    executor = AlpacaExecutor(trading_client=MagicMock())
    # Should not raise
    await executor.stop_stream()


@pytest.mark.asyncio
async def test_start_stream_skips_when_trading_stream_unavailable():
    """If alpaca-py is not installed, start_stream should log and return quietly."""
    executor = AlpacaExecutor(trading_client=MagicMock())
    with patch("executor.alpaca._ALPACA_AVAILABLE", False):
        with patch("executor.alpaca.TradingStream", None):
            # Should not raise
            await executor.start_stream()


# ---------------------------------------------------------------------------
# DB persistence of order id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_persists_order_id_to_db_when_db_provided():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="signal", confidence=0.75)
    session = _make_session(symbol="AMZN", capital=300.0)
    order = _make_order(order_id="persist-test-id", status="filled", filled_avg_price=120.0)
    mock_client = _make_alpaca_client(submit_return=order)
    filled_order = _make_order(order_id="persist-test-id", status="filled", filled_avg_price=120.0)
    mock_client.get_order_by_id = MagicMock(return_value=filled_order)

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    executor = AlpacaExecutor(trading_client=mock_client)

    with patch("models.paper_trade.PaperTrade", autospec=False) as MockTrade:
        MockTrade.return_value = MagicMock()
        result = await executor.execute(session, signal, current_price=120.0, db=mock_db)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert result["order_id"] == "persist-test-id"


@pytest.mark.asyncio
async def test_execute_does_not_require_db():
    """execute() must work without a db argument."""
    from strategies.base import Signal
    signal = Signal(action="sell", reason="exit", confidence=0.6)
    session = _make_session()
    mock_client = _make_alpaca_client()
    executor = AlpacaExecutor(trading_client=mock_client)

    result = await executor.execute(session, signal, current_price=50.0)

    assert result is not None
    assert "order_id" in result
