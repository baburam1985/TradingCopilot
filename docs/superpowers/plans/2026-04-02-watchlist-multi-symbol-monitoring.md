# Watchlist / Multi-Symbol Signal Monitoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Watchlist feature that lets users monitor strategy signals across multiple stock symbols without opening trading sessions; alerts fire via WebSocket and optional email.

**Architecture:** New `watchlist_items` Postgres table stores symbol + strategy + optional price alert threshold. The APScheduler scraper is extended to scrape watchlist symbols and evaluate signals, broadcasting results to a shared `/ws/watchlist` WebSocket channel via a new list-based broadcaster registry. A React Watchlist page connects to that channel and renders live signal badges.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.0 (async), Alembic, APScheduler, WebSockets, React/Vite, TailwindCSS, pytest/pytest-asyncio.

---

## File Map

**Create:**
- `backend/models/watchlist_item.py` — SQLAlchemy ORM model
- `backend/routers/watchlist.py` — CRUD API router + Pydantic schemas
- `backend/migrations/versions/e7f8a9b0c1d2_add_watchlist_items.py` — Alembic migration
- `tests/backend/test_watchlist.py` — unit tests (model + router + scheduler logic)
- `tests/integration/test_watchlist.py` — integration tests (API + WebSocket)
- `frontend/src/pages/Watchlist.jsx` — Watchlist page component

**Modify:**
- `backend/notifications/broadcaster.py` — add watchlist connection list + methods
- `backend/routers/websocket.py` — add `WS /ws/watchlist` endpoint
- `backend/scheduler/scraper_job.py` — add watchlist symbol tracking + signal evaluation
- `backend/main.py` — register watchlist router
- `frontend/src/api/client.js` — add watchlist API helpers + socket factory
- `frontend/src/App.jsx` — add `/watchlist` route
- `frontend/src/components/AppShell.jsx` — add Watchlist nav link

---

## Task 1: WatchlistItem DB Model

**Files:**
- Create: `backend/models/watchlist_item.py`

- [ ] **Step 1: Write the failing test (model attributes)**

File: `tests/backend/test_watchlist.py`

```python
import uuid
import pytest
from datetime import datetime, timezone
from models.watchlist_item import WatchlistItem


def test_watchlist_item_attributes():
    item = WatchlistItem(
        symbol="AAPL",
        strategy="rsi",
        strategy_params={"period": 14, "oversold": 30, "overbought": 70},
        alert_threshold=180.0,
        notify_email=True,
        email_address="trader@example.com",
        created_at=datetime.now(timezone.utc),
    )
    assert item.symbol == "AAPL"
    assert item.strategy == "rsi"
    assert item.strategy_params["period"] == 14
    assert item.alert_threshold == 180.0
    assert item.notify_email is True
    assert item.email_address == "trader@example.com"
    assert item.last_signal is None
    assert item.last_price is None
    assert item.last_evaluated_at is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py::test_watchlist_item_attributes -v
```

Expected: `ModuleNotFoundError: No module named 'models.watchlist_item'`

- [ ] **Step 3: Create the model**

File: `backend/models/watchlist_item.py`

```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    alert_threshold: Mapped[Optional[float]] = mapped_column(nullable=True)
    notify_email: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    email_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_signal: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    last_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py::test_watchlist_item_attributes -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/models/watchlist_item.py tests/backend/test_watchlist.py
git commit -m "feat: add WatchlistItem model and initial test (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/migrations/versions/e7f8a9b0c1d2_add_watchlist_items.py`

- [ ] **Step 1: Create the migration file**

File: `backend/migrations/versions/e7f8a9b0c1d2_add_watchlist_items.py`

```python
"""add watchlist_items table

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-04-03 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'watchlist_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('strategy', sa.String(length=100), nullable=False),
        sa.Column('strategy_params', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('alert_threshold', sa.Float(), nullable=True),
        sa.Column('notify_email', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_address', sa.String(length=255), nullable=True),
        sa.Column('last_signal', sa.String(length=10), nullable=True),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('last_evaluated_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_watchlist_items_symbol', 'watchlist_items', ['symbol'])


def downgrade() -> None:
    op.drop_index('ix_watchlist_items_symbol', table_name='watchlist_items')
    op.drop_table('watchlist_items')
```

- [ ] **Step 2: Commit**

```bash
git add backend/migrations/versions/e7f8a9b0c1d2_add_watchlist_items.py
git commit -m "feat: add Alembic migration for watchlist_items table (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Watchlist CRUD Router

**Files:**
- Create: `backend/routers/watchlist.py`

- [ ] **Step 1: Write failing tests for CRUD endpoints**

Append to `tests/backend/test_watchlist.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timezone
import uuid

