"""
Market Regime Detection + Strategy Fitness Score.

Inputs: at least 15 daily OHLCV bars (60 preferred).
Outputs:
  - regime: TRENDING_UP | TRENDING_DOWN | SIDEWAYS_HIGH_VOL | SIDEWAYS_LOW_VOL
  - adx, atr_pct, confidence
  - fitness_scores: dict[strategy_name, int 0-100]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


# ---------------------------------------------------------------------------
# Static fitness map: (strategy, regime) -> score 0-100
# ---------------------------------------------------------------------------

STRATEGIES = [
    "rsi",
    "macd",
    "moving_average_crossover",
    "bollinger_bands",
    "breakout",
    "mean_reversion",
    "vwap",
]

REGIMES = [
    "TRENDING_UP",
    "TRENDING_DOWN",
    "SIDEWAYS_HIGH_VOL",
    "SIDEWAYS_LOW_VOL",
]

FITNESS_MAP: dict[tuple[str, str], int] = {
    ("rsi", "TRENDING_UP"): 35,
    ("rsi", "TRENDING_DOWN"): 35,
    ("rsi", "SIDEWAYS_HIGH_VOL"): 85,
    ("rsi", "SIDEWAYS_LOW_VOL"): 90,
    ("macd", "TRENDING_UP"): 85,
    ("macd", "TRENDING_DOWN"): 80,
    ("macd", "SIDEWAYS_HIGH_VOL"): 30,
    ("macd", "SIDEWAYS_LOW_VOL"): 25,
    ("moving_average_crossover", "TRENDING_UP"): 88,
    ("moving_average_crossover", "TRENDING_DOWN"): 82,
    ("moving_average_crossover", "SIDEWAYS_HIGH_VOL"): 28,
    ("moving_average_crossover", "SIDEWAYS_LOW_VOL"): 20,
    ("bollinger_bands", "TRENDING_UP"): 50,
    ("bollinger_bands", "TRENDING_DOWN"): 50,
    ("bollinger_bands", "SIDEWAYS_HIGH_VOL"): 80,
    ("bollinger_bands", "SIDEWAYS_LOW_VOL"): 70,
    ("breakout", "TRENDING_UP"): 82,
    ("breakout", "TRENDING_DOWN"): 78,
    ("breakout", "SIDEWAYS_HIGH_VOL"): 40,
    ("breakout", "SIDEWAYS_LOW_VOL"): 25,
    ("mean_reversion", "TRENDING_UP"): 30,
    ("mean_reversion", "TRENDING_DOWN"): 30,
    ("mean_reversion", "SIDEWAYS_HIGH_VOL"): 88,
    ("mean_reversion", "SIDEWAYS_LOW_VOL"): 82,
    ("vwap", "TRENDING_UP"): 75,
    ("vwap", "TRENDING_DOWN"): 72,
    ("vwap", "SIDEWAYS_HIGH_VOL"): 55,
    ("vwap", "SIDEWAYS_LOW_VOL"): 50,
}


def get_fitness(strategy: str, regime: str) -> int:
    """Return fitness score 0-100. Unknown strategies get neutral 50."""
    return FITNESS_MAP.get((strategy, regime), 50)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Bar:
    high: float
    low: float
    close: float


@dataclass
class RegimeResult:
    regime: str
    adx: float
    atr_pct: float
    confidence: float
    fitness_scores: dict[str, int]


# ---------------------------------------------------------------------------
# Core detector
# ---------------------------------------------------------------------------


class RegimeDetector:
    """
    Detects market regime from OHLCV bars.

    Parameters
    ----------
    period : int
        ADX / ATR period (default 14).
    ma_period : int
        Moving-average period for direction (default 20).
    """

    MIN_BARS = 15

    def __init__(self, period: int = 14, ma_period: int = 20) -> None:
        self.period = period
        self.ma_period = ma_period

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, bars: Sequence[Bar]) -> RegimeResult:
        """
        Detect regime from a sequence of Bar objects.

        Raises ValueError if fewer than MIN_BARS bars are provided.
        """
        if len(bars) < self.MIN_BARS:
            raise ValueError(
                f"At least {self.MIN_BARS} bars required; got {len(bars)}."
            )

        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]

        adx, atr = self._compute_adx_atr(highs, lows, closes)
        atr_pct = (atr / closes[-1] * 100) if closes[-1] != 0 else 0.0

        # Direction: price vs 20-day MA
        ma_period = min(self.ma_period, len(closes))
        ma20 = sum(closes[-ma_period:]) / ma_period
        direction = "up" if closes[-1] > ma20 else "down"

        regime = self._classify(adx, atr_pct, direction)
        confidence = min(100.0, adx * 2)

        fitness_scores = {s: get_fitness(s, regime) for s in STRATEGIES}

        return RegimeResult(
            regime=regime,
            adx=round(adx, 2),
            atr_pct=round(atr_pct, 2),
            confidence=round(confidence, 2),
            fitness_scores=fitness_scores,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_adx_atr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> tuple[float, float]:
        """Return (adx, atr_14_last) computed over the provided series."""
        n = len(closes)
        period = self.period

        # True Range
        tr_values: list[float] = []
        pdm_values: list[float] = []
        ndm_values: list[float] = []

        for i in range(1, n):
            prev_close = closes[i - 1]
            prev_high = highs[i - 1]
            prev_low = lows[i - 1]

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - prev_close),
                abs(lows[i] - prev_close),
            )
            tr_values.append(tr)

            up_move = highs[i] - prev_high
            down_move = prev_low - lows[i]

            pdm = up_move if (up_move > down_move and up_move > 0) else 0.0
            ndm = down_move if (down_move > up_move and down_move > 0) else 0.0
            pdm_values.append(pdm)
            ndm_values.append(ndm)

        if not tr_values:
            return 0.0, 0.0

        # Wilder smoothing (EMA with alpha=1/period)
        def wilder_smooth(values: list[float]) -> list[float]:
            if len(values) < period:
                # Not enough bars: use simple mean for first value
                smoothed = [sum(values) / len(values)]
                alpha = 1.0 / max(1, period)
            else:
                smoothed = [sum(values[:period]) / period]
                alpha = 1.0 / period

            for v in values[period:]:
                smoothed.append(smoothed[-1] * (1 - alpha) + v * alpha)
            return smoothed

        atr_s = wilder_smooth(tr_values)
        pdm_s = wilder_smooth(pdm_values)
        ndm_s = wilder_smooth(ndm_values)

        atr_last = atr_s[-1]

        # +DI / -DI / DX / ADX
        dx_values: list[float] = []
        for atr_v, pdm_v, ndm_v in zip(atr_s, pdm_s, ndm_s):
            if atr_v == 0:
                dx_values.append(0.0)
                continue
            pdi = 100.0 * pdm_v / atr_v
            ndi = 100.0 * ndm_v / atr_v
            denom = pdi + ndi
            dx = (100.0 * abs(pdi - ndi) / denom) if denom != 0 else 0.0
            dx_values.append(dx)

        # ADX = Wilder smooth of DX
        adx_s = wilder_smooth(dx_values)
        adx_last = adx_s[-1]

        return adx_last, atr_last

    @staticmethod
    def _classify(adx: float, atr_pct: float, direction: str) -> str:
        if adx >= 25:
            return "TRENDING_UP" if direction == "up" else "TRENDING_DOWN"
        # Sideways: split on volatility
        return "SIDEWAYS_HIGH_VOL" if atr_pct > 2.0 else "SIDEWAYS_LOW_VOL"
