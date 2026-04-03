import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from notifications.broadcaster import NotificationBroadcaster, build_notification_payload
from notifications.email import send_trade_email, is_email_configured


# --- broadcaster ---

def test_build_notification_payload_structure():
    payload = build_notification_payload(
        level="warning",
        title="Stop-Loss Hit",
        message="Trade closed at $95.00",
    )
    assert payload["type"] == "notification"
    assert payload["level"] == "warning"
    assert payload["title"] == "Stop-Loss Hit"
    assert payload["message"] == "Trade closed at $95.00"
    assert "ts" in payload


def test_build_notification_payload_valid_levels():
    for level in ("info", "warning", "danger"):
        p = build_notification_payload(level=level, title="T", message="M")
        assert p["level"] == level


@pytest.mark.asyncio
async def test_register_and_broadcast():
    broadcaster = NotificationBroadcaster()
    session_id = uuid.uuid4()

    ws = AsyncMock()
    broadcaster.register(session_id, ws)

    payload = build_notification_payload("info", "Buy Signal", "Bought at $100")
    await broadcaster.broadcast(session_id, payload)

    ws.send_text.assert_called_once()
    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "notification"
    assert sent["title"] == "Buy Signal"


@pytest.mark.asyncio
async def test_broadcast_no_connection_does_not_raise():
    broadcaster = NotificationBroadcaster()
    session_id = uuid.uuid4()
    payload = build_notification_payload("info", "T", "M")
    # Should not raise — no connection registered
    await broadcaster.broadcast(session_id, payload)


@pytest.mark.asyncio
async def test_unregister_stops_delivery():
    broadcaster = NotificationBroadcaster()
    session_id = uuid.uuid4()
    ws = AsyncMock()

    broadcaster.register(session_id, ws)
    broadcaster.unregister(session_id)

    payload = build_notification_payload("info", "T", "M")
    await broadcaster.broadcast(session_id, payload)

    ws.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_broadcast_swallows_send_error():
    """If WebSocket.send_text raises, broadcast should not propagate."""
    broadcaster = NotificationBroadcaster()
    session_id = uuid.uuid4()
    ws = AsyncMock()
    ws.send_text.side_effect = RuntimeError("connection dropped")
    broadcaster.register(session_id, ws)

    payload = build_notification_payload("info", "T", "M")
    # Must not raise
    await broadcaster.broadcast(session_id, payload)
    # Connection should have been cleaned up
    assert session_id not in broadcaster._connections


# --- email ---

def test_is_email_configured_true(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "alerts@example.com")
    assert is_email_configured() is True


def test_is_email_configured_false(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    assert is_email_configured() is False


def test_send_trade_email_sends_when_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "alerts@example.com")

    with patch("notifications.email.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        send_trade_email(
            to_address="trader@example.com",
            subject="Buy signal fired",
            body="AAPL: bought at $150.00",
        )
        mock_smtp.sendmail.assert_called_once()


def test_send_trade_email_no_op_when_not_configured(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)

    with patch("notifications.email.smtplib.SMTP") as mock_smtp_cls:
        send_trade_email(
            to_address="trader@example.com",
            subject="Buy signal fired",
            body="AAPL: bought at $150.00",
        )
        mock_smtp_cls.assert_not_called()


# --- AlertEngine ---

def _make_fake_session(notify_email=False, email_address=None):
    session = MagicMock()
    session.id = uuid.uuid4()
    session.notify_email = notify_email
    session.email_address = email_address
    return session


def _make_fake_db():
    """Return a mock async db session. add() is sync; commit/refresh are async."""
    db = AsyncMock()
    db.add = MagicMock()  # SQLAlchemy Session.add() is synchronous
    # Support the push subscription query added to alert_engine: returns empty list
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)
    return db


@pytest.mark.asyncio
async def test_alert_engine_fire_persists(monkeypatch):
    from notifications.alert_engine import AlertEngine
    from models.alert_event import AlertEvent

    session = _make_fake_session()
    db = _make_fake_db()

    # Patch broadcaster to avoid real WS calls
    mock_broadcast = AsyncMock()
    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        mock_broadcast,
    )

    engine = AlertEngine()
    event = await engine.fire(
        session=session,
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL: buy at $150",
        db=db,
    )

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert isinstance(added, AlertEvent)
    assert added.event_type == "trade_executed"
    assert added.level == "info"
    assert added.session_id == session.id
    assert db.commit.called


@pytest.mark.asyncio
async def test_alert_engine_fire_broadcasts(monkeypatch):
    from notifications.alert_engine import AlertEngine

    session = _make_fake_session()
    db = _make_fake_db()

    mock_broadcast = AsyncMock()
    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        mock_broadcast,
    )

    engine = AlertEngine()
    await engine.fire(
        session=session,
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL: buy at $150",
        db=db,
    )

    mock_broadcast.assert_called_once()
    call_args = mock_broadcast.call_args[0]
    assert call_args[0] == session.id
    assert call_args[1]["level"] == "info"
    assert call_args[1]["title"] == "Buy Signal"


@pytest.mark.asyncio
async def test_alert_engine_fire_sends_email_when_configured(monkeypatch):
    from notifications.alert_engine import AlertEngine

    session = _make_fake_session(notify_email=True, email_address="trader@example.com")
    db = _make_fake_db()

    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        AsyncMock(),
    )
    # The lazy import inside fire() resolves to notifications.email.send_trade_email
    mock_send = MagicMock()
    monkeypatch.setattr("notifications.email.send_trade_email", mock_send)

    engine = AlertEngine()
    await engine.fire(
        session=session,
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL: buy at $150",
        db=db,
    )

    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_alert_engine_fire_email_failure_does_not_propagate(monkeypatch):
    from notifications.alert_engine import AlertEngine

    session = _make_fake_session(notify_email=True, email_address="trader@example.com")
    db = _make_fake_db()

    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        AsyncMock(),
    )
    # Make send_trade_email raise so we can verify the failure is swallowed
    monkeypatch.setattr(
        "notifications.email.send_trade_email",
        MagicMock(side_effect=Exception("SMTP error")),
    )

    engine = AlertEngine()
    # Must not raise
    await engine.fire(
        session=session,
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL: buy at $150",
        db=db,
    )


@pytest.mark.asyncio
async def test_alert_engine_fire_no_session():
    from notifications.alert_engine import AlertEngine
    from models.alert_event import AlertEvent

    db = _make_fake_db()

    engine = AlertEngine()
    event = await engine.fire(
        session=None,
        event_type="session_ended",
        level="info",
        title="Session ended",
        message="No session context",
        db=db,
    )

    added = db.add.call_args[0][0]
    assert added.session_id is None
