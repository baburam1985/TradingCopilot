import pytest
from strategies.mean_reversion import MeanReversionStrategy, _compute_zscore


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_mean_reversion_insufficient_data_returns_hold():
    strategy = MeanReversionStrategy(lookback=10)
    result = strategy.analyze(_flat(9))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_mean_reversion_buy_when_zscore_below_negative_threshold():
    """Z-score below -entry_zscore → price far below mean → buy."""
    strategy = MeanReversionStrategy(lookback=10, entry_zscore=2.0)
    # Flat base then a sharp drop → z-score well below -2
    closes = _flat(9, base=100.0) + [60.0]
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_mean_reversion_sell_when_zscore_above_positive_threshold():
    """Z-score above +entry_zscore → price far above mean → sell."""
    strategy = MeanReversionStrategy(lookback=10, entry_zscore=2.0)
    # Flat base then a sharp spike → z-score well above +2
    closes = _flat(9, base=100.0) + [140.0]
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_mean_reversion_hold_when_zscore_neutral():
    """Z-score within thresholds → hold."""
    strategy = MeanReversionStrategy(lookback=10, entry_zscore=2.0)
    closes = _flat(20)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_mean_reversion_hold_on_flat_series_zero_std():
    """Flat series → std=0, undefined z-score → hold (no signal)."""
    strategy = MeanReversionStrategy(lookback=5, entry_zscore=2.0)
    closes = _flat(10)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_mean_reversion_default_parameters():
    strategy = MeanReversionStrategy()
    assert strategy.lookback == 20
    assert strategy.entry_zscore == 2.0
    assert strategy.exit_zscore == 0.5


def test_compute_zscore_flat_series_returns_zero():
    """Flat series → mean == price, z-score = 0."""
    result = _compute_zscore(_flat(10), lookback=10)
    assert result == pytest.approx(0.0, abs=1e-9)


def test_compute_zscore_positive_for_high_price():
    """Price above mean → positive z-score."""
    closes = _flat(9, base=100.0) + [120.0]
    z = _compute_zscore(closes, lookback=10)
    assert z > 0


def test_compute_zscore_negative_for_low_price():
    """Price below mean → negative z-score."""
    closes = _flat(9, base=100.0) + [80.0]
    z = _compute_zscore(closes, lookback=10)
    assert z < 0


def test_mean_reversion_reason_includes_zscore():
    """Signal reason should reference the z-score."""
    strategy = MeanReversionStrategy(lookback=10, entry_zscore=2.0)
    closes = _flat(9, base=100.0) + [60.0]
    result = strategy.analyze(closes)
    assert "z" in result.reason.lower() or "zscore" in result.reason.lower() or "z-score" in result.reason.lower()


def test_mean_reversion_confidence_between_0_and_1():
    strategy = MeanReversionStrategy(lookback=10, entry_zscore=2.0)
    for closes in [
        _flat(20),
        _flat(9, base=100.0) + [60.0],
        _flat(9, base=100.0) + [140.0],
    ]:
        result = strategy.analyze(closes)
        assert 0.0 <= result.confidence <= 1.0
