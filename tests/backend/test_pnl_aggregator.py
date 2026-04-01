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
