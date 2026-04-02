# RSI Strategy Design

**Date:** 2026-04-02
**Scope:** RSI trading strategy + strategy registry + historical data seed endpoint
**Goal:** Add an RSI strategy that works with seeded historical data, visible immediately without waiting for live market hours.

---

## Motivation

The existing Moving Average Crossover strategy requires 201 bars before generating any signal. At 1 bar/minute during market hours, that is ~3.5 hours before the first trade. The RSI strategy requires only 15 bars and can run against seeded historical data immediately, enabling manual verification and demos outside market hours.

---

## Guiding Principles

- RSI strategy conforms to the existing `StrategyBase` interface — `analyze(closes: list[float]) -> Signal`
- A strategy registry replaces hardcoded strategy lookups in all routers and the scheduler
- Adding future strategies requires only: a new strategy file + one registry entry
- Both signal modes (transition and level) are user-selectable at session creation time

---

## File Structure

```
backend/
├── strategies/
│   ├── base.py                        (unchanged)
│   ├── moving_average_crossover.py    (unchanged)
│   ├── rsi.py                         (NEW)
│   └── registry.py                    (NEW)
├── routers/
│   ├── strategies.py                  (updated — dynamic from registry)
│   ├── backtest.py                    (updated — strategy lookup via registry)
│   └── market_data.py                 (unchanged)
├── scheduler/
│   └── scraper_job.py                 (updated — strategy lookup via registry)
tests/
├── backend/
│   └── test_rsi_strategy.py           (NEW)
└── integration/
    └── test_rsi_backtest.py           (NEW)
```

---

## Strategy Registry: `backend/strategies/registry.py`

```python
from strategies.moving_average_crossover import MovingAverageCrossover
from strategies.rsi import RSIStrategy

STRATEGY_REGISTRY: dict[str, type] = {
    "moving_average_crossover": MovingAverageCrossover,
    "rsi": RSIStrategy,
}
```

Used by: `routers/strategies.py`, `routers/backtest.py`, `scheduler/scraper_job.py`.

Each strategy class exposes:
- `name: str` — registry key
- `description: str` — human-readable
- `parameters: dict` — parameter names with type, default, and description (used by `/strategies` endpoint)

---

## RSI Strategy: `backend/strategies/rsi.py`

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | int | 14 | Number of bars for RSI calculation |
| `oversold` | int | 30 | RSI below this threshold → buy signal |
| `overbought` | int | 70 | RSI above this threshold → sell signal |
| `signal_mode` | str | `"transition"` | `"transition"` or `"level"` |

### RSI Calculation

Uses Wilder's smoothing (standard):
1. Compute price changes: `delta[i] = close[i] - close[i-1]`
2. Separate gains (delta > 0) and losses (abs(delta) where delta < 0)
3. Initial average gain/loss = simple average over first `period` bars
4. Subsequent: `avg_gain = (prev_avg_gain * (period - 1) + current_gain) / period`
5. `RS = avg_gain / avg_loss`; `RSI = 100 - (100 / (1 + RS))`

Minimum bars required: `period + 1` (15 with default period=14)

### Signal Modes

**Transition mode** (`signal_mode="transition"`):
- BUY fires once when RSI crosses *below* `oversold` (prev RSI >= oversold, current RSI < oversold)
- SELL fires once when RSI crosses *above* `overbought` (prev RSI <= overbought, current RSI > overbought)
- Returns HOLD at all other times
- Requires `period + 2` bars minimum (to compute two consecutive RSI values)

**Level mode** (`signal_mode="level"`):
- BUY fires every bar RSI is below `oversold`
- SELL fires every bar RSI is above `overbought`
- Returns HOLD when RSI is between thresholds
- Requires `period + 1` bars minimum

### Signal Output

```python
Signal(
    action="buy",
    reason="RSI(14) crossed below oversold threshold: RSI=28.3 < 30",
    confidence=0.75,
)
```

---

## Historical Seed Endpoint

**`POST /backtest/seed/{symbol}?days=365`**

- Fetches `days` of daily OHLCV bars from Yahoo Finance via `yf.download()`
- Flattens MultiIndex columns (yfinance 1.x)
- Inserts rows into `price_history`, skipping duplicates (same symbol + timestamp)
- Returns `{"inserted": N, "skipped": M, "symbol": "AAPL"}`
- Returns `422` if Yahoo Finance returns no data

Location: `backend/routers/backtest.py` (new route alongside existing `POST /backtest`)

### Typical workflow

```bash
# 1. Seed 1 year of history
POST /backtest/seed/AAPL?days=365

# 2. Run RSI backtest against it
POST /backtest
{
  "symbol": "AAPL",
  "strategy": "rsi",
  "strategy_params": {"period": 14, "oversold": 30, "overbought": 70, "signal_mode": "transition"},
  "starting_capital": 1000.0,
  "from_dt": "2025-04-01T00:00:00",
  "to_dt": "2026-04-01T00:00:00"
}
```

---

## Router Updates

### `routers/strategies.py`
Iterate `STRATEGY_REGISTRY` and return each strategy's `name`, `description`, and `parameters` dict. No hardcoded strategy names.

### `routers/backtest.py`
Look up strategy class from `STRATEGY_REGISTRY[req.strategy]`. Return `400` with a clear message if the strategy name is not found. Pass `req.strategy_params` as kwargs to the constructor.

### `scheduler/scraper_job.py`
Replace `from strategies.moving_average_crossover import MovingAverageCrossover` with a registry lookup using `session.strategy` field. Sessions with unknown strategy names log a warning and skip.

---

## Unit Tests: `tests/backend/test_rsi_strategy.py`

| Test | Description |
|------|-------------|
| `test_rsi_buy_on_oversold_transition` | RSI crosses below 30 → buy signal |
| `test_rsi_sell_on_overbought_transition` | RSI crosses above 70 → sell signal |
| `test_rsi_hold_when_sustained_below_oversold` | RSI stays below 30 (transition mode) → hold after first signal |
| `test_rsi_insufficient_data_returns_hold` | Fewer than period+2 bars → hold |
| `test_rsi_level_mode_signals_every_bar` | Level mode: buy fires each bar RSI < 30 |
| `test_rsi_boundary_exact_oversold` | RSI exactly at 30 → no buy signal (must be strictly below) |
| `test_rsi_boundary_exact_overbought` | RSI exactly at 70 → no sell signal (must be strictly above) |

---

## Integration Tests: `tests/integration/test_rsi_backtest.py`

| Test | Description |
|------|-------------|
| `test_seed_endpoint_inserts_rows` | `POST /backtest/seed/AAPL?days=90` returns inserted > 0 |
| `test_seed_endpoint_skips_duplicates` | Calling seed twice returns inserted=0 on second call |
| `test_rsi_backtest_returns_valid_structure` | Backtest response has `trades` list and `summary` dict |
| `test_rsi_backtest_summary_keys` | Summary has all required keys |
| `test_rsi_strategy_appears_in_list` | `GET /strategies` includes `rsi` entry |

---

## Running Tests

```bash
# Unit tests only
python -m pytest tests/backend/test_rsi_strategy.py -v

# Full integration suite (requires Docker)
./scripts/run-integration-tests.sh
```
