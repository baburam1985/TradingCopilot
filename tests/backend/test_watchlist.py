import uuid
import pytest
from datetime import datetime, timezone
from models.watchlist_item import WatchlistItem


def test_watchlist_item_attributes():
    item = WatchlistItem(
        symbol="AAPL",
        strategy="rsi",
        strategy_params={"period": 14, "oversold": 30, "overbought": 70},
        alert_threshold=180.0,
        notify_email=True,
        email_address="trader@example.com",
        created_at=datetime.now(timezone.utc),
    )
    assert item.symbol == "AAPL"
    assert item.strategy == "rsi"
    assert item.strategy_params["period"] == 14
    assert item.alert_threshold == 180.0
    assert item.notify_email is True
    assert item.email_address == "trader@example.com"
    assert item.last_signal is None
    assert item.last_price is None
    assert item.last_evaluated_at is None


import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timezone
import uuid

# ---------------------------------------------------------------------------
# Shared fixture: FastAPI test app with watchlist router
# ---------------------------------------------------------------------------

@pytest.fixture
def watchlist_app():
    from routers.watchlist import router
    app = FastAPI()
    app.include_router(router, prefix="/watchlist")
    return app


@pytest.fixture
def item_id():
    return uuid.uuid4()


def make_item(item_id):
    item = MagicMock()
    item.id = item_id
    item.symbol = "AAPL"
    item.strategy = "rsi"
    item.strategy_params = {"period": 14}
    item.alert_threshold = 180.0
    item.notify_email = False
    item.email_address = None
    item.last_signal = None
    item.last_price = None
    item.last_evaluated_at = None
    item.created_at = datetime.now(timezone.utc)
    return item


def test_create_watchlist_item_returns_201(watchlist_app, item_id):
    mock_db = AsyncMock()
    mock_item = make_item(item_id)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def fake_get_db():
        yield mock_db

    from database import get_db
    watchlist_app.dependency_overrides[get_db] = fake_get_db

    with patch("routers.watchlist.register_watchlist_symbol") as mock_reg, \
         patch("routers.watchlist.WatchlistItem", return_value=mock_item):
        client = TestClient(watchlist_app)
        resp = client.post("/watchlist", json={
            "symbol": "AAPL",
            "strategy": "rsi",
            "strategy_params": {"period": 14},
        })
    assert resp.status_code == 200
    mock_reg.assert_called_once_with("AAPL")


