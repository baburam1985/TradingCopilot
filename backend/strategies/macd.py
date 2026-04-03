from strategies.base import StrategyBase, Signal


def _compute_ema(prices: list[float], period: int) -> float:
    """Compute EMA of a price series, returning the final value."""
    if not prices:
        return 0.0
    k = 2.0 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def _compute_macd(
    closes: list[float], fast: int, slow: int, signal: int
) -> tuple[float, float]:
    """Compute current MACD line and signal line values."""
    # Compute EMA series for MACD line (fast EMA - slow EMA)
    k_fast = 2.0 / (fast + 1)
    k_slow = 2.0 / (slow + 1)

    ema_fast = closes[0]
    ema_slow = closes[0]
    for price in closes[1:]:
        ema_fast = price * k_fast + ema_fast * (1 - k_fast)
        ema_slow = price * k_slow + ema_slow * (1 - k_slow)

    # Build MACD line history from the slow period onward for signal EMA
    # We need enough bars to compute signal EMA from MACD values
    # Compute MACD value at each bar starting from index slow-1
    k_signal = 2.0 / (signal + 1)
    macd_values = []
    ema_f = closes[0]
    ema_s = closes[0]
    for price in closes[1:]:
        ema_f = price * k_fast + ema_f * (1 - k_fast)
        ema_s = price * k_slow + ema_s * (1 - k_slow)
        macd_values.append(ema_f - ema_s)

    macd_line = ema_fast - ema_slow

    # Signal line is EMA of MACD values
    if not macd_values:
        return macd_line, 0.0

    sig = macd_values[0]
    for m in macd_values[1:]:
        sig = m * k_signal + sig * (1 - k_signal)

    return macd_line, sig


class MACDStrategy(StrategyBase):
    name = "macd"
    description = (
        "Buy when MACD line crosses above the signal line (bullish), "
        "sell when MACD line crosses below the signal line (bearish)."
    )
    parameters = {
        "fast_period": {"type": "int", "default": 12, "description": "Fast EMA period"},
        "slow_period": {"type": "int", "default": 26, "description": "Slow EMA period"},
        "signal_period": {
            "type": "int",
            "default": 9,
            "description": "Signal line EMA period",
        },
    }

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def analyze(self, closes: list[float]) -> Signal:
        min_bars = self.slow_period + self.signal_period + 1
        if len(closes) < min_bars:
            return Signal(
                action="hold",
                reason=f"Insufficient data for MACD calculation (need {min_bars} bars, got {len(closes)})",
                confidence=0.0,
            )

        macd_now, signal_now = _compute_macd(
            closes, self.fast_period, self.slow_period, self.signal_period
        )
        macd_prev, signal_prev = _compute_macd(
            closes[:-1], self.fast_period, self.slow_period, self.signal_period
        )

        crossed_above = macd_prev <= signal_prev and macd_now > signal_now
        crossed_below = macd_prev >= signal_prev and macd_now < signal_now

        if crossed_above:
            return Signal(
                action="buy",
                reason=(
                    f"MACD bullish crossover: MACD({macd_now:.4f}) crossed above "
                    f"signal({signal_now:.4f})"
                ),
                confidence=0.7,
            )
        if crossed_below:
            return Signal(
                action="sell",
                reason=(
                    f"MACD bearish crossover: MACD({macd_now:.4f}) crossed below "
                    f"signal({signal_now:.4f})"
                ),
                confidence=0.7,
            )

        return Signal(
            action="hold",
            reason=f"No MACD crossover: MACD={macd_now:.4f}, signal={signal_now:.4f}",
            confidence=0.0,
        )
