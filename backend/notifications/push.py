import json
import logging
import os

from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)


def is_push_configured() -> bool:
    """Return True if all required VAPID env vars are set."""
    required = ("VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_CLAIM_EMAIL")
    return all(os.environ.get(k) for k in required)


def send_push(subscription, title: str, body: str, data: dict | None = None) -> None:
    """Send a Web Push notification to the given PushSubscription.

    No-op if VAPID is not configured. Delivery errors are caught and logged
    so callers are never interrupted by push failures.
    """
    if not is_push_configured():
        return

    private_key = os.environ["VAPID_PRIVATE_KEY"]
    claim_email = os.environ["VAPID_CLAIM_EMAIL"]

    message = json.dumps({"title": title, "body": body, "data": data or {}})

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=message,
            vapid_private_key=private_key,
            vapid_claims={"sub": f"mailto:{claim_email}"},
        )
    except Exception as exc:
        logger.warning("Push notification delivery failed: %s", exc)
