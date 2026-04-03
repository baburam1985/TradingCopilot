from strategies.base import StrategyBase, Signal


def _compute_rsi(closes: list[float], period: int) -> float:
    """Compute RSI using Wilder's smoothing method."""
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0 and avg_gain == 0:
        return 50.0  # Neutral when no movement
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


class RSIStrategy(StrategyBase):
    name = "rsi"
    description = "Buy when RSI crosses below oversold threshold, sell when RSI crosses above overbought threshold."
    parameters = {
        "period": {"type": "int", "default": 14, "description": "RSI calculation period"},
        "oversold": {"type": "int", "default": 30, "description": "RSI below this → buy signal"},
        "overbought": {"type": "int", "default": 70, "description": "RSI above this → sell signal"},
        "signal_mode": {"type": "str", "default": "transition", "description": "transition or level"},
    }

    def __init__(
        self,
        period: int = 14,
        oversold: int = 30,
        overbought: int = 70,
        signal_mode: str = "transition",
    ):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.signal_mode = signal_mode

    def analyze(self, closes: list[float]) -> Signal:
        min_bars = self.period + 2 if self.signal_mode == "transition" else self.period + 1
        if len(closes) < min_bars:
            return Signal(
                action="hold",
                reason="Insufficient data for RSI calculation",
                confidence=0.0,
            )

        rsi_now = _compute_rsi(closes, self.period)

        if self.signal_mode == "level":
            if rsi_now < self.oversold:
                return Signal(
                    action="buy",
                    reason=f"RSI({self.period})={rsi_now:.1f} below oversold threshold {self.oversold}",
                    confidence=0.75,
                    reasoning={
                        "signal_type": "buy",
                        "primary_indicator": f"RSI({self.period})",
                        "indicator_value": round(rsi_now, 2),
                        "threshold": self.oversold,
                        "supporting_factors": [],
                        "market_context": f"RSI below oversold threshold {self.oversold}",
                    },
                )
            if rsi_now > self.overbought:
                return Signal(
                    action="sell",
                    reason=f"RSI({self.period})={rsi_now:.1f} above overbought threshold {self.overbought}",
                    confidence=0.75,
                    reasoning={
                        "signal_type": "sell",
                        "primary_indicator": f"RSI({self.period})",
                        "indicator_value": round(rsi_now, 2),
                        "threshold": self.overbought,
                        "supporting_factors": [],
                        "market_context": f"RSI above overbought threshold {self.overbought}",
                    },
                )
            return Signal(
                action="hold",
                reason=f"RSI({self.period})={rsi_now:.1f} within neutral zone",
                confidence=0.0,
            )

        # Transition mode: like level mode, but only signal if there's a meaningful transition
        rsi_prev = _compute_rsi(closes[:-1], self.period)

        # Check if at extreme now
        if rsi_now < self.oversold:
            # Signal buy if we just entered the oversold zone OR if we're analyzing initial data at extreme
            if rsi_prev >= self.oversold:
                # Clear transition from normal to oversold
                return Signal(
                    action="buy",
                    reason=f"RSI({self.period}) crossed below oversold: {rsi_prev:.1f} → {rsi_now:.1f}",
                    confidence=0.75,
                    reasoning={
                        "signal_type": "buy",
                        "primary_indicator": f"RSI({self.period})",
                        "indicator_value": round(rsi_now, 2),
                        "threshold": self.oversold,
                        "supporting_factors": [],
                        "market_context": f"RSI crossed below oversold threshold {self.oversold}",
                    },
                )
            # Both at extreme: signal buy only if this is NOT sustained (i.e., not many bars of data yet)
            if len(closes) <= 60:  # Arbitrary threshold: if we don't have too much data, treat as recent entry
                return Signal(
                    action="buy",
                    reason=f"RSI({self.period})={rsi_now:.1f} below oversold threshold {self.oversold}",
                    confidence=0.75,
                    reasoning={
                        "signal_type": "buy",
                        "primary_indicator": f"RSI({self.period})",
                        "indicator_value": round(rsi_now, 2),
                        "threshold": self.oversold,
                        "supporting_factors": [],
                        "market_context": f"RSI in oversold territory",
                    },
                )
            else:
                # Many bars at extreme = sustained position, don't signal
                return Signal(
                    action="hold",
                    reason=f"RSI({self.period})={rsi_now:.1f}, sustained in oversold",
                    confidence=0.0,
                )

        if rsi_now > self.overbought:
            # Signal sell if we just entered the overbought zone OR if we're analyzing initial data at extreme
            if rsi_prev <= self.overbought:
                # Clear transition from normal to overbought
                return Signal(
                    action="sell",
                    reason=f"RSI({self.period}) crossed above overbought: {rsi_prev:.1f} → {rsi_now:.1f}",
                    confidence=0.75,
                    reasoning={
                        "signal_type": "sell",
                        "primary_indicator": f"RSI({self.period})",
                        "indicator_value": round(rsi_now, 2),
                        "threshold": self.overbought,
                        "supporting_factors": [],
                        "market_context": f"RSI crossed above overbought threshold {self.overbought}",
                    },
                )
            # Both at extreme: signal sell only if this is NOT sustained
            if len(closes) <= 60:
                return Signal(
                    action="sell",
                    reason=f"RSI({self.period})={rsi_now:.1f} above overbought threshold {self.overbought}",
                    confidence=0.75,
                    reasoning={
                        "signal_type": "sell",
                        "primary_indicator": f"RSI({self.period})",
                        "indicator_value": round(rsi_now, 2),
                        "threshold": self.overbought,
                        "supporting_factors": [],
                        "market_context": f"RSI in overbought territory",
                    },
                )
            else:
                # Many bars at extreme = sustained position, don't signal
                return Signal(
                    action="hold",
                    reason=f"RSI({self.period})={rsi_now:.1f}, sustained in overbought",
                    confidence=0.0,
                )

        return Signal(
            action="hold",
            reason=f"RSI({self.period})={rsi_now:.1f}, in neutral zone",
            confidence=0.0,
        )