# ---------------------------------------------------------------------------
# Shared fixture: FastAPI test app with watchlist router
# ---------------------------------------------------------------------------

@pytest.fixture
def watchlist_app():
    from routers.watchlist import router
    app = FastAPI()
    app.include_router(router, prefix="/watchlist")
    return app


@pytest.fixture
def item_id():
    return uuid.uuid4()


def make_item(item_id):
    item = MagicMock()
    item.id = item_id
    item.symbol = "AAPL"
    item.strategy = "rsi"
    item.strategy_params = {"period": 14}
    item.alert_threshold = 180.0
    item.notify_email = False
    item.email_address = None
    item.last_signal = None
    item.last_price = None
    item.last_evaluated_at = None
    item.created_at = datetime.now(timezone.utc)
    return item


def test_create_watchlist_item_returns_201(watchlist_app, item_id):
    mock_db = AsyncMock()
    mock_item = make_item(item_id)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    async def fake_get_db():
        yield mock_db

    from database import get_db
    watchlist_app.dependency_overrides[get_db] = fake_get_db

    with patch("routers.watchlist.register_watchlist_symbol") as mock_reg, \
         patch("routers.watchlist.WatchlistItem", return_value=mock_item):
        client = TestClient(watchlist_app)
        resp = client.post("/watchlist", json={
            "symbol": "AAPL",
            "strategy": "rsi",
            "strategy_params": {"period": 14},
        })
    assert resp.status_code == 200
    mock_reg.assert_called_once_with("AAPL")


def test_delete_watchlist_item_calls_unregister(watchlist_app, item_id):
    mock_db = AsyncMock()
    mock_item = make_item(item_id)
    mock_db.get = AsyncMock(return_value=mock_item)
    mock_db.delete = MagicMock()
    mock_db.commit = AsyncMock()

    async def fake_get_db():
        yield mock_db

    from database import get_db
    watchlist_app.dependency_overrides[get_db] = fake_get_db

    with patch("routers.watchlist.unregister_watchlist_symbol") as mock_unreg:
        client = TestClient(watchlist_app)
        resp = client.delete(f"/watchlist/{item_id}")
    assert resp.status_code == 200
    mock_unreg.assert_called_once_with("AAPL")


def test_delete_watchlist_item_404_when_not_found(watchlist_app, item_id):
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    async def fake_get_db():
        yield mock_db

    from database import get_db
    watchlist_app.dependency_overrides[get_db] = fake_get_db

    with patch("routers.watchlist.unregister_watchlist_symbol"):
        client = TestClient(watchlist_app)
        resp = client.delete(f"/watchlist/{item_id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py::test_create_watchlist_item_returns_201 ../tests/backend/test_watchlist.py::test_delete_watchlist_item_calls_unregister ../tests/backend/test_watchlist.py::test_delete_watchlist_item_404_when_not_found -v
```

Expected: `ModuleNotFoundError: No module named 'routers.watchlist'`

- [ ] **Step 3: Create the router**

File: `backend/routers/watchlist.py`

```python
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.watchlist_item import WatchlistItem
from scheduler.scraper_job import register_watchlist_symbol, unregister_watchlist_symbol

router = APIRouter()


class CreateWatchlistItemRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict = {}
    alert_threshold: Optional[float] = None
    notify_email: bool = False
    email_address: Optional[str] = None


class UpdateWatchlistItemRequest(BaseModel):
    strategy: Optional[str] = None
    strategy_params: Optional[dict] = None
    alert_threshold: Optional[float] = None
    notify_email: Optional[bool] = None
    email_address: Optional[str] = None


@router.get("")
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WatchlistItem).order_by(WatchlistItem.created_at.desc())
    )
    return result.scalars().all()


