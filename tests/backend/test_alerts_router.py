"""Tests for GET /alerts, PATCH /alerts/{id}/read, POST /alerts/mark-all-read."""
import sys
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from routers.alerts import router
from models.alert_event import AlertEvent
from database import get_db


def _make_event(session_id=None, read_at=None, created_at=None) -> AlertEvent:
    return AlertEvent(
        id=uuid.uuid4(),
        session_id=session_id or uuid.uuid4(),
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL: buy at $150",
        delivered_email=False,
        read_at=read_at,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _make_app(mock_db: AsyncSession) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/alerts")
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


# --- GET /alerts ---

def test_list_alerts_returns_events():
    session_id = uuid.uuid4()
    events = [_make_event(session_id=session_id) for _ in range(3)]

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = events
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_app(mock_db)
    response = client.get(f"/alerts?session_id={session_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_list_alerts_no_filter():
    events = [_make_event() for _ in range(2)]

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = events
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_app(mock_db)
    response = client.get("/alerts")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_alerts_unread_only_param():
    """Verify unread_only=true is accepted without error."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    client = _make_app(mock_db)
    response = client.get("/alerts?unread_only=true")
    assert response.status_code == 200


# --- PATCH /alerts/{event_id}/read ---

def test_mark_read_sets_read_at():
    event = _make_event()
    event.read_at = None

    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.get = AsyncMock(return_value=event)
    mock_db.refresh = AsyncMock()

    client = _make_app(mock_db)
    response = client.patch(f"/alerts/{event.id}/read")
    assert response.status_code == 200
    mock_db.commit.assert_called_once()


def test_mark_read_already_read_no_extra_commit():
    event = _make_event(read_at=datetime.now(timezone.utc))

    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.get = AsyncMock(return_value=event)

    client = _make_app(mock_db)
    response = client.patch(f"/alerts/{event.id}/read")
    assert response.status_code == 200
    mock_db.commit.assert_not_called()


def test_mark_read_not_found():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.get = AsyncMock(return_value=None)

    client = _make_app(mock_db)
    response = client.patch(f"/alerts/{uuid.uuid4()}/read")
    assert response.status_code == 404


# --- POST /alerts/mark-all-read ---

def test_mark_all_read():
    session_id = uuid.uuid4()

    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(return_value=MagicMock())

    client = _make_app(mock_db)
    response = client.post(f"/alerts/mark-all-read?session_id={session_id}")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_db.commit.assert_called_once()
