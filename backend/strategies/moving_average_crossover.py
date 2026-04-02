from strategies.base import StrategyBase, Signal

class MovingAverageCrossover(StrategyBase):
    name = "moving_average_crossover"
    description = "Buy on golden cross (short MA crosses above long MA), sell on death cross."
    parameters = {
        "short_window": {"type": "int", "default": 50, "description": "Short moving average window"},
        "long_window": {"type": "int", "default": 200, "description": "Long moving average window"},
    }

    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window

    def analyze(self, closes: list[float]) -> Signal:
        if len(closes) < self.long_window + 1:
            return Signal(action="hold", reason="Insufficient data for MA calculation", confidence=0.0)

        def ma(prices, window):
            return sum(prices[-window:]) / window

        short_ma_now = ma(closes, self.short_window)
        long_ma_now = ma(closes, self.long_window)

        prev_closes = closes[:-1]
        short_ma_prev = ma(prev_closes, self.short_window)
        long_ma_prev = ma(prev_closes, self.long_window)

        crossed_above = short_ma_prev <= long_ma_prev and short_ma_now > long_ma_now
        crossed_below = short_ma_prev >= long_ma_prev and short_ma_now < long_ma_now

        if crossed_above:
            return Signal(
                action="buy",
                reason=f"Golden cross: {self.short_window}MA ({short_ma_now:.2f}) crossed above {self.long_window}MA ({long_ma_now:.2f})",
                confidence=0.7,
            )
        if crossed_below:
            return Signal(
                action="sell",
                reason=f"Death cross: {self.short_window}MA ({short_ma_now:.2f}) crossed below {self.long_window}MA ({long_ma_now:.2f})",
                confidence=0.7,
            )
        return Signal(action="hold", reason="No crossover detected", confidence=0.0)
