import pytest
from strategies.vwap import VWAPStrategy, _compute_vwap


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def _uniform_volumes(n: int, vol: int = 1000) -> list[int]:
    return [vol] * n


def test_vwap_insufficient_data_returns_hold():
    strategy = VWAPStrategy()
    result = strategy.analyze([100.0])
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_vwap_buy_when_price_below_vwap():
    """Price crossing below VWAP → buy (mean-reversion upward)."""
    strategy = VWAPStrategy()
    # VWAP is a volume-weighted average; higher-volume bars at higher prices
    # make VWAP high, current price is low → buy
    closes = [110.0, 110.0, 110.0, 110.0, 110.0, 90.0]
    volumes = [10000, 10000, 10000, 10000, 10000, 100]
    result = strategy.analyze(closes, volumes=volumes)
    assert result.action == "buy"


def test_vwap_sell_when_price_above_vwap():
    """Price crossing above VWAP → sell (mean-reversion downward)."""
    strategy = VWAPStrategy()
    closes = [90.0, 90.0, 90.0, 90.0, 90.0, 110.0]
    volumes = [10000, 10000, 10000, 10000, 10000, 100]
    result = strategy.analyze(closes, volumes=volumes)
    assert result.action == "sell"


def test_vwap_hold_when_price_near_vwap():
    """Price at VWAP → hold."""
    strategy = VWAPStrategy()
    closes = _flat(10, base=100.0)
    volumes = _uniform_volumes(10)
    result = strategy.analyze(closes, volumes=volumes)
    assert result.action == "hold"


def test_vwap_without_volumes_uses_uniform_weights():
    """Without volume data, VWAP degrades to simple moving average."""
    strategy = VWAPStrategy()
    closes = _flat(10, base=100.0)
    # No volumes → uniform → SMA = 100 = price → hold
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_vwap_default_parameters():
    strategy = VWAPStrategy()
    assert strategy.period == 20


def test_compute_vwap_uniform_volumes_equals_average():
    """With equal volumes, VWAP = simple average."""
    closes = [90.0, 100.0, 110.0]
    volumes = [1000, 1000, 1000]
    vwap = _compute_vwap(closes, volumes)
    assert vwap == pytest.approx(100.0)


def test_compute_vwap_weighted_toward_high_volume():
    """VWAP should weight toward bars with higher volume."""
    closes = [80.0, 120.0]
    volumes = [100, 1000]  # 120 has 10x more volume
    vwap = _compute_vwap(closes, volumes)
    # Weighted: (80*100 + 120*1000) / 1100 = (8000 + 120000) / 1100 ≈ 116.36
    assert vwap == pytest.approx((80 * 100 + 120 * 1000) / 1100, rel=1e-6)
    assert vwap > 100.0  # VWAP should be closer to 120


def test_vwap_reason_includes_price_and_vwap():
    """Signal reason should reference price and VWAP values."""
    strategy = VWAPStrategy()
    closes = [110.0, 110.0, 110.0, 110.0, 110.0, 90.0]
    volumes = [10000, 10000, 10000, 10000, 10000, 100]
    result = strategy.analyze(closes, volumes=volumes)
    assert "VWAP" in result.reason


def test_vwap_confidence_between_0_and_1():
    """Confidence must be in [0, 1]."""
    strategy = VWAPStrategy()
    for closes, vols in [
        (_flat(10), _uniform_volumes(10)),
        ([110.0] * 5 + [90.0], [10000] * 5 + [100]),
        ([90.0] * 5 + [110.0], [10000] * 5 + [100]),
    ]:
        result = strategy.analyze(closes, volumes=vols)
        assert 0.0 <= result.confidence <= 1.0
