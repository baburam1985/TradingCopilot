"""Unit tests for the schedules CRUD router (/sessions/schedules).

Uses a minimal FastAPI app with mocked DB — no live database required.
"""

import sys
import os
import uuid
from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from routers.schedules import router
from database import get_db


def _make_mini_app(mock_db):
    app = FastAPI()
    app.include_router(router, prefix="/sessions/schedules")
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app)


def _make_mock_db():
    return AsyncMock()


def _mock_schedule(symbol="AAPL"):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.symbol = symbol
    s.strategy = "ma_crossover"
    s.strategy_params = {}
    s.capital = 100.0
    s.mode = "paper"
    s.days_of_week = [0, 1, 2, 3, 4]
    s.start_time_et = time(9, 30)
    s.stop_time_et = None
    s.stop_loss_pct = None
    s.take_profit_pct = None
    s.max_position_pct = None
    s.auto_stop_daily_loss_pct = None
    s.auto_stop_max_trades = None
    s.is_active = True
    s.last_triggered_date = None
    s.last_session_id = None
    s.last_run_status = None
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    return s


CREATE_PAYLOAD = {
    "symbol": "AAPL",
    "strategy": "ma_crossover",
    "strategy_params": {"short_window": 9, "long_window": 21},
    "capital": 1000.0,
    "mode": "paper",
    "days_of_week": [0, 1, 2, 3, 4],
    "start_time_et": "09:30",
    "stop_time_et": "16:00",
    "auto_stop_daily_loss_pct": 5.0,
    "auto_stop_max_trades": 10,
}


class TestCreateSchedule:
    def test_create_schedule_returns_201(self):
        db = _make_mock_db()
        db.refresh = AsyncMock()

        client = _make_mini_app(db)
        resp = client.post("/sessions/schedules", json=CREATE_PAYLOAD)
        assert resp.status_code == 201
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_invalid_days_raises_422(self):
        db = _make_mock_db()
        client = _make_mini_app(db)

        bad_payload = {**CREATE_PAYLOAD, "days_of_week": [7]}
        resp = client.post("/sessions/schedules", json=bad_payload)
        assert resp.status_code == 422

    def test_create_empty_days_raises_422(self):
        db = _make_mock_db()
        client = _make_mini_app(db)

        bad_payload = {**CREATE_PAYLOAD, "days_of_week": []}
        resp = client.post("/sessions/schedules", json=bad_payload)
        assert resp.status_code == 422

    def test_create_invalid_time_format_raises_422(self):
        db = _make_mock_db()
        client = _make_mini_app(db)

        bad_payload = {**CREATE_PAYLOAD, "start_time_et": "9:30am"}
        resp = client.post("/sessions/schedules", json=bad_payload)
        assert resp.status_code == 422


class TestListSchedules:
    def test_list_returns_schedules(self):
        db = _make_mock_db()
        schedules = [_mock_schedule("AAPL"), _mock_schedule("TSLA")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = schedules
        db.execute = AsyncMock(return_value=mock_result)

        client = _make_mini_app(db)
        resp = client.get("/sessions/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_list_returns_empty_list_when_none(self):
        db = _make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        client = _make_mini_app(db)
        resp = client.get("/sessions/schedules")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetSchedule:
    def test_get_existing_schedule(self):
        db = _make_mock_db()
        sched = _mock_schedule()
        db.get = AsyncMock(return_value=sched)

        client = _make_mini_app(db)
        resp = client.get(f"/sessions/schedules/{sched.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"

    def test_get_missing_schedule_returns_404(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        client = _make_mini_app(db)
        resp = client.get(f"/sessions/schedules/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_response_includes_next_run_at_field(self):
        db = _make_mock_db()
        sched = _mock_schedule()
        db.get = AsyncMock(return_value=sched)

        client = _make_mini_app(db)
        resp = client.get(f"/sessions/schedules/{sched.id}")
        assert resp.status_code == 200
        data = resp.json()
        # next_run_at may be None or a string but the key must exist
        assert "next_run_at" in data


class TestPauseSchedule:
    def test_pause_schedule_sets_is_active_false(self):
        db = _make_mock_db()
        sched = _mock_schedule()
        sched.last_run_status = None
        db.get = AsyncMock(return_value=sched)
        db.refresh = AsyncMock()

        client = _make_mini_app(db)
        resp = client.patch(f"/sessions/schedules/{sched.id}", json={"is_active": False})
        assert resp.status_code == 200
        assert sched.is_active is False

    def test_patch_running_schedule_rejects_symbol_change(self):
        db = _make_mock_db()
        sched = _mock_schedule()
        sched.last_run_status = "running"
        db.get = AsyncMock(return_value=sched)

        client = _make_mini_app(db)
        resp = client.patch(f"/sessions/schedules/{sched.id}", json={"symbol": "TSLA"})
        assert resp.status_code == 422

    def test_patch_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        client = _make_mini_app(db)
        resp = client.patch(f"/sessions/schedules/{uuid.uuid4()}", json={"is_active": True})
        assert resp.status_code == 404


class TestDeleteSchedule:
    def test_delete_removes_schedule(self):
        db = _make_mock_db()
        sched = _mock_schedule()
        db.get = AsyncMock(return_value=sched)
        db.delete = AsyncMock()

        client = _make_mini_app(db)
        resp = client.delete(f"/sessions/schedules/{sched.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        db.delete.assert_called_once_with(sched)

    def test_delete_returns_404_when_not_found(self):
        db = _make_mock_db()
        db.get = AsyncMock(return_value=None)

        client = _make_mini_app(db)
        resp = client.delete(f"/sessions/schedules/{uuid.uuid4()}")
        assert resp.status_code == 404
