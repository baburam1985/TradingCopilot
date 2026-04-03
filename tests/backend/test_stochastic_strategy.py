import pytest
from strategies.stochastic import StochasticStrategy


def _falling(n: int, start: float = 100.0, drop: float = 2.0) -> list[float]:
    return [start - i * drop for i in range(n)]


def _rising(n: int, start: float = 50.0, rise: float = 2.0) -> list[float]:
    return [start + i * rise for i in range(n)]


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_stochastic_insufficient_data_returns_hold():
    strategy = StochasticStrategy(k_period=14, d_period=3)
    # need k_period + d_period bars; supply fewer
    result = strategy.analyze(_flat(15))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_stochastic_buy_on_oversold_cross():
    """
    %K crosses up through oversold at the last bar.

    With k_period=5: falls steadily (k≈0), then last bar recovers just enough
    to push %K above 20 — crossover happens on the final bar.
    """
    strategy = StochasticStrategy(k_period=5, d_period=3, oversold=20, overbought=80)
    # Steady fall drives %K to 0, final bar recovers → %K ≈ 33 (above 20)
    closes = [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0, 65.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_stochastic_sell_on_overbought_cross():
    """
    %K crosses down through overbought at the last bar.

    With k_period=5: rises steadily (k≈100), then last bar drops just enough
    to push %K below 80 — crossover happens on the final bar.
    """
    strategy = StochasticStrategy(k_period=5, d_period=3, oversold=20, overbought=80)
    # Steady rise drives %K to 100, final bar dips → %K ≈ 67 (below 80)
    closes = [60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0, 100.0, 95.0]
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_stochastic_hold_when_no_threshold_cross():
    """Flat prices keep %K near 50 — no overbought/oversold signal."""
    strategy = StochasticStrategy(k_period=5, d_period=3)
    result = strategy.analyze(_flat(20))
    assert result.action == "hold"


def test_stochastic_default_parameters():
    strategy = StochasticStrategy()
    assert strategy.k_period == 14
    assert strategy.d_period == 3
    assert strategy.oversold == 20
    assert strategy.overbought == 80


def test_stochastic_configurable_parameters():
    strategy = StochasticStrategy(k_period=9, d_period=5, oversold=25, overbought=75)
    assert strategy.k_period == 9
    assert strategy.d_period == 5
    assert strategy.oversold == 25
    assert strategy.overbought == 75


def test_stochastic_buy_signal_has_confidence():
    strategy = StochasticStrategy(k_period=5, d_period=3, oversold=20, overbought=80)
    closes = [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0, 65.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"
    assert result.confidence > 0.0


def test_stochastic_has_parameters_dict():
    assert hasattr(StochasticStrategy, "parameters")
    assert "k_period" in StochasticStrategy.parameters
    assert "d_period" in StochasticStrategy.parameters
    assert "oversold" in StochasticStrategy.parameters
    assert "overbought" in StochasticStrategy.parameters
