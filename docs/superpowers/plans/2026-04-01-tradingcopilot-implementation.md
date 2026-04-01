# TradingCopilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized day trading web application that scrapes multi-source market data, runs Moving Average Crossover strategy signals, and executes paper trades (real-time and backtest) with full P&L reporting.

**Architecture:** FastAPI backend with APScheduler for on-demand multi-source scraping (Yahoo Finance + Alpha Vantage + Finnhub), Postgres for all persistent data, and a React frontend served by Nginx — all wired via Docker Compose.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, APScheduler, yfinance, httpx, finnhub-python, pandas, React 18, Recharts, Axios, Postgres 15, Nginx, Docker Compose

---

## File Structure

```
TradingCopilot/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                         # FastAPI app entry point + scheduler startup
│   ├── config.py                       # Settings loaded from env vars
│   ├── database.py                     # SQLAlchemy async engine + session factory
│   ├── models/
│   │   ├── price_history.py            # PriceHistory ORM model
│   │   ├── trading_session.py          # TradingSession ORM model
│   │   ├── paper_trade.py              # PaperTrade ORM model
│   │   └── aggregated_pnl.py          # AggregatedPnl ORM model
│   ├── migrations/                     # Alembic migration files
│   │   ├── env.py
│   │   └── versions/
│   ├── scrapers/
│   │   ├── base.py                     # FetchResult dataclass
│   │   ├── yahoo.py                    # fetch_yahoo(symbol) -> FetchResult
│   │   ├── alpha_vantage.py            # fetch_alpha_vantage(symbol) -> FetchResult
│   │   ├── finnhub.py                  # fetch_finnhub(symbol) -> FetchResult
│   │   └── aggregator.py              # aggregate(results) -> ConsensusBar
│   ├── scheduler/
│   │   ├── market_hours.py             # is_market_open() -> bool
│   │   └── scraper_job.py              # APScheduler setup, register/unregister symbol
│   ├── strategies/
│   │   ├── base.py                     # StrategyBase (ABC), Signal dataclass
│   │   └── moving_average_crossover.py # MovingAverageCrossover(StrategyBase)
│   ├── executor/
│   │   ├── base.py                     # ExecutorBase (ABC)
│   │   ├── paper.py                    # PaperExecutor — open/close trades, compute P&L
│   │   └── live_stub.py                # LiveExecutorStub — logs only, no real orders
│   ├── backtester/
│   │   └── runner.py                   # BacktestRunner — no-lookahead replay
│   ├── pnl/
│   │   └── aggregator.py              # compute_aggregated_pnl(session_id, db)
│   └── routers/
│       ├── sessions.py                 # POST/GET /sessions, PATCH /sessions/{id}/stop
│       ├── market_data.py              # GET /symbols/{symbol}/history|latest
│       ├── strategies.py               # GET /strategies
│       ├── trades.py                   # GET /sessions/{id}/trades|pnl
│       ├── backtest.py                 # POST /backtest
│       └── websocket.py               # WS /ws/sessions/{id}
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       │   └── client.js               # Axios instance + WebSocket helper
│       ├── pages/
│       │   ├── NewSession.jsx          # Session creation form
│       │   ├── LiveDashboard.jsx       # Real-time chart + trade log
│       │   └── Reports.jsx             # P&L charts + comparison view
│       └── components/
│           ├── PriceChart.jsx          # Recharts candlestick with signal markers
│           ├── TradeLog.jsx            # Table of trades for a session
│           ├── PnLChart.jsx            # P&L bar chart with period toggle
│           └── ComparisonView.jsx      # Paper P&L vs actual outcome side by side
└── tests/
    └── backend/
        ├── conftest.py                 # pytest fixtures: test DB, async client
        ├── test_aggregator.py          # consensus logic unit tests
        ├── test_moving_average_crossover.py
        ├── test_paper_executor.py
        ├── test_backtester.py
        ├── test_pnl_aggregator.py
        └── test_api.py                 # FastAPI integration tests
```

---

## Task 1: Project Scaffold + Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: Create `.env.example`**

```bash
# backend/.env (copy from .env.example and fill in)
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=tradingcopilot
POSTGRES_USER=trading
POSTGRES_PASSWORD=trading_secret
ALPHA_VANTAGE_API_KEY=your_key_here
FINNHUB_API_KEY=your_key_here
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

- [ ] **Step 3: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 4: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

- [ ] **Step 5: Create `frontend/nginx.conf`**

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

- [ ] **Step 6: Verify Docker Compose syntax**

```bash
docker compose config
```
Expected: prints resolved config with no errors.

- [ ] **Step 7: Commit**

```bash
git init
git add docker-compose.yml .env.example backend/Dockerfile frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: add Docker Compose scaffold with 3-container stack"
```

---

## Task 2: Backend Requirements + Config

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.29
asyncpg==0.29.0
alembic==1.13.1
apscheduler==3.10.4
yfinance==0.2.37
httpx==0.27.0
finnhub-python==2.4.19
pandas==2.2.1
python-dotenv==1.0.1
pytest==8.1.1
pytest-asyncio==0.23.6
httpx==0.27.0
```

- [ ] **Step 2: Create `backend/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

POSTGRES_HOST = os.environ["POSTGRES_HOST"]
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ["POSTGRES_DB"]
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]

DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt backend/config.py
git commit -m "feat: add backend requirements and config"
```

---

## Task 3: Database Models + Migrations

**Files:**
- Create: `backend/database.py`
- Create: `backend/models/price_history.py`
- Create: `backend/models/trading_session.py`
- Create: `backend/models/paper_trade.py`
- Create: `backend/models/aggregated_pnl.py`
- Create: `backend/migrations/env.py` (Alembic)

- [ ] **Step 1: Write failing test for model imports**

```python
# tests/backend/test_models.py
def test_models_importable():
    from backend.models.price_history import PriceHistory
    from backend.models.trading_session import TradingSession
    from backend.models.paper_trade import PaperTrade
    from backend.models.aggregated_pnl import AggregatedPnl
    assert PriceHistory.__tablename__ == "price_history"
    assert TradingSession.__tablename__ == "sessions"
    assert PaperTrade.__tablename__ == "paper_trades"
    assert AggregatedPnl.__tablename__ == "aggregated_pnl"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest ../tests/backend/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `backend/database.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: Create `backend/models/price_history.py`**

```python
import uuid
from sqlalchemy import String, Numeric, BigInteger, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    yahoo_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    alphavantage_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    finnhub_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    outlier_flags: Mapped[dict] = mapped_column(JSONB, nullable=True)
    sources_available: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
```

- [ ] **Step 5: Create `backend/models/trading_session.py`**

```python
import uuid
from sqlalchemy import String, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class TradingSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    starting_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # "paper" or "live"
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=False)
    closed_at: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=True)
```

- [ ] **Step 6: Create `backend/models/paper_trade.py`**

