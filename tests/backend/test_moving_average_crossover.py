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
