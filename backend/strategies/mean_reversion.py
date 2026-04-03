import math
from strategies.base import StrategyBase, Signal


def _compute_zscore(closes: list[float], lookback: int) -> float:
    """Return z-score of the last price relative to the lookback window."""
    window = closes[-lookback:]
    mean = sum(window) / len(window)
    variance = sum((p - mean) ** 2 for p in window) / len(window)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (closes[-1] - mean) / std


class MeanReversionStrategy(StrategyBase):
    name = "mean_reversion"
    description = (
        "Statistical mean-reversion: buy when price falls significantly below its "
        "recent mean (low z-score), sell when it rises significantly above (high z-score)."
    )
    parameters = {
        "lookback": {
            "type": "int",
            "default": 20,
            "description": "Lookback window for mean and std calculation",
        },
        "entry_zscore": {
            "type": "float",
            "default": 2.0,
            "description": "Z-score magnitude threshold to trigger entry signal",
        },
        "exit_zscore": {
            "type": "float",
            "default": 0.5,
            "description": "Z-score magnitude threshold to trigger exit (not yet wired)",
        },
    }

    def __init__(self, lookback: int = 20, entry_zscore: float = 2.0, exit_zscore: float = 0.5):
        self.lookback = lookback
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore

    def analyze(self, closes: list[float]) -> Signal:
        if len(closes) < self.lookback:
            return Signal(
                action="hold",
                reason=(
                    f"Insufficient data for mean reversion "
                    f"(need {self.lookback} bars, got {len(closes)})"
                ),
                confidence=0.0,
            )

        z = _compute_zscore(closes, self.lookback)

        if z == 0.0:
            return Signal(
                action="hold",
                reason="Z-score undefined (zero std dev) — flat series, no signal",
                confidence=0.0,
            )

        if z <= -self.entry_zscore:
            return Signal(
                action="buy",
                reason=f"Z-score ({z:.2f}) below -{self.entry_zscore:.1f} — price far below mean",
                confidence=min(abs(z) / (self.entry_zscore * 2), 1.0),
                reasoning={
                    "signal_type": "buy",
                    "primary_indicator": "Mean Reversion",
                    "indicator_value": round(z, 2),
                    "threshold": -self.entry_zscore,
                    "supporting_factors": [],
                    "market_context": f"Z-score ({round(z, 2)}) below -{self.entry_zscore} — price significantly below mean",
                },
            )
        if z >= self.entry_zscore:
            return Signal(
                action="sell",
                reason=f"Z-score ({z:.2f}) above +{self.entry_zscore:.1f} — price far above mean",
                confidence=min(abs(z) / (self.entry_zscore * 2), 1.0),
                reasoning={
                    "signal_type": "sell",
                    "primary_indicator": "Mean Reversion",
                    "indicator_value": round(z, 2),
                    "threshold": self.entry_zscore,
                    "supporting_factors": [],
                    "market_context": f"Z-score ({round(z, 2)}) above +{self.entry_zscore} — price significantly above mean",
                },
            )
        return Signal(
            action="hold",
            reason=f"Z-score ({z:.2f}) within neutral zone ±{self.entry_zscore:.1f}",
            confidence=0.0,
        )
