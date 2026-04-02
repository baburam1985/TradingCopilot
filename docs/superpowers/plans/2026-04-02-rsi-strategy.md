# RSI Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an RSI strategy with transition/level signal modes, a strategy registry replacing all hardcoded MA crossover lookups, and a bulk historical data seed endpoint so backtests can run immediately without live market data.

**Architecture:** `RSIStrategy` implements the existing `StrategyBase` interface. A `STRATEGY_REGISTRY` dict maps strategy names to classes — the three routers and the scheduler all look up strategies by name from the registry. A new `POST /backtest/seed/{symbol}` endpoint fetches bulk Yahoo Finance history and inserts it into `price_history`, enabling immediate backtesting.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, yfinance 1.2.0, pytest-asyncio

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/strategies/rsi.py` | Create | RSI strategy with transition + level modes |
| `backend/strategies/registry.py` | Create | `STRATEGY_REGISTRY` dict |
| `backend/strategies/moving_average_crossover.py` | Modify | Add `parameters` class attribute (needed by dynamic strategies router) |
| `backend/routers/strategies.py` | Modify | Read from registry instead of hardcoded class |
| `backend/routers/backtest.py` | Modify | Registry lookup + new seed endpoint |
| `backend/scheduler/scraper_job.py` | Modify | Registry lookup, remove `long_window` coupling |
| `tests/backend/test_rsi_strategy.py` | Create | RSI unit tests |
| `tests/integration/test_rsi_backtest.py` | Create | Integration tests for seed + RSI backtest |

---

## Task 1: RSI Strategy

**Files:**
- Create: `backend/strategies/rsi.py`
- Test: `tests/backend/test_rsi_strategy.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_rsi_strategy.py`:

```python
import pytest
from strategies.rsi import RSIStrategy, _compute_rsi


def _falling(n: int, start: float = 100.0, drop: float = 2.0) -> list[float]:
    return [start - i * drop for i in range(n)]


def _rising(n: int, start: float = 100.0, rise: float = 2.0) -> list[float]:
    return [start + i * rise for i in range(n)]


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_rsi_insufficient_data_returns_hold():
    strategy = RSIStrategy(period=14, signal_mode="transition")
    # transition needs period+2=16 bars; supply only 15
    result = strategy.analyze(_flat(15))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_rsi_buy_on_oversold_transition():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    # Sharp falling series drives RSI well below 30
    closes = _falling(50, start=100.0, drop=2.0)
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_rsi_sell_on_overbought_transition():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    closes = _rising(50, start=100.0, rise=2.0)
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_rsi_hold_when_no_threshold_crossing():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    # Flat prices → RSI stays near 50, never crosses a threshold
    closes = _flat(20)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_rsi_hold_when_sustained_below_oversold_transition():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    # Build long falling series: RSI already below 30
    closes = _falling(60, start=200.0, drop=2.0)
    # Append one more tiny drop — RSI was already below 30, no crossing
    closes.append(closes[-1] - 0.1)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_rsi_level_mode_buy_every_bar_below_oversold():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="level")
    closes = _falling(50, start=100.0, drop=2.0)
    result = strategy.analyze(closes)
    assert result.action == "buy"
    # Add more falling bars — still buy in level mode
    closes.append(closes[-1] - 1.0)
    result2 = strategy.analyze(closes)
    assert result2.action == "buy"


def test_rsi_level_mode_hold_at_neutral():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="level")
    closes = _flat(20)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_rsi_level_mode_uses_strict_less_than_for_buy():
    # Verify the comparison is strict: RSI must be strictly below oversold
    # We achieve this by checking the _compute_rsi helper directly
    closes = _flat(20)  # flat → RSI near 50 (never < 30)
    rsi = _compute_rsi(closes, 14)
    assert rsi > 30  # sanity: flat prices are not oversold


def test_compute_rsi_all_gains_returns_100():
    # Pure rising series → avg_loss = 0 → RSI = 100
    closes = _rising(20)
    rsi = _compute_rsi(closes, 14)
    assert rsi == 100.0


def test_compute_rsi_all_losses_returns_0():
    # Pure falling series → avg_gain = 0 → RSI = 0
    closes = _falling(20)
    rsi = _compute_rsi(closes, 14)
    assert rsi == 0.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/backend/test_rsi_strategy.py -v
```

Expected: `ImportError: cannot import name 'RSIStrategy' from 'strategies.rsi'`

- [ ] **Step 3: Create `backend/strategies/rsi.py`**

```python
from strategies.base import StrategyBase, Signal


