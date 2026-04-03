from strategies.base import StrategyBase, Signal


def _compute_stochastic_k(closes: list[float], period: int) -> float:
    """Compute raw %K = (close - period_low) / (period_high - period_low) * 100."""
    window = closes[-period:]
    lo = min(window)
    hi = max(window)
    if hi == lo:
        return 50.0  # no range — neutral
    return (closes[-1] - lo) / (hi - lo) * 100.0


def _compute_k_series(closes: list[float], period: int) -> list[float]:
    """Compute %K for each bar starting at index period-1."""
    result = []
    for i in range(period - 1, len(closes)):
        result.append(_compute_stochastic_k(closes[: i + 1], period))
    return result


def _compute_d(k_series: list[float], d_period: int) -> float:
    """Compute %D as SMA of the last d_period %K values."""
    return sum(k_series[-d_period:]) / d_period


class StochasticStrategy(StrategyBase):
    """
    Stochastic Oscillator (George Lane, 1950s).

    %K = (close - period_low) / (period_high - period_low) * 100
    %D = SMA of %K over d_period bars

    Buy when %K crosses up through the oversold threshold.
    Sell when %K crosses down through the overbought threshold.
    """

    name = "stochastic"
    description = (
        "Buy when Stochastic %K crosses up from oversold (<20); "
        "sell when %K crosses down from overbought (>80)."
    )
    parameters = {
        "k_period": {
            "type": "int",
            "default": 14,
            "description": "Look-back period for raw %K calculation",
        },
        "d_period": {
            "type": "int",
            "default": 3,
            "description": "Smoothing period for %D signal line",
        },
        "oversold": {
            "type": "int",
            "default": 20,
            "description": "Stochastic below this level → oversold (buy zone)",
        },
        "overbought": {
            "type": "int",
            "default": 80,
            "description": "Stochastic above this level → overbought (sell zone)",
        },
    }

    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        oversold: int = 20,
        overbought: int = 80,
    ):
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought

    def analyze(self, closes: list[float]) -> Signal:
        min_bars = self.k_period + self.d_period
        if len(closes) < min_bars:
            return Signal(
                action="hold",
                reason=(
                    f"Insufficient data for Stochastic calculation "
                    f"(need {min_bars} bars, got {len(closes)})"
                ),
                confidence=0.0,
            )

        k_series = _compute_k_series(closes, self.k_period)

        if len(k_series) < self.d_period + 1:
            return Signal(
                action="hold",
                reason="Insufficient %K history for %D and crossover detection",
                confidence=0.0,
            )

        k_now = k_series[-1]
        k_prev = k_series[-2]

        # Buy: %K crosses up through oversold (was below, now above)
        if k_prev <= self.oversold and k_now > self.oversold:
            return Signal(
                action="buy",
                reason=(
                    f"Stochastic %K crossed up from oversold: "
                    f"{k_prev:.1f} → {k_now:.1f} (threshold={self.oversold})"
                ),
                confidence=0.7,
            )

        # Sell: %K crosses down through overbought (was above, now below)
        if k_prev >= self.overbought and k_now < self.overbought:
            return Signal(
                action="sell",
                reason=(
                    f"Stochastic %K crossed down from overbought: "
                    f"{k_prev:.1f} → {k_now:.1f} (threshold={self.overbought})"
                ),
                confidence=0.7,
            )

        return Signal(
            action="hold",
            reason=f"Stochastic %K={k_now:.1f}, no threshold crossing",
            confidence=0.0,
        )
