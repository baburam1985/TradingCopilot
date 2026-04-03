"""Walk-Forward Backtesting Engine.

Splits historical data into rolling train/test windows to detect overfitting.
No data leakage: test bars are strictly after train bars, determined by calendar
date, not bar count.
"""

import itertools
import math
import statistics
from datetime import timedelta

from backtester.runner import BacktestRunner
from pnl.aggregator import compute_period_summary
from strategies.registry import STRATEGY_REGISTRY

_MIN_BARS_FOR_SIGNAL = 5  # skip windows with fewer bars than this


class WalkForwardEngine:
    """Performs walk-forward optimization and out-of-sample validation.

    Args:
        strategy_name: Name of strategy in STRATEGY_REGISTRY.
        strategy_params: Fixed params used when no param_grid is supplied.
        param_grid: Optional dict of {param: [values]} for grid search.
                    When provided, each train window is optimized independently.
        train_window_days: Calendar-day length of each training window.
        test_window_days: Calendar-day length of each test (out-of-sample) window.
        step_days: How far to advance each window's start.
        starting_capital: Capital used for each sub-run.
    """

    def __init__(
        self,
        strategy_name: str,
        strategy_params: dict,
        param_grid: dict,
        train_window_days: int,
        test_window_days: int,
        step_days: int,
        starting_capital: float,
    ):
        if strategy_name not in STRATEGY_REGISTRY:
            raise ValueError(
                f"Unknown strategy: '{strategy_name}'. "
                f"Available: {list(STRATEGY_REGISTRY.keys())}"
            )
        self.strategy_cls = STRATEGY_REGISTRY[strategy_name]
        self.strategy_params = strategy_params
        self.param_grid = param_grid or {}
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days
        self.starting_capital = starting_capital

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, bars: list) -> dict:
        """Execute walk-forward over *bars* and return windows + aggregate.

        Args:
            bars: Sorted list of PriceHistory-like objects with `.timestamp`
                  and `.close` attributes.

        Returns:
            dict with keys ``windows`` (list of per-window dicts) and
            ``aggregate`` (averaged out-of-sample metrics).
        """
        if not bars:
            return {"windows": [], "aggregate": self._empty_aggregate()}

        windows = self._build_windows(bars)
        return {
            "windows": windows,
            "aggregate": self._aggregate(windows),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_windows(self, bars: list) -> list[dict]:
        """Slice bars into rolling windows and run each one."""
        from datetime import timezone

        def _as_date(ts):
            """Normalise timestamp → date regardless of type."""
            if hasattr(ts, "date"):
                return ts.date()
            # string ISO: "2024-01-15" or "2024-01-15T..."
            return ts.split("T")[0] if isinstance(ts, str) else ts

        first_date = _as_date(bars[0].timestamp)
        last_date = _as_date(bars[-1].timestamp)

        # Build a date→bars index for O(1) slicing by date range
        from collections import defaultdict
        date_to_bars: dict = defaultdict(list)
        for b in bars:
            date_to_bars[_as_date(b.timestamp)].append(b)

        all_dates = sorted(date_to_bars.keys())

        windows = []
        window_index = 0
        cursor = first_date

        while True:
            train_start = cursor
            train_end = train_start + timedelta(days=self.train_window_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_window_days)

            # Stop if test window exceeds available data
            if test_end > last_date + timedelta(days=1):
                break

            train_bars = [b for d in all_dates if train_start <= d < train_end for b in date_to_bars[d]]
            test_bars = [b for d in all_dates if test_start <= d < test_end for b in date_to_bars[d]]

            # Skip degenerate windows
            if len(train_bars) < _MIN_BARS_FOR_SIGNAL or len(test_bars) < 1:
                cursor += timedelta(days=self.step_days)
                continue

            best_params, train_sharpe = self._optimize_on_train(train_bars)
            test_result = self._run_test_window(test_bars, best_params)

            windows.append(
                {
                    "window_index": window_index,
                    "train_start": str(train_start),
                    "train_end": str(train_end),
                    "test_start": str(test_start),
                    "test_end": str(test_end),
                    "best_params": best_params,
                    "train_sharpe": train_sharpe,
                    "test_sharpe": test_result["sharpe_ratio"],
                    "test_pnl": test_result["total_pnl"],
                    "test_win_rate": test_result["win_rate"],
                    "test_num_trades": test_result["num_trades"],
                    "test_max_drawdown_pct": test_result["max_drawdown_pct"],
                }
            )
            window_index += 1
            cursor += timedelta(days=self.step_days)

        return windows

    def _optimize_on_train(self, train_bars: list) -> tuple[dict, float | None]:
        """Grid-search params on train_bars; return (best_params, train_sharpe)."""
        if not self.param_grid:
            # No grid — just use fixed params
            summary = self._run_summary(train_bars, self.strategy_params)
            return self.strategy_params, summary["sharpe_ratio"]

        param_names = list(self.param_grid.keys())
        param_values = [self.param_grid[k] for k in param_names]
        combos = list(itertools.product(*param_values))

        best_sharpe: float | None = None
        best_params: dict = {}
        best_combo_summary: dict = {}

        for combo in combos:
            params = dict(zip(param_names, combo))
            try:
                summary = self._run_summary(train_bars, params)
            except (TypeError, ValueError):
                continue

            s = summary["sharpe_ratio"]
            # Prefer combo with higher sharpe; treat None as -inf
            if best_sharpe is None or (s is not None and s > (best_sharpe or -math.inf)):
                best_sharpe = s
                best_params = params
                best_combo_summary = summary

        if not best_params:
            # All combos failed — fall back to fixed params
            best_params = self.strategy_params
            best_sharpe = None

        return best_params, best_sharpe

    def _run_test_window(self, test_bars: list, params: dict) -> dict:
        """Run strategy on out-of-sample test bars and return summary."""
        return self._run_summary(test_bars, params)

    def _run_summary(self, bars: list, params: dict) -> dict:
        strategy = self.strategy_cls(**params)
        runner = BacktestRunner(strategy=strategy, starting_capital=self.starting_capital)
        trades = runner.run(bars)
        return compute_period_summary(trades, self.starting_capital)

    @staticmethod
    def _aggregate(windows: list[dict]) -> dict:
        if not windows:
            return WalkForwardEngine._empty_aggregate()

        test_sharpes = [w["test_sharpe"] for w in windows if w["test_sharpe"] is not None]
        test_pnls = [w["test_pnl"] for w in windows]
        test_win_rates = [w["test_win_rate"] for w in windows]

        avg_test_sharpe = (
            statistics.mean(test_sharpes) if test_sharpes else None
        )
        avg_test_pnl = statistics.mean(test_pnls) if test_pnls else 0.0
        avg_win_rate = statistics.mean(test_win_rates) if test_win_rates else 0.0

        # Consistency score: fraction of windows with positive test PnL
        positive_windows = sum(1 for p in test_pnls if p > 0)
        consistency_score = positive_windows / len(test_pnls) if test_pnls else 0.0

        # Overfitting score: ratio of avg train_sharpe to avg test_sharpe.
        # Higher → more overfitting. None when test sharpe is unavailable.
        train_sharpes = [w["train_sharpe"] for w in windows if w["train_sharpe"] is not None]
        avg_train_sharpe = statistics.mean(train_sharpes) if train_sharpes else None
        overfitting_score: float | None = None
        if avg_train_sharpe is not None and avg_test_sharpe is not None and avg_test_sharpe != 0:
            overfitting_score = avg_train_sharpe / avg_test_sharpe

        return {
            "num_windows": len(windows),
            "avg_test_sharpe": avg_test_sharpe,
            "avg_test_pnl": avg_test_pnl,
            "avg_win_rate": avg_win_rate,
            "consistency_score": consistency_score,
            "avg_train_sharpe": avg_train_sharpe,
            "overfitting_score": overfitting_score,
        }

    @staticmethod
    def _empty_aggregate() -> dict:
        return {
            "num_windows": 0,
            "avg_test_sharpe": None,
            "avg_test_pnl": 0.0,
            "avg_win_rate": 0.0,
            "consistency_score": 0.0,
            "avg_train_sharpe": None,
            "overfitting_score": None,
        }
