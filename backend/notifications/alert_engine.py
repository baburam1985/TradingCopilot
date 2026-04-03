import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert_event import AlertEvent
from models.push_subscription import PushSubscription
from notifications.broadcaster import notification_broadcaster, build_notification_payload
from notifications.push import send_push

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
        """Persist, broadcast, and optionally email/push an alert event.

        Fire order: (1) persist to DB, (2) WS push, (3) browser push, (4) email if configured.
        Delivery failures are caught — log warning, never propagate.
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

        # Browser push (Web Push / VAPID), failure-safe
        if session is not None:
            result = await db.execute(
                select(PushSubscription).where(PushSubscription.session_id == session.id)
            )
            subscriptions = result.scalars().all()
            for sub in subscriptions:
                try:
                    send_push(
                        sub,
                        title=title,
                        body=message,
                        data={"event_type": event_type, "level": level},
                    )
                except Exception as exc:
                    logger.warning("Push notification delivery failed: %s", exc)

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
