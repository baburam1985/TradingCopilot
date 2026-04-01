# Integration Test Suite Design

**Date:** 2026-04-01  
**Scope:** Docker-based end-to-end integration tests for TradingCopilot  
**Goal:** Verify the full stack (FastAPI + Postgres + real Yahoo Finance data) works correctly as a deployed system, with zero mocking.

---

## Motivation

Existing unit tests (`tests/backend/`) run against in-process code with stubbed dependencies. They cannot catch:
- Database schema mismatches
- Router wiring errors
- Real Postgres query failures
- Broken Docker builds or missing env vars
- End-to-end signal → trade → P&L correctness against real market data

The integration suite fills this gap by running against the live Docker Compose stack.

---

## Guiding Principles

- **No mocking** — every test hits the real running FastAPI server, real Postgres, real Yahoo Finance HTTP API
- **Structural assertions** — assert on shape/types, not exact values (market prices change daily)
- **Clean state** — each test function that writes data truncates relevant tables after (function-scoped fixture)
- **Isolated from unit tests** — tagged with `integration` pytest marker; `pytest tests/backend/` and `pytest tests/integration/` run independently
- **Self-teardown** — shell script tears down the stack whether tests pass or fail

---

## File Structure

```
TradingCopilot/
├── scripts/
│   └── run-integration-tests.sh        # Orchestration: up → migrate → test → down
├── tests/
│   └── integration/
│       ├── __init__.py
│       ├── conftest.py                  # Shared fixtures
│       ├── test_api_health.py           # Basic endpoint health checks
│       ├── test_sessions.py             # Session lifecycle CRUD
│       ├── test_trading_flow.py         # Scrape → backtest → trades → P&L
│       └── test_backtest.py             # Seed real prices → backtest summary
```

---

## Shell Script: `scripts/run-integration-tests.sh`

Responsibilities:
1. `docker compose up --build -d` — build all images and start containers in background
2. Poll `GET http://localhost:8000/strategies` every 2s, up to 60s — wait for backend to be ready
3. `docker compose exec -T backend alembic upgrade head` — run DB migrations
4. `python -m pytest tests/integration/ -v --timeout=30 -m integration` — run the suite
5. Capture pytest exit code
6. `docker compose down -v` — tear down stack and wipe Postgres volume (ensures clean state for next run)
7. Exit with pytest's captured exit code

---

## New Backend Endpoint

**`POST /symbols/{symbol}/scrape`**

Immediately triggers the Yahoo Finance scraper for `{symbol}`, stores the result as a `PriceHistory` row, and returns the stored row. Returns `422` if Yahoo returns no data.

- Location: `backend/routers/market_data.py`
- No authentication required
- Retries: none (caller handles retries)
- Purpose: allows integration tests to seed real price data without waiting for the scheduler

---

## Test Fixtures: `tests/integration/conftest.py`

| Fixture | Scope | Description |
|---------|-------|-------------|
| `base_url` | session | `"http://localhost:8000"` |
| `client` | session | `httpx.AsyncClient` pointed at `base_url`, timeout=20s |
| `db_session` | session | Async SQLAlchemy connection to `localhost:5432` using `.env` credentials — for direct DB inspection and seeding |
| `clean_db` | function | Truncates `paper_trades`, `trading_sessions`, `price_history`, `aggregated_pnl` after each test that writes data |
| `scrape_symbol` | function | Calls `POST /symbols/{symbol}/scrape` with 3 retries (2s apart) — raises `pytest.skip` if Yahoo unreachable after all retries |

---

## Test Files

### `test_api_health.py`

- `GET /strategies` → status 200, body is a list, first item has keys `name`, `description`, `parameters`
- `GET /sessions/00000000-0000-0000-0000-000000000000` → status 404
- `GET /symbols/AAPL/latest` with empty DB → status 200, body is `null`

### `test_sessions.py`

Full session lifecycle with real Postgres:
1. `POST /sessions` with `{symbol: "INTC", strategy: "moving_average_crossover", strategy_params: {short_window: 3, long_window: 5}, starting_capital: 500, mode: "paper"}` → 200, response has `id`, `status == "active"`
2. `GET /sessions` → list contains the created session
3. `GET /sessions/{id}` → returns the session with correct symbol
4. `PATCH /sessions/{id}/stop` → status becomes `"closed"`
5. Verify `GET /sessions/{id}` shows `status == "closed"` after stop

Uses `clean_db` fixture.

### `test_trading_flow.py`

End-to-end: real price data → real strategy evaluation → real trades → real P&L

1. Call `scrape_symbol("AAPL")` fixture → verifies a `PriceHistory` row was stored
2. `GET /symbols/AAPL/latest` → returns a row with `close` > 0
3. `POST /sessions` to create a paper session for AAPL
4. `POST /backtest` with `symbol="AAPL"`, date range covering the scraped data, `strategy_params: {short_window: 3, long_window: 5}`, `starting_capital: 1000`
5. Assert response has keys: `trades` (list), `summary` (dict with `total_pnl`, `num_trades`, `win_rate`, `ending_capital`)
6. Assert all numeric summary fields are actual numbers (not None)
7. Assert `summary["ending_capital"]` is a float

Uses `clean_db` fixture.

### `test_backtest.py`

Seed 60 days of real AAPL historical prices, then run a full backtest:

1. Fetch 60 days of AAPL OHLCV from Yahoo Finance via `yfinance.download` directly in the fixture — insert all rows into `price_history` table via `db_session`
2. `POST /backtest` with `symbol="AAPL"`, full 60-day date range, `short_window=10, long_window=20`, `starting_capital=1000`
3. Assert response structure: `trades` is a list, `summary` has all required keys
4. Assert `summary["num_trades"] >= 0`
5. Assert `summary["win_rate"]` is between 0.0 and 1.0
6. Assert `summary["ending_capital"]` is a positive float
7. If any trades exist, assert each trade has `action`, `price_at_signal`, `pnl` (may be None if open), `status`

Uses `clean_db` fixture.

---

## pytest.ini Changes

Add to existing `pytest.ini`:

```ini
markers =
    integration: marks tests as integration tests requiring Docker stack
```

Unit tests (`tests/backend/`) are unaffected — they have no `integration` marker and run without Docker.

---

## Running the Tests

```bash
# Full run (builds, tests, tears down)
./scripts/run-integration-tests.sh

# If stack is already running (development iteration)
python -m pytest tests/integration/ -v -m integration
```

---

## Assumptions & Constraints

- Docker Desktop must be running before executing the shell script
- Internet access required (Yahoo Finance)
- Yahoo Finance rate limits may cause occasional flakiness — `scrape_symbol` fixture retries 3x before skipping
- Tests assert on structure/types, not exact market values
- `docker compose down -v` wipes the Postgres volume — do not run against a stack with data you want to keep
