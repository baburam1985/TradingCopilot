# TradingCopilot — Design Spec

**Date:** 2026-04-01  
**Status:** Approved

---

## Overview

TradingCopilot is a web-based day trading application that analyzes market signals for any stock symbol and executes trades — or simulates them — using well-known trading strategies. The end goal is to make money for the user by faithfully following the methodology they select.

---

## Deployment Architecture

Three Docker containers managed by a single `docker-compose.yml`:

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ frontend │  │ backend  │  │    db    │  │
│  │          │  │          │  │          │  │
│  │  React   │  │  FastAPI │  │ Postgres │  │
│  │  Nginx   │  │    +     │  │    15    │  │
│  │          │  │ Scraper  │  │          │  │
│  │  port 80 │  │ port 8000│  │ port 5432│  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
```

- **frontend** — React app served by Nginx on port 80
- **backend** — FastAPI server + APScheduler background scheduler in the same Python process on port 8000
- **db** — Postgres 15 with a named persistent volume (data survives restarts)

A single `docker-compose up` starts the entire stack. Designed to be deployable anywhere Docker runs.

---

## System Architecture

```
React Frontend
    │  HTTP / WebSocket
FastAPI Backend
    ├── Price Scraper (APScheduler — runs inside backend, no separate port)
    ├── Strategy Engine
    ├── Trade Executor (Paper | Live stub)
    └── Postgres (all data persisted)
```

### Price Scraper
- Runs as a background thread inside the backend container via APScheduler
- **On-demand only** — scraping starts when a user creates a session for a symbol, stops when the session is closed. No background scraping of unused symbols.
- During market hours (9:30am–4:00pm ET, weekdays): fetches 1-minute OHLCV bars from all three sources in parallel for all symbols with active sessions
- All three sources fetched simultaneously using `asyncio.gather` — 3 sources costs the same time as 1
- Writes consensus price + per-source raw values to `price_history` in Postgres — permanently, no expiry
- After each new bar: triggers the strategy engine
- Outside market hours: idle
- For backtesting: performs a one-time bulk fetch for the requested date range before replay
- Historical data already in DB is reused — no re-fetch needed

### Market Data Sources (Multi-Source Consensus)
Three free-tier sources fetched in parallel. Consensus price is the average across sources; outliers are flagged.

| Source | Library | Rate Limit (free) | Provides |
|---|---|---|---|
| Yahoo Finance | `yfinance` | No hard limit | OHLCV, historical data |
| Alpha Vantage | `httpx` (async) | 5 calls/min, 500/day | OHLCV + technical indicators |
| Finnhub | `finnhub-python` + `websockets` | 60 calls/min | Real-time quotes, news/sentiment |

**Aggregation logic:**
- Consensus `close` = average across all available sources
- Any source deviating >1% from consensus is flagged in `price_history`
- If one source is unavailable, remaining sources still form consensus
- Strategy engine always receives consensus price — never a single-source value

**Async fetch pattern:**
```python
async def scrape_symbol(symbol):
    results = await asyncio.gather(
        fetch_yahoo(symbol),
        fetch_alpha_vantage(symbol),
        fetch_finnhub(symbol),
    )
    consensus = aggregate(results)   # average + outlier flagging
    await write_to_db(symbol, consensus, results)
```

---

## Strategy Engine

Strategies are implemented as a plugin-style module — each strategy is an independent class implementing a common interface. This makes adding new strategies straightforward.

```python
class StrategyBase:
    name: str
    description: str
    parameters: dict        # e.g. {short_window: 50, long_window: 200}
    def analyze(price_history) -> Signal

class Signal:
    action: "buy" | "sell" | "hold"
    reason: str             # e.g. "Golden cross: 50MA crossed above 200MA"
    confidence: float
