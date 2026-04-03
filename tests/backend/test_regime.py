"""
Unit tests for backend/analysis/regime.py

8 tests covering:
  - regime classification × 4 (TRENDING_UP, TRENDING_DOWN, SIDEWAYS_HIGH_VOL, SIDEWAYS_LOW_VOL)
  - fitness scores × 3 (rsi sideways, macd trending, unknown strategy)
  - insufficient bars guard
"""

import math
import sys
import os

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import pytest
from analysis.regime import Bar, RegimeDetector, get_fitness, STRATEGIES


# ---------------------------------------------------------------------------
# Helpers to build synthetic bar sequences
# ---------------------------------------------------------------------------


def _trending_bars(n: int, start: float, step: float, noise: float = 0.05) -> list[Bar]:
    """
    Generate n bars with a clear directional trend (ADX > 25).
    Uses a consistent slope so +DM dominates for uptrend, -DM for downtrend.
    """
    bars = []
    price = start
    for i in range(n):
        price += step
        high = price + abs(step) * 0.6
        low = price - abs(step) * 0.2
        bars.append(Bar(high=high, low=low, close=price))
    return bars


def _sideways_bars(n: int, center: float, atr_range: float) -> list[Bar]:
    """
    Generate n bars oscillating around a center price (no trend direction).
    atr_range controls absolute daily range (high-low).
    """
    import math

    bars = []
    for i in range(n):
        # Sine wave so price returns to center repeatedly
        close = center + center * 0.005 * math.sin(i * 0.8)
        high = close + atr_range / 2
        low = close - atr_range / 2
        bars.append(Bar(high=high, low=low, close=close))
    return bars


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trending_up_detection():
    """Strong up-trend → TRENDING_UP."""
    bars = _trending_bars(60, start=100.0, step=0.5)
    result = RegimeDetector().detect(bars)
    assert result.regime == "TRENDING_UP"
    assert result.adx >= 25


def test_trending_down_detection():
    """Strong down-trend → TRENDING_DOWN."""
    bars = _trending_bars(60, start=200.0, step=-0.5)
    result = RegimeDetector().detect(bars)
    assert result.regime == "TRENDING_DOWN"
    assert result.adx >= 25


def test_sideways_high_vol():
    """
    Sideways market with large daily swings → SIDEWAYS_HIGH_VOL.
    atr_range > 2% of center ensures atr_pct > 2.0.
    """
    center = 100.0
    # 4% daily range → atr_pct well above 2%
    bars = _sideways_bars(60, center=center, atr_range=4.0)
    result = RegimeDetector().detect(bars)
    assert result.regime == "SIDEWAYS_HIGH_VOL"


def test_sideways_low_vol():
    """
    Sideways market with small daily swings → SIDEWAYS_LOW_VOL.
    atr_range < 2% of center ensures atr_pct ≤ 2.0.
    """
    center = 100.0
    # 0.5% daily range → atr_pct well below 2%
    bars = _sideways_bars(60, center=center, atr_range=0.5)
    result = RegimeDetector().detect(bars)
    assert result.regime == "SIDEWAYS_LOW_VOL"


def test_fitness_rsi_sideways():
    """RSI in SIDEWAYS_LOW_VOL → score 90."""
    score = get_fitness("rsi", "SIDEWAYS_LOW_VOL")
    assert score == 90


def test_fitness_macd_trending():
    """MACD in TRENDING_UP → score 85."""
    score = get_fitness("macd", "TRENDING_UP")
    assert score == 85


def test_fitness_unknown_strategy():
    """Unknown strategy → neutral default 50."""
    score = get_fitness("some_unknown_strategy_xyz", "TRENDING_UP")
    assert score == 50


def test_insufficient_bars():
    """Fewer than MIN_BARS raises ValueError."""
    detector = RegimeDetector()
    bars = _sideways_bars(detector.MIN_BARS - 1, center=100.0, atr_range=1.0)
    with pytest.raises(ValueError, match="bars required"):
        detector.detect(bars)


def test_all_strategies_covered():
    """Every known strategy has an entry for every regime in FITNESS_MAP."""
    from analysis.regime import FITNESS_MAP, STRATEGIES, REGIMES

    for strategy in STRATEGIES:
        for regime in REGIMES:
            assert (strategy, regime) in FITNESS_MAP, (
                f"Missing FITNESS_MAP entry: ({strategy!r}, {regime!r})"
            )


def test_confidence_capped():
    """Confidence should never exceed 100."""
    bars = _trending_bars(60, start=100.0, step=1.0)
    result = RegimeDetector().detect(bars)
    assert result.confidence <= 100.0


def test_result_has_all_strategies():
    """detect() result contains fitness scores for all 7 known strategies."""
    bars = _sideways_bars(60, center=100.0, atr_range=1.0)
    result = RegimeDetector().detect(bars)
    for strategy in STRATEGIES:
        assert strategy in result.fitness_scores