```python
import uuid
from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(4), nullable=False)  # "buy" or "sell"
    signal_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    price_at_signal: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    timestamp_open: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=False)
    timestamp_close: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=True)
    price_at_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    pnl: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
```

- [ ] **Step 7: Create `backend/models/aggregated_pnl.py`**

```python
import uuid
from sqlalchemy import String, Numeric, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class AggregatedPnl(Base):
    __tablename__ = "aggregated_pnl"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "day","week","month","all_time"
    period_start: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=False)
    period_end: Mapped[str] = mapped_column(TIMESTAMPTZ, nullable=False)
    total_pnl: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    num_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    num_wins: Mapped[int] = mapped_column(Integer, nullable=False)
    num_losses: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    starting_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    ending_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
```

- [ ] **Step 8: Run test to verify it passes**

```bash
cd backend && pytest ../tests/backend/test_models.py -v
```
Expected: PASS

- [ ] **Step 9: Initialize Alembic and create initial migration**

```bash
cd backend
alembic init migrations
# Edit migrations/env.py to use async engine and import all models
alembic revision --autogenerate -m "initial tables"
```

In `migrations/env.py`, add before `run_migrations_offline()`:
```python
from database import Base
from models.price_history import PriceHistory
from models.trading_session import TradingSession
from models.paper_trade import PaperTrade
from models.aggregated_pnl import AggregatedPnl

target_metadata = Base.metadata
```

- [ ] **Step 10: Commit**

```bash
git add backend/database.py backend/models/ backend/migrations/
git commit -m "feat: add SQLAlchemy models and Alembic migrations for all 4 tables"
```

---

## Task 4: Multi-Source Data Fetchers + Consensus Aggregator

**Files:**
- Create: `backend/scrapers/base.py`
- Create: `backend/scrapers/yahoo.py`
- Create: `backend/scrapers/alpha_vantage.py`
- Create: `backend/scrapers/finnhub.py`
- Create: `backend/scrapers/aggregator.py`
- Test: `tests/backend/test_aggregator.py`

- [ ] **Step 1: Write failing tests for aggregator**

```python
# tests/backend/test_aggregator.py
import pytest
from backend.scrapers.base import FetchResult
from backend.scrapers.aggregator import aggregate

def make_result(source, close, open_=100.0, high=105.0, low=99.0, volume=1000000):
    return FetchResult(source=source, open=open_, high=high, low=low,
                       close=close, volume=volume, success=True)

def test_consensus_is_average_of_closes():
    results = [
        make_result("yahoo", close=150.0),
        make_result("alphavantage", close=150.6),
        make_result("finnhub", close=149.4),
    ]
    bar = aggregate(results)
    assert bar.close == pytest.approx(150.0, abs=0.01)

def test_outlier_flagged_when_deviation_over_1_percent():
    results = [
        make_result("yahoo", close=150.0),
        make_result("alphavantage", close=150.0),
        make_result("finnhub", close=160.0),  # >1% deviation
    ]
    bar = aggregate(results)
    assert "finnhub" in bar.outlier_flags

def test_consensus_works_with_two_sources():
    results = [
        make_result("yahoo", close=100.0),
        FetchResult(source="alphavantage", open=0, high=0, low=0, close=0, volume=0, success=False),
        make_result("finnhub", close=102.0),
    ]
    bar = aggregate(results)
    assert bar.close == pytest.approx(101.0, abs=0.01)
    assert "alphavantage" not in bar.sources_available

def test_sources_available_lists_successful_sources():
    results = [
        make_result("yahoo", close=100.0),
        make_result("alphavantage", close=100.0),
        FetchResult(source="finnhub", open=0, high=0, low=0, close=0, volume=0, success=False),
    ]
    bar = aggregate(results)
    assert set(bar.sources_available) == {"yahoo", "alphavantage"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest ../tests/backend/test_aggregator.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `backend/scrapers/base.py`**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FetchResult:
    source: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    success: bool
    error: Optional[str] = None

@dataclass
class ConsensusBar:
    open: float
    high: float
    low: float
    close: float
    volume: int
    yahoo_close: Optional[float]
    alphavantage_close: Optional[float]
    finnhub_close: Optional[float]
    outlier_flags: dict
    sources_available: list[str]
```

- [ ] **Step 4: Create `backend/scrapers/aggregator.py`**

```python
from scrapers.base import FetchResult, ConsensusBar

def aggregate(results: list[FetchResult]) -> ConsensusBar:
    successful = [r for r in results if r.success]
    if not successful:
        raise ValueError("All data sources failed — cannot form consensus")

    closes = [r.close for r in successful]
    consensus_close = sum(closes) / len(closes)

    outlier_flags = {}
    for r in successful:
        deviation = abs(r.close - consensus_close) / consensus_close
        if deviation > 0.01:
            outlier_flags[r.source] = {
                "close": r.close,
                "deviation_pct": round(deviation * 100, 2)
            }

    opens = [r.open for r in successful]
    highs = [r.high for r in successful]
    lows = [r.low for r in successful]
    volumes = [r.volume for r in successful]

    by_source = {r.source: r for r in results}

    return ConsensusBar(
        open=sum(opens) / len(opens),
        high=max(highs),
        low=min(lows),
        close=consensus_close,
        volume=int(sum(volumes) / len(volumes)),
        yahoo_close=by_source["yahoo"].close if by_source.get("yahoo") and by_source["yahoo"].success else None,
        alphavantage_close=by_source["alphavantage"].close if by_source.get("alphavantage") and by_source["alphavantage"].success else None,
        finnhub_close=by_source["finnhub"].close if by_source.get("finnhub") and by_source["finnhub"].success else None,
        outlier_flags=outlier_flags,
        sources_available=[r.source for r in successful],
    )
```

- [ ] **Step 5: Create `backend/scrapers/yahoo.py`**

```python
import asyncio
import yfinance as yf
from scrapers.base import FetchResult

async def fetch_yahoo(symbol: str) -> FetchResult:
    try:
        ticker = await asyncio.to_thread(
            lambda: yf.download(symbol, period="1d", interval="1m", progress=False)
        )
        if ticker.empty:
            return FetchResult(source="yahoo", open=0, high=0, low=0, close=0,
                               volume=0, success=False, error="Empty response")
        last = ticker.iloc[-1]
        return FetchResult(
            source="yahoo",
            open=float(last["Open"]),
            high=float(last["High"]),
            low=float(last["Low"]),
            close=float(last["Close"]),
            volume=int(last["Volume"]),
            success=True,
        )
    except Exception as e:
        return FetchResult(source="yahoo", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error=str(e))
```

- [ ] **Step 6: Create `backend/scrapers/alpha_vantage.py`**