```

### Launch Strategy: Moving Average Crossover
- **Buy signal** — short MA crosses above long MA (golden cross)
- **Sell signal** — short MA crosses below long MA (death cross)
- **Hold** — no crossover detected
- Parameters are configurable per session (e.g. 10/50 or 50/200 windows)

---

## Operating Modes

### Real-Time Paper Trading
1. Scraper fetches latest price bar every minute
2. Strategy engine generates signal
3. Paper Executor records hypothetical trade at current market price
4. Position stays open until sell signal fires
5. At close: actual close price from `price_history` used to settle trade and compute P&L

### Historical Backtesting
1. User selects symbol, date range, starting capital, strategy parameters
2. System fetches historical bars from Yahoo Finance (writes to `price_history` if not already stored)
3. Strategy engine replays bars in chronological order — **no lookahead** (strategy only sees bars up to current replay point)
4. Each signal recorded as a paper trade with historical timestamps
5. Full P&L report generated at trade, day, week, month, and all-time levels

### Live Trading
- Stubbed executor interface — logs "would execute order" but takes no real action
- Designed to be wired into a real brokerage API (e.g. Alpaca) in a future phase
- Requires explicit opt-in; paper trading is the default

---

## Data Layer

All data is stored permanently in Postgres. Nothing is ephemeral.

### Tables

**price_history**
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| symbol | varchar | e.g. "AAPL" |
| timestamp | timestamptz | bar open time |
| open | numeric | consensus open |
| high | numeric | consensus high |
| low | numeric | consensus low |
| close | numeric | consensus close (average across sources) |
| volume | bigint | consensus volume |
| yahoo_close | numeric | raw Yahoo Finance close (nullable) |
| alphavantage_close | numeric | raw Alpha Vantage close (nullable) |
| finnhub_close | numeric | raw Finnhub close (nullable) |
| outlier_flags | jsonb | sources that deviated >1% from consensus |
| sources_available | varchar[] | which sources contributed this bar |

**sessions**
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| symbol | varchar | |
| strategy | varchar | e.g. "moving_average_crossover" |
| strategy_params | jsonb | e.g. {short_window: 50, long_window: 200} |
| starting_capital | numeric | |
| mode | varchar | "paper" or "live" |
| status | varchar | "active" or "closed" |
| created_at | timestamptz | |
| closed_at | timestamptz | nullable |

**paper_trades**
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| session_id | uuid | FK → sessions |
| action | varchar | "buy" or "sell" |
| signal_reason | varchar | e.g. "Golden cross: 50MA crossed above 200MA" |
| price_at_signal | numeric | price when signal fired |
| quantity | numeric | shares (based on capital allocation) |
| timestamp_open | timestamptz | when trade was entered |
| timestamp_close | timestamptz | when trade was exited (nullable if open) |
| price_at_close | numeric | actual market price at close (nullable if open) |
| pnl | numeric | realized P&L (nullable if open) |
| status | varchar | "open" or "closed" |

**aggregated_pnl**
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| session_id | uuid | FK → sessions |
| period_type | varchar | "day", "week", "month", "all_time" |
| period_start | timestamptz | |
| period_end | timestamptz | |
| total_pnl | numeric | |
| num_trades | int | |
| num_wins | int | |
| num_losses | int | |
| win_rate | numeric | 0.0–1.0 |
| starting_capital | numeric | capital at start of period |
| ending_capital | numeric | capital at end of period |

`aggregated_pnl` is recomputed at end-of-day, end-of-week, and end-of-month — not on every trade.

---

## API (FastAPI)

### Sessions
```
POST   /sessions                  Create new trading session
GET    /sessions                  List all sessions
GET    /sessions/{id}             Session detail + status
PATCH  /sessions/{id}/stop        Close active session
```

### Market Data
```
GET    /symbols/{symbol}/history?from=&to=    Price history for symbol
GET    /symbols/{symbol}/latest               Latest price bar
```

### Strategies
```
GET    /strategies                List available strategies + configurable params
```

### Paper Trading
```
GET    /sessions/{id}/trades      All trades for a session
GET    /sessions/{id}/pnl         Aggregated P&L (day/week/month/all-time)
```

### Backtesting
```
POST   /backtest                  Run backtest, returns full trade list + P&L report
```

### WebSocket
```
WS     /ws/sessions/{id}          Live price updates + signals during active session
```

---

## Frontend (React) — 3 Screens

### 1. New Session
- Input: stock symbol, starting capital, strategy, strategy parameters, mode (paper / backtest)
- For backtest mode: date range picker

### 2. Live Dashboard (real-time paper trading)
- Price chart with buy/sell signal markers overlaid
- Open position tracker: entry price, current price, unrealized P&L
- Trade log: all trades in this session

### 3. Reports
- Session selector
- P&L chart with Day / Week / Month / All-time toggle
- Trade table: each trade with entry price, exit price, P&L, signal reason
- Comparison view: paper P&L vs actual market outcome side by side

---

## Design Principles

- **Strategy-first** — each strategy is an independent, testable module
- **Mode-agnostic execution** — same strategy logic runs in paper and live modes; only the executor differs
- **No lookahead** — backtester never feeds future prices to the strategy
- **All data persisted** — every price bar (with per-source raw values), every signal, every trade, every P&L rollup is stored permanently
- **Paper by default** — live trading requires explicit opt-in
- **Portable** — single `docker-compose up` runs the full stack anywhere
- **On-demand scraping** — only active session symbols are scraped; rate limits never exceeded
- **Multi-source consensus** — strategy engine acts on averaged price across 3 sources, never a single-source value

---

## Out of Scope (Phase 1)
- Multiple strategies (only Moving Average Crossover at launch)
- Multi-asset portfolios (single stock per session)
- Options, futures, or crypto (equities only)
- Real live trade execution (stubbed)
- Multi-user / authentication
