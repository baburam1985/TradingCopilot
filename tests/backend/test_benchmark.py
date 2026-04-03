"""Unit tests for BenchmarkCalculator.

Covers:
- Correct return calculation for known price series
- Edge cases: < 2 bars, zero start price
- Equity curve shape and downsampling guard
"""

import pytest
from types import SimpleNamespace
from datetime import date, timedelta

from backend.backtester.benchmark import BenchmarkCalculator, _MAX_EQUITY_CURVE_POINTS


def _make_bars(prices: list[float], start_date: date = date(2024, 1, 1)):
    bars = []
    for i, price in enumerate(prices):
        ts = start_date + timedelta(days=i)
        bars.append(SimpleNamespace(close=price, timestamp=ts))
    return bars


class TestBenchmarkCompute:
    def test_known_return(self):
        """Buy at 100, sell at 150 → +50%."""
        bars = _make_bars([100.0, 125.0, 150.0])
        result = BenchmarkCalculator.compute(bars, starting_capital=1000.0)
        assert result["bnh_return_pct"] == pytest.approx(50.0, rel=1e-4)
        assert result["bnh_final_value"] == pytest.approx(1500.0, rel=1e-4)

    def test_negative_return(self):
        """Buy at 200, price drops to 100 → -50%."""
        bars = _make_bars([200.0, 150.0, 100.0])
        result = BenchmarkCalculator.compute(bars, starting_capital=1000.0)
        assert result["bnh_return_pct"] == pytest.approx(-50.0, rel=1e-4)
        assert result["bnh_final_value"] == pytest.approx(500.0, rel=1e-4)

    def test_flat_return(self):
        """Price unchanged → 0% return."""
        bars = _make_bars([50.0, 50.0, 50.0])
        result = BenchmarkCalculator.compute(bars, starting_capital=500.0)
        assert result["bnh_return_pct"] == pytest.approx(0.0, abs=1e-6)
        assert result["bnh_final_value"] == pytest.approx(500.0, rel=1e-4)

    def test_equity_curve_length_matches_bars(self):
        bars = _make_bars([10.0 + i for i in range(20)])
        result = BenchmarkCalculator.compute(bars, starting_capital=100.0)
        assert len(result["bnh_equity_curve"]) == 20

    def test_equity_curve_first_and_last_values(self):
        bars = _make_bars([100.0, 110.0, 120.0])
        result = BenchmarkCalculator.compute(bars, starting_capital=1000.0)
        curve = result["bnh_equity_curve"]
        assert curve[0]["value"] == pytest.approx(1000.0, rel=1e-4)
        assert curve[-1]["value"] == pytest.approx(1200.0, rel=1e-4)


class TestBenchmarkEdgeCases:
    def test_single_bar_returns_nulls(self):
        bars = _make_bars([100.0])
        result = BenchmarkCalculator.compute(bars, starting_capital=1000.0)
        assert result["bnh_return_pct"] is None
        assert result["bnh_final_value"] is None
        assert result["bnh_equity_curve"] == []

    def test_empty_bars_returns_nulls(self):
        result = BenchmarkCalculator.compute([], starting_capital=1000.0)
        assert result["bnh_return_pct"] is None
        assert result["bnh_final_value"] is None
        assert result["bnh_equity_curve"] == []

    def test_zero_start_price_returns_nulls(self):
        bars = _make_bars([0.0, 100.0, 150.0])
        result = BenchmarkCalculator.compute(bars, starting_capital=1000.0)
        assert result["bnh_return_pct"] is None
        assert result["bnh_final_value"] is None

    def test_large_series_is_downsampled(self):
        """Bar series longer than _MAX_EQUITY_CURVE_POINTS is downsampled."""
        prices = [100.0 + i * 0.01 for i in range(_MAX_EQUITY_CURVE_POINTS + 100)]
        bars = _make_bars(prices)
        result = BenchmarkCalculator.compute(bars, starting_capital=1000.0)
        # Must be at most the limit (with last point always included)
        assert len(result["bnh_equity_curve"]) <= _MAX_EQUITY_CURVE_POINTS + 1
        # Last point always equals the actual last bar value
        last_bar_value = (1000.0 / prices[0]) * prices[-1]
        assert result["bnh_equity_curve"][-1]["value"] == pytest.approx(last_bar_value, rel=1e-3)
