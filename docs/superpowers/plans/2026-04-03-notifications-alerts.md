# Notifications & Alerts (AGEAAA-3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-app WebSocket-driven toast notifications and optional email alerts so users know when signals fire or risk guardrails trigger, without watching the dashboard.

**Architecture:** A new `backend/notifications/` package handles two concerns independently — a `broadcaster.py` maintains an in-memory registry of active WebSocket connections keyed by session ID and exposes a `broadcast_notification()` coroutine, while `email.py` wraps Python's stdlib `smtplib` to send SMTP messages when configured. The scheduler (`scraper_job.py`) calls these after every significant event (trade signal, stop-loss, take-profit, circuit breaker). The frontend receives `notification` WebSocket frames and funnels them through a React Context to a fixed toast stack and a slide-out history panel.

**Tech Stack:** Python `smtplib` (stdlib), FastAPI WebSocket, React Context API, Tailwind CSS (existing patterns)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/notifications/__init__.py` | Package marker |
| Create | `backend/notifications/broadcaster.py` | In-memory WS registry + `broadcast_notification()` |
| Create | `backend/notifications/email.py` | SMTP sender, reads `SMTP_*` env vars |
| Modify | `backend/migrations/versions/b2c3d4e5f6a7_add_notification_prefs.py` | DB migration: `notify_email`, `email_address` columns |
| Modify | `backend/models/trading_session.py` | Add `notify_email`, `email_address` ORM fields |
| Modify | `backend/routers/sessions.py` | Accept `notify_email`, `email_address` in `CreateSessionRequest` |
| Modify | `backend/routers/websocket.py` | Register/deregister WS connections with broadcaster |
| Modify | `backend/scheduler/scraper_job.py` | Call broadcaster + email sender on events |
| Create | `tests/backend/test_notifications.py` | Unit tests for broadcaster message construction + email sender |
| Create | `frontend/src/context/NotificationContext.jsx` | Context + Provider: stores list, exposes `addNotification` |
| Create | `frontend/src/components/Toast.jsx` | Auto-dismiss toast stack (fixed bottom-right) |
| Create | `frontend/src/components/NotificationHistory.jsx` | Slide-out panel listing all notifications |
| Modify | `frontend/src/App.jsx` | Wrap tree with `NotificationProvider` |
| Modify | `frontend/src/components/AppShell.jsx` | Render `<Toast />`, wire 🔔 button to history panel |
| Modify | `frontend/src/pages/LiveDashboard.jsx` | Handle `notification` WS frames → `addNotification` |
| Modify | `frontend/src/pages/NewSession.jsx` | Add `notify_email` toggle + `email_address` field |

---

## Task 1: DB Migration — Notification Preferences

**Files:**
- Create: `backend/migrations/versions/b2c3d4e5f6a7_add_notification_prefs.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/migrations/versions/b2c3d4e5f6a7_add_notification_prefs.py
"""add notification prefs to sessions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('notify_email', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sessions', sa.Column('email_address', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'email_address')
    op.drop_column('sessions', 'notify_email')
```

- [ ] **Step 2: Commit**

```bash
git add backend/migrations/versions/b2c3d4e5f6a7_add_notification_prefs.py
git commit -m "feat: migration — add notify_email and email_address to sessions

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 2: Update TradingSession Model

**Files:**
- Modify: `backend/models/trading_session.py`

- [ ] **Step 1: Add ORM fields to `TradingSession`**

In `backend/models/trading_session.py`, after the `daily_max_loss_pct` field, add:

```python
    # Notification preferences
    notify_email: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    email_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

Also add `Boolean, String` to the sqlalchemy import:
```python
from sqlalchemy import String, Numeric, Boolean
```

- [ ] **Step 2: Commit**

```bash
git add backend/models/trading_session.py
git commit -m "feat: add notify_email + email_address to TradingSession model

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 3: Notifications Package — Broadcaster

**Files:**
- Create: `backend/notifications/__init__.py`
- Create: `backend/notifications/broadcaster.py`
- Test: `tests/backend/test_notifications.py`

- [ ] **Step 1: Write failing tests for broadcaster**

```python
# tests/backend/test_notifications.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid
from notifications.broadcaster import NotificationBroadcaster, build_notification_payload


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
    import json
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
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/test_notifications.py -v 2>&1 | head -30
```

Expected: ModuleNotFoundError for `notifications.broadcaster`

- [ ] **Step 3: Create package files**

```python
# backend/notifications/__init__.py
```

```python
# backend/notifications/broadcaster.py
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
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/test_notifications.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/notifications/ tests/backend/test_notifications.py
git commit -m "feat: notifications broadcaster with in-memory WS registry

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 4: Notifications Package — Email Sender

**Files:**
- Modify: `backend/notifications/email.py`
- Modify: `tests/backend/test_notifications.py` (append)

- [ ] **Step 1: Append email tests**

Add to `tests/backend/test_notifications.py`:

```python
import os
from unittest.mock import patch, MagicMock
from notifications.email import send_trade_email, is_email_configured


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
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/test_notifications.py -v -k "email" 2>&1 | head -20
```

Expected: ImportError for `notifications.email`

- [ ] **Step 3: Create email sender**

```python
# backend/notifications/email.py
import os
import smtplib
from email.mime.text import MIMEText


def is_email_configured() -> bool:
    """Return True if all required SMTP env vars are set."""
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")
    return all(os.environ.get(k) for k in required)


def send_trade_email(to_address: str, subject: str, body: str) -> None:
    """Send a plain-text email. No-op if SMTP not configured."""
    if not is_email_configured():
        return

    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    from_addr = os.environ["SMTP_FROM"]

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_address

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(from_addr, [to_address], msg.as_string())
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/test_notifications.py -v
```

Expected: 9 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/notifications/email.py tests/backend/test_notifications.py
git commit -m "feat: SMTP email sender for trade notifications

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 5: Update Sessions Router — Accept Notification Preferences

**Files:**
- Modify: `backend/routers/sessions.py`

- [ ] **Step 1: Add fields to `CreateSessionRequest` and session creation**

In `backend/routers/sessions.py`, update `CreateSessionRequest`:

```python
class CreateSessionRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    mode: str  # "paper" or "live"
    # Risk management (all optional)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_position_pct: Optional[float] = None
    daily_max_loss_pct: Optional[float] = None
    # Notification preferences
    notify_email: bool = False
    email_address: Optional[str] = None
```

Update session construction in `create_session`:

```python
    session = TradingSession(
        symbol=req.symbol.upper(),
        strategy=req.strategy,
        strategy_params=req.strategy_params,
        starting_capital=req.starting_capital,
        mode=req.mode,
        status="active",
        created_at=datetime.now(timezone.utc),
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        max_position_pct=req.max_position_pct,
        daily_max_loss_pct=req.daily_max_loss_pct,
        notify_email=req.notify_email,
        email_address=req.email_address,
    )
```

- [ ] **Step 2: Run existing API tests to confirm no regression**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/test_api.py -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/routers/sessions.py
git commit -m "feat: accept notify_email and email_address in session creation

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 6: Update WebSocket Router — Register/Unregister with Broadcaster

**Files:**
- Modify: `backend/routers/websocket.py`

- [ ] **Step 1: Wire broadcaster registration into the WebSocket lifecycle**

Replace `backend/routers/websocket.py` with:

```python
import uuid
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from database import AsyncSessionLocal
from models.price_history import PriceHistory
from notifications.broadcaster import notification_broadcaster

router = APIRouter()

@router.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: uuid.UUID):
    await websocket.accept()
    notification_broadcaster.register(session_id, websocket)
    last_timestamp = None
    try:
        while True:
            async with AsyncSessionLocal() as db:
                from models.trading_session import TradingSession
                session = await db.get(TradingSession, session_id)
                if not session or session.status == "closed":
                    await websocket.send_text(json.dumps({"type": "session_closed"}))
                    break

                result = await db.execute(
                    select(PriceHistory)
                    .where(PriceHistory.symbol == session.symbol)
                    .order_by(PriceHistory.timestamp.desc())
                    .limit(1)
                )
                latest = result.scalar_one_or_none()
                if latest and latest.timestamp != last_timestamp:
                    last_timestamp = latest.timestamp
                    await websocket.send_text(json.dumps({
                        "type": "price_update",
                        "symbol": session.symbol,
                        "close": float(latest.close),
                        "timestamp": str(latest.timestamp),
                    }))
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    finally:
        notification_broadcaster.unregister(session_id)
```

- [ ] **Step 2: Run all backend tests to confirm no regression**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/ -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/routers/websocket.py
git commit -m "feat: register WS connections with notification broadcaster

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 7: Update Scheduler — Emit Notifications on Events

**Files:**
- Modify: `backend/scheduler/scraper_job.py`

- [ ] **Step 1: Add notification dispatch to `_trigger_strategy`**

At the top of `_trigger_strategy`, add imports inside the function (maintaining existing import style):

```python
        from notifications.broadcaster import notification_broadcaster, build_notification_payload
        from notifications.email import send_trade_email
```

**After stop-loss/take-profit closure** (after the `logger.info` on line ~112), add:

```python
                    payload = build_notification_payload(
                        level="warning",
                        title=f"{reason.replace('-', '-').title()} Triggered",
                        message=f"{session.symbol}: trade closed at ${current_price:.2f} ({reason})",
                    )
                    await notification_broadcaster.broadcast(session.id, payload)
                    if session.notify_email and session.email_address:
                        send_trade_email(
                            to_address=session.email_address,
                            subject=f"TradingCopilot: {reason.title()} on {session.symbol}",
                            body=f"Your {reason} was triggered for {session.symbol}.\nTrade closed at ${current_price:.2f}.",
                        )
```

**After the daily max loss circuit breaker** (after the `logger.warning` on line ~142), add:

```python
                payload = build_notification_payload(
                    level="danger",
                    title="Daily Loss Limit Hit",
                    message=f"{session.symbol}: session closed — daily loss limit reached (P&L: ${daily_pnl:.2f})",
                )
                await notification_broadcaster.broadcast(session.id, payload)
                if session.notify_email and session.email_address:
                    send_trade_email(
                        to_address=session.email_address,
                        subject=f"TradingCopilot: Daily loss limit hit for {session.symbol}",
                        body=f"Your daily max loss limit was breached for {session.symbol}.\nSession closed. Daily P&L: ${daily_pnl:.2f}.",
                    )
```

**After the strategy signal executes** (after the `logger.info` at the end), add:

```python
        payload = build_notification_payload(
            level="info",
            title=f"{'Buy' if signal.action == 'buy' else 'Sell'} Signal",
            message=f"{session.symbol}: {signal.action} at ${current_price:.2f} — {signal.reason}",
        )
        await notification_broadcaster.broadcast(session.id, payload)
        if session.notify_email and session.email_address:
            send_trade_email(
                to_address=session.email_address,
                subject=f"TradingCopilot: {signal.action.title()} signal for {session.symbol}",
                body=f"A {signal.action} signal fired for {session.symbol}.\nPrice: ${current_price:.2f}\nReason: {signal.reason}",
            )
```

- [ ] **Step 2: Run all backend tests**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/ -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/scheduler/scraper_job.py
git commit -m "feat: emit WS notifications and optional email on risk events and signals

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 8: Frontend — Notification Context

**Files:**
- Create: `frontend/src/context/NotificationContext.jsx`

- [ ] **Step 1: Create the notification context**

```jsx
// frontend/src/context/NotificationContext.jsx
import { createContext, useContext, useState, useCallback } from "react";

const NotificationContext = createContext(null);

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([]);

  const addNotification = useCallback((notif) => {
    const entry = { ...notif, id: crypto.randomUUID() };
    setNotifications((prev) => [entry, ...prev].slice(0, 100)); // cap at 100
  }, []);

  const dismissNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ notifications, addNotification, dismissNotification }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationProvider");
  return ctx;
}
```

- [ ] **Step 2: Wrap App with NotificationProvider**

In `frontend/src/App.jsx`, import and wrap:

```jsx
import { NotificationProvider } from "./context/NotificationContext";

// Wrap the existing JSX tree:
<NotificationProvider>
  {/* existing BrowserRouter / AppShell tree */}
</NotificationProvider>
```

Read `frontend/src/App.jsx` first to find the exact wrapping point, then apply the edit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/context/NotificationContext.jsx frontend/src/App.jsx
git commit -m "feat: notification context provider

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 9: Frontend — Toast Component

**Files:**
- Create: `frontend/src/components/Toast.jsx`

- [ ] **Step 1: Create the toast component**

```jsx
// frontend/src/components/Toast.jsx
import { useEffect, useState } from "react";
import { useNotifications } from "../context/NotificationContext";

const LEVEL_STYLES = {
  info:    "border-[#00e676] text-[#00e676]",
  warning: "border-[#ffb300] text-[#ffb300]",
  danger:  "border-[#ff4444] text-[#ff4444]",
};

function ToastItem({ notif, onDismiss }) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(notif.id), 300); // allow fade-out
    }, 5000);
    return () => clearTimeout(timer);
  }, [notif.id, onDismiss]);

  return (
    <div
      className={`flex items-start gap-3 bg-[#141414] border-l-4 rounded px-4 py-3 shadow-lg w-80 transition-opacity duration-300 ${LEVEL_STYLES[notif.level] ?? LEVEL_STYLES.info} ${visible ? "opacity-100" : "opacity-0"}`}
    >
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-semibold leading-tight">{notif.title}</p>
        <p className="text-[#888] text-xs mt-0.5 break-words">{notif.message}</p>
      </div>
      <button
        onClick={() => onDismiss(notif.id)}
        className="text-[#555] hover:text-white text-xs ml-2 flex-shrink-0"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export default function Toast() {
  const { notifications, dismissNotification } = useNotifications();
  // Show only the 3 most recent un-dismissed toasts
  const visible = notifications.slice(0, 3);

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 items-end">
      {visible.map((n) => (
        <ToastItem key={n.id} notif={n} onDismiss={dismissNotification} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Toast.jsx
git commit -m "feat: auto-dismiss toast component

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 10: Frontend — Notification History Panel

**Files:**
- Create: `frontend/src/components/NotificationHistory.jsx`

- [ ] **Step 1: Create the notification history panel**

```jsx
// frontend/src/components/NotificationHistory.jsx
import { useNotifications } from "../context/NotificationContext";

const LEVEL_DOT = {
  info:    "bg-[#00e676]",
  warning: "bg-[#ffb300]",
  danger:  "bg-[#ff4444]",
};

export default function NotificationHistory({ open, onClose }) {
  const { notifications, dismissNotification } = useNotifications();

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed top-12 right-0 w-80 h-[calc(100vh-3rem)] bg-[#111] border-l border-[#1e1e1e] z-50 flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e1e]">
          <span className="text-[#00e676] text-xs uppercase tracking-widest">Notifications</span>
          <button
            onClick={onClose}
            className="text-[#555] hover:text-white text-xs"
            aria-label="Close"
          >✕</button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {notifications.length === 0 ? (
            <p className="text-[#555] text-xs text-center mt-8 px-4">No notifications yet.</p>
          ) : (
            notifications.map((n) => (
              <div key={n.id} className="flex items-start gap-3 px-4 py-3 border-b border-[#1a1a1a] hover:bg-[#141414]">
                <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${LEVEL_DOT[n.level] ?? LEVEL_DOT.info}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-white text-xs font-semibold">{n.title}</p>
                  <p className="text-[#666] text-xs mt-0.5 break-words">{n.message}</p>
                  <p className="text-[#444] text-xs mt-1">{new Date(n.ts).toLocaleTimeString()}</p>
                </div>
                <button
                  onClick={() => dismissNotification(n.id)}
                  className="text-[#555] hover:text-white text-xs flex-shrink-0"
                  aria-label="Dismiss"
                >✕</button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/NotificationHistory.jsx
git commit -m "feat: notification history panel

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 11: Frontend — Wire AppShell (Toast + Bell Button)

**Files:**
- Modify: `frontend/src/components/AppShell.jsx`

- [ ] **Step 1: Import and render Toast + NotificationHistory in AppShell**

Read `frontend/src/components/AppShell.jsx` and apply these changes:

1. Add imports at the top:
```jsx
import Toast from "./Toast";
import NotificationHistory from "./NotificationHistory";
import { useNotifications } from "../context/NotificationContext";
import { useState } from "react";  // already imported
```

2. Add state and unread count inside `AppShell`:
```jsx
  const [historyOpen, setHistoryOpen] = useState(false);
  const { notifications } = useNotifications();
  const unreadCount = notifications.length;
```

3. Replace the existing `🔔` span in the top bar with:
```jsx
            <button
              onClick={() => setHistoryOpen((o) => !o)}
              className="relative text-[#888] hover:text-white text-sm"
              aria-label="Notifications"
            >
              🔔
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-[#ff4444] text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>
```

4. Before the closing `</div>` of the outer container, add:
```jsx
      <Toast />
      <NotificationHistory open={historyOpen} onClose={() => setHistoryOpen(false)} />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AppShell.jsx
git commit -m "feat: wire toast and notification history bell in AppShell

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 12: Frontend — LiveDashboard Handles Notification WS Frames

**Files:**
- Modify: `frontend/src/pages/LiveDashboard.jsx`

- [ ] **Step 1: Import and dispatch notifications from WebSocket**

In `frontend/src/pages/LiveDashboard.jsx`:

1. Add import:
```jsx
import { useNotifications } from "../context/NotificationContext";
```

2. Inside the component, add:
```jsx
  const { addNotification } = useNotifications();
```

3. In the WebSocket callback, add handling for `notification` type alongside `price_update`:
```jsx
    wsRef.current = createSessionSocket(sessionId, (msg) => {
      if (msg.type === "price_update") {
        setLatestPrice(msg.close);
        setBars(prev => [...prev.slice(-199), { timestamp: msg.timestamp, close: msg.close }]);
        getTrades(sessionId).then(r => setTrades(r.data));
      } else if (msg.type === "notification") {
        addNotification(msg);
      }
    });
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/LiveDashboard.jsx
git commit -m "feat: LiveDashboard routes notification WS frames to toast system

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 13: Frontend — NewSession Form Notification Preferences

**Files:**
- Modify: `frontend/src/pages/NewSession.jsx`

- [ ] **Step 1: Add `notify_email` and `email_address` to form state**

In the `form` state initialization, add:
```jsx
    notify_email: false,
    email_address: "",
```

- [ ] **Step 2: Add notification preferences section to the form JSX**

After the Risk Management section and before the Execution Logic / backtest date section, add (only shown for paper/live modes):

```jsx
            {/* Notifications */}
            {form.mode !== "backtest" && (
              <div className="bg-[#141414] border border-[#1e1e1e] rounded p-4">
                <h2 className="text-[#00e676] text-xs uppercase tracking-widest mb-4">Notifications</h2>
                <div className="flex flex-col gap-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <div
                      onClick={() => setForm({ ...form, notify_email: !form.notify_email })}
                      className={`w-9 h-5 rounded-full transition-colors ${form.notify_email ? "bg-[#00e676]" : "bg-[#333]"} relative flex-shrink-0`}
                    >
                      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${form.notify_email ? "left-4" : "left-0.5"}`} />
                    </div>
                    <span className="text-[#888] text-xs">Email alerts on trade open/close</span>
                  </label>
                  {form.notify_email && (
                    <div>
                      <label className={labelClass}>Email Address</label>
                      <input
                        type="email"
                        className={inputClass}
                        value={form.email_address}
                        onChange={e => setForm({ ...form, email_address: e.target.value })}
                        placeholder="you@example.com"
                        required={form.notify_email}
                      />
                    </div>
                  )}
                </div>
              </div>
            )}
```

- [ ] **Step 3: Pass notification prefs in `handleSubmit`**

In the `createSession` call inside `handleSubmit`, add:
```jsx
          notify_email: form.notify_email,
          email_address: form.notify_email && form.email_address !== "" ? form.email_address : null,
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NewSession.jsx
git commit -m "feat: notification preferences in New Session form

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 14: Run Full Test Suite

- [ ] **Step 1: Run unit tests**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/backend"
python -m pytest ../tests/backend/ -v
```

Expected: All PASS, zero failures.

- [ ] **Step 2: Note integration test status**

Integration tests require Docker Desktop. Run if available:
```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot"
./scripts/run-integration-tests.sh
```

If Docker is unavailable, state: *"Integration tests not run — Docker unavailable."*

- [ ] **Step 3: Final commit (if any fixups needed)**

```bash
git add -p  # stage any fixup changes
git commit -m "fix: address any test failures from final suite run

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```
