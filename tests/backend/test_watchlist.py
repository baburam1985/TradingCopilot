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
    mock_db.delete = MagicMock()
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
