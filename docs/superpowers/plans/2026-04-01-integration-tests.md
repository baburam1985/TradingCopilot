# Integration Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker-based integration test suite that hits the real running stack with zero mocking — real Postgres, real FastAPI endpoints, real Yahoo Finance data.

**Architecture:** A shell script (`scripts/run-integration-tests.sh`) orchestrates `docker compose up → migrate → pytest → docker compose down`. The pytest suite in `tests/integration/` connects to `localhost:8000` (FastAPI) and `localhost:5432` (Postgres) directly from the host machine. A new `POST /symbols/{symbol}/scrape` endpoint allows tests to trigger real Yahoo Finance fetches on demand.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio, httpx, SQLAlchemy asyncio + asyncpg, yfinance, python-dotenv, Docker Compose, bash

---

## File Structure

```
TradingCopilot/
├── scripts/
│   └── run-integration-tests.sh          # NEW: orchestration script
├── backend/
│   └── routers/
│       └── market_data.py                # MODIFY: add POST /symbols/{symbol}/scrape
├── tests/
│   └── integration/
│       ├── __init__.py                   # NEW: empty
│       ├── requirements.txt              # NEW: local deps for integration tests
│       ├── conftest.py                   # NEW: httpx client, db_session, clean_db, scrape_symbol fixtures
│       ├── test_api_health.py            # NEW: /strategies shape, 404s, empty latest
│       ├── test_sessions.py              # NEW: full session lifecycle CRUD
│       ├── test_trading_flow.py          # NEW: scrape real data → store → verify in DB → session
│       └── test_backtest.py              # NEW: seed 90 days real AAPL → backtest → verify summary
└── pytest.ini                            # MODIFY: add integration marker + asyncio_mode
```

---

## Task 1: Add `POST /symbols/{symbol}/scrape` Endpoint

**Files:**
- Modify: `backend/routers/market_data.py`
- Test: `tests/backend/test_api.py` (add one new unit test with scraper stubbed)

- [ ] **Step 1: Add a unit test for the scrape endpoint to `tests/backend/test_api.py`**

Append to the existing file (the scraper stubs at the top already cover `scrapers.yahoo`):

```python
@pytest.mark.asyncio
async def test_scrape_endpoint_returns_422_when_yahoo_fails(monkeypatch):
    """When yahoo scraper returns success=False, endpoint returns 422."""
    import scrapers.yahoo as yahoo_mod
    from scrapers.base import FetchResult

    async def fake_fetch(symbol):
        return FetchResult(source="yahoo", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error="No data")

    monkeypatch.setattr(yahoo_mod, "fetch_yahoo", fake_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/symbols/FAKE/scrape")
    assert resp.status_code == 422
```

