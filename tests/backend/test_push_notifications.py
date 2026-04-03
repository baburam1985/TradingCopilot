"""
Tests for VAPID browser push notification support.
TDD: Tests written before implementation.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))


# ---------------------------------------------------------------------------
# notifications/push.py
# ---------------------------------------------------------------------------

class TestIsPushConfigured:
    def test_returns_true_when_all_vapid_vars_set(self, monkeypatch):
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "private_key_value")
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "public_key_value")
        monkeypatch.setenv("VAPID_CLAIM_EMAIL", "alerts@example.com")
        from notifications.push import is_push_configured
        assert is_push_configured() is True

    def test_returns_false_when_private_key_missing(self, monkeypatch):
        monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "public_key_value")
        monkeypatch.setenv("VAPID_CLAIM_EMAIL", "alerts@example.com")
        from notifications.push import is_push_configured
        assert is_push_configured() is False

    def test_returns_false_when_public_key_missing(self, monkeypatch):
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "private_key_value")
        monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
        monkeypatch.setenv("VAPID_CLAIM_EMAIL", "alerts@example.com")
        from notifications.push import is_push_configured
        assert is_push_configured() is False

    def test_returns_false_when_claim_email_missing(self, monkeypatch):
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "private_key_value")
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "public_key_value")
        monkeypatch.delenv("VAPID_CLAIM_EMAIL", raising=False)
        from notifications.push import is_push_configured
        assert is_push_configured() is False

    def test_returns_false_when_no_vars_set(self, monkeypatch):
        for k in ("VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_CLAIM_EMAIL"):
            monkeypatch.delenv(k, raising=False)
        from notifications.push import is_push_configured
        assert is_push_configured() is False


class TestSendPush:
    def _make_subscription(self):
        """Build a minimal PushSubscription-like object."""
        sub = MagicMock()
        sub.endpoint = "https://fcm.googleapis.com/fcm/send/abc123"
        sub.p256dh = "p256dh_key_base64"
        sub.auth = "auth_secret_base64"
        return sub

    def test_calls_webpush_with_correct_args(self, monkeypatch):
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "private_key_value")
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "public_key_value")
        monkeypatch.setenv("VAPID_CLAIM_EMAIL", "alerts@example.com")

        mock_webpush = MagicMock()
        monkeypatch.setattr("notifications.push.webpush", mock_webpush)
        monkeypatch.setattr("notifications.push.is_push_configured", lambda: True)

        from notifications.push import send_push
        sub = self._make_subscription()
        send_push(sub, title="Trade Alert", body="AAPL bought at $150", data={"symbol": "AAPL"})

        mock_webpush.assert_called_once()
        call_kwargs = mock_webpush.call_args[1]
        assert call_kwargs["subscription_info"]["endpoint"] == sub.endpoint
        assert call_kwargs["subscription_info"]["keys"]["p256dh"] == sub.p256dh
        assert call_kwargs["subscription_info"]["keys"]["auth"] == sub.auth
        assert call_kwargs["vapid_private_key"] == "private_key_value"
        assert call_kwargs["vapid_claims"]["sub"] == "mailto:alerts@example.com"

    def test_noop_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("notifications.push.is_push_configured", lambda: False)
        mock_webpush = MagicMock()
        monkeypatch.setattr("notifications.push.webpush", mock_webpush)

        from notifications.push import send_push
        sub = self._make_subscription()
        send_push(sub, title="T", body="B")

        mock_webpush.assert_not_called()

    def test_swallows_webpush_exception(self, monkeypatch):
        """WebPushException during send must not propagate."""
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "private_key_value")
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "public_key_value")
        monkeypatch.setenv("VAPID_CLAIM_EMAIL", "alerts@example.com")
        monkeypatch.setattr("notifications.push.is_push_configured", lambda: True)

        # Simulate WebPushException (subclass of Exception for testing)
        mock_webpush = MagicMock(side_effect=Exception("push delivery failed"))
        monkeypatch.setattr("notifications.push.webpush", mock_webpush)

        from notifications.push import send_push
        sub = self._make_subscription()
        # Must not raise
        send_push(sub, title="T", body="B")

    def test_send_push_encodes_json_data_in_message(self, monkeypatch):
        """The data dict should appear as JSON in the push message body."""
        monkeypatch.setenv("VAPID_PRIVATE_KEY", "pk")
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "pubk")
        monkeypatch.setenv("VAPID_CLAIM_EMAIL", "alerts@example.com")
        monkeypatch.setattr("notifications.push.is_push_configured", lambda: True)

        captured = {}

        def capture_webpush(**kwargs):
            captured.update(kwargs)

        monkeypatch.setattr("notifications.push.webpush", capture_webpush)

        from notifications.push import send_push
        import json
        sub = self._make_subscription()
        send_push(sub, title="Alert", body="msg", data={"type": "trade_executed"})

        message_str = captured["data"]
        message = json.loads(message_str)
        assert message["title"] == "Alert"
        assert message["body"] == "msg"
        assert message["data"]["type"] == "trade_executed"


# ---------------------------------------------------------------------------
# models/push_subscription.py
# ---------------------------------------------------------------------------

class TestPushSubscriptionModel:
    def test_model_has_required_columns(self):
        from models.push_subscription import PushSubscription
        # Verify SQLAlchemy column names exist on the mapped table
        cols = {c.name for c in PushSubscription.__table__.columns}
        assert "id" in cols
        assert "session_id" in cols
        assert "endpoint" in cols
        assert "p256dh" in cols
        assert "auth" in cols
        assert "created_at" in cols

    def test_model_tablename(self):
        from models.push_subscription import PushSubscription
        assert PushSubscription.__tablename__ == "push_subscriptions"

    def test_model_instantiation(self):
        from models.push_subscription import PushSubscription
        sub = PushSubscription(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            endpoint="https://fcm.googleapis.com/fcm/send/abc",
            p256dh="p256dh_key",
            auth="auth_secret",
            created_at=datetime.now(timezone.utc),
        )
        assert sub.endpoint == "https://fcm.googleapis.com/fcm/send/abc"
        assert sub.p256dh == "p256dh_key"
        assert sub.auth == "auth_secret"


# ---------------------------------------------------------------------------
# alert_engine.py — push integration
# ---------------------------------------------------------------------------

def _make_fake_session(notify_email=False, email_address=None, notify_push=True):
    session = MagicMock()
    session.id = uuid.uuid4()
    session.notify_email = notify_email
    session.email_address = email_address
    session.notify_push = notify_push
    return session


def _make_fake_db(push_subscriptions=None):
    """Return a mock async db session with optional push subscriptions result."""
    db = AsyncMock()
    db.add = MagicMock()

    if push_subscriptions is not None:
        # Mock scalars().all() for the push subscription query
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = push_subscriptions
        db.execute = AsyncMock(return_value=result_mock)

    return db


@pytest.mark.asyncio
async def test_alert_engine_calls_push_when_subscriptions_exist(monkeypatch):
    """AlertEngine.fire() should call send_push for each subscription."""
    from notifications.alert_engine import AlertEngine

    session = _make_fake_session(notify_push=True)

    # Build a mock subscription
    mock_sub = MagicMock()
    mock_sub.endpoint = "https://fcm.googleapis.com/test"
    mock_sub.p256dh = "key"
    mock_sub.auth = "auth"

    db = _make_fake_db(push_subscriptions=[mock_sub])

    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        AsyncMock(),
    )
    mock_send_push = MagicMock()
    monkeypatch.setattr("notifications.alert_engine.send_push", mock_send_push)

    engine = AlertEngine()
    await engine.fire(
        session=session,
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL at $150",
        db=db,
    )

    mock_send_push.assert_called_once_with(
        mock_sub,
        title="Buy Signal",
        body="AAPL at $150",
        data={"event_type": "trade_executed", "level": "info"},
    )


@pytest.mark.asyncio
async def test_alert_engine_push_failure_does_not_propagate(monkeypatch):
    """Push delivery errors must be swallowed, not propagated."""
    from notifications.alert_engine import AlertEngine

    session = _make_fake_session(notify_push=True)
    mock_sub = MagicMock()
    db = _make_fake_db(push_subscriptions=[mock_sub])

    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "notifications.alert_engine.send_push",
        MagicMock(side_effect=Exception("push failed")),
    )

    engine = AlertEngine()
    # Must not raise
    await engine.fire(
        session=session,
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL at $150",
        db=db,
    )


@pytest.mark.asyncio
async def test_alert_engine_no_push_when_no_session(monkeypatch):
    """When session is None, push delivery must not be attempted."""
    from notifications.alert_engine import AlertEngine

    db = _make_fake_db(push_subscriptions=[])

    monkeypatch.setattr(
        "notifications.alert_engine.notification_broadcaster.broadcast",
        AsyncMock(),
    )
    mock_send_push = MagicMock()
    monkeypatch.setattr("notifications.alert_engine.send_push", mock_send_push)

    engine = AlertEngine()
    await engine.fire(
        session=None,
        event_type="session_ended",
        level="info",
        title="Done",
        message="No session",
        db=db,
    )

    mock_send_push.assert_not_called()
