import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from models.alert_event import AlertEvent
from notifications.broadcaster import notification_broadcaster, build_notification_payload

logger = logging.getLogger(__name__)


class AlertEngine:
    async def fire(
        self,
        session,
        event_type: str,
        level: str,
        title: str,
        message: str,
        db: AsyncSession,
    ) -> AlertEvent:
        """Persist, broadcast, and optionally email an alert event.

        Fire order: (1) persist to DB, (2) WS push, (3) email if configured.
        Email failure is caught — log warning, set delivered_email=False, never propagate.
        """
        event = AlertEvent(
            id=uuid.uuid4(),
            session_id=session.id if session is not None else None,
            event_type=event_type,
            level=level,
            title=title,
            message=message,
            delivered_email=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        # WebSocket push
        if session is not None:
            payload = build_notification_payload(level=level, title=title, message=message)
            await notification_broadcaster.broadcast(session.id, payload)

        # Email (optional, failure-safe)
        if session is not None and getattr(session, "notify_email", False) and getattr(session, "email_address", None):
            from notifications.email import send_trade_email
            try:
                send_trade_email(
                    to_address=session.email_address,
                    subject=f"TradingCopilot: {title}",
                    body=message,
                )
                event.delivered_email = True
                await db.commit()
            except Exception as exc:
                logger.warning("Alert email delivery failed: %s", exc)
                # delivered_email remains False — already committed above

        return event
