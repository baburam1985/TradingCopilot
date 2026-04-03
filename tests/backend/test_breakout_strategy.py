import pytest
from strategies.breakout import BreakoutStrategy


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_breakout_insufficient_data_returns_hold():
    strategy = BreakoutStrategy(period=10)
    # Need period+1 bars to compare current bar against prior N-day channel
    result = strategy.analyze(_flat(10))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_breakout_buy_on_new_high():
    """Price exceeding the N-day high → buy (breakout)."""
    strategy = BreakoutStrategy(period=5)
    # 5-bar channel: all at 100, then price breaks above to 110
    closes = [100.0, 98.0, 99.0, 101.0, 100.0, 110.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_breakout_sell_on_new_low():
    """Price falling below the N-day low → sell (breakdown)."""
    strategy = BreakoutStrategy(period=5)
    closes = [100.0, 102.0, 99.0, 101.0, 100.0, 85.0]
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_breakout_hold_when_price_in_channel():
    """Price within N-day channel → hold."""
    strategy = BreakoutStrategy(period=5)
    closes = [95.0, 100.0, 105.0, 98.0, 97.0, 100.0]
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_breakout_hold_on_flat_series():
    """Flat series: price == channel high == channel low → hold."""
    strategy = BreakoutStrategy(period=5)
    closes = _flat(10)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_breakout_default_parameters():
    strategy = BreakoutStrategy()
    assert strategy.period == 20


def test_breakout_buy_uses_prior_period_not_including_current():
    """Channel high/low should be computed from the prior N bars (no lookahead)."""
    strategy = BreakoutStrategy(period=3)
    # Prior 3 bars: 90, 95, 100 → channel high=100, low=90
    # Current bar: 101 → breaks above 100
    closes = [90.0, 95.0, 100.0, 101.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_breakout_reason_includes_channel_level():
    """Signal reason should reference the breakout level."""
    strategy = BreakoutStrategy(period=5)
    closes = [100.0, 98.0, 99.0, 101.0, 100.0, 110.0]
    result = strategy.analyze(closes)
    assert "110" in result.reason or "high" in result.reason.lower()


def test_breakout_confidence_between_0_and_1():
    strategy = BreakoutStrategy(period=5)
    for closes in [
        _flat(10),
        [100.0, 98.0, 99.0, 101.0, 100.0, 110.0],
        [100.0, 102.0, 99.0, 101.0, 100.0, 85.0],
    ]:
        result = strategy.analyze(closes)
        assert 0.0 <= result.confidence <= 1.0
