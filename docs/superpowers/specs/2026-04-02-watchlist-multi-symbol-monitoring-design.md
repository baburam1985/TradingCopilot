# Watchlist / Multi-Symbol Signal Monitoring — Design Spec

**Date:** 2026-04-02  
**Task:** [AGEAAA-5](/AGEAAA/issues/AGEAAA-5)  
**Status:** Approved for implementation

---

## Overview

Add a Watchlist feature that lets users monitor market signals across multiple symbols without committing capital to a full trading session. Each watchlist item pairs a symbol with a strategy and optional alert threshold. The background scraper evaluates signals for watched symbols and delivers alerts through the existing notification infrastructure.

---

## Architecture

### Data Flow

```
Scheduler tick
  └─► for each active watchlist symbol
        ├─► fetch price (same aggregator as sessions)
        ├─► run strategy.analyze() → signal (buy/sell/hold)
        ├─► persist last_signal + last_price + last_evaluated_at on WatchlistItem
        └─► if signal is buy/sell (or price crosses alert_threshold)
              ├─► broadcast to watchlist WebSocket channel
              └─► send email if item.notify_email is set
```

### Integration Points

- **Scraper/Scheduler** — reuses `_active_symbols` set; watchlist symbols are added/removed via a reference-counted registry shared with sessions.
- **Notification broadcaster** — uses a reserved key `"watchlist"` in the existing `broadcaster.py` in-memory registry.
- **Strategy engine** — reuses existing `strategy.analyze()` call; no trade execution follows.
- **Email** — reuses `send_trade_email()` from `notifications/email.py`.

---

## Database Model

**Table:** `watchlist_items`

| Column              | Type                        | Notes                                        |
|---------------------|-----------------------------|----------------------------------------------|
| `id`                | UUID (PK)                   | default uuid4                                |
| `symbol`            | VARCHAR                     | ticker symbol, e.g. "AAPL"                   |
| `strategy`          | VARCHAR                     | strategy name matching existing registry     |
| `strategy_params`   | JSONB                       | optional overrides for strategy parameters   |
| `alert_threshold`   | FLOAT (nullable)            | optional price level; alert when crossed     |
| `notify_email`      | BOOLEAN                     | default False                                |
| `email_address`     | VARCHAR (nullable)          | required when notify_email=True              |
| `last_signal`       | VARCHAR (nullable)          | "buy", "sell", or "hold"                     |
| `last_price`        | FLOAT (nullable)            | price at last evaluation                     |
| `last_evaluated_at` | TIMESTAMP WITH TZ (nullable)| when signal was last computed                |
| `created_at`        | TIMESTAMP WITH TZ           | default now()                                |

**Index:** `(symbol)` — to query all watchlist items for a symbol efficiently.

**Alert threshold semantics:** if `alert_threshold` is set, emit an alert when the current price crosses above or below that level (tracked by comparing last_price to current_price on each tick). Strategy-signal alerts are always emitted on buy/sell regardless of threshold.

---

## Backend — New Files

### `backend/models/watchlist_item.py`

SQLAlchemy ORM model for `watchlist_items`. Follows the same pattern as `TradingSession`.

### `backend/routers/watchlist.py`

CRUD router mounted at `/watchlist`:

| Method   | Path                 | Description                          |
|----------|----------------------|--------------------------------------|
| GET      | `/watchlist`         | List all watchlist items              |
| POST     | `/watchlist`         | Create a new watchlist item          |
| GET      | `/watchlist/{id}`    | Get a single item                    |
| PATCH    | `/watchlist/{id}`    | Update symbol/strategy/threshold     |
| DELETE   | `/watchlist/{id}`    | Remove item                          |

Pydantic request/response models live in `backend/routers/watchlist.py` (co-located, following project convention).

### `backend/migrations/versions/<rev>_add_watchlist_items.py`

Alembic migration adding the `watchlist_items` table.

---

## Backend — Modified Files

### `backend/scheduler/scraper_job.py`

- `register_watchlist_symbol(symbol)` — increments reference count, adds to `_active_symbols`.
- `unregister_watchlist_symbol(symbol)` — decrements reference count; removes from `_active_symbols` only when count reaches zero AND no active sessions use the symbol.
- `_trigger_watchlist_signals(symbol, current_price, db)` — loads all watchlist items for symbol, runs strategy.analyze(), updates item fields, fires alerts.

Reference counting avoids stopping price scraping for a symbol that is simultaneously used by a live trading session.

### `backend/notifications/broadcaster.py`

- Add `WATCHLIST_CHANNEL = "watchlist"` constant.
- No structural change needed; the existing in-memory dict already supports arbitrary keys.

### `backend/main.py`

- Register `watchlist` router.
- Add `WS /ws/watchlist` endpoint (analogous to `/ws/sessions/{session_id}` but with no session ID — all watchlist clients share one channel).

---

## Frontend

### New Page: `frontend/src/pages/Watchlist.jsx`

**Layout:**
- Header row with "Watchlist" title and "Add Symbol" button.
- Table columns: Symbol | Strategy | Latest Signal | Latest Price | Alert Threshold | Added | Actions.
- Signal displayed as color-coded badge: green=Buy, red=Sell, gray=Hold.
- "Add Symbol" opens a modal with: symbol input, strategy selector (same dropdown as NewSession), optional strategy params, optional alert threshold, optional email notification toggle + address.
- Delete button per row (confirmation prompt).
- WebSocket connection to `/ws/watchlist` updates signal/price cells in real time.

### Modified: `frontend/src/App.jsx` (or router file)

- Add `/watchlist` route pointing to `Watchlist` page.

### Modified: `frontend/src/components/AppShell.jsx`

- Add "Watchlist" nav link alongside existing navigation items.

---

## Notification Payload (Watchlist)

```json
{
  "type": "notification",
  "level": "info",
  "title": "Watchlist Signal: AAPL",
  "message": "RSI strategy generated a BUY signal at $182.45",
  "ts": "2026-04-02T14:30:00Z",
  "watchlist_item_id": "<uuid>"
}
```

Price-threshold alerts use `level: "warning"` and a message like `"AAPL crossed alert threshold $180.00 (current: $182.45)"`.

---

## Testing

### Unit Tests (`tests/backend/test_watchlist.py`)

- CRUD operations on WatchlistItem model (create, read, update, delete).
- `_trigger_watchlist_signals()` with mocked strategy and broadcaster — verifies signal persisted and notification broadcast on buy/sell but not on hold.
- Price-threshold alert logic — verifies alert fires when price crosses threshold.
- `register_watchlist_symbol` / `unregister_watchlist_symbol` reference counting — symbol not removed from active set when session also uses it.
- Email sent when `notify_email=True` and signal fires.

### Integration Tests (`tests/integration/test_watchlist.py`)

- `POST /watchlist` creates item, GET returns it, DELETE removes it.
- WebSocket `/ws/watchlist` receives signal notification after scheduler tick.

---

## Acceptance Criteria (from ticket)

- [x] User can add/remove symbols to watchlist
- [x] Signals computed and displayed for watchlist symbols
- [x] No paper trades executed for watchlist (signals only)
- [x] Alerts delivered via P2-2 notification system (WebSocket + optional email)
- [x] Depends on: P2-2 (already implemented in AGEAAA-3)

---

## Out of Scope

- Bulk import of watchlist symbols.
- Per-symbol WebSocket channels (all watchlist clients share one channel).
- Watchlist sharing between users.
