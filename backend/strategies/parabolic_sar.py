from strategies.base import StrategyBase, Signal


def _compute_psar(
    closes: list[float],
    af_start: float,
    af_step: float,
    af_max: float,
) -> tuple[float, bool]:
    """
    Compute Parabolic SAR over a close-only price series.

    Because we only have closing prices, 'high' and 'low' are approximated
    by the close value itself.

    Returns:
        (sar_value, is_bullish) where is_bullish=True means price is above SAR.
    """
    if len(closes) < 3:
        return closes[-1], True

    # Initialise: first bar determines initial trend direction
    bullish = closes[1] >= closes[0]
    if bullish:
        sar = closes[0]
        ep = closes[1]  # extreme point
    else:
        sar = closes[0]
        ep = closes[1]

    af = af_start

    for i in range(2, len(closes)):
        price = closes[i]
        prev_price = closes[i - 1]

        if bullish:
            # Move SAR upward using parabolic formula
            sar = sar + af * (ep - sar)
            # SAR must not be above the two prior closes
            sar = min(sar, prev_price, closes[i - 2] if i >= 2 else prev_price)

            if price < sar:
                # Reversal: flip to bearish
                bullish = False
                sar = ep  # SAR becomes prior EP
                ep = price
                af = af_start
            else:
                if price > ep:
                    ep = price
                    af = min(af + af_step, af_max)
        else:
            # Bearish: SAR moves downward
            sar = sar + af * (ep - sar)
            # SAR must not be below the two prior closes
            sar = max(sar, prev_price, closes[i - 2] if i >= 2 else prev_price)

            if price > sar:
                # Reversal: flip to bullish
                bullish = True
                sar = ep
                ep = price
                af = af_start
            else:
                if price < ep:
                    ep = price
                    af = min(af + af_step, af_max)

    return sar, bullish


class ParabolicSARStrategy(StrategyBase):
    """
    Parabolic SAR (J. Welles Wilder, 1978).

    A trailing stop-and-reversal system. The SAR value accelerates toward
    the current price as a trend matures.

    Buy when price crosses above SAR (bullish flip).
    Sell when price crosses below SAR (bearish flip).
    """

    name = "parabolic_sar"
    description = (
        "Buy when price crosses above Parabolic SAR (bullish reversal); "
        "sell when price crosses below SAR (bearish reversal). "
        "Acceleration factor starts at 0.02 and increments to 0.20."
    )
    parameters = {
        "af_start": {
            "type": "float",
            "default": 0.02,
            "description": "Initial acceleration factor",
        },
        "af_step": {
            "type": "float",
            "default": 0.02,
            "description": "Acceleration factor step per new extreme",
        },
        "af_max": {
            "type": "float",
            "default": 0.20,
            "description": "Maximum acceleration factor",
        },
    }

    def __init__(
        self,
        af_start: float = 0.02,
        af_step: float = 0.02,
        af_max: float = 0.20,
    ):
        self.af_start = af_start
        self.af_step = af_step
        self.af_max = af_max

    def analyze(self, closes: list[float]) -> Signal:
        if len(closes) < 3:
            return Signal(
                action="hold",
                reason="Insufficient data for Parabolic SAR calculation (need ≥3 bars)",
                confidence=0.0,
            )

        sar_now, bullish_now = _compute_psar(
            closes, self.af_start, self.af_step, self.af_max
        )
        _, bullish_prev = _compute_psar(
            closes[:-1], self.af_start, self.af_step, self.af_max
        )

        price = closes[-1]

        # Bullish flip: was bearish last bar, now bullish (price crossed above SAR)
        if bullish_now and not bullish_prev:
            return Signal(
                action="buy",
                reason=(
                    f"Parabolic SAR bullish flip: price {price:.2f} crossed above "
                    f"SAR {sar_now:.2f}"
                ),
                confidence=0.7,
            )

        # Bearish flip: was bullish last bar, now bearish (price crossed below SAR)
        if not bullish_now and bullish_prev:
            return Signal(
                action="sell",
                reason=(
                    f"Parabolic SAR bearish flip: price {price:.2f} crossed below "
                    f"SAR {sar_now:.2f}"
                ),
                confidence=0.7,
            )

        return Signal(
            action="hold",
            reason=(
                f"Parabolic SAR: price {price:.2f}, SAR {sar_now:.2f} "
                f"({'bullish' if bullish_now else 'bearish'}, no flip)"
            ),
            confidence=0.0,
        )
