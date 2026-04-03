from strategies.base import StrategyBase, Signal


class TurtleStrategy(StrategyBase):
    """
    Turtle Trading System (Richard Dennis, 1983).

    Entry: price breaks above the highest close of the last entry_period bars.
    Exit:  price breaks below the lowest close of the last exit_period bars.

    Because the base interface provides only closing prices, highs/lows are
    approximated by channel extremes of the close series.
    """

    name = "turtle"
    description = (
        "Buy on 20-day channel breakout (price exceeds prior-period high); "
        "sell when price falls below 10-day channel low. "
        "Classic trend-following from the Turtle Trading experiment."
    )
    parameters = {
        "entry_period": {
            "type": "int",
            "default": 20,
            "description": "Look-back period for entry channel breakout",
        },
        "exit_period": {
            "type": "int",
            "default": 10,
            "description": "Look-back period for exit channel breakdown",
        },
    }

    def __init__(self, entry_period: int = 20, exit_period: int = 10):
        self.entry_period = entry_period
        self.exit_period = exit_period

    def analyze(self, closes: list[float]) -> Signal:
        min_bars = self.entry_period + 1
        if len(closes) < min_bars:
            return Signal(
                action="hold",
                reason=f"Insufficient data for Turtle strategy (need {min_bars} bars, got {len(closes)})",
                confidence=0.0,
            )

        current = closes[-1]

        # Entry channel: highest close of the previous entry_period bars (excluding current)
        entry_window = closes[-(self.entry_period + 1) : -1]
        channel_high = max(entry_window)

        # Exit channel: lowest close over the last exit_period bars (excluding current)
        exit_window_size = min(self.exit_period, len(closes) - 1)
        exit_window = closes[-exit_window_size - 1 : -1]
        channel_low = min(exit_window)

        if current > channel_high:
            return Signal(
                action="buy",
                reason=(
                    f"Turtle breakout: close {current:.2f} > {self.entry_period}-bar "
                    f"channel high {channel_high:.2f}"
                ),
                confidence=0.7,
            )

        if current < channel_low:
            return Signal(
                action="sell",
                reason=(
                    f"Turtle exit: close {current:.2f} < {self.exit_period}-bar "
                    f"channel low {channel_low:.2f}"
                ),
                confidence=0.7,
            )

        return Signal(
            action="hold",
            reason=(
                f"Turtle: close {current:.2f} within channel "
                f"[{channel_low:.2f}, {channel_high:.2f}]"
            ),
            confidence=0.0,
        )
