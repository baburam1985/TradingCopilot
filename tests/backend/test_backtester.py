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
    # Flat prices then spike triggers golden cross (BUY at index 6)
    prices = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0]
    bars = _make_bars(prices)
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    runner = BacktestRunner(strategy=strategy, starting_capital=1000.0)
    trades = runner.run(bars)
    buy_trades = [t for t in trades if t["action"] == "buy"]
    assert len(buy_trades) >= 1

def test_backtest_pnl_calculated_on_close():
    # Golden cross at index 6, death cross at index 11
    prices = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0,
              20.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    bars = _make_bars(prices)
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    runner = BacktestRunner(strategy=strategy, starting_capital=1000.0)
    trades = runner.run(bars)
    closed = [t for t in trades if t["status"] == "closed"]
    assert len(closed) >= 1
    assert closed[0]["pnl"] is not None