```python
import httpx
from config import ALPHA_VANTAGE_API_KEY
from scrapers.base import FetchResult

AV_BASE = "https://www.alphavantage.co/query"

async def fetch_alpha_vantage(symbol: str) -> FetchResult:
    if not ALPHA_VANTAGE_API_KEY:
        return FetchResult(source="alphavantage", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error="No API key configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(AV_BASE, params={
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": "1min",
                "outputsize": "compact",
                "apikey": ALPHA_VANTAGE_API_KEY,
            })
            data = resp.json()
            ts = data.get("Time Series (1min)", {})
            if not ts:
                return FetchResult(source="alphavantage", open=0, high=0, low=0, close=0,
                                   volume=0, success=False, error="No time series in response")
            latest_key = sorted(ts.keys())[-1]
            bar = ts[latest_key]
            return FetchResult(
                source="alphavantage",
                open=float(bar["1. open"]),
                high=float(bar["2. high"]),
                low=float(bar["3. low"]),
                close=float(bar["4. close"]),
                volume=int(bar["5. volume"]),
                success=True,
            )
    except Exception as e:
        return FetchResult(source="alphavantage", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error=str(e))
```

- [ ] **Step 7: Create `backend/scrapers/finnhub.py`**

```python
import asyncio
import finnhub
from config import FINNHUB_API_KEY
from scrapers.base import FetchResult

async def fetch_finnhub(symbol: str) -> FetchResult:
    if not FINNHUB_API_KEY:
        return FetchResult(source="finnhub", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error="No API key configured")
    try:
        client = finnhub.Client(api_key=FINNHUB_API_KEY)
        quote = await asyncio.to_thread(client.quote, symbol)
        if not quote or quote.get("c") == 0:
            return FetchResult(source="finnhub", open=0, high=0, low=0, close=0,
                               volume=0, success=False, error="Empty quote")
        return FetchResult(
            source="finnhub",
            open=float(quote["o"]),
            high=float(quote["h"]),
            low=float(quote["l"]),
            close=float(quote["c"]),
            volume=0,  # Finnhub quote doesn't include volume
            success=True,
        )
    except Exception as e:
        return FetchResult(source="finnhub", open=0, high=0, low=0, close=0,
                           volume=0, success=False, error=str(e))
```

- [ ] **Step 8: Run aggregator tests to verify they pass**

```bash
cd backend && pytest ../tests/backend/test_aggregator.py -v
```
Expected: 4 tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/scrapers/
git commit -m "feat: add multi-source data fetchers (Yahoo, AlphaVantage, Finnhub) and consensus aggregator"
```

---

## Task 5: APScheduler + On-Demand Scraper Job

**Files:**
- Create: `backend/scheduler/market_hours.py`
- Create: `backend/scheduler/scraper_job.py`

- [ ] **Step 1: Write failing tests for market hours**

```python
# tests/backend/test_market_hours.py
from datetime import datetime, timezone
import pytest
from backend.scheduler.market_hours import is_market_open