- [ ] **Step 2: Run the new test to verify it FAILS**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && python -m pytest tests/backend/test_api.py::test_scrape_endpoint_returns_422_when_yahoo_fails -v
```
Expected: FAIL — endpoint does not exist yet.

- [ ] **Step 3: Add the scrape endpoint to `backend/routers/market_data.py`**

Open `backend/routers/market_data.py` and add these imports at the top:

```python
from datetime import datetime, timezone
from fastapi import HTTPException
from scrapers.yahoo import fetch_yahoo
```

Then append this endpoint after the existing `get_latest` function:

```python
@router.post("/{symbol}/scrape")
async def scrape_symbol(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await fetch_yahoo(symbol.upper())
    if not result.success:
        raise HTTPException(status_code=422, detail=f"Yahoo Finance returned no data: {result.error}")
    row = PriceHistory(
        symbol=symbol.upper(),
        timestamp=datetime.now(timezone.utc),
        open=result.open,
        high=result.high,
        low=result.low,
        close=result.close,
        volume=result.volume,
        yahoo_close=result.close,
        alphavantage_close=None,
        finnhub_close=None,
        outlier_flags={},
        sources_available=["yahoo"],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && python -m pytest tests/backend/test_api.py -v
```
Expected: 2 passed, 1 skipped.

- [ ] **Step 5: Run full unit test suite to confirm nothing broke**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && python -m pytest tests/backend/ -v
```
Expected: 25 passed, 1 skipped.

- [ ] **Step 6: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add backend/routers/market_data.py tests/backend/test_api.py && git commit -m "feat: add POST /symbols/{symbol}/scrape endpoint for on-demand Yahoo Finance fetch"
```

---

## Task 2: Shell Script + pytest.ini Update

**Files:**
- Create: `scripts/run-integration-tests.sh`
- Modify: `pytest.ini`

- [ ] **Step 1: Update `pytest.ini` to add integration marker and asyncio mode**

Replace the contents of `pytest.ini` with:

```ini
[pytest]
testpaths = tests
pythonpath = backend
asyncio_mode = auto
markers =
    integration: marks tests as integration tests requiring a running Docker stack
```

- [ ] **Step 2: Verify existing unit tests still pass with new pytest.ini**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && python -m pytest tests/backend/ -v
```
Expected: 25 passed, 1 skipped (same as before).

- [ ] **Step 3: Create `scripts/` directory and `scripts/run-integration-tests.sh`**

```bash
mkdir -p "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/scripts"
```

Create `scripts/run-integration-tests.sh` with this content:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "==> Building and starting Docker Compose stack..."
docker compose up --build -d

echo "==> Waiting for backend to be ready (up to 60s)..."
TIMEOUT=60
ELAPSED=0
until curl -sf http://localhost:8000/strategies > /dev/null 2>&1; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: Backend did not become ready within ${TIMEOUT}s"
    docker compose down -v
    exit 1
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo "    Backend is ready (${ELAPSED}s elapsed)"

echo "==> Running database migrations..."
docker compose exec -T backend alembic upgrade head

echo "==> Running integration tests..."
set +e
python -m pytest tests/integration/ -v -m integration --timeout=60
TEST_EXIT_CODE=$?
set -e

echo "==> Tearing down Docker Compose stack..."
docker compose down -v

echo "==> Done. Exit code: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE
```

- [ ] **Step 4: Make the script executable**

```bash
chmod +x "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot/scripts/run-integration-tests.sh"
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add pytest.ini scripts/run-integration-tests.sh && git commit -m "feat: add integration test shell script and pytest integration marker"
```

---

## Task 3: Integration Test Infrastructure — `conftest.py` + `requirements.txt`

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/requirements.txt`
- Create: `tests/integration/conftest.py`

- [ ] **Step 1: Create `tests/integration/__init__.py`** (empty file)

- [ ] **Step 2: Create `tests/integration/requirements.txt`**

```
httpx>=0.27.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
yfinance>=0.2.37
python-dotenv>=1.0.0
pytest-timeout>=2.3.0
```

- [ ] **Step 3: Create `tests/integration/conftest.py`**

```python
import asyncio
import os
import pytest
import httpx
from dotenv import dotenv_values
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Read credentials from .env (which has POSTGRES_HOST=db for Docker internal networking)
# We override host to localhost since tests run on the host machine, not inside Docker
_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

INTEGRATION_DB_URL = (
    f"postgresql+asyncpg://{_env['POSTGRES_USER']}:{_env['POSTGRES_PASSWORD']}"
    f"@localhost:{_env.get('POSTGRES_PORT', '5432')}/{_env['POSTGRES_DB']}"
)
BASE_URL = "http://localhost:8000"

_engine = create_async_engine(INTEGRATION_DB_URL, echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as c:
        yield c


@pytest.fixture(scope="session")
async def db_session():
    async with _session_factory() as session:
        yield session


@pytest.fixture
async def clean_db(db_session):
    yield
    # Truncate in FK-safe order after each test
    await db_session.execute(
        __import__("sqlalchemy").text(
            "TRUNCATE TABLE paper_trades, aggregated_pnl, sessions, price_history RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()


@pytest.fixture
async def scrape_symbol(client):
    """Returns an async callable that POSTs /symbols/{symbol}/scrape with retries."""
    async def _scrape(symbol: str, retries: int = 3, delay: float = 2.0):
        last_exc = None
        for attempt in range(retries):
            try:
                resp = await client.post(f"/symbols/{symbol}/scrape")
                if resp.status_code == 200:
                    return resp.json()
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        pytest.skip(f"Yahoo Finance unreachable after {retries} attempts: {last_exc}")
    return _scrape
```

- [ ] **Step 4: Verify conftest imports cleanly (no Docker needed yet)**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && python -c "import tests.integration.conftest; print('OK')"
```
Expected: `OK` (no import errors).

- [ ] **Step 5: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add tests/integration/ && git commit -m "feat: add integration test infrastructure (conftest, fixtures, requirements)"
```

---

## Task 4: `test_api_health.py`

**Files:**
- Create: `tests/integration/test_api_health.py`

- [ ] **Step 1: Create `tests/integration/test_api_health.py`**

```python
import pytest
import uuid

pytestmark = pytest.mark.integration


async def test_strategies_returns_moving_average(client):
    resp = await client.get("/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    strategy = data[0]
    assert "name" in strategy
    assert "description" in strategy
    assert "parameters" in strategy
    assert strategy["name"] == "moving_average_crossover"


async def test_unknown_session_returns_404(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/sessions/{fake_id}")
    assert resp.status_code == 404


async def test_latest_price_empty_db_returns_null(client, clean_db):
    resp = await client.get("/symbols/ZZZTEST/latest")
    assert resp.status_code == 200
    assert resp.json() is None
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add tests/integration/test_api_health.py && git commit -m "feat: add integration health check tests"
```

---

## Task 5: `test_sessions.py`

**Files:**
- Create: `tests/integration/test_sessions.py`

- [ ] **Step 1: Create `tests/integration/test_sessions.py`**

```python
import pytest

pytestmark = pytest.mark.integration

SESSION_PAYLOAD = {
    "symbol": "INTC",
    "strategy": "moving_average_crossover",
    "strategy_params": {"short_window": 3, "long_window": 5},
    "starting_capital": 500.0,
    "mode": "paper",
}


async def test_create_session(client, clean_db):
    resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["symbol"] == "INTC"
    assert data["status"] == "active"
    assert data["mode"] == "paper"
    assert float(data["starting_capital"]) == 500.0


async def test_list_sessions_contains_created(client, clean_db):
    await client.post("/sessions", json=SESSION_PAYLOAD)
    resp = await client.get("/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    assert any(s["symbol"] == "INTC" for s in sessions)


async def test_get_session_by_id(client, clean_db):
    create_resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = create_resp.json()["id"]
    resp = await client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == session_id
    assert resp.json()["symbol"] == "INTC"


async def test_stop_session(client, clean_db):
    create_resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = create_resp.json()["id"]
    stop_resp = await client.patch(f"/sessions/{session_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "closed"


async def test_get_stopped_session_shows_closed(client, clean_db):
    create_resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = create_resp.json()["id"]
    await client.patch(f"/sessions/{session_id}/stop")
    resp = await client.get(f"/sessions/{session_id}")
    assert resp.json()["status"] == "closed"
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add tests/integration/test_sessions.py && git commit -m "feat: add integration tests for session lifecycle CRUD"
```

---

## Task 6: `test_trading_flow.py`

**Files:**
- Create: `tests/integration/test_trading_flow.py`

- [ ] **Step 1: Create `tests/integration/test_trading_flow.py`**

```python
import pytest

pytestmark = pytest.mark.integration


async def test_scrape_stores_price_row(client, scrape_symbol, clean_db):
    row = await scrape_symbol("AAPL")
    assert row is not None
    assert row["symbol"] == "AAPL"
    assert float(row["close"]) > 0
    assert row["sources_available"] == ["yahoo"]


async def test_latest_price_after_scrape(client, scrape_symbol, clean_db):
    await scrape_symbol("AAPL")
    resp = await client.get("/symbols/AAPL/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["symbol"] == "AAPL"
    assert float(data["close"]) > 0


async def test_create_session_and_query_trades(client, scrape_symbol, clean_db):
    await scrape_symbol("AAPL")

    session_resp = await client.post("/sessions", json={
        "symbol": "AAPL",
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 3, "long_window": 5},
        "starting_capital": 1000.0,
        "mode": "paper",
    })
    assert session_resp.status_code == 200
    session_id = session_resp.json()["id"]

    trades_resp = await client.get(f"/sessions/{session_id}/trades")
    assert trades_resp.status_code == 200
    assert isinstance(trades_resp.json(), list)


async def test_pnl_endpoint_returns_summary_structure(client, scrape_symbol, clean_db):
    await scrape_symbol("AAPL")

    session_resp = await client.post("/sessions", json={
        "symbol": "AAPL",
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 3, "long_window": 5},
        "starting_capital": 1000.0,
        "mode": "paper",
    })
    session_id = session_resp.json()["id"]

    pnl_resp = await client.get(f"/sessions/{session_id}/pnl")
    assert pnl_resp.status_code == 200
    data = pnl_resp.json()
    assert "all_time" in data
    summary = data["all_time"]
    for key in ("total_pnl", "num_trades", "num_wins", "num_losses", "win_rate", "ending_capital"):
        assert key in summary, f"Missing key: {key}"
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add tests/integration/test_trading_flow.py && git commit -m "feat: add integration tests for scrape → session → trades → P&L flow"
```

---

## Task 7: `test_backtest.py`

**Files:**
- Create: `tests/integration/test_backtest.py`

- [ ] **Step 1: Create `tests/integration/test_backtest.py`**

```python
import uuid
import pytest
import yfinance as yf
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def _seed_price_history(db_session, symbol: str, days: int = 90):
    """Fetch real historical daily bars from Yahoo Finance and insert into price_history."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = await __import__("asyncio").to_thread(
        lambda: yf.download(symbol, start=start.date(), end=end.date(), progress=False)
    )
    if df.empty:
        pytest.skip(f"Yahoo Finance returned no historical data for {symbol}")

    # Flatten MultiIndex columns if present (yfinance >= 0.2.38 returns MultiIndex)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
            "yahoo_close": float(row["Close"]),
            "alphavantage_close": None,
            "finnhub_close": None,
            "outlier_flags": "{}",
            "sources_available": "{yahoo}",
        })

    if not rows:
        pytest.skip("No rows to insert after parsing Yahoo Finance data")

    await db_session.execute(
        text("""
            INSERT INTO price_history
              (id, symbol, timestamp, open, high, low, close, volume,
               yahoo_close, alphavantage_close, finnhub_close, outlier_flags, sources_available)
            VALUES
              (:id, :symbol, :timestamp, :open, :high, :low, :close, :volume,
               :yahoo_close, :alphavantage_close, :finnhub_close, :outlier_flags::jsonb, :sources_available::text[])
        """),
        rows,
    )
    await db_session.commit()
    return rows


async def test_backtest_returns_valid_structure(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)

    timestamps = [r["timestamp"] for r in rows]
    from_dt = min(timestamps).isoformat()
    to_dt = max(timestamps).isoformat()

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": from_dt,
        "to_dt": to_dt,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "summary" in data
    assert isinstance(data["trades"], list)


async def test_backtest_summary_has_required_keys(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": min(timestamps).isoformat(),
        "to_dt": max(timestamps).isoformat(),
    })
    summary = resp.json()["summary"]
    for key in ("total_pnl", "num_trades", "num_wins", "num_losses", "win_rate", "starting_capital", "ending_capital"):
        assert key in summary, f"Missing key in summary: {key}"


async def test_backtest_summary_values_are_valid_types(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": min(timestamps).isoformat(),
        "to_dt": max(timestamps).isoformat(),
    })
    summary = resp.json()["summary"]
    assert summary["num_trades"] >= 0
    assert 0.0 <= summary["win_rate"] <= 1.0
    assert summary["ending_capital"] > 0
    assert isinstance(summary["total_pnl"], (int, float))


async def test_backtest_trades_have_required_fields(client, db_session, clean_db):
    symbol = "AAPL"
    rows = await _seed_price_history(db_session, symbol, days=90)
    timestamps = [r["timestamp"] for r in rows]

    resp = await client.post("/backtest", json={
        "symbol": symbol,
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 10, "long_window": 20},
        "starting_capital": 1000.0,
        "from_dt": min(timestamps).isoformat(),
        "to_dt": max(timestamps).isoformat(),
    })
    trades = resp.json()["trades"]
    for trade in trades:
        assert "action" in trade
        assert "price_at_signal" in trade
        assert "status" in trade
        assert trade["action"] in ("buy", "sell")
        assert float(trade["price_at_signal"]) > 0
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add tests/integration/test_backtest.py && git commit -m "feat: add integration backtest tests with real Yahoo Finance historical data"
```

---

## Task 8: Smoke-Test the Full Suite

This task verifies everything works end-to-end. Requires Docker Desktop running.

- [ ] **Step 1: Ensure Docker is running**

```bash
docker info
```
Expected: prints Docker version info without error.

- [ ] **Step 2: Run the integration test script**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && ./scripts/run-integration-tests.sh
```
Expected: all integration tests pass, stack tears down, script exits 0.

- [ ] **Step 3: Verify unit tests are unaffected**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && python -m pytest tests/backend/ -v
```
Expected: 25 passed, 1 skipped.

- [ ] **Step 4: Final commit**

```bash
cd "/Users/rambabubandam/My Drive/Documents-Master/Workspace/CursorWorkspace/TradingCopilot" && git add . && git commit -m "chore: verify integration test suite runs end-to-end"
```
