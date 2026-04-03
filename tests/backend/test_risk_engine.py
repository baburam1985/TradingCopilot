import pytest
from risk.engine import (
    should_stop_loss,
    should_take_profit,
    exceeds_max_position,
    daily_loss_limit_breached,
)


# --- stop-loss ---

def test_stop_loss_buy_triggered():
    # Bought at 100, price drops to 94 — 6% loss, limit 5%
    assert should_stop_loss(100.0, 94.0, "buy", 5.0) is True

def test_stop_loss_buy_not_triggered():
    # Bought at 100, price drops to 96 — 4% loss, limit 5%
    assert should_stop_loss(100.0, 96.0, "buy", 5.0) is False

def test_stop_loss_buy_exactly_at_threshold():
    # Price exactly at threshold (100 * 0.95 = 95)
    assert should_stop_loss(100.0, 95.0, "buy", 5.0) is True

def test_stop_loss_sell_triggered():
    # Shorted at 100, price rises to 106 — 6% loss, limit 5%
    assert should_stop_loss(100.0, 106.0, "sell", 5.0) is True

def test_stop_loss_sell_not_triggered():
    # Shorted at 100, price rises to 104 — 4% loss, limit 5%
    assert should_stop_loss(100.0, 104.0, "sell", 5.0) is False

def test_stop_loss_none_disabled():
    assert should_stop_loss(100.0, 50.0, "buy", None) is False

def test_stop_loss_zero_disabled():
    assert should_stop_loss(100.0, 50.0, "buy", 0.0) is False


# --- take-profit ---

def test_take_profit_buy_triggered():
    # Bought at 100, price rises to 116 — 16% gain, limit 15%
    assert should_take_profit(100.0, 116.0, "buy", 15.0) is True

def test_take_profit_buy_not_triggered():
    # Bought at 100, price rises to 114 — 14% gain, limit 15%
    assert should_take_profit(100.0, 114.0, "buy", 15.0) is False

def test_take_profit_sell_triggered():
    # Shorted at 100, price drops to 84 — 16% gain, limit 15%
    assert should_take_profit(100.0, 84.0, "sell", 15.0) is True

def test_take_profit_sell_not_triggered():
    # Shorted at 100, price drops to 86 — 14% gain, limit 15%
    assert should_take_profit(100.0, 86.0, "sell", 15.0) is False

def test_take_profit_none_disabled():
    assert should_take_profit(100.0, 200.0, "buy", None) is False

def test_take_profit_zero_disabled():
    assert should_take_profit(100.0, 200.0, "buy", 0.0) is False


# --- max position ---

def test_max_position_exceeded():
    # qty=10, price=100 → position=1000; capital=1000, limit=50% → max=500
    assert exceeds_max_position(10.0, 100.0, 1000.0, 50.0) is True

def test_max_position_within_limit():
    # qty=4, price=100 → position=400; capital=1000, limit=50% → max=500
    assert exceeds_max_position(4.0, 100.0, 1000.0, 50.0) is False

def test_max_position_none_disabled():
    assert exceeds_max_position(999.0, 999.0, 1000.0, None) is False

def test_max_position_zero_disabled():
    assert exceeds_max_position(999.0, 999.0, 1000.0, 0.0) is False


# --- daily max loss ---

def test_daily_loss_limit_breached():
    # capital=1000, limit=3% → floor=-30; daily_pnl=-35
    assert daily_loss_limit_breached(-35.0, 1000.0, 3.0) is True

def test_daily_loss_limit_not_breached():
    # capital=1000, limit=3% → floor=-30; daily_pnl=-25
    assert daily_loss_limit_breached(-25.0, 1000.0, 3.0) is False

def test_daily_loss_limit_exactly_at_boundary():
    # Exactly at limit — triggers circuit breaker
    assert daily_loss_limit_breached(-30.0, 1000.0, 3.0) is True

def test_daily_loss_limit_profit_no_breach():
    assert daily_loss_limit_breached(50.0, 1000.0, 3.0) is False

def test_daily_loss_limit_none_disabled():
    assert daily_loss_limit_breached(-9999.0, 1000.0, None) is False

def test_daily_loss_limit_zero_disabled():
    assert daily_loss_limit_breached(-9999.0, 1000.0, 0.0) is False
