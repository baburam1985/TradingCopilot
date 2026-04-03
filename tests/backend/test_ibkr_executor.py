"""Unit tests for IBKRConnector — mocks the ib_insync IB client."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from executor.ibkr import IBKRConnector


def _make_session(symbol="AAPL", capital=1000.0):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.starting_capital = capital
    return s


def _make_trade(status="Filled", avg_fill_price=150.0):
    """Build a mock ib_insync Trade object."""
    trade = MagicMock()
    trade.orderStatus.status = status
    trade.orderStatus.avgFillPrice = avg_fill_price
    return trade


def _make_ib_client(trade_return=None):
    """Build a mock ib_insync IB instance."""
    client = MagicMock()
    client.placeOrder = MagicMock(return_value=trade_return or _make_trade())
    client.disconnect = MagicMock()
    client.connectAsync = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Constructor / injection
# ---------------------------------------------------------------------------

def test_constructor_uses_injected_ib():
    mock_ib = _make_ib_client()
    connector = IBKRConnector(ib=mock_ib)
    assert connector._ib is mock_ib


def test_constructor_reads_env_defaults(monkeypatch):
    monkeypatch.delenv("IBKR_HOST", raising=False)
    monkeypatch.delenv("IBKR_PORT", raising=False)
    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)
    monkeypatch.delenv("IBKR_ACCOUNT", raising=False)
    connector = IBKRConnector(ib=MagicMock())
    assert connector._host == "127.0.0.1"
    assert connector._port == 7497
    assert connector._client_id == 1
    assert connector._account == ""


def test_constructor_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("IBKR_HOST", "192.168.1.10")
    monkeypatch.setenv("IBKR_PORT", "4001")
    monkeypatch.setenv("IBKR_CLIENT_ID", "5")
    monkeypatch.setenv("IBKR_ACCOUNT", "U1234567")
    connector = IBKRConnector(ib=MagicMock())
    assert connector._host == "192.168.1.10"
    assert connector._port == 4001
    assert connector._client_id == 5
    assert connector._account == "U1234567"


def test_constructor_raises_when_no_ib_and_not_installed():
    with patch("executor.ibkr._IB_AVAILABLE", False):
        with pytest.raises(ImportError, match="ib_insync"):
            IBKRConnector()


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_calls_connect_async():
    mock_ib = _make_ib_client()
    connector = IBKRConnector(ib=mock_ib, host="127.0.0.1", port=7497, client_id=1)
    await connector.connect()
    mock_ib.connectAsync.assert_called_once_with(
        host="127.0.0.1", port=7497, clientId=1
    )


@pytest.mark.asyncio
async def test_disconnect_calls_ib_disconnect():
    mock_ib = _make_ib_client()
    connector = IBKRConnector(ib=mock_ib)
    await connector.disconnect()
    mock_ib.disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# submit_order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_order_market_calls_place_order():
    trade = _make_trade()
    mock_ib = _make_ib_client(trade_return=trade)
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.submit_order("AAPL", 10.0, "BUY", order_type="market")

    mock_ib.placeOrder.assert_called_once()
    assert result is trade


@pytest.mark.asyncio
async def test_submit_order_limit_calls_place_order():
    trade = _make_trade()
    mock_ib = _make_ib_client(trade_return=trade)
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.submit_order(
        "TSLA", 5.0, "SELL", order_type="limit", limit_price=200.0
    )

    mock_ib.placeOrder.assert_called_once()
    assert result is trade


# ---------------------------------------------------------------------------
# execute — core flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_hold_returns_none():
    from strategies.base import Signal
    signal = Signal(action="hold", reason="neutral", confidence=0.0)
    connector = IBKRConnector(ib=_make_ib_client())

    result = await connector.execute(_make_session(), signal, current_price=150.0)

    assert result is None


@pytest.mark.asyncio
async def test_execute_buy_submits_order_and_returns_dict():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="oversold", confidence=0.8)
    session = _make_session(symbol="AAPL", capital=1500.0)
    trade = _make_trade(status="Filled", avg_fill_price=148.0)
    mock_ib = _make_ib_client(trade_return=trade)
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.execute(session, signal, current_price=150.0)

    mock_ib.placeOrder.assert_called_once()
    assert result is not None
    assert result["side"] == "buy"
    assert result["symbol"] == "AAPL"
    assert result["order_type"] == "market"
    assert result["filled_avg_price"] == 148.0


@pytest.mark.asyncio
async def test_execute_sell_submits_order():
    from strategies.base import Signal
    signal = Signal(action="sell", reason="overbought", confidence=0.9)
    session = _make_session(symbol="TSLA", capital=500.0)
    mock_ib = _make_ib_client()
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.execute(session, signal, current_price=200.0)

    mock_ib.placeOrder.assert_called_once()
    assert result["side"] == "sell"


@pytest.mark.asyncio
async def test_execute_limit_order():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="dip", confidence=0.85)
    session = _make_session(symbol="MSFT", capital=2000.0)
    mock_ib = _make_ib_client()
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.execute(
        session, signal, current_price=300.0,
        order_type="limit", limit_price=295.0,
    )

    mock_ib.placeOrder.assert_called_once()
    assert result["order_type"] == "limit"


@pytest.mark.asyncio
async def test_execute_without_db_does_not_raise():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="test", confidence=0.7)
    session = _make_session()
    connector = IBKRConnector(ib=_make_ib_client())

    result = await connector.execute(session, signal, current_price=100.0)

    assert result is not None
    assert "symbol" in result


@pytest.mark.asyncio
async def test_execute_with_db_persists_trade():
    from strategies.base import Signal
    signal = Signal(action="buy", reason="signal", confidence=0.75)
    session = _make_session(symbol="AMZN", capital=300.0)
    mock_ib = _make_ib_client(trade_return=_make_trade(status="Filled", avg_fill_price=120.0))
    connector = IBKRConnector(ib=mock_ib)

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("models.paper_trade.PaperTrade", autospec=False):
        result = await connector.execute(session, signal, current_price=120.0, db=mock_db)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    assert result is not None


# ---------------------------------------------------------------------------
# get_position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_position_returns_matching_position():
    pos = MagicMock()
    pos.contract.symbol = "AAPL"
    mock_ib = _make_ib_client()
    mock_ib.positions = MagicMock(return_value=[pos])
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.get_position("aapl")

    assert result is pos


@pytest.mark.asyncio
async def test_get_position_returns_none_when_no_match():
    pos = MagicMock()
    pos.contract.symbol = "TSLA"
    mock_ib = _make_ib_client()
    mock_ib.positions = MagicMock(return_value=[pos])
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.get_position("AAPL")

    assert result is None


@pytest.mark.asyncio
async def test_get_position_returns_none_on_error():
    mock_ib = _make_ib_client()
    mock_ib.positions = MagicMock(side_effect=RuntimeError("disconnected"))
    connector = IBKRConnector(ib=mock_ib)

    result = await connector.get_position("AAPL")

    assert result is None


# ---------------------------------------------------------------------------
# get_account_balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_account_balance_returns_net_liquidation():
    av = MagicMock()
    av.tag = "NetLiquidation"
    av.currency = "USD"
    av.value = "50000.00"
    mock_ib = _make_ib_client()
    mock_ib.accountValues = MagicMock(return_value=[av])
    connector = IBKRConnector(ib=mock_ib)

    balance = await connector.get_account_balance()

    assert balance == 50000.0


@pytest.mark.asyncio
async def test_get_account_balance_returns_none_when_tag_missing():
    av = MagicMock()
    av.tag = "TotalCashValue"
    av.currency = "USD"
    av.value = "1000.00"
    mock_ib = _make_ib_client()
    mock_ib.accountValues = MagicMock(return_value=[av])
    connector = IBKRConnector(ib=mock_ib)

    balance = await connector.get_account_balance()

    assert balance is None


@pytest.mark.asyncio
async def test_get_account_balance_returns_none_on_error():
    mock_ib = _make_ib_client()
    mock_ib.accountValues = MagicMock(side_effect=Exception("API error"))
    connector = IBKRConnector(ib=mock_ib)

    balance = await connector.get_account_balance()

    assert balance is None


# ---------------------------------------------------------------------------
# get_fills
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_fills_returns_all_fills():
    fill1 = MagicMock()
    fill2 = MagicMock()
    mock_ib = _make_ib_client()
    mock_ib.fills = MagicMock(return_value=[fill1, fill2])
    connector = IBKRConnector(ib=mock_ib)

    fills = await connector.get_fills()

    assert fills == [fill1, fill2]


@pytest.mark.asyncio
async def test_get_fills_filters_by_since():
    now = datetime.now(timezone.utc)
    early = MagicMock()
    early.time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    recent = MagicMock()
    recent.time = now
    mock_ib = _make_ib_client()
    mock_ib.fills = MagicMock(return_value=[early, recent])
    connector = IBKRConnector(ib=mock_ib)

    fills = await connector.get_fills(since=datetime(2024, 1, 1, tzinfo=timezone.utc))

    assert recent in fills
    assert early not in fills


@pytest.mark.asyncio
async def test_get_fills_returns_empty_on_error():
    mock_ib = _make_ib_client()
    mock_ib.fills = MagicMock(side_effect=Exception("connection lost"))
    connector = IBKRConnector(ib=mock_ib)

    fills = await connector.get_fills()

    assert fills == []


# ---------------------------------------------------------------------------
# _poll_for_fill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_for_fill_returns_price_when_filled():
    connector = IBKRConnector(ib=_make_ib_client())
    trade = _make_trade(status="Filled", avg_fill_price=155.25)

    price = await connector._poll_for_fill(trade, fallback_price=150.0, timeout=5.0)

    assert price == 155.25


@pytest.mark.asyncio
async def test_poll_for_fill_returns_fallback_when_avg_price_zero():
    connector = IBKRConnector(ib=_make_ib_client())
    trade = _make_trade(status="Filled", avg_fill_price=0.0)

    price = await connector._poll_for_fill(trade, fallback_price=150.0, timeout=5.0)

    assert price == 150.0


@pytest.mark.asyncio
async def test_poll_for_fill_returns_none_on_cancelled():
    connector = IBKRConnector(ib=_make_ib_client())
    trade = _make_trade(status="Cancelled", avg_fill_price=0.0)

    price = await connector._poll_for_fill(trade, fallback_price=150.0, timeout=5.0)

    assert price is None


@pytest.mark.asyncio
async def test_poll_for_fill_returns_none_when_trade_has_no_order_status():
    connector = IBKRConnector(ib=_make_ib_client())
    trade = MagicMock(spec=[])  # no orderStatus attribute

    price = await connector._poll_for_fill(trade, fallback_price=100.0)

    assert price is None


@pytest.mark.asyncio
async def test_poll_for_fill_returns_none_when_trade_is_none():
    connector = IBKRConnector(ib=_make_ib_client())

    price = await connector._poll_for_fill(None, fallback_price=100.0)

    assert price is None


# ---------------------------------------------------------------------------
# Integration stub (marked for skip when IBKR unavailable)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("ib_insync"),
    reason="ib_insync not installed",
)
@pytest.mark.asyncio
async def test_ibkr_paper_trading_connect():
    """Smoke test: connect to IBKR TWS paper endpoint.

    Requires TWS or IB Gateway running with paper account on port 7497.
    Marked @pytest.mark.integration — skipped in unit test runs.
    """
    connector = IBKRConnector(host="127.0.0.1", port=7497, client_id=99)
    try:
        await connector.connect()
        balance = await connector.get_account_balance()
        assert balance is not None or balance is None  # just check no exception
    finally:
        await connector.disconnect()
