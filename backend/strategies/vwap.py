from typing import Optional
from strategies.base import StrategyBase, Signal


def _compute_vwap(closes: list[float], volumes: list[int | float]) -> float:
    """Return Volume-Weighted Average Price over the given series."""
    total_vol = sum(volumes)
    if total_vol == 0:
        return sum(closes) / len(closes)
    return sum(p * v for p, v in zip(closes, volumes)) / total_vol


class VWAPStrategy(StrategyBase):
    name = "vwap"
    description = (
        "Mean-reversion strategy: buy when price falls below VWAP, "
        "sell when price rises above VWAP."
    )
    parameters = {
        "period": {
            "type": "int",
            "default": 20,
            "description": "Lookback window for VWAP calculation",
        },
    }

    def __init__(self, period: int = 20):
        self.period = period

    def analyze(
        self,
        closes: list[float],
        volumes: Optional[list[int | float]] = None,
    ) -> Signal:
        if len(closes) < 2:
            return Signal(
                action="hold",
                reason="Insufficient data for VWAP calculation",
                confidence=0.0,
            )

        window_closes = closes[-self.period:]
        if volumes is not None:
            window_volumes = volumes[-self.period:]
        else:
            window_volumes = [1] * len(window_closes)

        vwap = _compute_vwap(window_closes, window_volumes)
        price = closes[-1]

        if price < vwap:
            return Signal(
                action="buy",
                reason=f"Price ({price:.2f}) below VWAP ({vwap:.2f})",
                confidence=0.65,
                reasoning={
                    "signal_type": "buy",
                    "primary_indicator": "VWAP",
                    "indicator_value": round(vwap, 2),
                    "threshold": round(vwap, 2),
                    "supporting_factors": [f"current price={round(price, 2)}"],
                    "market_context": f"Price ({round(price, 2)}) is below VWAP ({round(vwap, 2)})",
                },
            )
        if price > vwap:
            return Signal(
                action="sell",
                reason=f"Price ({price:.2f}) above VWAP ({vwap:.2f})",
                confidence=0.65,
                reasoning={
                    "signal_type": "sell",
                    "primary_indicator": "VWAP",
                    "indicator_value": round(vwap, 2),
                    "threshold": round(vwap, 2),
                    "supporting_factors": [f"current price={round(price, 2)}"],
                    "market_context": f"Price ({round(price, 2)}) is above VWAP ({round(vwap, 2)})",
                },
            )
        return Signal(
            action="hold",
            reason=f"Price ({price:.2f}) at VWAP ({vwap:.2f})",
            confidence=0.0,
        )
