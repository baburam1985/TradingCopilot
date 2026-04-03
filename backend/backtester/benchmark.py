"""Buy-and-Hold Benchmark Calculator.

Computes what a simple buy-and-hold strategy would have returned over the
same bar series used for a backtest, so users can compare strategy alpha.
"""

import math

_MAX_EQUITY_CURVE_POINTS = 365  # downsample to weekly beyond this


class BenchmarkCalculator:
    """Stateless helper — all methods are static."""

    @staticmethod
    def compute(bars: list, starting_capital: float) -> dict:
        """Return buy-and-hold metrics for *bars*.

        Buys at the close of the first bar and sells at the close of the last
        bar.  Returns null fields when data is insufficient or degenerate.

        Args:
            bars: Sorted list of PriceHistory-like objects with `.close` and
                  `.timestamp` attributes.
            starting_capital: Notional capital to invest.

        Returns:
            dict with keys:
              - ``bnh_return_pct``   – percentage return (or None)
              - ``bnh_final_value``  – ending portfolio value (or None)
              - ``bnh_equity_curve`` – list of {"timestamp": str, "value": float}
        """
        if len(bars) < 2:
            return {
                "bnh_return_pct": None,
                "bnh_final_value": None,
                "bnh_equity_curve": [],
            }

        start_price = float(bars[0].close)
        if start_price == 0:
            return {
                "bnh_return_pct": None,
                "bnh_final_value": None,
                "bnh_equity_curve": [],
            }

        shares = starting_capital / start_price
        equity_curve = BenchmarkCalculator._build_equity_curve(bars, shares)

        final_value = equity_curve[-1]["value"] if equity_curve else None
        bnh_return_pct = (
            (final_value - starting_capital) / starting_capital * 100
            if final_value is not None
            else None
        )

        return {
            "bnh_return_pct": round(bnh_return_pct, 4) if bnh_return_pct is not None else None,
            "bnh_final_value": round(final_value, 4) if final_value is not None else None,
            "bnh_equity_curve": equity_curve,
        }

    @staticmethod
    def _build_equity_curve(bars: list, shares: float) -> list[dict]:
        """Build daily equity curve, downsampling if > _MAX_EQUITY_CURVE_POINTS."""

        def _ts_str(ts) -> str:
            if hasattr(ts, "isoformat"):
                return ts.isoformat()
            return str(ts)

        all_points = [
            {"timestamp": _ts_str(b.timestamp), "value": round(shares * float(b.close), 4)}
            for b in bars
        ]

        if len(all_points) <= _MAX_EQUITY_CURVE_POINTS:
            return all_points

        # Downsample: keep every Nth point plus always include last
        step = math.ceil(len(all_points) / _MAX_EQUITY_CURVE_POINTS)
        sampled = all_points[::step]
        if sampled[-1] != all_points[-1]:
            sampled.append(all_points[-1])
        return sampled


