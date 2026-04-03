import math
import pytest
from backend.pnl.aggregator import compute_period_summary


def test_day_summary_sums_pnl():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": -5.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["total_pnl"] == pytest.approx(25.0)
    assert summary["num_trades"] == 3
    assert summary["num_wins"] == 2
    assert summary["num_losses"] == 1
    assert summary["win_rate"] == pytest.approx(2/3, abs=0.01)
    assert summary["ending_capital"] == pytest.approx(1025.0)


def test_summary_with_no_trades():
    summary = compute_period_summary([], starting_capital=500.0)
    assert summary["total_pnl"] == 0.0
    assert summary["num_trades"] == 0
    assert summary["win_rate"] == 0.0
    assert summary["ending_capital"] == 500.0


def test_open_trades_excluded_from_summary():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": None, "status": "open"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["num_trades"] == 1
    assert summary["total_pnl"] == 10.0


# --- Advanced performance metrics ---

def test_profit_factor_wins_and_losses():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": -5.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    # gross profit = 30, gross loss = 5 → profit_factor = 6.0
    assert summary["profit_factor"] == pytest.approx(6.0)


def test_profit_factor_no_losses_returns_none():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["profit_factor"] is None


def test_profit_factor_no_trades_returns_none():
    summary = compute_period_summary([], starting_capital=1000.0)
    assert summary["profit_factor"] is None


def test_sharpe_ratio_with_mixed_pnl():
    # Deterministic: pnls = [10, -5, 20, -3, 15]
    # mean = 7.4, std = stdev of [10,-5,20,-3,15] (population or sample?)
    # Use sample std (ddof=1) to match statistics.stdev
    import statistics
    pnls = [10.0, -5.0, 20.0, -3.0, 15.0]
    mean = statistics.mean(pnls)
    std = statistics.stdev(pnls)  # sample std
    expected_sharpe = mean / std
    trades = [{"pnl": p, "status": "closed"} for p in pnls]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["sharpe_ratio"] == pytest.approx(expected_sharpe, rel=1e-4)


def test_sharpe_ratio_single_trade_returns_none():
    trades = [{"pnl": 10.0, "status": "closed"}]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["sharpe_ratio"] is None


def test_sharpe_ratio_no_trades_returns_none():
    summary = compute_period_summary([], starting_capital=1000.0)
    assert summary["sharpe_ratio"] is None


def test_sortino_ratio_with_losses():
    import statistics
    pnls = [10.0, -5.0, 20.0, -3.0, 15.0]
    mean = statistics.mean(pnls)
    downside = [p for p in pnls if p < 0]
    # population std of downside deviations
    downside_variance = sum(p**2 for p in downside) / len(downside)
    downside_std = math.sqrt(downside_variance)
    expected_sortino = mean / downside_std
    trades = [{"pnl": p, "status": "closed"} for p in pnls]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["sortino_ratio"] == pytest.approx(expected_sortino, rel=1e-4)


def test_sortino_ratio_no_losses_returns_none():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["sortino_ratio"] is None


def test_max_drawdown_pct_tracks_equity_decline():
    # starting_capital=1000, pnls=[10, -30, 20]
    # equity curve: 1000 → 1010 → 980 → 1000
    # peak at 1010, trough at 980 → drawdown = (1010-980)/1010 ≈ 2.97%
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": -30.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    expected = (1010.0 - 980.0) / 1010.0 * 100
    assert summary["max_drawdown_pct"] == pytest.approx(expected, rel=1e-4)


def test_max_drawdown_pct_zero_when_all_gains():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["max_drawdown_pct"] == pytest.approx(0.0)


def test_max_drawdown_pct_zero_when_no_trades():
    summary = compute_period_summary([], starting_capital=1000.0)
    assert summary["max_drawdown_pct"] == pytest.approx(0.0)


def test_calmar_ratio_positive_return_with_drawdown():
    # starting=1000, pnls=[10, -30, 50]
    # ending=1030, total_return_pct = 3%
    # equity: 1000→1010→980→1030, peak=1010, trough=980, drawdown=(30/1010)*100
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": -30.0, "status": "closed"},
        {"pnl": 50.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    total_return_pct = (1030.0 - 1000.0) / 1000.0 * 100
    max_dd_pct = (1010.0 - 980.0) / 1010.0 * 100
    expected_calmar = total_return_pct / max_dd_pct
    assert summary["calmar_ratio"] == pytest.approx(expected_calmar, rel=1e-4)


def test_calmar_ratio_zero_drawdown_returns_none():
    trades = [
        {"pnl": 10.0, "status": "closed"},
        {"pnl": 20.0, "status": "closed"},
    ]
    summary = compute_period_summary(trades, starting_capital=1000.0)
    assert summary["calmar_ratio"] is None


def test_calmar_ratio_no_trades_returns_none():
    summary = compute_period_summary([], starting_capital=1000.0)
    assert summary["calmar_ratio"] is None
