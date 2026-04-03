import pytest
from strategies.macd import MACDStrategy, _compute_ema, _compute_macd


def _rising(n: int, start: float = 100.0, rise: float = 1.5) -> list[float]:
    return [start + i * rise for i in range(n)]


def _falling(n: int, start: float = 100.0, drop: float = 1.5) -> list[float]:
    return [start - i * drop for i in range(n)]


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_macd_insufficient_data_returns_hold():
    strategy = MACDStrategy()
    # Need fast_period(12) + slow_period(26) + signal_period(9) + 1 = 47 bars for crossover
    result = strategy.analyze(_flat(30))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_macd_buy_on_bullish_crossover():
    """MACD line crossing above signal line → buy.

    Series: 20 falling bars then 2 rising bars.
    The reversal causes fast EMA to lift faster than slow EMA,
    producing a MACD bullish crossover on the final bar.
    """
    strategy = MACDStrategy(fast_period=3, slow_period=6, signal_period=2)
    closes = _falling(20, start=100.0, drop=2.0) + _rising(2, start=60.0, rise=3.0)
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_macd_sell_on_bearish_crossover():
    """MACD line crossing below signal line → sell.

    Series: 20 rising bars then 2 falling bars.
    The reversal causes fast EMA to drop faster than slow EMA,
    producing a MACD bearish crossover on the final bar.
    """
    strategy = MACDStrategy(fast_period=3, slow_period=6, signal_period=2)
    closes = _rising(20, start=50.0, rise=3.0) + _falling(2, start=110.0, drop=4.0)
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_macd_hold_on_no_crossover():
    """Flat or monotone series with no crossover → hold."""
    strategy = MACDStrategy(fast_period=3, slow_period=6, signal_period=2)
    # Perfectly flat series → MACD and signal both zero, no crossover
    closes = _flat(30)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_macd_default_parameters():
    strategy = MACDStrategy()
    assert strategy.fast_period == 12
    assert strategy.slow_period == 26
    assert strategy.signal_period == 9


def test_compute_ema_single_value():
    """EMA of a single value equals that value."""
    result = _compute_ema([42.0], period=1)
    assert result == pytest.approx(42.0)


def test_compute_ema_all_same_returns_same():
    """EMA of constant series equals the constant."""
    result = _compute_ema([5.0] * 20, period=10)
    assert result == pytest.approx(5.0)


def test_compute_macd_flat_series_is_zero():
    """MACD of flat price series is zero (fast EMA == slow EMA)."""
    macd_line, signal_line = _compute_macd(_flat(50), fast=12, slow=26, signal=9)
    assert macd_line == pytest.approx(0.0, abs=1e-9)
    assert signal_line == pytest.approx(0.0, abs=1e-9)


def test_macd_reason_includes_values():
    """Signal reason should include numeric MACD details."""
    strategy = MACDStrategy(fast_period=3, slow_period=6, signal_period=2)
    closes = _falling(20, start=100.0, drop=2.0) + _rising(2, start=60.0, rise=3.0)
    result = strategy.analyze(closes)
    assert "MACD" in result.reason


def test_macd_confidence_between_0_and_1():
    """Confidence must be in [0, 1]."""
    strategy = MACDStrategy(fast_period=3, slow_period=6, signal_period=2)
    for closes in [
        _flat(30),
        _rising(50),
        _falling(50),
        _falling(20, start=100.0, drop=2.0) + _rising(2, start=60.0, rise=3.0),
    ]:
        result = strategy.analyze(closes)
        assert 0.0 <= result.confidence <= 1.0
