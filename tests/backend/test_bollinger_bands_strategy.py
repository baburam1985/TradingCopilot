import pytest
from strategies.bollinger_bands import BollingerBandsStrategy, _compute_bollinger_bands


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def _spike_down(base_series: list[float], spike: float) -> list[float]:
    """Return series with a final bar sharply below base."""
    return base_series[:-1] + [base_series[-1] - spike]


def _spike_up(base_series: list[float], spike: float) -> list[float]:
    """Return series with a final bar sharply above base."""
    return base_series[:-1] + [base_series[-1] + spike]


def test_bollinger_insufficient_data_returns_hold():
    strategy = BollingerBandsStrategy(period=20)
    result = strategy.analyze(_flat(19))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_bollinger_buy_when_price_touches_lower_band():
    """Price dropping far below mean → buy (lower band touch)."""
    strategy = BollingerBandsStrategy(period=10, std_dev_multiplier=2.0)
    # Flat base so bands are tight (std≈0), then one sharp dip below lower band
    base = _flat(15, base=100.0)
    closes = _spike_down(base, spike=50.0)  # 50 far exceeds any std band
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_bollinger_sell_when_price_touches_upper_band():
    """Price spiking far above mean → sell (upper band touch)."""
    strategy = BollingerBandsStrategy(period=10, std_dev_multiplier=2.0)
    base = _flat(15, base=100.0)
    closes = _spike_up(base, spike=50.0)
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_bollinger_hold_when_price_in_middle():
    """Price near the mean → hold (not touching either band)."""
    strategy = BollingerBandsStrategy(period=10, std_dev_multiplier=2.0)
    closes = _flat(20, base=100.0)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_bollinger_default_parameters():
    strategy = BollingerBandsStrategy()
    assert strategy.period == 20
    assert strategy.std_dev_multiplier == 2.0


def test_compute_bollinger_bands_flat_series():
    """Flat series → std=0, upper=lower=mean."""
    upper, middle, lower = _compute_bollinger_bands(_flat(20), period=10, multiplier=2.0)
    assert middle == pytest.approx(100.0)
    assert upper == pytest.approx(100.0)
    assert lower == pytest.approx(100.0)


def test_compute_bollinger_bands_spread():
    """Bands should be symmetric around the mean."""
    import random
    random.seed(42)
    closes = [100.0 + random.gauss(0, 5) for _ in range(30)]
    upper, middle, lower = _compute_bollinger_bands(closes, period=20, multiplier=2.0)
    assert upper > middle > lower
    assert upper - middle == pytest.approx(middle - lower, rel=1e-6)


def test_bollinger_reason_includes_price_and_band():
    """Signal reason should reference the band and price."""
    strategy = BollingerBandsStrategy(period=10, std_dev_multiplier=2.0)
    base = _flat(15, base=100.0)
    closes = _spike_down(base, spike=50.0)
    result = strategy.analyze(closes)
    assert "lower" in result.reason.lower() or "band" in result.reason.lower()


def test_bollinger_confidence_between_0_and_1():
    """Confidence must be in [0, 1] for any series."""
    strategy = BollingerBandsStrategy(period=10, std_dev_multiplier=2.0)
    base = _flat(15, base=100.0)
    for closes in [
        _flat(20),
        _spike_down(base, 50.0),
        _spike_up(base, 50.0),
    ]:
        result = strategy.analyze(closes)
        assert 0.0 <= result.confidence <= 1.0
