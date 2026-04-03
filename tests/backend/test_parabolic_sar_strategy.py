import pytest
from strategies.parabolic_sar import ParabolicSARStrategy


def _rising(n: int, start: float = 50.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def _falling(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start - i * step for i in range(n)]


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_psar_insufficient_data_returns_hold():
    strategy = ParabolicSARStrategy()
    result = strategy.analyze([100.0, 101.0])  # too few bars
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_psar_buy_when_price_rises_above_sar():
    """
    SAR bullish flip occurs on the last bar.

    A 20-bar downtrend leaves SAR in bearish mode (SAR ≥ ~83).
    A single massive jump to 1000 crosses above SAR → flip to bullish.
    The series without the last bar is still bearish, so bullish_prev=False.
    """
    strategy = ParabolicSARStrategy(af_start=0.02, af_step=0.02, af_max=0.20)
    closes = [100.0 - i for i in range(20)] + [1000.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_psar_sell_when_price_falls_below_sar():
    """
    SAR bearish flip occurs on the last bar.

    A 20-bar uptrend leaves SAR in bullish mode (SAR ≤ ~66).
    A single massive drop to 0 crosses below SAR → flip to bearish.
    The series without the last bar is still bullish, so bullish_prev=True.
    """
    strategy = ParabolicSARStrategy(af_start=0.02, af_step=0.02, af_max=0.20)
    closes = [50.0 + i for i in range(20)] + [0.0]
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_psar_hold_on_flat_prices():
    """Flat prices keep SAR stationary relative to price — no reversal."""
    strategy = ParabolicSARStrategy()
    result = strategy.analyze(_flat(30))
    assert result.action == "hold"


def test_psar_default_parameters():
    strategy = ParabolicSARStrategy()
    assert strategy.af_start == pytest.approx(0.02)
    assert strategy.af_step == pytest.approx(0.02)
    assert strategy.af_max == pytest.approx(0.20)


def test_psar_configurable_parameters():
    strategy = ParabolicSARStrategy(af_start=0.01, af_step=0.01, af_max=0.10)
    assert strategy.af_start == pytest.approx(0.01)
    assert strategy.af_step == pytest.approx(0.01)
    assert strategy.af_max == pytest.approx(0.10)


def test_psar_buy_signal_has_confidence():
    strategy = ParabolicSARStrategy()
    closes = [100.0 - i for i in range(20)] + [1000.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"
    assert result.confidence > 0.0


def test_psar_sell_signal_has_confidence():
    strategy = ParabolicSARStrategy()
    closes = [50.0 + i for i in range(20)] + [0.0]
    result = strategy.analyze(closes)
    assert result.action == "sell"
    assert result.confidence > 0.0


def test_psar_has_parameters_dict():
    assert hasattr(ParabolicSARStrategy, "parameters")
    assert "af_start" in ParabolicSARStrategy.parameters
    assert "af_step" in ParabolicSARStrategy.parameters
    assert "af_max" in ParabolicSARStrategy.parameters
