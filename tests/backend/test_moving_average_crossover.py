# tests/backend/test_moving_average_crossover.py
import pytest
from backend.strategies.moving_average_crossover import MovingAverageCrossover


def test_golden_cross_generates_buy_signal():
    # short MA (3) crosses above long MA (5) at the last bar
    # prices = [20.0, 18.0, 16.0, 14.0, 12.0, 26.0], short_window=3, long_window=5
    # prev (5 prices=[20,18,16,14,12]): short_ma_prev=(16+14+12)/3=14.0, long_ma_prev=(20+18+16+14+12)/5=16.0 → short < long
    # now (6 prices=[20,18,16,14,12,26]): short_ma_now=(14+12+26)/3=17.33, long_ma_now=(18+16+14+12+26)/5=17.2 → short > long
    # This IS a golden cross transition.
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    prices = [20.0, 18.0, 16.0, 14.0, 12.0, 26.0]
    signal = strategy.analyze(prices)
    assert signal.action == "buy"
    assert "golden cross" in signal.reason.lower()


def test_death_cross_generates_sell_signal():
    # prices = [12.0, 14.0, 16.0, 18.0, 20.0, 5.0], short_window=3, long_window=5
    # prev (5 prices=[12,14,16,18,20]): short_ma_prev=(16+18+20)/3=18.0, long_ma_prev=(12+14+16+18+20)/5=16.0 → short > long
    # now (6 prices=[12,14,16,18,20,5]): short_ma_now=(18+20+5)/3=14.33, long_ma_now=(14+16+18+20+5)/5=14.6 → short < long
    # This IS a death cross transition.
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    prices = [12.0, 14.0, 16.0, 18.0, 20.0, 5.0]
    signal = strategy.analyze(prices)
    assert signal.action == "sell"
    assert "death cross" in signal.reason.lower()


def test_no_crossover_generates_hold():
    # Flat prices: short MA == long MA throughout, no transition
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    prices = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    signal = strategy.analyze(prices)
    assert signal.action == "hold"


def test_insufficient_data_generates_hold():
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    prices = [10.0, 11.0]  # Not enough for long_window+1=6
    signal = strategy.analyze(prices)
    assert signal.action == "hold"


def test_no_signal_on_sustained_position():
    """After a golden cross, if short stays above long, subsequent bars are hold."""
    strategy = MovingAverageCrossover(short_window=3, long_window=5)
    # Golden cross on bar 6
    prices = [20.0, 18.0, 16.0, 14.0, 12.0, 26.0]
    signal = strategy.analyze(prices)
    assert signal.action == "buy"

    # Add another bar where short is still above long — should be hold now
    prices_extended = prices + [22.0]
    signal2 = strategy.analyze(prices_extended)
    assert signal2.action == "hold"
