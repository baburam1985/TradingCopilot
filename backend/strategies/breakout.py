from strategies.base import StrategyBase, Signal


class BreakoutStrategy(StrategyBase):
    name = "breakout"
    description = (
        "Buy on N-day high breakout; sell on N-day low breakdown. "
        "Channel computed from prior N bars (no current bar lookahead)."
    )
    parameters = {
        "period": {
            "type": "int",
            "default": 20,
            "description": "Number of prior bars used to define the breakout channel",
        },
    }

    def __init__(self, period: int = 20):
        self.period = period

    def analyze(self, closes: list[float]) -> Signal:
        if len(closes) < self.period + 1:
            return Signal(
                action="hold",
                reason=(
                    f"Insufficient data for breakout calculation "
                    f"(need {self.period + 1} bars, got {len(closes)})"
                ),
                confidence=0.0,
            )

        # Channel is computed from the N bars BEFORE the current bar
        channel = closes[-(self.period + 1):-1]
        channel_high = max(channel)
        channel_low = min(channel)
        price = closes[-1]

        if price > channel_high:
            return Signal(
                action="buy",
                reason=(
                    f"Breakout: price ({price:.2f}) above {self.period}-bar high ({channel_high:.2f})"
                ),
                confidence=0.7,
            )
        if price < channel_low:
            return Signal(
                action="sell",
                reason=(
                    f"Breakdown: price ({price:.2f}) below {self.period}-bar low ({channel_low:.2f})"
                ),
                confidence=0.7,
            )
        return Signal(
            action="hold",
            reason=(
                f"Price ({price:.2f}) within channel [{channel_low:.2f}, {channel_high:.2f}]"
            ),
            confidence=0.0,
        )