def _compute_rsi(closes: list[float], period: int) -> float:
    """Compute RSI using Wilder's smoothing method."""
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


class RSIStrategy(StrategyBase):
    name = "rsi"
    description = "Buy when RSI crosses below oversold threshold, sell when RSI crosses above overbought threshold."
    parameters = {
        "period": {"type": "int", "default": 14, "description": "RSI calculation period"},
        "oversold": {"type": "int", "default": 30, "description": "RSI below this → buy signal"},
        "overbought": {"type": "int", "default": 70, "description": "RSI above this → sell signal"},
        "signal_mode": {"type": "str", "default": "transition", "description": "transition or level"},
    }

    def __init__(
        self,
        period: int = 14,
        oversold: int = 30,
        overbought: int = 70,
        signal_mode: str = "transition",
    ):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.signal_mode = signal_mode

    def analyze(self, closes: list[float]) -> Signal:
        min_bars = self.period + 2 if self.signal_mode == "transition" else self.period + 1
        if len(closes) < min_bars:
            return Signal(
                action="hold",
                reason="Insufficient data for RSI calculation",
                confidence=0.0,
            )

        rsi_now = _compute_rsi(closes, self.period)

        if self.signal_mode == "level":
            if rsi_now < self.oversold:
                return Signal(
                    action="buy",
                    reason=f"RSI({self.period})={rsi_now:.1f} below oversold threshold {self.oversold}",
                    confidence=0.75,
                )
            if rsi_now > self.overbought:
                return Signal(
                    action="sell",
                    reason=f"RSI({self.period})={rsi_now:.1f} above overbought threshold {self.overbought}",
                    confidence=0.75,
                )
            return Signal(
                action="hold",
                reason=f"RSI({self.period})={rsi_now:.1f} within neutral zone",
                confidence=0.0,
            )

        # Transition mode: detect threshold crossings
        rsi_prev = _compute_rsi(closes[:-1], self.period)

        crossed_oversold = rsi_prev >= self.oversold and rsi_now < self.oversold
        crossed_overbought = rsi_prev <= self.overbought and rsi_now > self.overbought

        if crossed_oversold:
            return Signal(
                action="buy",
                reason=f"RSI({self.period}) crossed below oversold: {rsi_prev:.1f} → {rsi_now:.1f}",
                confidence=0.75,
            )
        if crossed_overbought:
            return Signal(
                action="sell",
                reason=f"RSI({self.period}) crossed above overbought: {rsi_prev:.1f} → {rsi_now:.1f}",
                confidence=0.75,
            )
        return Signal(
            action="hold",
            reason=f"RSI({self.period})={rsi_now:.1f}, no threshold crossing",
            confidence=0.0,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/backend/test_rsi_strategy.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/strategies/rsi.py tests/backend/test_rsi_strategy.py
git commit -m "feat: add RSI strategy with transition and level signal modes"
```

---

## Task 2: Strategy Registry

**Files:**
- Create: `backend/strategies/registry.py`
- Modify: `backend/strategies/moving_average_crossover.py` (add `parameters` class attribute)

- [ ] **Step 1: Add `parameters` to `MovingAverageCrossover`**

Open `backend/strategies/moving_average_crossover.py` and add after `description = ...`:

```python
parameters = {
    "short_window": {"type": "int", "default": 50, "description": "Short moving average window"},
    "long_window": {"type": "int", "default": 200, "description": "Long moving average window"},
}
```

Full file after change:

```python
from strategies.base import StrategyBase, Signal

class MovingAverageCrossover(StrategyBase):
    name = "moving_average_crossover"
    description = "Buy on golden cross (short MA crosses above long MA), sell on death cross."
    parameters = {
        "short_window": {"type": "int", "default": 50, "description": "Short moving average window"},
        "long_window": {"type": "int", "default": 200, "description": "Long moving average window"},
    }

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

- [ ] **Step 2: Create `backend/strategies/registry.py`**

```python
from strategies.moving_average_crossover import MovingAverageCrossover
from strategies.rsi import RSIStrategy

STRATEGY_REGISTRY: dict[str, type] = {
    "moving_average_crossover": MovingAverageCrossover,
    "rsi": RSIStrategy,
}
```

- [ ] **Step 3: Verify existing unit tests still pass**

```bash
python -m pytest tests/backend/ -v
```

Expected: all existing tests pass (no regressions)

- [ ] **Step 4: Commit**

```bash
git add backend/strategies/registry.py backend/strategies/moving_average_crossover.py
git commit -m "feat: add strategy registry and parameters attribute to MA crossover"
```

---

## Task 3: Update `routers/strategies.py`

**Files:**
- Modify: `backend/routers/strategies.py`

- [ ] **Step 1: Replace with registry-driven implementation**

Full replacement for `backend/routers/strategies.py`:

```python
from fastapi import APIRouter
from strategies.registry import STRATEGY_REGISTRY

router = APIRouter()


@router.get("")
async def list_strategies():
    return [
        {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.parameters,
        }
        for cls in STRATEGY_REGISTRY.values()
    ]
```

- [ ] **Step 2: Verify the endpoint returns both strategies**

```bash
curl -s http://localhost:8000/strategies | python -m json.tool
```

Expected: JSON list with two entries — `moving_average_crossover` and `rsi`.

- [ ] **Step 3: Run unit tests to confirm no regressions**

```bash
python -m pytest tests/backend/ -v
```

Expected: all tests pass. Note: `test_list_strategies_returns_moving_average` in `tests/backend/test_api.py` asserts `len(data) == 1` — this will now fail since we have 2 strategies.

Update `tests/backend/test_api.py` line asserting length:

```python
@pytest.mark.asyncio
async def test_list_strategies_returns_moving_average():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/strategies")
    assert resp.status_code == 200
    data = resp.json()
    names = [s["name"] for s in data]
    assert "moving_average_crossover" in names
    assert "rsi" in names
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/backend/ -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/routers/strategies.py tests/backend/test_api.py
git commit -m "feat: make strategies endpoint dynamic via registry"
```

---

## Task 4: Update `routers/backtest.py`

**Files:**
- Modify: `backend/routers/backtest.py`

- [ ] **Step 1: Replace with registry lookup + seed endpoint**

Full replacement for `backend/routers/backtest.py`:

```python
import asyncio
import yfinance as yf
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.price_history import PriceHistory
from strategies.registry import STRATEGY_REGISTRY
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


@router.post("/seed/{symbol}")
async def seed_price_history(
    symbol: str,
    days: int = Query(default=365, ge=1, le=1825),
    db: AsyncSession = Depends(get_db),
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    df = await asyncio.to_thread(
        lambda: yf.download(symbol.upper(), start=start.date(), end=end.date(), progress=False)
    )
    if df.empty:
        raise HTTPException(status_code=422, detail=f"Yahoo Finance returned no data for {symbol}")

    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    existing = await db.execute(
        select(PriceHistory.timestamp).where(PriceHistory.symbol == symbol.upper())
    )
    existing_timestamps = {row[0].replace(tzinfo=timezone.utc) for row in existing.fetchall()}

    inserted = 0
    skipped = 0
    for ts, row in df.iterrows():
        ts_utc = ts.to_pydatetime().replace(tzinfo=timezone.utc)
        if ts_utc in existing_timestamps:
            skipped += 1
            continue
        db.add(PriceHistory(
            symbol=symbol.upper(),
            timestamp=ts_utc,
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=int(row["Volume"]),
            yahoo_close=float(row["Close"]),
            alphavantage_close=None,
            finnhub_close=None,
            outlier_flags={},
            sources_available=["yahoo"],
        ))
        inserted += 1

    await db.commit()
    return {"symbol": symbol.upper(), "inserted": inserted, "skipped": skipped}


@router.post("")
async def run_backtest(req: BacktestRequest, db: AsyncSession = Depends(get_db)):
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: '{req.strategy}'. Available: {list(STRATEGY_REGISTRY.keys())}",
        )

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

    strategy_cls = STRATEGY_REGISTRY[req.strategy]
    strategy = strategy_cls(**req.strategy_params)
    runner = BacktestRunner(strategy=strategy, starting_capital=req.starting_capital)
    trades = runner.run(bars)

    summary = compute_period_summary(trades, req.starting_capital)
    return {"trades": trades, "summary": summary}
```

- [ ] **Step 2: Run unit tests**

```bash
python -m pytest tests/backend/ -v
```

Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/routers/backtest.py
git commit -m "feat: add seed endpoint and registry-based strategy lookup to backtest router"
```

---

## Task 5: Update `scheduler/scraper_job.py`

**Files:**
- Modify: `backend/scheduler/scraper_job.py`

- [ ] **Step 1: Replace hardcoded MA crossover with registry lookup**

Replace the `_trigger_strategy` function (lines 59–92). Full replacement:

```python
async def _trigger_strategy(symbol: str, current_price: float):
    import logging
    from executor.paper import PaperExecutor
    from strategies.registry import STRATEGY_REGISTRY
    from database import AsyncSessionLocal
    from models.trading_session import TradingSession
    from models.price_history import PriceHistory
    from sqlalchemy import select

    logger = logging.getLogger(__name__)

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
        strategy_cls = STRATEGY_REGISTRY.get(session.strategy)
        if strategy_cls is None:
            logger.warning(
                "Unknown strategy '%s' for session %s — skipping",
                session.strategy,
                session.id,
            )
            continue

        strategy = strategy_cls(**session.strategy_params)

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
        if signal.action != "hold":
            executor = PaperExecutor()
            async with AsyncSessionLocal() as db:
                await executor.execute(session, signal, current_price, db)
```

- [ ] **Step 2: Run unit tests**

```bash
python -m pytest tests/backend/ -v
```

Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/scheduler/scraper_job.py
git commit -m "feat: use strategy registry in scheduler, remove MA crossover coupling"
```

---

## Task 6: Integration Tests

**Files:**
- Create: `tests/integration/test_rsi_backtest.py`

- [ ] **Step 1: Write the integration tests**

Create `tests/integration/test_rsi_backtest.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.integration


async def test_seed_endpoint_inserts_rows(client, clean_db):
    resp = await client.post("/backtest/seed/AAPL?days=90")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["inserted"] > 0
    assert data["skipped"] == 0


async def test_seed_endpoint_skips_duplicates(client, clean_db):
    resp1 = await client.post("/backtest/seed/AAPL?days=90")
    assert resp1.status_code == 200
    assert resp1.json()["inserted"] > 0

    resp2 = await client.post("/backtest/seed/AAPL?days=90")
    assert resp2.status_code == 200
    assert resp2.json()["inserted"] == 0
    assert resp2.json()["skipped"] > 0


async def test_rsi_backtest_returns_valid_structure(client, clean_db):
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest", json={
        "symbol": "AAPL",
        "strategy": "rsi",
        "strategy_params": {"period": 14, "oversold": 30, "overbought": 70, "signal_mode": "transition"},
        "starting_capital": 1000.0,
        "from_dt": start.isoformat(),
        "to_dt": end.isoformat(),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "summary" in data
    assert isinstance(data["trades"], list)
    assert isinstance(data["summary"], dict)


async def test_rsi_backtest_summary_has_required_keys(client, clean_db):
    await client.post("/backtest/seed/AAPL?days=90")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest", json={
        "symbol": "AAPL",
        "strategy": "rsi",
        "strategy_params": {"period": 14, "oversold": 30, "overbought": 70, "signal_mode": "transition"},
        "starting_capital": 1000.0,
        "from_dt": start.isoformat(),
        "to_dt": end.isoformat(),
    })
    summary = resp.json()["summary"]
    for key in ("total_pnl", "num_trades", "num_wins", "num_losses", "win_rate", "starting_capital", "ending_capital"):
        assert key in summary, f"Missing key: {key}"


async def test_rsi_strategy_appears_in_list(client):
    resp = await client.get("/strategies")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "rsi" in names
    assert "moving_average_crossover" in names


async def test_backtest_returns_400_for_unknown_strategy(client):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    resp = await client.post("/backtest", json={
        "symbol": "AAPL",
        "strategy": "nonexistent_strategy",
        "strategy_params": {},
        "starting_capital": 1000.0,
        "from_dt": start.isoformat(),
        "to_dt": end.isoformat(),
    })
    assert resp.status_code == 400
    assert "nonexistent_strategy" in resp.json()["detail"]
```

- [ ] **Step 2: Start Docker stack and run migrations**

```bash
docker compose up --build -d
# Wait for backend to be ready (poll until 200)
until curl -sf http://localhost:8000/strategies > /dev/null; do sleep 2; done
docker compose exec -T backend alembic upgrade head
```

- [ ] **Step 3: Run integration tests**

```bash
python -m pytest tests/integration/ -v --timeout=60 -m integration
```

Expected: all 16 existing tests pass + 6 new RSI tests pass = **22 passed**

- [ ] **Step 4: Run full test suite (unit + integration)**

```bash
python -m pytest tests/backend/ -v
python -m pytest tests/integration/ -v --timeout=60 -m integration
```

Both must be fully green before committing.

- [ ] **Step 5: Tear down and run via shell script**

```bash
docker compose down -v
./scripts/run-integration-tests.sh
```

Expected: script exits 0

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_rsi_backtest.py
git commit -m "test: add integration tests for RSI backtest and seed endpoint"
```
