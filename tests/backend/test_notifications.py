import pytest
import asyncio
import json
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