def test_market_open_on_weekday_during_hours():
    # Tuesday 10:00 AM ET = 14:00 UTC
    dt = datetime(2026, 3, 17, 14, 0, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is True

def test_market_closed_before_open():
    # Tuesday 9:00 AM ET = 13:00 UTC
    dt = datetime(2026, 3, 17, 13, 0, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is False

def test_market_closed_after_close():
    # Tuesday 4:30 PM ET = 20:30 UTC
    dt = datetime(2026, 3, 17, 20, 30, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is False

def test_market_closed_on_saturday():
    dt = datetime(2026, 3, 14, 15, 0, 0, tzinfo=timezone.utc)
    assert is_market_open(dt) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest ../tests/backend/test_market_hours.py -v
```
Expected: FAIL

- [ ] **Step 3: Create `backend/scheduler/market_hours.py`**

```python
from datetime import datetime, time, timezone
import zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def is_market_open(dt: datetime | None = None) -> bool:
    if dt is None:
        dt = datetime.now(timezone.utc)
    et_dt = dt.astimezone(ET)
    if et_dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return MARKET_OPEN <= et_dt.time() < MARKET_CLOSE
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest ../tests/backend/test_market_hours.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Create `backend/scheduler/scraper_job.py`**

```python
import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scrapers.yahoo import fetch_yahoo
from scrapers.alpha_vantage import fetch_alpha_vantage
from scrapers.finnhub import fetch_finnhub
from scrapers.aggregator import aggregate
from scheduler.market_hours import is_market_open

scheduler = AsyncIOScheduler()
_active_symbols: set[str] = set()

def register_symbol(symbol: str):
    _active_symbols.add(symbol.upper())

def unregister_symbol(symbol: str):
    _active_symbols.discard(symbol.upper())

async def _scrape_all():
    if not is_market_open():
        return
    tasks = [_scrape_symbol(sym) for sym in list(_active_symbols)]
    await asyncio.gather(*tasks)

async def _scrape_symbol(symbol: str):
    from database import AsyncSessionLocal
    from models.price_history import PriceHistory

    results = await asyncio.gather(
        fetch_yahoo(symbol),
        fetch_alpha_vantage(symbol),
        fetch_finnhub(symbol),
    )
    try:
        bar = aggregate(results)
    except ValueError:
        return  # All sources failed — skip this tick

    record = PriceHistory(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        yahoo_close=bar.yahoo_close,
        alphavantage_close=bar.alphavantage_close,
        finnhub_close=bar.finnhub_close,
        outlier_flags=bar.outlier_flags,
        sources_available=bar.sources_available,
    )
    async with AsyncSessionLocal() as db:
        db.add(record)
        await db.commit()

    await _trigger_strategy(symbol, bar.close)

async def _trigger_strategy(symbol: str, current_price: float):
    # Imported here to avoid circular imports
    from executor.paper import PaperExecutor
    from strategies.moving_average_crossover import MovingAverageCrossover
    from database import AsyncSessionLocal
    from models.trading_session import TradingSession
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.symbol == symbol,
                TradingSession.status == "active",
                TradingSession.mode == "paper",
            )
        )
        sessions = result.scalars().all()

    for session in sessions:
        strategy = MovingAverageCrossover(**session.strategy_params)
        from sqlalchemy import select as sel
        async with AsyncSessionLocal() as db:
            ph_result = await db.execute(
                sel(PriceHistory)
                .where(PriceHistory.symbol == symbol)
                .order_by(PriceHistory.timestamp.desc())
                .limit(strategy.long_window + 1)
            )
            bars = ph_result.scalars().all()
        closes = [float(b.close) for b in reversed(bars)]
        signal = strategy.analyze(closes)
        if signal.action != "hold":
            executor = PaperExecutor()
            await executor.execute(session, signal, current_price)

def start_scheduler():
    scheduler.add_job(_scrape_all, "interval", minutes=1, id="scrape_all")
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()
```

- [ ] **Step 6: Commit**

```bash
git add backend/scheduler/
git commit -m "feat: add APScheduler with on-demand symbol registration and market hours check"
```

---

## Task 6: Strategy Engine — Base + Moving Average Crossover

**Files:**
- Create: `backend/strategies/base.py`
- Create: `backend/strategies/moving_average_crossover.py`
- Test: `tests/backend/test_moving_average_crossover.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backend/test_moving_average_crossover.py
import pytest
from backend.strategies.moving_average_crossover import MovingAverageCrossover

def _prices(n: int, value: float) -> list[float]:
    return [value] * n

def test_golden_cross_generates_buy_signal():
    # short MA (3) crosses above long MA (5)
    # last 5 prices trending up: long MA = 10, short MA rising above
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    # prices: [8, 9, 10, 15, 16, 17]
    # short MA of last 3 = (15+16+17)/3 = 16.0
    # long MA of last 5  = (9+10+15+16+17)/5 = 13.4
    # prev short MA of [8,9,10,15,16] last 3 = (10+15+16)/3 = 13.67
    # prev long MA = (8+9+10+15+16)/5 = 11.6
    # short crossed above long
    prices = [8.0, 9.0, 10.0, 15.0, 16.0, 17.0]
    signal = strategy.analyze(prices)
    assert signal.action == "buy"
    assert "golden cross" in signal.reason.lower()

def test_death_cross_generates_sell_signal():
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    # prices trending down: short MA crosses below long MA
    prices = [17.0, 16.0, 15.0, 10.0, 9.0, 8.0]
    signal = strategy.analyze(prices)
    assert signal.action == "sell"
    assert "death cross" in signal.reason.lower()

def test_no_crossover_generates_hold():
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    prices = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    signal = strategy.analyze(prices)
    assert signal.action == "hold"

def test_insufficient_data_generates_hold():
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    prices = [10.0, 11.0]  # Not enough for long_window=5
    signal = strategy.analyze(prices)
    assert signal.action == "hold"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest ../tests/backend/test_moving_average_crossover.py -v
```
Expected: FAIL

- [ ] **Step 3: Create `backend/strategies/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Signal:
    action: str  # "buy" | "sell" | "hold"
    reason: str
    confidence: float

class StrategyBase(ABC):
    name: str
    description: str

    @abstractmethod
    def analyze(self, closes: list[float]) -> Signal:
        ...
```

- [ ] **Step 4: Create `backend/strategies/moving_average_crossover.py`**

```python
from strategies.base import StrategyBase, Signal

class MovingAverageCrossover(StrategyBase):
    name = "moving_average_crossover"
    description = "Buy on golden cross (short MA crosses above long MA), sell on death cross."

    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window

    def analyze(self, closes: list[float]) -> Signal:
        if len(closes) < self.long_window + 1:
            return Signal(action="hold", reason="Insufficient data for MA calculation", confidence=0.0)

        def ma(prices, window):
            return sum(prices[-window:]) / window

        short_ma_now = ma(closes, self.short_window)
        long_ma_now = ma(closes, self.long_window)

        prev_closes = closes[:-1]
        short_ma_prev = ma(prev_closes, self.short_window)
        long_ma_prev = ma(prev_closes, self.long_window)

        crossed_above = short_ma_prev <= long_ma_prev and short_ma_now > long_ma_now
        crossed_below = short_ma_prev >= long_ma_prev and short_ma_now < long_ma_now

        if crossed_above:
            return Signal(
                action="buy",
                reason=f"Golden cross: {self.short_window}MA ({short_ma_now:.2f}) crossed above {self.long_window}MA ({long_ma_now:.2f})",
                confidence=0.7,
            )
        if crossed_below:
            return Signal(
                action="sell",
                reason=f"Death cross: {self.short_window}MA ({short_ma_now:.2f}) crossed below {self.long_window}MA ({long_ma_now:.2f})",
                confidence=0.7,
            )
        return Signal(action="hold", reason="No crossover detected", confidence=0.0)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest ../tests/backend/test_moving_average_crossover.py -v
```
Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/strategies/
git commit -m "feat: add StrategyBase interface and MovingAverageCrossover strategy"
```

---

## Task 7: Paper Executor + Live Stub

**Files:**
- Create: `backend/executor/base.py`
- Create: `backend/executor/paper.py`
- Create: `backend/executor/live_stub.py`
- Test: `tests/backend/test_paper_executor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backend/test_paper_executor.py
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from backend.executor.paper import PaperExecutor
from backend.strategies.base import Signal

@pytest.fixture
def mock_session():
    s = MagicMock()
    s.id = uuid.uuid4()
    s.starting_capital = 1000.0
    s.strategy_params = {"short_window": 3, "long_window": 5}
    return s

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_buy_signal_creates_open_trade(mock_session, mock_db):
    executor = PaperExecutor()
    signal = Signal(action="buy", reason="Golden cross", confidence=0.7)
    trade = await executor.execute(mock_session, signal, current_price=150.0, db=mock_db)
    assert trade.action == "buy"
    assert trade.status == "open"
    assert float(trade.price_at_signal) == 150.0
    assert float(trade.quantity) > 0

@pytest.mark.asyncio
async def test_sell_signal_closes_open_trade(mock_session, mock_db):
    executor = PaperExecutor()
    buy_signal = Signal(action="buy", reason="Golden cross", confidence=0.7)
    open_trade = await executor.execute(mock_session, buy_signal, current_price=150.0, db=mock_db)

    sell_signal = Signal(action="sell", reason="Death cross", confidence=0.7)
    closed_trade = await executor.close_trade(open_trade, current_price=160.0, db=mock_db)
    assert closed_trade.status == "closed"
    assert float(closed_trade.price_at_close) == 160.0
    assert float(closed_trade.pnl) == pytest.approx(
        (160.0 - 150.0) * float(closed_trade.quantity), abs=0.01
    )

@pytest.mark.asyncio
async def test_pnl_is_negative_on_losing_trade(mock_session, mock_db):
    executor = PaperExecutor()
    buy_signal = Signal(action="buy", reason="Golden cross", confidence=0.7)
    open_trade = await executor.execute(mock_session, buy_signal, current_price=150.0, db=mock_db)
    closed_trade = await executor.close_trade(open_trade, current_price=140.0, db=mock_db)
    assert float(closed_trade.pnl) < 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest ../tests/backend/test_paper_executor.py -v
```
Expected: FAIL

- [ ] **Step 3: Create `backend/executor/base.py`**

```python
from abc import ABC, abstractmethod
from strategies.base import Signal

class ExecutorBase(ABC):
    @abstractmethod
    async def execute(self, session, signal: Signal, current_price: float, db):
        ...
```

- [ ] **Step 4: Create `backend/executor/paper.py`**

```python
from datetime import datetime, timezone
from executor.base import ExecutorBase
from models.paper_trade import PaperTrade
from strategies.base import Signal

class PaperExecutor(ExecutorBase):
    async def execute(self, session, signal: Signal, current_price: float, db=None):
        quantity = float(session.starting_capital) / current_price
        trade = PaperTrade(
            session_id=session.id,
            action=signal.action,
            signal_reason=signal.reason,
            price_at_signal=current_price,
            quantity=quantity,
            timestamp_open=datetime.now(timezone.utc),
            status="open",
        )
        if db:
            db.add(trade)
            await db.commit()
        return trade

    async def close_trade(self, trade: PaperTrade, current_price: float, db=None):
        trade.timestamp_close = datetime.now(timezone.utc)
        trade.price_at_close = current_price
        trade.pnl = (current_price - float(trade.price_at_signal)) * float(trade.quantity)
        trade.status = "closed"
        if db:
            await db.commit()
        return trade
```

- [ ] **Step 5: Create `backend/executor/live_stub.py`**

```python
import logging
from executor.base import ExecutorBase
from strategies.base import Signal

logger = logging.getLogger(__name__)

class LiveExecutorStub(ExecutorBase):
    async def execute(self, session, signal: Signal, current_price: float, db=None):
        logger.info(
            "[LIVE STUB] Would execute %s for %s at $%.4f (session %s)",
            signal.action, session.symbol, current_price, session.id
        )
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd backend && pytest ../tests/backend/test_paper_executor.py -v
```
Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/executor/
git commit -m "feat: add PaperExecutor with open/close trade logic and P&L computation, plus LiveExecutorStub"
```

---

## Task 8: Backtester

**Files:**
- Create: `backend/backtester/runner.py`
- Test: `tests/backend/test_backtester.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backend/test_backtester.py
import pytest
from backend.backtester.runner import BacktestRunner
from backend.strategies.moving_average_crossover import MovingAverageCrossover

def _make_bars(prices: list[float]):
    from types import SimpleNamespace
    return [SimpleNamespace(close=p, timestamp=f"2026-01-{i+1:02d}") for i, p in enumerate(prices)]

def test_backtest_no_lookahead():
    """Strategy at step N must only see prices up to step N."""
    seen_lengths = []

    class SpyStrategy(MovingAverageCrossover):
        def analyze(self, closes):
            seen_lengths.append(len(closes))
            return super().analyze(closes)

    bars = _make_bars([100.0] * 20)
    strategy = SpyStrategy(short_window=3, long_window=5)
    runner = BacktestRunner(strategy=strategy, starting_capital=1000.0)
    runner.run(bars)

    # At step i, strategy should see exactly i+1 prices
    for i, length in enumerate(seen_lengths):
        assert length == i + 1, f"At step {i}, saw {length} prices (expected {i+1})"

def test_backtest_records_trades_on_signals():
    # Create a price series that triggers a golden cross
    prices = [8.0, 9.0, 10.0, 15.0, 16.0, 17.0, 17.0, 17.0, 17.0, 17.0]
    bars = _make_bars(prices)
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    runner = BacktestRunner(strategy=strategy, starting_capital=1000.0)
    trades = runner.run(bars)
    buy_trades = [t for t in trades if t["action"] == "buy"]
    assert len(buy_trades) >= 1

def test_backtest_pnl_calculated_on_close():
    prices = [8.0, 9.0, 10.0, 15.0, 16.0, 17.0,  # golden cross → buy
              17.0, 16.0, 15.0, 10.0, 9.0, 8.0]   # death cross → sell
    bars = _make_bars(prices)
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    runner = BacktestRunner(strategy=strategy, starting_capital=1000.0)
    trades = runner.run(bars)
    closed = [t for t in trades if t["status"] == "closed"]
    assert len(closed) >= 1
    assert closed[0]["pnl"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest ../tests/backend/test_backtester.py -v
```
Expected: FAIL

- [ ] **Step 3: Create `backend/backtester/runner.py`**

```python
from strategies.base import StrategyBase, Signal

class BacktestRunner:
    def __init__(self, strategy: StrategyBase, starting_capital: float):
        self.strategy = strategy
        self.starting_capital = starting_capital

    def run(self, bars: list) -> list[dict]:
        trades = []
        open_trade = None

        for i, bar in enumerate(bars):
            # No lookahead: only feed prices up to and including current bar
            closes = [float(b.close) for b in bars[:i + 1]]
            signal = self.strategy.analyze(closes)

            if signal.action == "buy" and open_trade is None:
                quantity = self.starting_capital / float(bar.close)
                open_trade = {
                    "action": "buy",
                    "signal_reason": signal.reason,
                    "price_at_signal": float(bar.close),
                    "quantity": quantity,
                    "timestamp_open": bar.timestamp,
                    "timestamp_close": None,
                    "price_at_close": None,
                    "pnl": None,
                    "status": "open",
                }
                trades.append(open_trade)

            elif signal.action == "sell" and open_trade is not None:
                open_trade["timestamp_close"] = bar.timestamp
                open_trade["price_at_close"] = float(bar.close)
                open_trade["pnl"] = (float(bar.close) - open_trade["price_at_signal"]) * open_trade["quantity"]
                open_trade["status"] = "closed"
                open_trade = None

        return trades
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest ../tests/backend/test_backtester.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/backtester/
git commit -m "feat: add BacktestRunner with no-lookahead price replay"
```

---

## Task 9: P&L Aggregator

**Files:**
- Create: `backend/pnl/aggregator.py`
- Test: `tests/backend/test_pnl_aggregator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/backend/test_pnl_aggregator.py
import pytest
from backend.pnl.aggregator import compute_period_summary

def test_day_summary_sums_pnl():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": -5.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["total_pnl"] == pytest.approx(25.0)
    assert summary["num_trades"] == 3
    assert summary["num_wins"] == 2
    assert summary["num_losses"] == 1
    assert summary["win_rate"] == pytest.approx(2/3, abs=0.01)
    assert summary["ending_capital"] == pytest.approx(1025.0)

def test_summary_with_no_trades():
    summary = compute_period_summary([], starting_capital=500.0)
    assert summary["total_pnl"] == 0.0
    assert summary["num_trades"] == 0
    assert summary["win_rate"] == 0.0
    assert summary["ending_capital"] == 500.0

def test_open_trades_excluded_from_summary():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": None, "status": "open"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["num_trades"] == 1
    assert summary["total_pnl"] == 10.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest ../tests/backend/test_pnl_aggregator.py -v
```
Expected: FAIL

- [ ] **Step 3: Create `backend/pnl/aggregator.py`**

```python
def compute_period_summary(trades: list[dict], starting_capital: float) -> dict:
    closed = [t for t in trades if t.get("status") == "closed" and t.get("pnl") is not None]
    total_pnl = sum(t["pnl"] for t in closed)
    num_wins = sum(1 for t in closed if t["pnl"] > 0)
    num_losses = sum(1 for t in closed if t["pnl"] <= 0)
    num_trades = len(closed)
    win_rate = (num_wins / num_trades) if num_trades > 0 else 0.0

    return {
        "total_pnl": total_pnl,
        "num_trades": num_trades,
        "num_wins": num_wins,
        "num_losses": num_losses,
        "win_rate": win_rate,
        "starting_capital": starting_capital,
        "ending_capital": starting_capital + total_pnl,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest ../tests/backend/test_pnl_aggregator.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pnl/
git commit -m "feat: add P&L period aggregator (total, wins, losses, win rate, ending capital)"
```

---

## Task 10: FastAPI App + All Routers

**Files:**
- Create: `backend/main.py`
- Create: `backend/routers/sessions.py`
- Create: `backend/routers/market_data.py`
- Create: `backend/routers/strategies.py`
- Create: `backend/routers/trades.py`
- Create: `backend/routers/backtest.py`
- Create: `backend/routers/websocket.py`
- Test: `tests/backend/test_api.py`

- [ ] **Step 1: Create `backend/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from scheduler.scraper_job import start_scheduler, stop_scheduler
from routers import sessions, market_data, strategies, trades, backtest, websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="TradingCopilot", lifespan=lifespan)

app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(market_data.router, prefix="/symbols", tags=["market-data"])
app.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
app.include_router(trades.router, prefix="/sessions", tags=["trades"])
app.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
app.include_router(websocket.router, tags=["websocket"])
```

- [ ] **Step 2: Create `backend/routers/sessions.py`**

```python
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.trading_session import TradingSession
from scheduler.scraper_job import register_symbol, unregister_symbol

router = APIRouter()

class CreateSessionRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    mode: str  # "paper" or "live"

@router.post("")
async def create_session(req: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = TradingSession(
        symbol=req.symbol.upper(),
        strategy=req.strategy,
        strategy_params=req.strategy_params,
        starting_capital=req.starting_capital,
        mode=req.mode,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    register_symbol(session.symbol)
    return session

@router.get("")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TradingSession).order_by(TradingSession.created_at.desc()))
    return result.scalars().all()

@router.get("/{session_id}")
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.patch("/{session_id}/stop")
async def stop_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    await db.commit()
    unregister_symbol(session.symbol)
    return session
```

- [ ] **Step 3: Create `backend/routers/market_data.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from database import get_db
from models.price_history import PriceHistory

router = APIRouter()

@router.get("/{symbol}/history")
async def get_history(
    symbol: str,
    from_dt: datetime = Query(alias="from"),
    to_dt: datetime = Query(alias="to"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == symbol.upper(),
            PriceHistory.timestamp >= from_dt,
            PriceHistory.timestamp <= to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    return result.scalars().all()

@router.get("/{symbol}/latest")
async def get_latest(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.symbol == symbol.upper())
        .order_by(PriceHistory.timestamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Create `backend/routers/strategies.py`**

```python
from fastapi import APIRouter
from strategies.moving_average_crossover import MovingAverageCrossover

router = APIRouter()

@router.get("")
async def list_strategies():
    return [
        {
            "name": MovingAverageCrossover.name,
            "description": MovingAverageCrossover.description,
            "parameters": {
                "short_window": {"type": "int", "default": 50, "description": "Short moving average window"},
                "long_window": {"type": "int", "default": 200, "description": "Long moving average window"},
            },
        }
    ]
```

- [ ] **Step 5: Create `backend/routers/trades.py`**

```python
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.paper_trade import PaperTrade
from models.aggregated_pnl import AggregatedPnl
from models.trading_session import TradingSession
from pnl.aggregator import compute_period_summary

router = APIRouter()

@router.get("/{session_id}/trades")
async def get_trades(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .order_by(PaperTrade.timestamp_open.asc())
    )
    return result.scalars().all()

@router.get("/{session_id}/pnl")
async def get_pnl(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(TradingSession, session_id)
    trades_result = await db.execute(
        select(PaperTrade).where(PaperTrade.session_id == session_id)
    )
    trades = [
        {"pnl": float(t.pnl) if t.pnl else None, "status": t.status}
        for t in trades_result.scalars().all()
    ]
    return {
        "all_time": compute_period_summary(trades, float(session.starting_capital)),
    }
```

- [ ] **Step 6: Create `backend/routers/backtest.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from database import get_db
from models.price_history import PriceHistory
from strategies.moving_average_crossover import MovingAverageCrossover
from backtester.runner import BacktestRunner
from pnl.aggregator import compute_period_summary

router = APIRouter()

class BacktestRequest(BaseModel):
    symbol: str
    strategy: str
    strategy_params: dict
    starting_capital: float
    from_dt: datetime
    to_dt: datetime

@router.post("")
async def run_backtest(req: BacktestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == req.symbol.upper(),
            PriceHistory.timestamp >= req.from_dt,
            PriceHistory.timestamp <= req.to_dt,
        )
        .order_by(PriceHistory.timestamp.asc())
    )
    bars = result.scalars().all()

    strategy = MovingAverageCrossover(**req.strategy_params)
    runner = BacktestRunner(strategy=strategy, starting_capital=req.starting_capital)
    trades = runner.run(bars)

    summary = compute_period_summary(trades, req.starting_capital)
    return {"trades": trades, "summary": summary}
```

- [ ] **Step 7: Create `backend/routers/websocket.py`**

```python
import uuid
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from database import AsyncSessionLocal
from models.price_history import PriceHistory

router = APIRouter()

@router.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: uuid.UUID):
    await websocket.accept()
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
```

- [ ] **Step 8: Write and run API integration tests**

```python
# tests/backend/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_list_strategies_returns_moving_average():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "moving_average_crossover"

@pytest.mark.asyncio
async def test_list_sessions_returns_empty_list(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/sessions")
    assert resp.status_code == 200
    assert resp.json() == []
```

Run:
```bash
cd backend && pytest ../tests/backend/test_api.py -v
```
Expected: 2 tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/main.py backend/routers/
git commit -m "feat: add FastAPI app with all routers (sessions, market data, strategies, trades, backtest, websocket)"
```

---

## Task 11: Frontend Scaffold + API Client

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/api/client.js`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "trading-copilot",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.23.0",
    "axios": "^1.7.0",
    "recharts": "^2.12.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.2.0"
  }
}
```

- [ ] **Step 2: Create `frontend/src/api/client.js`**

```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export const getSessions = () => api.get("/sessions");
export const createSession = (data) => api.post("/sessions", data);
export const stopSession = (id) => api.patch(`/sessions/${id}/stop`);
export const getStrategies = () => api.get("/strategies");
export const getTrades = (sessionId) => api.get(`/sessions/${sessionId}/trades`);
export const getPnl = (sessionId) => api.get(`/sessions/${sessionId}/pnl`);
export const runBacktest = (data) => api.post("/backtest", data);
export const getLatestPrice = (symbol) => api.get(`/symbols/${symbol}/latest`);

export function createSessionSocket(sessionId, onMessage) {
  const ws = new WebSocket(`ws://${window.location.host}/ws/sessions/${sessionId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  return ws;
}
```

- [ ] **Step 3: Create `frontend/src/App.jsx`**

```jsx
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import NewSession from "./pages/NewSession";
import LiveDashboard from "./pages/LiveDashboard";
import Reports from "./pages/Reports";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #ddd", display: "flex", gap: "1rem" }}>
        <Link to="/">New Session</Link>
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/reports">Reports</Link>
      </nav>
      <Routes>
        <Route path="/" element={<NewSession />} />
        <Route path="/dashboard/:sessionId" element={<LiveDashboard />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Create `frontend/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/src/main.jsx frontend/src/App.jsx frontend/src/api/
git commit -m "feat: add React app scaffold with router and API client"
```

---

## Task 12: New Session Page

**Files:**
- Create: `frontend/src/pages/NewSession.jsx`

- [ ] **Step 1: Create `frontend/src/pages/NewSession.jsx`**

```jsx
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getStrategies, createSession, runBacktest } from "../api/client";

export default function NewSession() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState([]);
  const [form, setForm] = useState({
    symbol: "",
    strategy: "moving_average_crossover",
    short_window: 50,
    long_window: 200,
    starting_capital: 1000,
    mode: "paper",
    from_dt: "",
    to_dt: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getStrategies().then((r) => setStrategies(r.data));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (form.mode === "backtest") {
        const result = await runBacktest({
          symbol: form.symbol,
          strategy: form.strategy,
          strategy_params: { short_window: +form.short_window, long_window: +form.long_window },
          starting_capital: +form.starting_capital,
          from_dt: form.from_dt,
          to_dt: form.to_dt,
        });
        navigate("/reports", { state: { backtestResult: result.data } });
      } else {
        const session = await createSession({
          symbol: form.symbol,
          strategy: form.strategy,
          strategy_params: { short_window: +form.short_window, long_window: +form.long_window },
          starting_capital: +form.starting_capital,
          mode: form.mode,
        });
        navigate(`/dashboard/${session.data.id}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>New Trading Session</h1>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <label>Symbol<input value={form.symbol} onChange={e => setForm({...form, symbol: e.target.value})} placeholder="AAPL" required /></label>
        <label>Strategy
          <select value={form.strategy} onChange={e => setForm({...form, strategy: e.target.value})}>
            {strategies.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label>Short Window<input type="number" value={form.short_window} onChange={e => setForm({...form, short_window: e.target.value})} /></label>
        <label>Long Window<input type="number" value={form.long_window} onChange={e => setForm({...form, long_window: e.target.value})} /></label>
        <label>Capital ($)<input type="number" value={form.starting_capital} onChange={e => setForm({...form, starting_capital: e.target.value})} /></label>
        <label>Mode
          <select value={form.mode} onChange={e => setForm({...form, mode: e.target.value})}>
            <option value="paper">Paper Trading (Real-time)</option>
            <option value="backtest">Backtest (Historical)</option>
            <option value="live">Live (Stubbed)</option>
          </select>
        </label>
        {form.mode === "backtest" && (<>
          <label>From<input type="datetime-local" value={form.from_dt} onChange={e => setForm({...form, from_dt: e.target.value})} required /></label>
          <label>To<input type="datetime-local" value={form.to_dt} onChange={e => setForm({...form, to_dt: e.target.value})} required /></label>
        </>)}
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={loading}>{loading ? "Starting..." : "Start Session"}</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/NewSession.jsx
git commit -m "feat: add NewSession page with paper/backtest/live mode selection"
```

---

## Task 13: Live Dashboard Page

**Files:**
- Create: `frontend/src/pages/LiveDashboard.jsx`
- Create: `frontend/src/components/PriceChart.jsx`
- Create: `frontend/src/components/TradeLog.jsx`

- [ ] **Step 1: Create `frontend/src/components/PriceChart.jsx`**

```jsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";

export default function PriceChart({ bars, trades }) {
  const data = bars.map(b => ({
    time: new Date(b.timestamp).toLocaleTimeString(),
    price: parseFloat(b.close),
  }));

  const buyTimes = new Set(trades.filter(t => t.action === "buy").map(t =>
    new Date(t.timestamp_open).toLocaleTimeString()
  ));
  const sellTimes = new Set(trades.filter(t => t.action === "sell").map(t =>
    new Date(t.timestamp_open).toLocaleTimeString()
  ));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="time" tick={{ fontSize: 10 }} />
        <YAxis domain={["auto", "auto"]} />
        <Tooltip />
        <Line type="monotone" dataKey="price" dot={false} stroke="#2563eb" strokeWidth={2} />
        {data.map((d, i) =>
          buyTimes.has(d.time) ? <ReferenceLine key={`b${i}`} x={d.time} stroke="green" label="B" /> : null
        )}
        {data.map((d, i) =>
          sellTimes.has(d.time) ? <ReferenceLine key={`s${i}`} x={d.time} stroke="red" label="S" /> : null
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/TradeLog.jsx`**

```jsx
export default function TradeLog({ trades }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{ borderBottom: "1px solid #ddd" }}>
          <th>Action</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Reason</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        {trades.map(t => (
          <tr key={t.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
            <td style={{ color: t.action === "buy" ? "green" : "red" }}>{t.action.toUpperCase()}</td>
            <td>${parseFloat(t.price_at_signal).toFixed(2)}</td>
            <td>{t.price_at_close ? `$${parseFloat(t.price_at_close).toFixed(2)}` : "—"}</td>
            <td style={{ color: t.pnl > 0 ? "green" : t.pnl < 0 ? "red" : "inherit" }}>
              {t.pnl != null ? `${t.pnl > 0 ? "+" : ""}$${parseFloat(t.pnl).toFixed(2)}` : "—"}
            </td>
            <td style={{ fontSize: 12, color: "#666" }}>{t.signal_reason}</td>
            <td>{t.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 3: Create `frontend/src/pages/LiveDashboard.jsx`**

```jsx
import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import { getTrades, getLatestPrice } from "../api/client";
import { createSessionSocket } from "../api/client";
import PriceChart from "../components/PriceChart";
import TradeLog from "../components/TradeLog";

export default function LiveDashboard() {
  const { sessionId } = useParams();
  const [bars, setBars] = useState([]);
  const [trades, setTrades] = useState([]);
  const [latestPrice, setLatestPrice] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    getTrades(sessionId).then(r => setTrades(r.data));

    wsRef.current = createSessionSocket(sessionId, (msg) => {
      if (msg.type === "price_update") {
        setLatestPrice(msg.close);
        setBars(prev => [...prev.slice(-199), { timestamp: msg.timestamp, close: msg.close }]);
        getTrades(sessionId).then(r => setTrades(r.data));
      }
    });

    return () => wsRef.current?.close();
  }, [sessionId]);

  const openTrade = trades.find(t => t.status === "open");
  const unrealizedPnl = openTrade && latestPrice
    ? ((latestPrice - parseFloat(openTrade.price_at_signal)) * parseFloat(openTrade.quantity)).toFixed(2)
    : null;

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Live Dashboard</h2>
      {latestPrice && <p>Current Price: <strong>${latestPrice.toFixed(2)}</strong></p>}
      {openTrade && (
        <div style={{ padding: "0.5rem", background: "#f0f9ff", borderRadius: 4, marginBottom: "1rem" }}>
          <strong>Open Position</strong> — Entry: ${parseFloat(openTrade.price_at_signal).toFixed(2)} |
          Unrealized P&L: <span style={{ color: unrealizedPnl > 0 ? "green" : "red" }}>${unrealizedPnl}</span>
        </div>
      )}
      <PriceChart bars={bars} trades={trades} />
      <h3>Trade Log</h3>
      <TradeLog trades={trades} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LiveDashboard.jsx frontend/src/components/PriceChart.jsx frontend/src/components/TradeLog.jsx
git commit -m "feat: add LiveDashboard with real-time price chart, signal markers, and trade log"
```

---

## Task 14: Reports Page

**Files:**
- Create: `frontend/src/pages/Reports.jsx`
- Create: `frontend/src/components/PnLChart.jsx`
- Create: `frontend/src/components/ComparisonView.jsx`

- [ ] **Step 1: Create `frontend/src/components/PnLChart.jsx`**

```jsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from "recharts";

export default function PnLChart({ trades }) {
  const data = trades
    .filter(t => t.status === "closed" && t.pnl != null)
    .map((t, i) => ({
      name: `Trade ${i + 1}`,
      pnl: parseFloat(t.pnl),
    }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis />
        <Tooltip formatter={(v) => [`$${v.toFixed(2)}`, "P&L"]} />
        <Bar dataKey="pnl">
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.pnl >= 0 ? "#16a34a" : "#dc2626"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/ComparisonView.jsx`**

```jsx
export default function ComparisonView({ trades, summary }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
      <div style={{ padding: "1rem", background: "#f0fdf4", borderRadius: 8 }}>
        <h4>Paper Trading Result</h4>
        <p>Total P&L: <strong style={{ color: summary.total_pnl >= 0 ? "green" : "red" }}>
          {summary.total_pnl >= 0 ? "+" : ""}${summary.total_pnl?.toFixed(2)}
        </strong></p>
        <p>Trades: {summary.num_trades} ({summary.num_wins}W / {summary.num_losses}L)</p>
        <p>Win Rate: {(summary.win_rate * 100).toFixed(1)}%</p>
        <p>Capital: ${summary.starting_capital?.toFixed(2)} → <strong>${summary.ending_capital?.toFixed(2)}</strong></p>
      </div>
      <div style={{ padding: "1rem", background: "#eff6ff", borderRadius: 8 }}>
        <h4>Actual Market Outcome</h4>
        {trades.filter(t => t.status === "closed").map(t => (
          <div key={t.id} style={{ fontSize: 13, borderBottom: "1px solid #e0e0e0", padding: "0.25rem 0" }}>
            {t.action.toUpperCase()} @ ${parseFloat(t.price_at_signal).toFixed(2)} →
            closed @ ${parseFloat(t.price_at_close).toFixed(2)} |
            <span style={{ color: parseFloat(t.pnl) >= 0 ? "green" : "red" }}>
              {" "}{parseFloat(t.pnl) >= 0 ? "+" : ""}${parseFloat(t.pnl).toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/pages/Reports.jsx`**

```jsx
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getSessions, getTrades, getPnl } from "../api/client";
import PnLChart from "../components/PnLChart";
import TradeLog from "../components/TradeLog";
import ComparisonView from "../components/ComparisonView";

export default function Reports() {
  const location = useLocation();
  const backtestResult = location.state?.backtestResult;

  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [trades, setTrades] = useState([]);
  const [pnl, setPnl] = useState(null);

  useEffect(() => {
    if (backtestResult) return;
    getSessions().then(r => setSessions(r.data));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([getTrades(selectedId), getPnl(selectedId)]).then(([t, p]) => {
      setTrades(t.data);
      setPnl(p.data.all_time);
    });
  }, [selectedId]);

  if (backtestResult) {
    return (
      <div style={{ padding: "1rem" }}>
        <h2>Backtest Results</h2>
        <PnLChart trades={backtestResult.trades} />
        <ComparisonView trades={backtestResult.trades} summary={backtestResult.summary} />
        <h3>Trade Log</h3>
        <TradeLog trades={backtestResult.trades} />
      </div>
    );
  }

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Reports</h2>
      <select value={selectedId || ""} onChange={e => setSelectedId(e.target.value)}>
        <option value="">Select a session...</option>
        {sessions.map(s => (
          <option key={s.id} value={s.id}>{s.symbol} — {s.strategy} ({s.mode}) — {new Date(s.created_at).toLocaleDateString()}</option>
        ))}
      </select>
      {pnl && trades.length > 0 && (<>
        <PnLChart trades={trades} />
        <ComparisonView trades={trades} summary={pnl} />
        <h3>Trade Log</h3>
        <TradeLog trades={trades} />
      </>)}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Reports.jsx frontend/src/components/PnLChart.jsx frontend/src/components/ComparisonView.jsx
git commit -m "feat: add Reports page with P&L chart, comparison view, and trade log"
```

---

## Task 15: End-to-End Smoke Test

- [ ] **Step 1: Copy `.env.example` to `.env` and fill in API keys**

```bash
cp .env.example .env
# Edit .env: set ALPHA_VANTAGE_API_KEY and FINNHUB_API_KEY if available
# (both are optional — system falls back to Yahoo only if keys absent)
```

- [ ] **Step 2: Build and start the full stack**

```bash
docker compose up --build
```
Expected: all 3 containers start, backend logs "Uvicorn running on http://0.0.0.0:8000", db logs "database system is ready to accept connections"

- [ ] **Step 3: Run database migrations**

```bash
docker compose exec backend alembic upgrade head
```
Expected: "Running upgrade -> <hash>, initial tables"

- [ ] **Step 4: Verify API is alive**

```bash
curl http://localhost:8000/strategies
```
Expected:
```json
[{"name":"moving_average_crossover","description":"...","parameters":{...}}]
```

- [ ] **Step 5: Open browser and create a paper session**

Open `http://localhost:80`, fill in symbol `AAPL`, mode `Paper Trading`, click Start Session.
Expected: redirects to `/dashboard/<session-id>`

- [ ] **Step 6: Run all backend tests inside container**

```bash
docker compose exec backend pytest ../tests/backend/ -v
```
Expected: all tests PASS

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "feat: complete TradingCopilot v1 — multi-source scraper, MA crossover strategy, paper trading, backtesting, React dashboard"
```
