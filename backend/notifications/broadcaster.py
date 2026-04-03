import json
import uuid
from datetime import datetime, timezone
from fastapi import WebSocket


def build_notification_payload(level: str, title: str, message: str) -> dict:
    """Build a notification dict ready to JSON-serialise and send over WebSocket."""
    return {
        "type": "notification",
        "level": level,   # "info" | "warning" | "danger"
        "title": title,
        "message": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


class NotificationBroadcaster:
    """In-memory registry: session_id -> active WebSocket connection."""

    def __init__(self):
        self._connections: dict[uuid.UUID, WebSocket] = {}

    def register(self, session_id: uuid.UUID, ws: WebSocket) -> None:
        self._connections[session_id] = ws

    def unregister(self, session_id: uuid.UUID) -> None:
        self._connections.pop(session_id, None)

    async def broadcast(self, session_id: uuid.UUID, payload: dict) -> None:
        ws = self._connections.get(session_id)
        if ws is None:
            return
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            # Connection dropped — clean up silently
            self.unregister(session_id)


# Module-level singleton shared across routers and scheduler
notification_broadcaster = NotificationBroadcaster()
