"""Tests for the watchlist router (/watchlist).

Uses a minimal FastAPI app (not main.app) since the watchlist router
is not yet registered in main.py.
"""

import sys
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from routers.watchlist import router
from database import get_db


def _make_mini_app(mock_db):
    """Build a throwaway FastAPI app with just the watchlist router and a mocked DB."""
    app = FastAPI()
    app.include_router(router, prefix="/watchlist")
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


def _make_mock_db():
    return AsyncMock()


def _mock_item(symbol="AAPL"):
    item = MagicMock()
    item.id = uuid.uuid4()
    item.symbol = symbol.upper()
    item.strategy = "rsi"
    item.strategy_params = {"period": 14}
    item.alert_threshold = None
    item.notify_email = False
    item.email_address = None
    item.created_at = datetime.now(timezone.utc)
    return item


class TestWatchlistRouter:
    def test_list_watchlist_returns_items(self):
        db = _make_mock_db()
        items = [_mock_item("AAPL"), _mock_item("TSLA")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        db.execute = AsyncMock(return_value=mock_result)

        client = _make_mini_app(db)
        resp = client.get("/watchlist")
        assert resp.status_code == 200

    def test_create_watchlist_item(self):
        db = _make_mock_db()
        db.refresh = AsyncMock()

        with patch("routers.watchlist.register_watchlist_symbol"):
            client = _make_mini_app(db)
            resp = client.post("/watchlist", json={
                "symbol": "AAPL",
                "strategy": "rsi",
                "strategy_params": {"period": 14},
                "alert_threshold": 5.0,
                "notify_email": True,
                "email_address": "watcher@example.com",
            })
        assert resp.status_code == 200
        db.add.assert_called_once()

    def test_get_watchlist_item_returns_item(self):
        db = _make_mock_db()
        item = _mock_item()
        db.get = AsyncMock(return_value=item)

        client = _make_mini_app(db)
        resp = client.get(f"/watchlist/{item.id}")
        assert resp.status_code == 200

    def test_get_watchlist_item_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        client = _make_mini_app(db)
        resp = client.get(f"/watchlist/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_watchlist_item_patches_fields(self):
        db = _make_mock_db()
        item = _mock_item()
        item.notify_email = False
        db.get = AsyncMock(return_value=item)
        db.refresh = AsyncMock()

        client = _make_mini_app(db)
        resp = client.patch(f"/watchlist/{item.id}", json={
            "strategy": "macd",
            "alert_threshold": 2.5,
            "notify_email": True,
            "email_address": "alert@example.com",
        })
        assert resp.status_code == 200
        assert item.strategy == "macd"
        assert item.alert_threshold == 2.5
        assert item.notify_email is True

    def test_update_watchlist_item_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        client = _make_mini_app(db)
        resp = client.patch(f"/watchlist/{uuid.uuid4()}", json={"strategy": "rsi"})
        assert resp.status_code == 404

    def test_delete_watchlist_item_removes_it(self):
        db = _make_mock_db()
        item = _mock_item("AAPL")
        db.get = AsyncMock(return_value=item)
        db.delete = MagicMock()

        with patch("routers.watchlist.unregister_watchlist_symbol"):
            client = _make_mini_app(db)
            resp = client.delete(f"/watchlist/{item.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["symbol"] == "AAPL"
        db.delete.assert_called_once_with(item)

    def test_delete_watchlist_item_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        client = _make_mini_app(db)
        resp = client.delete(f"/watchlist/{uuid.uuid4()}")
        assert resp.status_code == 404