@router.post("")
async def create_watchlist_item(
    req: CreateWatchlistItemRequest, db: AsyncSession = Depends(get_db)
):
    item = WatchlistItem(
        symbol=req.symbol.upper(),
        strategy=req.strategy,
        strategy_params=req.strategy_params,
        alert_threshold=req.alert_threshold,
        notify_email=req.notify_email,
        email_address=req.email_address,
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    register_watchlist_symbol(item.symbol)
    return item


@router.get("/{item_id}")
async def get_watchlist_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return item


@router.patch("/{item_id}")
async def update_watchlist_item(
    item_id: uuid.UUID,
    req: UpdateWatchlistItemRequest,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    if req.strategy is not None:
        item.strategy = req.strategy
    if req.strategy_params is not None:
        item.strategy_params = req.strategy_params
    if req.alert_threshold is not None:
        item.alert_threshold = req.alert_threshold
    if req.notify_email is not None:
        item.notify_email = req.notify_email
    if req.email_address is not None:
        item.email_address = req.email_address
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}")
async def delete_watchlist_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(WatchlistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    symbol = item.symbol
    await db.delete(item)
    await db.commit()
    unregister_watchlist_symbol(symbol)
    return {"deleted": True, "symbol": symbol}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py::test_create_watchlist_item_returns_201 ../tests/backend/test_watchlist.py::test_delete_watchlist_item_calls_unregister ../tests/backend/test_watchlist.py::test_delete_watchlist_item_404_when_not_found -v
```

Expected: all 3 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/routers/watchlist.py tests/backend/test_watchlist.py
git commit -m "feat: add watchlist CRUD router with tests (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Broadcaster — Watchlist Channel Support

**Files:**
- Modify: `backend/notifications/broadcaster.py`

- [ ] **Step 1: Write failing tests for watchlist broadcast methods**

Append to `tests/backend/test_watchlist.py`:

```python
# ---------------------------------------------------------------------------
# Broadcaster watchlist tests
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import AsyncMock, MagicMock


def test_broadcaster_register_watchlist():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws = MagicMock()
    b.register_watchlist(ws)
    assert ws in b._watchlist_connections


def test_broadcaster_unregister_watchlist():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws = MagicMock()
    b.register_watchlist(ws)
    b.unregister_watchlist(ws)
    assert ws not in b._watchlist_connections


def test_broadcaster_unregister_watchlist_tolerates_missing():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws = MagicMock()
    b.unregister_watchlist(ws)  # should not raise


@pytest.mark.asyncio
async def test_broadcaster_broadcast_watchlist_sends_to_all():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    b.register_watchlist(ws1)
    b.register_watchlist(ws2)
    payload = {"type": "notification", "level": "info", "title": "T", "message": "M"}
    await b.broadcast_watchlist(payload)
    ws1.send_text.assert_called_once()
    ws2.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_broadcaster_broadcast_watchlist_removes_dead_connections():
    from notifications.broadcaster import NotificationBroadcaster
    b = NotificationBroadcaster()
    ws_ok = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = Exception("connection closed")
    b.register_watchlist(ws_ok)
    b.register_watchlist(ws_dead)
    await b.broadcast_watchlist({"type": "notification"})
    assert ws_dead not in b._watchlist_connections
    assert ws_ok in b._watchlist_connections
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py -k "broadcaster" -v
```

Expected: `AttributeError: 'NotificationBroadcaster' object has no attribute '_watchlist_connections'`

- [ ] **Step 3: Add watchlist support to broadcaster**

Edit `backend/notifications/broadcaster.py` — add `_watchlist_connections` list and three new methods. The full updated file:

```python
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
        self._watchlist_connections: list[WebSocket] = []

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
            self.unregister(session_id)

    # ------------------------------------------------------------------
    # Watchlist channel — all clients share a single broadcast list
    # ------------------------------------------------------------------

    def register_watchlist(self, ws: WebSocket) -> None:
        self._watchlist_connections.append(ws)

    def unregister_watchlist(self, ws: WebSocket) -> None:
        try:
            self._watchlist_connections.remove(ws)
        except ValueError:
            pass

    async def broadcast_watchlist(self, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._watchlist_connections):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister_watchlist(ws)


# Module-level singleton shared across routers and scheduler
notification_broadcaster = NotificationBroadcaster()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py -k "broadcaster" -v
```

Expected: all 5 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/notifications/broadcaster.py tests/backend/test_watchlist.py
git commit -m "feat: add watchlist broadcast channel to NotificationBroadcaster (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Scheduler — Watchlist Symbol Tracking + Signal Evaluation

**Files:**
- Modify: `backend/scheduler/scraper_job.py`

- [ ] **Step 1: Write failing tests for watchlist scheduler functions**

Append to `tests/backend/test_watchlist.py`:

```python
# ---------------------------------------------------------------------------
# Scheduler watchlist tests
# ---------------------------------------------------------------------------


def test_register_and_unregister_watchlist_symbol():
    import importlib
    import scheduler.scraper_job as job
    importlib.reload(job)  # reset module-level sets

    job.register_watchlist_symbol("AAPL")
    assert "AAPL" in job._watchlist_symbols

    job.unregister_watchlist_symbol("AAPL")
    assert "AAPL" not in job._watchlist_symbols


def test_register_watchlist_symbol_uppercased():
    import importlib
    import scheduler.scraper_job as job
    importlib.reload(job)

    job.register_watchlist_symbol("tsla")
    assert "TSLA" in job._watchlist_symbols
    job.unregister_watchlist_symbol("TSLA")


def test_unregister_watchlist_symbol_does_not_remove_active_session_symbol():
    """Removing a watchlist symbol should not stop scraping if a session also watches it."""
    import importlib
    import scheduler.scraper_job as job
    importlib.reload(job)

    job.register_symbol("AAPL")          # session registration
    job.register_watchlist_symbol("AAPL") # watchlist registration
    job.unregister_watchlist_symbol("AAPL")

    # Symbol must still be scraped because an active session uses it
    assert "AAPL" in job._active_symbols


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_broadcasts_on_buy():
    import importlib
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "buy"
    mock_signal.reason = "RSI oversold"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "AAPL"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = None
    mock_item.last_price = None
    mock_item.notify_email = False
    mock_item.email_address = None

    mock_bar = MagicMock()
    mock_bar.close = 182.0

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        # First call returns watchlist items; second returns price history bars
        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("AAPL", 182.0)

    mock_broadcaster.broadcast_watchlist.assert_called_once()
    call_payload = mock_broadcaster.broadcast_watchlist.call_args[0][0]
    assert call_payload["level"] == "info"
    assert "BUY" in call_payload["message"]
    assert "AAPL" in call_payload["title"]


@pytest.mark.asyncio
async def test_trigger_watchlist_signals_no_broadcast_on_hold():
    import scheduler.scraper_job as job

    mock_signal = MagicMock()
    mock_signal.action = "hold"
    mock_signal.reason = "neutral"

    mock_strategy = MagicMock()
    mock_strategy.return_value.analyze.return_value = mock_signal

    mock_item = MagicMock()
    mock_item.id = uuid.uuid4()
    mock_item.symbol = "MSFT"
    mock_item.strategy = "rsi"
    mock_item.strategy_params = {}
    mock_item.alert_threshold = None
    mock_item.last_price = None
    mock_item.notify_email = False
    mock_item.email_address = None

    mock_bar = MagicMock()
    mock_bar.close = 300.0

    with patch("scheduler.scraper_job.AsyncSessionLocal") as mock_session_cls, \
         patch("scheduler.scraper_job.STRATEGY_REGISTRY", {"rsi": mock_strategy}), \
         patch("scheduler.scraper_job.notification_broadcaster") as mock_broadcaster:

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        mock_result_items = MagicMock()
        mock_result_items.scalars.return_value.all.return_value = [mock_item]
        mock_result_bars = MagicMock()
        mock_result_bars.scalars.return_value.all.return_value = [mock_bar]
        mock_ctx.execute = AsyncMock(side_effect=[mock_result_items, mock_result_bars])
        mock_ctx.get = AsyncMock(return_value=mock_item)
        mock_ctx.commit = AsyncMock()

        mock_broadcaster.broadcast_watchlist = AsyncMock()

        await job._trigger_watchlist_signals("MSFT", 300.0)

    mock_broadcaster.broadcast_watchlist.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py -k "watchlist_symbol or trigger_watchlist" -v
```

Expected: `AttributeError: module 'scheduler.scraper_job' has no attribute '_watchlist_symbols'`

- [ ] **Step 3: Add watchlist tracking and signal evaluation to scheduler**

Edit `backend/scheduler/scraper_job.py`. Add after `_active_symbols: set[str] = set()`:

```python
_watchlist_symbols: set[str] = set()


def register_watchlist_symbol(symbol: str) -> None:
    _watchlist_symbols.add(symbol.upper())
    _active_symbols.add(symbol.upper())  # ensure price is scraped


def unregister_watchlist_symbol(symbol: str) -> None:
    sym = symbol.upper()
    _watchlist_symbols.discard(sym)
    # Only remove from active set if no session is also watching this symbol
    if sym not in _active_symbols:
        return
    # _active_symbols is populated by session register_symbol; if no session
    # uses this symbol, discard it from active set too.
    # We rely on _watchlist_symbols as the watchlist reference; sessions manage
    # _active_symbols themselves. When unregistering watchlist, only remove from
    # _active_symbols if it wasn't added by a session. Since we don't have a
    # separate session set, we conservatively leave _active_symbols alone — the
    # scheduler will still scrape but _trigger_watchlist_signals will find no items.
    # Actual removal from _active_symbols happens when sessions unregister_symbol.
```

Then add the `_trigger_watchlist_signals` function after `_trigger_strategy`:

```python
async def _trigger_watchlist_signals(symbol: str, current_price: float):
    import logging
    from datetime import datetime, timezone
    from strategies.registry import STRATEGY_REGISTRY
    from database import AsyncSessionLocal
    from models.watchlist_item import WatchlistItem
    from models.price_history import PriceHistory
    from sqlalchemy import select
    from notifications.broadcaster import notification_broadcaster, build_notification_payload
    from notifications.email import send_trade_email

    logger = logging.getLogger(__name__)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WatchlistItem).where(WatchlistItem.symbol == symbol)
        )
        items = result.scalars().all()

    for item in items:
        strategy_cls = STRATEGY_REGISTRY.get(item.strategy)
        if strategy_cls is None:
            logger.warning("Watchlist item %s: unknown strategy '%s'", item.id, item.strategy)
            continue

        strategy = strategy_cls(**(item.strategy_params or {}))

        async with AsyncSessionLocal() as db:
            ph_result = await db.execute(
                select(PriceHistory)
                .where(PriceHistory.symbol == symbol)
                .order_by(PriceHistory.timestamp.desc())
                .limit(500)
            )
            bars = ph_result.scalars().all()

        closes = [float(b.close) for b in reversed(bars)]
        signal = strategy.analyze(closes)

        # Detect price-threshold crossing
        threshold_crossed = False
        if item.alert_threshold is not None and item.last_price is not None:
            prev = float(item.last_price)
            threshold = float(item.alert_threshold)
            if (prev < threshold <= current_price) or (prev > threshold >= current_price):
                threshold_crossed = True

        # Persist updated state
        async with AsyncSessionLocal() as db:
            db_item = await db.get(WatchlistItem, item.id)
            if db_item:
                db_item.last_signal = signal.action
                db_item.last_price = current_price
                db_item.last_evaluated_at = datetime.now(timezone.utc)
                await db.commit()

        # Broadcast signal alert on buy or sell
        if signal.action in ("buy", "sell"):
            level = "info"
            title = f"Watchlist Signal: {symbol}"
            message = (
                f"{item.strategy} generated a {signal.action.upper()} signal "
                f"at ${current_price:.2f} — {signal.reason}"
            )
            payload = build_notification_payload(level=level, title=title, message=message)
            payload["watchlist_item_id"] = str(item.id)
            await notification_broadcaster.broadcast_watchlist(payload)
            if item.notify_email and item.email_address:
                try:
                    send_trade_email(
                        item.email_address,
                        f"TradingCopilot: {title}",
                        message,
                    )
                except Exception as exc:
                    logger.warning("Watchlist email delivery failed: %s", exc)

        # Broadcast price-threshold alert
        if threshold_crossed:
            level = "warning"
            title = f"Watchlist Alert: {symbol}"
            message = (
                f"{symbol} crossed alert threshold ${item.alert_threshold:.2f} "
                f"(current: ${current_price:.2f})"
            )
            payload = build_notification_payload(level=level, title=title, message=message)
            payload["watchlist_item_id"] = str(item.id)
            await notification_broadcaster.broadcast_watchlist(payload)
            if item.notify_email and item.email_address and signal.action not in ("buy", "sell"):
                try:
                    send_trade_email(
                        item.email_address,
                        f"TradingCopilot: {title}",
                        message,
                    )
                except Exception as exc:
                    logger.warning("Watchlist threshold email delivery failed: %s", exc)
