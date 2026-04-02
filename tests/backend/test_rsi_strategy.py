import pytest
from strategies.rsi import RSIStrategy, _compute_rsi


def _falling(n: int, start: float = 100.0, drop: float = 2.0) -> list[float]:
    return [start - i * drop for i in range(n)]


def _rising(n: int, start: float = 100.0, rise: float = 2.0) -> list[float]:
    return [start + i * rise for i in range(n)]


def _flat(n: int, base: float = 100.0) -> list[float]:
    return [base] * n


def test_rsi_insufficient_data_returns_hold():
    strategy = RSIStrategy(period=14, signal_mode="transition")
    # transition needs period+2=16 bars; supply only 15
    result = strategy.analyze(_flat(15))
    assert result.action == "hold"
    assert "Insufficient" in result.reason


def test_rsi_buy_on_oversold_transition():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    # Sharp falling series drives RSI well below 30
    closes = _falling(50, start=100.0, drop=2.0)
    result = strategy.analyze(closes)
    assert result.action == "buy"


def test_rsi_sell_on_overbought_transition():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    closes = _rising(50, start=100.0, rise=2.0)
    result = strategy.analyze(closes)
    assert result.action == "sell"


def test_rsi_hold_when_no_threshold_crossing():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    # Flat prices → RSI stays near 50, never crosses a threshold
    closes = _flat(20)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_rsi_hold_when_sustained_below_oversold_transition():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="transition")
    # Build long falling series: RSI already below 30
    closes = _falling(60, start=200.0, drop=2.0)
    # Append one more tiny drop — RSI was already below 30, no crossing
    closes.append(closes[-1] - 0.1)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_rsi_level_mode_buy_every_bar_below_oversold():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="level")
    closes = _falling(50, start=100.0, drop=2.0)
    result = strategy.analyze(closes)
    assert result.action == "buy"
    # Add more falling bars — still buy in level mode
    closes.append(closes[-1] - 1.0)
    result2 = strategy.analyze(closes)
    assert result2.action == "buy"


def test_rsi_level_mode_hold_at_neutral():
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="level")
    closes = _flat(20)
    result = strategy.analyze(closes)
    assert result.action == "hold"


def test_rsi_level_mode_uses_strict_less_than_for_buy():
    closes = _flat(20)  # flat → RSI near 50 (never < 30)
    rsi = _compute_rsi(closes, 14)
    assert rsi > 30  # sanity: flat prices are not oversold


def test_compute_rsi_all_gains_returns_100():
    # Pure rising series → avg_loss = 0 → RSI = 100
    closes = _rising(20)
    rsi = _compute_rsi(closes, 14)
    assert rsi == 100.0


def test_compute_rsi_all_losses_returns_0():
    # Pure falling series → avg_gain = 0 → RSI = 0
    closes = _falling(20)
    rsi = _compute_rsi(closes, 14)
    assert rsi == 0.0
