from strategies.base import StrategyBase, Signal


def _compute_adx(
    closes: list[float], period: int
) -> tuple[float, float, float]:
    """
    Compute ADX, DI+, and DI− from a close-only price series.

    Since we have no separate high/low data, directional movement is
    approximated using consecutive close differences:
      +DM approximation: max(close - prev_close, 0)
      -DM approximation: max(prev_close - close, 0)
      TR approximation:  abs(close - prev_close)

    Returns:
        (adx, di_plus, di_minus) — values in [0, 100]
    """
    if len(closes) < period + 2:
        return 0.0, 0.0, 0.0

    # Build raw directional movement and true range series
    dm_plus_raw = []
    dm_minus_raw = []
    tr_raw = []

    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        dm_plus_raw.append(max(diff, 0.0))
        dm_minus_raw.append(max(-diff, 0.0))
        tr_raw.append(abs(diff))

    # Wilder smoothing (same as RSI's smoothing)
    def _wilder_smooth(values: list[float], n: int) -> list[float]:
        smoothed = [sum(values[:n]) / n]
        for v in values[n:]:
            smoothed.append((smoothed[-1] * (n - 1) + v) / n)
        return smoothed

    if len(tr_raw) < period:
        return 0.0, 0.0, 0.0

    tr_smooth = _wilder_smooth(tr_raw, period)
    dmp_smooth = _wilder_smooth(dm_plus_raw, period)
    dmm_smooth = _wilder_smooth(dm_minus_raw, period)

    # Compute DI+ and DI−
    di_plus_series = []
    di_minus_series = []
    dx_series = []

    for tr_s, dmp_s, dmm_s in zip(tr_smooth, dmp_smooth, dmm_smooth):
        if tr_s == 0:
            di_p = 0.0
            di_m = 0.0
        else:
            di_p = (dmp_s / tr_s) * 100.0
            di_m = (dmm_s / tr_s) * 100.0

        di_plus_series.append(di_p)
        di_minus_series.append(di_m)

        di_sum = di_p + di_m
        dx = (abs(di_p - di_m) / di_sum * 100.0) if di_sum > 0 else 0.0
        dx_series.append(dx)

    if len(dx_series) < period:
        return 0.0, di_plus_series[-1], di_minus_series[-1]

    # ADX = Wilder smoothed DX
    adx_series = _wilder_smooth(dx_series, period)

    return adx_series[-1], di_plus_series[-1], di_minus_series[-1]


class ADXStrategy(StrategyBase):
    """
    ADX / DMI (J. Welles Wilder, 1978).

    The Average Directional Index measures trend strength.
    DI+ and DI− measure directional bias.

    Only trades when ADX > adx_threshold (strong trend):
    - Buy when ADX > threshold AND DI+ > DI−
    - Sell when ADX > threshold AND DI− > DI+
    - Hold when ADX ≤ threshold (weak/no trend)
    """

    name = "adx"
    description = (
        "Buy when ADX > 25 and DI+ > DI− (strong uptrend); "
        "sell when ADX > 25 and DI− > DI+ (strong downtrend); "
        "hold when trend is weak (ADX ≤ 25)."
    )
    parameters = {
        "adx_period": {
            "type": "int",
            "default": 14,
            "description": "Period for ADX and DI smoothing (Wilder's method)",
        },
        "adx_threshold": {
            "type": "int",
            "default": 25,
            "description": "Minimum ADX value required to act on a DI signal",
        },
    }

    def __init__(self, adx_period: int = 14, adx_threshold: int = 25):
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def analyze(self, closes: list[float]) -> Signal:
        min_bars = self.adx_period * 2 + 2
        if len(closes) < min_bars:
            return Signal(
                action="hold",
                reason=(
                    f"Insufficient data for ADX calculation "
                    f"(need {min_bars} bars, got {len(closes)})"
                ),
                confidence=0.0,
            )

        adx, di_plus, di_minus = _compute_adx(closes, self.adx_period)

        if adx <= self.adx_threshold:
            return Signal(
                action="hold",
                reason=(
                    f"ADX({self.adx_period})={adx:.1f} ≤ {self.adx_threshold} "
                    f"(trend too weak to trade)"
                ),
                confidence=0.0,
            )

        if di_plus > di_minus:
            return Signal(
                action="buy",
                reason=(
                    f"ADX={adx:.1f} > {self.adx_threshold}, "
                    f"DI+={di_plus:.1f} > DI−={di_minus:.1f} (strong uptrend)"
                ),
                confidence=min(adx / 100.0, 0.9),
            )

        if di_minus > di_plus:
            return Signal(
                action="sell",
                reason=(
                    f"ADX={adx:.1f} > {self.adx_threshold}, "
                    f"DI−={di_minus:.1f} > DI+={di_plus:.1f} (strong downtrend)"
                ),
                confidence=min(adx / 100.0, 0.9),
            )

        return Signal(
            action="hold",
            reason=(
                f"ADX={adx:.1f} > {self.adx_threshold} but "
                f"DI+={di_plus:.1f} == DI−={di_minus:.1f} (no directional bias)"
            ),
            confidence=0.0,
        )