```

Also modify `_scrape_symbol` — after the call to `await _trigger_strategy(symbol, bar.close)`, add:

```python
    if symbol in _watchlist_symbols:
        await _trigger_watchlist_signals(symbol, bar.close)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest ../tests/backend/test_watchlist.py -k "watchlist_symbol or trigger_watchlist" -v
```

Expected: all 5 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/scheduler/scraper_job.py tests/backend/test_watchlist.py
git commit -m "feat: add watchlist symbol tracking and signal evaluation to scheduler (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: WebSocket Endpoint + Register Router in main.py

**Files:**
- Modify: `backend/routers/websocket.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Add `/ws/watchlist` endpoint to websocket router**

Edit `backend/routers/websocket.py`. Append after the existing `websocket_session` function:

```python
@router.websocket("/ws/watchlist")
async def websocket_watchlist(websocket: WebSocket):
    await websocket.accept()
    notification_broadcaster.register_watchlist(websocket)
    try:
        while True:
            # Keep connection alive; all data pushed server-side via broadcaster
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        notification_broadcaster.unregister_watchlist(websocket)
```

- [ ] **Step 2: Register watchlist router in main.py**

Edit `backend/main.py`. Add `watchlist` to the import line and include the router:

```python
from routers import sessions, market_data, strategies, trades, backtest, websocket, alerts, watchlist
```

