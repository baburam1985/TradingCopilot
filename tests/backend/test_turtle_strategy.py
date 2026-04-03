import pytest
from strategies.turtle import TurtleStrategy


def _channel_breakout_closes(entry_period: int = 20) -> list[float]:
    """Produces a series where the last close breaks above the prior 20-bar high."""
    base = [100.0 + i * 0.1 for i in range(entry_period)]  # gently rising
    # last bar spikes well above the channel high
    base.append(base[-1] + 10.0)
    return base


def _channel_breakdown_closes(entry_period: int = 20, exit_period: int = 10) -> list[float]:
    """Series where price collapses below the 10-bar low after being in an uptrend."""
    # Build enough bars so we have 20 bars of history plus an exit signal
    bars = [100.0 + i * 0.5 for i in range(30)]  # rising trend
    bars.append(bars[-exit_period] - 5.0)         # sharp drop below 10-bar low
    return bars


def _flat_closes(n: int = 30, base: float = 100.0) -> list[float]:
    return [base] * n


def test_turtle_insufficient_data_returns_hold():
    strategy = TurtleStrategy(entry_period=20, exit_period=10)
    # Need at least entry_period + 1 bars; supply fewer
    result = strategy.analyze([100.0] * 20)
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_turtle_buy_on_channel_breakout():
    strategy = TurtleStrategy(entry_period=20, exit_period=10)
    closes = _channel_breakout_closes(entry_period=20)
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_turtle_sell_when_price_falls_below_exit_channel():
    strategy = TurtleStrategy(entry_period=20, exit_period=10)
    closes = _channel_breakdown_closes()
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_turtle_hold_when_no_breakout_or_breakdown():
    strategy = TurtleStrategy(entry_period=20, exit_period=10)
    # Flat prices — close equals the channel high and low, no breakout
    closes = _flat_closes(30)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_turtle_default_parameters():
    strategy = TurtleStrategy()
    assert strategy.entry_period == 20
    assert strategy.exit_period == 10


def test_turtle_configurable_periods():
    strategy = TurtleStrategy(entry_period=10, exit_period=5)
    assert strategy.entry_period == 10
    assert strategy.exit_period == 5


def test_turtle_buy_signal_has_confidence():
    strategy = TurtleStrategy(entry_period=20, exit_period=10)
    closes = _channel_breakout_closes(entry_period=20)
    result = strategy.analyze(closes)
    assert result.action == "buy"
    assert result.confidence > 0.0


def test_turtle_sell_signal_has_confidence():
    strategy = TurtleStrategy(entry_period=20, exit_period=10)
    closes = _channel_breakdown_closes()
    result = strategy.analyze(closes)
    assert result.action == "sell"
    assert result.confidence > 0.0


def test_turtle_has_parameters_dict():
    assert hasattr(TurtleStrategy, "parameters")
    assert "entry_period" in TurtleStrategy.parameters
    assert "exit_period" in TurtleStrategy.parameters
