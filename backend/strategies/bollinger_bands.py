import math
from strategies.base import StrategyBase, Signal


def _compute_bollinger_bands(
    closes: list[float], period: int, multiplier: float
) -> tuple[float, float, float]:
    """Return (upper, middle, lower) Bollinger Bands using the last `period` closes."""
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((p - middle) ** 2 for p in window) / period
    std = math.sqrt(variance)
    upper = middle + multiplier * std
    lower = middle - multiplier * std
    return upper, middle, lower


class BollingerBandsStrategy(StrategyBase):
    name = "bollinger_bands"
    description = (
        "Mean-reversion strategy: buy when price touches or crosses below the lower "
        "Bollinger Band, sell when price touches or crosses above the upper band."
    )
    parameters = {
        "period": {
            "type": "int",
            "default": 20,
            "description": "Rolling window for band calculation",
        },
        "std_dev_multiplier": {
            "type": "float",
            "default": 2.0,
            "description": "Number of standard deviations for band width",
        },
    }

    def __init__(self, period: int = 20, std_dev_multiplier: float = 2.0):
        self.period = period
        self.std_dev_multiplier = std_dev_multiplier

    def analyze(self, closes: list[float]) -> Signal:
        if len(closes) < self.period:
            return Signal(
                action="hold",
                reason=(
                    f"Insufficient data for Bollinger Bands "
                    f"(need {self.period} bars, got {len(closes)})"
                ),
                confidence=0.0,
            )

        upper, middle, lower = _compute_bollinger_bands(
            closes, self.period, self.std_dev_multiplier
        )
        price = closes[-1]

        # Zero bandwidth (flat series) → no meaningful signal
        if upper == lower:
            return Signal(
                action="hold",
                reason=f"Bollinger Bands have zero width (price={price:.2f}, mean={middle:.2f})",
                confidence=0.0,
            )

        if price <= lower:
            return Signal(
                action="buy",
                reason=(
                    f"Price ({price:.2f}) at/below lower Bollinger Band ({lower:.2f}); "
                    f"mean={middle:.2f}"
                ),
                confidence=0.7,
                reasoning={
                    "signal_type": "buy",
                    "primary_indicator": "Bollinger Bands",
                    "indicator_value": round(price, 2),
                    "threshold": round(lower, 2),
                    "supporting_factors": [f"middle band={round(middle, 2)}"],
                    "market_context": f"Price touched/crossed below lower Bollinger Band ({round(lower, 2)})",
                },
            )
        if price >= upper:
            return Signal(
                action="sell",
                reason=(
                    f"Price ({price:.2f}) at/above upper Bollinger Band ({upper:.2f}); "
                    f"mean={middle:.2f}"
                ),
                confidence=0.7,
                reasoning={
                    "signal_type": "sell",
                    "primary_indicator": "Bollinger Bands",
                    "indicator_value": round(price, 2),
                    "threshold": round(upper, 2),
                    "supporting_factors": [f"middle band={round(middle, 2)}"],
                    "market_context": f"Price touched/crossed above upper Bollinger Band ({round(upper, 2)})",
                },
            )

        return Signal(
            action="hold",
            reason=(
                f"Price ({price:.2f}) within bands [{lower:.2f}, {upper:.2f}]; "
                f"mean={middle:.2f}"
            ),
            confidence=0.0,
        )
