import pytest
from strategies.adx import ADXStrategy


def _rising(n: int, start: float = 50.0, step: float = 2.0) -> list[float]:
    return [start + i * step for i in range(n)]


def _falling(n: int, start: float = 100.0, step: float = 2.0) -> list[float]:
    return [start - i * step for i in range(n)]


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_adx_insufficient_data_returns_hold():
    strategy = ADXStrategy(adx_period=14)
    # Need at least adx_period + 2 bars; supply fewer
    result = strategy.analyze(_flat(14))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_adx_buy_on_strong_uptrend():
    """
    A sustained strong uptrend produces ADX > 25 and DI+ > DI−,
    generating a buy signal.
    """
    strategy = ADXStrategy(adx_period=14, adx_threshold=25)
    closes = _rising(60, start=50.0, step=1.5)
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_adx_sell_on_strong_downtrend():
    """
    A sustained strong downtrend produces ADX > 25 and DI− > DI+,
    generating a sell signal.
    """
    strategy = ADXStrategy(adx_period=14, adx_threshold=25)
    closes = _falling(60, start=200.0, step=1.5)
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_adx_hold_when_trend_weak():
    """
    Flat prices produce ADX near 0 (weak trend) — no trade signal.
    """
    strategy = ADXStrategy(adx_period=14, adx_threshold=25)
    result = strategy.analyze(_flat(40))
    assert result.action == "hold"


def test_adx_default_parameters():
    strategy = ADXStrategy()
    assert strategy.adx_period == 14
    assert strategy.adx_threshold == 25


def test_adx_configurable_parameters():
    strategy = ADXStrategy(adx_period=10, adx_threshold=20)
    assert strategy.adx_period == 10
    assert strategy.adx_threshold == 20


def test_adx_buy_signal_has_confidence():
    strategy = ADXStrategy(adx_period=14, adx_threshold=25)
    closes = _rising(60, start=50.0, step=1.5)
    result = strategy.analyze(closes)
    assert result.action == "buy"
    assert result.confidence > 0.0


def test_adx_sell_signal_has_confidence():
    strategy = ADXStrategy(adx_period=14, adx_threshold=25)
    closes = _falling(60, start=200.0, step=1.5)
    result = strategy.analyze(closes)
    assert result.action == "sell"
    assert result.confidence > 0.0


def test_adx_has_parameters_dict():
    assert hasattr(ADXStrategy, "parameters")
    assert "adx_period" in ADXStrategy.parameters
    assert "adx_threshold" in ADXStrategy.parameters