def test_delete_watchlist_item_calls_unregister(watchlist_app, item_id):
    mock_db = AsyncMock()
    mock_item = make_item(item_id)
    mock_db.get = AsyncMock(return_value=mock_item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    async def fake_get_db():
        yield mock_db

    from database import get_db
    watchlist_app.dependency_overrides[get_db] = fake_get_db

    with patch("routers.watchlist.unregister_watchlist_symbol") as mock_unreg:
        client = TestClient(watchlist_app)
        resp = client.delete(f"/watchlist/{item_id}")
    assert resp.status_code == 200
    mock_unreg.assert_called_once_with("AAPL")


def test_delete_watchlist_item_404_when_not_found(watchlist_app, item_id):
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    async def fake_get_db():
        yield mock_db

    from database import get_db
    watchlist_app.dependency_overrides[get_db] = fake_get_db

    with patch("routers.watchlist.unregister_watchlist_symbol"):
        client = TestClient(watchlist_app)
        resp = client.delete(f"/watchlist/{item_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Broadcaster watchlist tests
# ---------------------------------------------------------------------------


def test_broadcaster_register_watchlist():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws = MagicMock()
    b.register_watchlist(ws)
    assert ws in b._watchlist_connections


def test_broadcaster_unregister_watchlist():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws = MagicMock()
    b.register_watchlist(ws)
    b.unregister_watchlist(ws)
    assert ws not in b._watchlist_connections


def test_broadcaster_unregister_watchlist_tolerates_missing():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws = MagicMock()
    b.unregister_watchlist(ws)  # should not raise


@pytest.mark.asyncio
async def test_broadcaster_broadcast_watchlist_sends_to_all():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    b.register_watchlist(ws1)
    b.register_watchlist(ws2)
    payload = {"type": "notification", "level": "info", "title": "T", "message": "M"}
    await b.broadcast_watchlist(payload)
    ws1.send_text.assert_called_once()
    ws2.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_broadcaster_broadcast_watchlist_removes_dead_connections():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws_ok = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = Exception("connection closed")
    b.register_watchlist(ws_ok)
    b.register_watchlist(ws_dead)
    await b.broadcast_watchlist({"type": "notification"})
    assert ws_dead not in b._watchlist_connections
    assert ws_ok in b._watchlist_connections


# ---------------------------------------------------------------------------
# Scheduler watchlist tests
# ---------------------------------------------------------------------------


def test_register_and_unregister_watchlist_symbol():
    import importlib
    import scheduler.scraper_job as job
    importlib.reload(job)  # reset module-level sets

    job.register_watchlist_symbol("AAPL")
    assert "AAPL" in job._watchlist_symbols

    job.unregister_watchlist_symbol("AAPL")
    assert "AAPL" not in job._watchlist_symbols


def test_register_watchlist_symbol_uppercased():
    import importlib
    import scheduler.scraper_job as job
    importlib.reload(job)

    job.register_watchlist_symbol("tsla")
    assert "TSLA" in job._watchlist_symbols
    job.unregister_watchlist_symbol("TSLA")


def test_unregister_watchlist_symbol_does_not_remove_active_session_symbol():
    """Removing a watchlist symbol should not stop scraping if a session also watches it."""
    import importlib
    import scheduler.scraper_job as job
    importlib.reload(job)

    job.register_symbol("AAPL")          # session registration
    job.register_watchlist_symbol("AAPL") # watchlist registration
    job.unregister_watchlist_symbol("AAPL")

    # Symbol must still be scraped because an active session uses it
    assert "AAPL" in job._active_symbols


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_broadcasts_on_buy():
    import importlib
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "buy"
    mock_signal.reason = "RSI oversold"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "AAPL"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = None
    mock_item.last_price = None
    mock_item.notify_email = False
    mock_item.email_address = None

    mock_bar = MagicMock()
    mock_bar.close = 182.0

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        # First call returns watchlist items; second returns price history bars
        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("AAPL", 182.0)

    mock_broadcaster.broadcast_watchlist.assert_called_once()
    call_payload = mock_broadcaster.broadcast_watchlist.call_args[0][0]
    assert call_payload["level"] == "info"
    assert "BUY" in call_payload["message"]
    assert "AAPL" in call_payload["title"]


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_no_broadcast_on_hold():
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "hold"
    mock_signal.reason = "neutral"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "MSFT"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = None
    mock_item.last_price = None
    mock_item.notify_email = False
    mock_item.email_address = None

    mock_bar = MagicMock()
    mock_bar.close = 300.0

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("MSFT", 300.0)

    mock_broadcaster.broadcast_watchlist.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_broadcasts_on_sell():
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "sell"
    mock_signal.reason = "RSI overbought"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "AAPL"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = None
    mock_item.last_price = None
    mock_item.notify_email = False
    mock_item.email_address = None

    mock_bar = MagicMock()
    mock_bar.close = 190.0

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("AAPL", 190.0)

    mock_broadcaster.broadcast_watchlist.assert_called_once()
    call_payload = mock_broadcaster.broadcast_watchlist.call_args[0][0]
    assert call_payload["level"] == "info"
    assert "SELL" in call_payload["message"]


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_broadcasts_threshold_crossing():
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "hold"
    mock_signal.reason = "neutral"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "AAPL"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = 185.0   # threshold to cross
    mock_item.last_price = 182.0        # price was below threshold
    mock_item.notify_email = False
    mock_item.email_address = None

    mock_bar = MagicMock()
    mock_bar.close = 186.0  # price crossed above threshold

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("AAPL", 186.0)

    mock_broadcaster.broadcast_watchlist.assert_called_once()
    call_payload = mock_broadcaster.broadcast_watchlist.call_args[0][0]
    assert call_payload["level"] == "warning"
    assert "185.00" in call_payload["message"]


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_sends_email_on_buy():
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "buy"
    mock_signal.reason = "RSI oversold"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "AAPL"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = None
    mock_item.last_price = None
    mock_item.notify_email = True
    mock_item.email_address = "trader@test.com"

    mock_bar = MagicMock()
    mock_bar.close = 182.0

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster, \
         patch("notifications.email.send_trade_email") as mock_email:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("AAPL", 182.0)

    mock_email.assert_called_once()
    call_args = mock_email.call_args
    assert call_args[0][0] == "trader@test.com"
    assert "AAPL" in call_args[0][1]
