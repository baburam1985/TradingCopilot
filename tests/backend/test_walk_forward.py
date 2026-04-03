"""Unit tests for the WalkForwardEngine.

Focus areas:
- Window splitting produces non-overlapping train/test sets (no data leakage)
- Overfitting score calculation
- Aggregate metrics computation
- Edge cases: empty bars, windows smaller than minimum bar count
"""

import pytest
from types import SimpleNamespace
from datetime import date, timedelta

from backend.backtester.walk_forward import WalkForwardEngine


def _make_bars(prices: list[float], start_date: date = date(2022, 1, 1)):
    """Create minimal bar objects from price list, 1 bar per calendar day."""
    bars = []
    for i, price in enumerate(prices):
        ts = start_date + timedelta(days=i)
        bars.append(SimpleNamespace(close=price, timestamp=ts))
    return bars


def _engine(
    strategy_name="moving_average_crossover",
    strategy_params=None,
    param_grid=None,
    train_window_days=30,
    test_window_days=10,
    step_days=10,
    starting_capital=1000.0,
):
    return WalkForwardEngine(
        strategy_name=strategy_name,
        strategy_params=strategy_params or {"short_window": 3, "long_window": 7},
        param_grid=param_grid or {},
        train_window_days=train_window_days,
        test_window_days=test_window_days,
        step_days=step_days,
        starting_capital=starting_capital,
    )


class TestWindowSplitting:
    def test_no_data_leakage(self):
        """Train bars and test bars must not share any timestamp."""
        prices = [100.0 + i * 0.5 for i in range(100)]
        bars = _make_bars(prices)
        eng = _engine(train_window_days=40, test_window_days=20, step_days=20)

        # Patch _build_windows to capture the slices used
        train_sets = []
        test_sets = []
        original = eng._optimize_on_train

        def spy_optimize(train_bars):
            train_sets.append([str(b.timestamp) for b in train_bars])
            return original(train_bars)

        eng._optimize_on_train = spy_optimize

        original_test = eng._run_test_window

        def spy_test(test_bars, params):
            test_sets.append([str(b.timestamp) for b in test_bars])
            return original_test(test_bars, params)

        eng._run_test_window = spy_test
        eng.run(bars)

        for i, (train, test) in enumerate(zip(train_sets, test_sets)):
            overlap = set(train) & set(test)
            assert not overlap, f"Window {i} has data leakage: {overlap}"

    def test_test_bars_strictly_after_train_bars(self):
        """For every window, max(train_date) < min(test_date)."""
        prices = [float(i + 1) for i in range(120)]
        bars = _make_bars(prices)
        eng = _engine(train_window_days=50, test_window_days=20, step_days=20)
        result = eng.run(bars)

        for w in result["windows"]:
            assert w["train_end"] <= w["test_start"], (
                f"Window {w['window_index']}: train ends {w['train_end']} "
                f"but test starts {w['test_start']}"
            )

    def test_window_count_matches_expected(self):
        """With 90 bars, train=30, test=10, step=10 → expect multiple windows."""
        prices = [100.0] * 90
        bars = _make_bars(prices)
        eng = _engine(train_window_days=30, test_window_days=10, step_days=10)
        result = eng.run(bars)
        assert result["aggregate"]["num_windows"] >= 3

    def test_empty_bars_returns_zero_windows(self):
        eng = _engine()
        result = eng.run([])
        assert result["windows"] == []
        assert result["aggregate"]["num_windows"] == 0

    def test_insufficient_bars_skips_window(self):
        """Only 3 bars: not enough for any window."""
        prices = [100.0, 101.0, 102.0]
        bars = _make_bars(prices)
        eng = _engine(train_window_days=30, test_window_days=10, step_days=10)
        result = eng.run(bars)
        assert result["windows"] == []


class TestAggregateMetrics:
    def test_consistency_score_all_positive(self):
        """All positive test PnL → consistency score = 1.0."""
        windows = [
            {"test_pnl": 100.0, "test_sharpe": 1.2, "test_win_rate": 0.6,
             "train_sharpe": 1.5, "test_num_trades": 5, "test_max_drawdown_pct": 5.0},
            {"test_pnl": 50.0, "test_sharpe": 0.8, "test_win_rate": 0.55,
             "train_sharpe": 1.1, "test_num_trades": 3, "test_max_drawdown_pct": 3.0},
        ]
        agg = WalkForwardEngine._aggregate(windows)
        assert agg["consistency_score"] == 1.0

    def test_consistency_score_mixed(self):
        windows = [
            {"test_pnl": 100.0, "test_sharpe": 1.2, "test_win_rate": 0.6,
             "train_sharpe": 1.5, "test_num_trades": 5, "test_max_drawdown_pct": 5.0},
            {"test_pnl": -50.0, "test_sharpe": -0.3, "test_win_rate": 0.4,
             "train_sharpe": 1.1, "test_num_trades": 3, "test_max_drawdown_pct": 10.0},
        ]
        agg = WalkForwardEngine._aggregate(windows)
        assert agg["consistency_score"] == 0.5

    def test_overfitting_score_high_when_train_much_better(self):
        """If train Sharpe >> test Sharpe, overfitting_score should be > 1."""
        windows = [
            {"test_pnl": 10.0, "test_sharpe": 0.2, "test_win_rate": 0.5,
             "train_sharpe": 2.0, "test_num_trades": 5, "test_max_drawdown_pct": 2.0},
        ]
        agg = WalkForwardEngine._aggregate(windows)
        assert agg["overfitting_score"] is not None
        assert agg["overfitting_score"] > 1.0

    def test_avg_test_pnl_is_average_of_windows(self):
        windows = [
            {"test_pnl": 100.0, "test_sharpe": 1.0, "test_win_rate": 0.6,
             "train_sharpe": 1.2, "test_num_trades": 4, "test_max_drawdown_pct": 4.0},
            {"test_pnl": 200.0, "test_sharpe": 1.5, "test_win_rate": 0.7,
             "train_sharpe": 1.8, "test_num_trades": 6, "test_max_drawdown_pct": 3.0},
        ]
        agg = WalkForwardEngine._aggregate(windows)
        assert abs(agg["avg_test_pnl"] - 150.0) < 1e-6

    def test_empty_windows_returns_empty_aggregate(self):
        agg = WalkForwardEngine._aggregate([])
        assert agg["num_windows"] == 0
        assert agg["avg_test_sharpe"] is None


class TestParamGrid:
    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            WalkForwardEngine(
                strategy_name="nonexistent_strategy_xyz",
                strategy_params={},
                param_grid={},
                train_window_days=30,
                test_window_days=10,
                step_days=10,
                starting_capital=1000.0,
            )

    def test_no_param_grid_uses_fixed_params(self):
        """Without a param_grid, engine uses strategy_params on every window."""
        prices = [10.0 + (i % 5) for i in range(80)]
        bars = _make_bars(prices)
        eng = _engine(
            strategy_params={"short_window": 3, "long_window": 7},
            param_grid={},
            train_window_days=30,
            test_window_days=15,
            step_days=15,
        )
        result = eng.run(bars)
        for w in result["windows"]:
            assert w["best_params"] == {"short_window": 3, "long_window": 7}