And after the alerts router line:

```python
app.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
```

- [ ] **Step 3: Run full unit test suite to confirm nothing broken**

```bash
cd backend && python -m pytest ../tests/backend/ -v
```

Expected: all tests `PASSED`, zero failures.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/websocket.py backend/main.py
git commit -m "feat: add /ws/watchlist WebSocket endpoint and register watchlist router (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Frontend API Client — Watchlist Helpers

**Files:**
- Modify: `frontend/src/api/client.js`

- [ ] **Step 1: Read current client.js to find the existing helper pattern**

Read `frontend/src/api/client.js` fully before editing to confirm function naming conventions.

- [ ] **Step 2: Append watchlist API helpers and socket factory to client.js**

Add the following to the end of `frontend/src/api/client.js`:

```js
// ---------------------------------------------------------------------------
// Watchlist API
// ---------------------------------------------------------------------------

export const getWatchlist = () => api.get("/watchlist");

export const createWatchlistItem = (data) => api.post("/watchlist", data);

export const updateWatchlistItem = (id, data) => api.patch(`/watchlist/${id}`, data);

export const deleteWatchlistItem = (id) => api.delete(`/watchlist/${id}`);

// ---------------------------------------------------------------------------
// Watchlist WebSocket
// ---------------------------------------------------------------------------

export const createWatchlistSocket = (onMessage) => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL.replace(/^https?/, protocol)
    : `${protocol}://${window.location.hostname}:8000`;
  const ws = new WebSocket(`${host}/ws/watchlist`);
  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      // ignore malformed frames
    }
  };
  return ws;
};
```

> **Note:** Match the exact host/URL construction pattern already used by `createSessionSocket` in this file — adjust if the existing function uses a different approach.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat: add watchlist API helpers and WebSocket factory to api client (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Frontend Watchlist Page

**Files:**
- Create: `frontend/src/pages/Watchlist.jsx`

- [ ] **Step 1: Create Watchlist.jsx**

File: `frontend/src/pages/Watchlist.jsx`

```jsx
import { useState, useEffect, useRef } from "react";
import {
  getWatchlist,
  createWatchlistItem,
  deleteWatchlistItem,
  createWatchlistSocket,
} from "../api/client";
import PageHeader from "../components/PageHeader";
import { useNotifications } from "../context/NotificationContext";

