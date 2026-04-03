"""Tests for multi-strategy comparison logic — used by POST /backtest/compare."""
import pytest
from backtester.compare import run_comparison


def _bar(close: float):
    """Minimal price bar stub."""
    class Bar:
        def __init__(self, c):
            self.close = c
            self.timestamp = None
    return Bar(close)


def _bars(closes):
    return [_bar(c) for c in closes]


def test_compare_returns_one_result_per_strategy():
    bars = _bars([100.0] * 30)
    specs = [
        {"name": "moving_average_crossover", "params": {"short_window": 5, "long_window": 10}},
        {"name": "rsi", "params": {"period": 14}},
    ]
    results = run_comparison(bars, strategy_specs=specs, starting_capital=1000.0)
    assert len(results) == 2
    assert results[0]["strategy"] == "moving_average_crossover"
    assert results[1]["strategy"] == "rsi"


def test_compare_result_contains_summary_and_trades():
    bars = _bars([100.0] * 30)
    specs = [{"name": "rsi", "params": {"period": 14}}]
    results = run_comparison(bars, strategy_specs=specs, starting_capital=1000.0)
    assert "summary" in results[0]
    assert "trades" in results[0]


def test_compare_summary_has_required_metrics():
    bars = _bars([100.0] * 30)
    specs = [{"name": "rsi", "params": {"period": 14}}]
    results = run_comparison(bars, strategy_specs=specs, starting_capital=1000.0)
    summary = results[0]["summary"]
    for key in ("total_pnl", "win_rate", "num_trades", "sharpe_ratio", "max_drawdown_pct"):
        assert key in summary, f"Missing key: {key}"


def test_compare_empty_specs_returns_empty_list():
    bars = _bars([100.0] * 30)
    results = run_comparison(bars, strategy_specs=[], starting_capital=1000.0)
    assert results == []


def test_compare_unknown_strategy_raises_value_error():
    bars = _bars([100.0] * 30)
    specs = [{"name": "nonexistent_strategy", "params": {}}]
    with pytest.raises(ValueError, match="Unknown strategy"):
        run_comparison(bars, strategy_specs=specs, starting_capital=1000.0)


def test_compare_all_strategies_use_same_bars():
    """Both strategies receive identical bar data — results should be deterministic."""
    closes = [100 + i * 0.5 for i in range(60)]
    bars = _bars(closes)
    specs = [
        {"name": "moving_average_crossover", "params": {"short_window": 5, "long_window": 10}},
        {"name": "moving_average_crossover", "params": {"short_window": 5, "long_window": 10}},
    ]
    results = run_comparison(bars, strategy_specs=specs, starting_capital=500.0)
    assert results[0]["summary"]["total_pnl"] == results[1]["summary"]["total_pnl"]
