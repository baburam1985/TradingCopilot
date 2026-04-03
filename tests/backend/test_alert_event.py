"""Round-trip tests for the AlertEvent model."""
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from models.alert_event import AlertEvent


def _make_event(**overrides) -> AlertEvent:
    defaults = dict(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        event_type="trade_executed",
        level="info",
        title="Buy Signal",
        message="AAPL: buy at $150.00 — MA crossover",
        delivered_email=False,
        read_at=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return AlertEvent(**defaults)


def test_alert_event_fields():
    event = _make_event()
    assert event.event_type == "trade_executed"
    assert event.level == "info"
    assert event.title == "Buy Signal"
    assert event.delivered_email is False
    assert event.read_at is None


def test_alert_event_nullable_session_id():
    event = _make_event(session_id=None)
    assert event.session_id is None


def test_alert_event_all_event_types():
    for et in ("trade_executed", "stop_loss", "take_profit", "daily_loss_limit", "session_ended"):
        event = _make_event(event_type=et)
        assert event.event_type == et


def test_alert_event_all_levels():
    for lvl in ("info", "warning", "danger"):
        event = _make_event(level=lvl)
        assert event.level == lvl


def test_alert_event_read_at_settable():
    now = datetime.now(timezone.utc)
    event = _make_event(read_at=now)
    assert event.read_at == now


def test_alert_event_delivered_email_true():
    event = _make_event(delivered_email=True)
    assert event.delivered_email is True


def test_alert_event_tablename():
    assert AlertEvent.__tablename__ == "alert_events"