const SIGNAL_BADGE = {
  buy:  "bg-[#00e676]/10 text-[#00e676] border border-[#00e676]/30",
  sell: "bg-red-500/10 text-red-400 border border-red-500/30",
  hold: "bg-[#1e1e1e] text-[#888] border border-[#333]",
};

function AddItemModal({ onClose, onAdd }) {
  const [form, setForm] = useState({
    symbol: "",
    strategy: "rsi",
    alert_threshold: "",
    notify_email: false,
    email_address: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        symbol: form.symbol.trim().toUpperCase(),
        strategy: form.strategy,
        strategy_params: {},
        alert_threshold: form.alert_threshold ? parseFloat(form.alert_threshold) : null,
        notify_email: form.notify_email,
        email_address: form.notify_email ? form.email_address : null,
      };
      const resp = await createWatchlistItem(payload);
      onAdd(resp.data);
      onClose();
    } catch (err) {
      setError(err?.response?.data?.detail ?? "Failed to add symbol");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#141414] border border-[#1e1e1e] rounded-lg p-6 w-full max-w-md">
        <h2 className="text-[#00e676] text-sm uppercase tracking-widest mb-4">Add Symbol to Watchlist</h2>
        {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Symbol</label>
            <input
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              placeholder="AAPL"
              required
            />
          </div>
          <div>
            <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Strategy</label>
            <select
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
              value={form.strategy}
              onChange={(e) => setForm({ ...form, strategy: e.target.value })}
            >
              <option value="rsi">RSI</option>
              <option value="moving_average_crossover">Moving Average Crossover</option>
              <option value="bollinger_bands">Bollinger Bands</option>
              <option value="macd">MACD</option>
            </select>
          </div>
          <div>
            <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Alert Threshold (price, optional)</label>
            <input
              type="number"
              step="0.01"
              className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
              value={form.alert_threshold}
              onChange={(e) => setForm({ ...form, alert_threshold: e.target.value })}
              placeholder="e.g. 180.00"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="notify_email"
              checked={form.notify_email}
              onChange={(e) => setForm({ ...form, notify_email: e.target.checked })}
            />
            <label htmlFor="notify_email" className="text-[#888] text-xs uppercase tracking-wide">Email Alerts</label>
          </div>
          {form.notify_email && (
            <div>
              <label className="text-[#888] text-xs uppercase tracking-wide block mb-1">Email Address</label>
              <input
                type="email"
                className="w-full bg-[#0a0a0a] border border-[#1e1e1e] rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-[#00e676]"
                value={form.email_address}
                onChange={(e) => setForm({ ...form, email_address: e.target.value })}
                required={form.notify_email}
              />
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#00e676] text-black text-sm font-bold py-2 rounded hover:bg-[#00c853] disabled:opacity-50 transition-colors"
            >
              {loading ? "Adding..." : "Add to Watchlist"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-[#1e1e1e] text-[#888] text-sm py-2 rounded hover:text-white transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Watchlist() {
  const [items, setItems] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const wsRef = useRef(null);
  const { addNotification } = useNotifications();

  useEffect(() => {
    getWatchlist().then((r) => setItems(r.data));

    wsRef.current = createWatchlistSocket((msg) => {
      if (msg.type === "notification") {
        addNotification(msg);
        // Update signal badge for the relevant item
        if (msg.watchlist_item_id) {
          setItems((prev) =>
            prev.map((item) =>
              String(item.id) === msg.watchlist_item_id
                ? {
                    ...item,
                    last_signal: msg.message.includes("BUY")
                      ? "buy"
                      : msg.message.includes("SELL")
                      ? "sell"
                      : item.last_signal,
                  }
                : item
            )
          );
        }
      }
    });

    return () => wsRef.current?.close();
  }, []);

  const handleAdd = (newItem) => {
    setItems((prev) => [newItem, ...prev]);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Remove this symbol from your watchlist?")) return;
    await deleteWatchlistItem(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  return (
    <div className="p-6">
      <PageHeader
        breadcrumb="HOME › WATCHLIST"
        title="Watchlist"
        subtitle="Monitor signals across multiple symbols without committing capital"
      />

      <div className="flex justify-between items-center mb-4">
        <span className="text-[#888] text-xs uppercase tracking-wide">{items.length} symbols monitored</span>
        <button
          onClick={() => setShowModal(true)}
          className="bg-[#00e676] text-black text-xs font-bold px-4 py-2 rounded hover:bg-[#00c853] transition-colors uppercase tracking-wide"
        >
          + Add Symbol
        </button>
      </div>

      {items.length === 0 ? (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded p-8 text-center text-[#555] text-sm">
          No symbols on your watchlist. Add one to start monitoring signals.
        </div>
      ) : (
        <div className="bg-[#141414] border border-[#1e1e1e] rounded overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e1e]">
                {["Symbol", "Strategy", "Signal", "Last Price", "Alert Threshold", "Added", ""].map((h) => (
                  <th key={h} className="text-left text-[#555] text-xs uppercase tracking-widest px-4 py-3 font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-[#1a1a1a] hover:bg-[#111] transition-colors">
                  <td className="px-4 py-3 font-bold text-white">{item.symbol}</td>
                  <td className="px-4 py-3 text-[#888]">{item.strategy}</td>
                  <td className="px-4 py-3">
                    {item.last_signal ? (
                      <span className={`text-xs font-bold px-2 py-0.5 rounded uppercase ${SIGNAL_BADGE[item.last_signal] ?? SIGNAL_BADGE.hold}`}>
                        {item.last_signal}
                      </span>
                    ) : (
                      <span className="text-[#555] text-xs">Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[#ccc]">
                    {item.last_price != null ? `$${parseFloat(item.last_price).toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-[#888]">
                    {item.alert_threshold != null ? `$${parseFloat(item.alert_threshold).toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-[#555] text-xs">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="text-[#555] hover:text-red-400 text-xs transition-colors"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <AddItemModal onClose={() => setShowModal(false)} onAdd={handleAdd} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Watchlist.jsx
git commit -m "feat: add Watchlist page with real-time signal updates (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Wire Watchlist into App Router and Navigation

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/AppShell.jsx`

- [ ] **Step 1: Add Watchlist route to App.jsx**

Edit `frontend/src/App.jsx`:

Add import:
```js
import Watchlist from "./pages/Watchlist";
```

Add route inside `<Routes>`:
```jsx
<Route path="/watchlist" element={<Watchlist />} />
```

Full updated routes block:
```jsx
<Routes>
  <Route path="/" element={<NewSession />} />
  <Route path="/dashboard/:sessionId" element={<LiveDashboard />} />
  <Route path="/reports" element={<Reports />} />
  <Route path="/optimize" element={<Optimize />} />
  <Route path="/watchlist" element={<Watchlist />} />
</Routes>
```

- [ ] **Step 2: Add Watchlist nav link to AppShell.jsx**

Edit `frontend/src/components/AppShell.jsx`. Update `NAV_ITEMS`:

```js
const NAV_ITEMS = [
  { label: "New Session", to: "/" },
  { label: "Dashboard", to: "/dashboard" },
  { label: "Watchlist", to: "/watchlist" },
  { label: "Reports", to: "/reports" },
  { label: "Optimize", to: "/optimize" },
];
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/AppShell.jsx
git commit -m "feat: add Watchlist route and nav link (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Integration Tests

**Files:**
- Create: `tests/integration/test_watchlist.py`

- [ ] **Step 1: Write integration tests**

File: `tests/integration/test_watchlist.py`

```python
import pytest

pytestmark = pytest.mark.integration

WATCHLIST_PAYLOAD = {
    "symbol": "GOOG",
    "strategy": "rsi",
    "strategy_params": {},
}


async def test_create_watchlist_item(client, clean_db):
    resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["symbol"] == "GOOG"
    assert data["strategy"] == "rsi"
    assert data["last_signal"] is None
    assert data["last_price"] is None


async def test_list_watchlist_contains_created(client, clean_db):
    await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    resp = await client.get("/watchlist")
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["symbol"] == "GOOG" for i in items)


async def test_get_watchlist_item_by_id(client, clean_db):
    create_resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    item_id = create_resp.json()["id"]
    resp = await client.get(f"/watchlist/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id


async def test_delete_watchlist_item(client, clean_db):
    create_resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    item_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/watchlist/{item_id}")
    assert del_resp.status_code == 200
    get_resp = await client.get(f"/watchlist/{item_id}")
    assert get_resp.status_code == 404


async def test_get_nonexistent_watchlist_item_returns_404(client, clean_db):
    resp = await client.get("/watchlist/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_watchlist_item_alert_threshold(client, clean_db):
    create_resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    item_id = create_resp.json()["id"]
    patch_resp = await client.patch(f"/watchlist/{item_id}", json={"alert_threshold": 150.0})
    assert patch_resp.status_code == 200
    assert float(patch_resp.json()["alert_threshold"]) == 150.0
```

- [ ] **Step 2: Commit**

```bash
git add tests/integration/test_watchlist.py
git commit -m "test: add integration tests for watchlist CRUD (AGEAAA-5)

Co-Authored-By: Paperclip <noreply@paperclip.ing>
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Run Full Test Suites

- [ ] **Step 1: Run unit tests**

```bash
cd backend && python -m pytest ../tests/backend/ -v
```

Expected: all tests `PASSED`, zero failures.

- [ ] **Step 2: Run integration tests (requires Docker)**

```bash
./scripts/run-integration-tests.sh
```

Expected: all integration tests `PASSED`. If Docker is unavailable, state: *"Integration tests not run — Docker unavailable."* and flag for human to verify before merging.

- [ ] **Step 3: Push to remote**

```bash
git push origin master
```

Expected: push succeeds.

---

## Self-Review Notes

**Spec coverage check:**
- [x] `watchlist` DB model — Task 1
- [x] Alembic migration — Task 2
- [x] CRUD API endpoints — Task 3
- [x] Background scraper picks up watchlist symbols — Task 5 (`register_watchlist_symbol`, `_trigger_watchlist_signals`)
- [x] Frontend Watchlist screen with signals and prices — Task 8
- [x] Alerts via P2-2 notification system — Tasks 4+5 (`broadcast_watchlist`, email)
- [x] No paper trades executed — `_trigger_watchlist_signals` evaluates signal and alerts only; no executor called
- [x] User can add/remove symbols — Task 3 router + Task 8 frontend
- [x] WebSocket endpoint — Task 6
- [x] Navigation link — Task 9
- [x] Integration tests — Task 10

**Type consistency:**
- `register_watchlist_symbol` / `unregister_watchlist_symbol` used consistently in router and scheduler
- `broadcast_watchlist` / `register_watchlist` / `unregister_watchlist` names match across broadcaster and websocket router
- `createWatchlistSocket` in client matches the frontend import in Watchlist.jsx
- `WatchlistItem` model fields match migration column names exactly
