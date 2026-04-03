import pytest
from backend.pnl.aggregator import compute_equity_curve

SESSION_START = "2024-01-01T09:00:00+00:00"


def test_equity_curve_starts_at_starting_capital():
    curve = compute_equity_curve([], starting_capital=1000.0, session_start=SESSION_START)
    assert len(curve) == 1
    assert curve[0]["portfolio_value"] == pytest.approx(1000.0)
    assert curve[0]["timestamp"] == SESSION_START


def test_equity_curve_accumulates_pnl_in_order():
    trades = [
        {"pnl": 50.0, "status": "closed", "timestamp_close": "2024-01-01T10:00:00+00:00"},
        {"pnl": -20.0, "status": "closed", "timestamp_close": "2024-01-01T11:00:00+00:00"},
        {"pnl": 30.0, "status": "closed", "timestamp_close": "2024-01-01T12:00:00+00:00"},
    ]
    curve = compute_equity_curve(trades, starting_capital=1000.0, session_start=SESSION_START)
    assert len(curve) == 4
    assert curve[0]["portfolio_value"] == pytest.approx(1000.0)
    assert curve[1]["portfolio_value"] == pytest.approx(1050.0)
    assert curve[2]["portfolio_value"] == pytest.approx(1030.0)
    assert curve[3]["portfolio_value"] == pytest.approx(1060.0)


def test_equity_curve_sorts_by_timestamp_close():
    trades = [
        {"pnl": 30.0, "status": "closed", "timestamp_close": "2024-01-01T12:00:00+00:00"},
        {"pnl": 50.0, "status": "closed", "timestamp_close": "2024-01-01T10:00:00+00:00"},
    ]
    curve = compute_equity_curve(trades, starting_capital=500.0, session_start=SESSION_START)
    # First closed trade by time is the 50.0 one
    assert curve[1]["portfolio_value"] == pytest.approx(550.0)
    assert curve[2]["portfolio_value"] == pytest.approx(580.0)


def test_equity_curve_excludes_open_trades():
    trades = [
        {"pnl": 100.0, "status": "closed", "timestamp_close": "2024-01-01T10:00:00+00:00"},
        {"pnl": None, "status": "open", "timestamp_close": None},
    ]
    curve = compute_equity_curve(trades, starting_capital=1000.0, session_start=SESSION_START)
    assert len(curve) == 2  # anchor + 1 closed trade only


def test_equity_curve_excludes_trades_with_no_timestamp_close():
    trades = [
        {"pnl": 20.0, "status": "closed", "timestamp_close": None},
        {"pnl": 40.0, "status": "closed", "timestamp_close": "2024-01-01T10:00:00+00:00"},
    ]
    curve = compute_equity_curve(trades, starting_capital=500.0, session_start=SESSION_START)
    assert len(curve) == 2
    assert curve[1]["portfolio_value"] == pytest.approx(540.0)
