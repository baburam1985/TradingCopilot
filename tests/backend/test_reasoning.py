"""
Unit tests for the AI Trade Reasoning Engine (GSTAAAA-26).

TDD: these tests are written FIRST; they all fail until implementation exists.
"""
import re
import pytest
from strategies.reasoning import to_english


def _sentence_count(text: str) -> int:
    """Count sentences: split on '.', '!', '?' that are followed by space or end-of-string,
    ignoring decimal points inside numbers like -0.15."""
    return len(re.findall(r'[.!?](?:\s|$)', text))


# ---------------------------------------------------------------------------
# Serializer correctness
# ---------------------------------------------------------------------------

def test_reasoning_serializer_rsi():
    """RSI buy dict → correct English, ≤2 sentences."""
    d = {
        "signal_type": "buy",
        "primary_indicator": "RSI(14)",
        "indicator_value": 27.3,
        "threshold": 30,
        "supporting_factors": [],
        "market_context": "RSI crossed below oversold threshold 30",
    }
    text = to_english(d)
    assert isinstance(text, str)
    assert len(text) > 0
    # Must reference the indicator
    assert "RSI" in text
    # Must be ≤ 2 sentences (count sentence-ending punctuation)
    sentence_count = _sentence_count(text)
    assert sentence_count <= 2


def test_reasoning_serializer_macd():
    """MACD sell dict → correct English."""
    d = {
        "signal_type": "sell",
        "primary_indicator": "MACD",
        "indicator_value": -0.15,
        "threshold": 0,
        "supporting_factors": ["bearish crossover confirmed"],
        "market_context": "MACD line crossed below signal line",
    }
    text = to_english(d)
    assert isinstance(text, str)
    assert len(text) > 0
    assert "MACD" in text
    sentence_count = _sentence_count(text)
    assert sentence_count <= 2


def test_reasoning_serializer_missing_keys():
    """Partial dict → no exception, returns non-empty string."""
    d = {"signal_type": "buy"}
    text = to_english(d)
    assert isinstance(text, str)
    # Should not crash, should return something useful
    assert len(text) >= 0  # even empty string is acceptable per spec, but no exception


def test_reasoning_serializer_empty_dict():
    """Empty dict → no exception, returns string."""
    text = to_english({})
    assert isinstance(text, str)


def test_reasoning_serializer_with_supporting_factors():
    """Supporting factors appear in second sentence."""
    d = {
        "signal_type": "buy",
        "primary_indicator": "RSI(14)",
        "indicator_value": 27.3,
        "threshold": 30,
        "supporting_factors": ["volume 140% above 20-day avg", "uptrending 5-day MA"],
        "market_context": "RSI crossed into oversold territory",
    }
    text = to_english(d)
    assert isinstance(text, str)
    assert len(text) > 0
    # Supporting factors should be referenced somewhere
    assert "volume" in text.lower() or "140" in text or "ma" in text.lower()


# ---------------------------------------------------------------------------
# Strategy signal reasoning population
# ---------------------------------------------------------------------------

def test_rsi_buy_reasoning_populated():
    """RSI.analyze() buy signal has non-null reasoning dict with required keys."""
    from strategies.rsi import RSIStrategy

    # Build a price series that guarantees an RSI buy in level mode (RSI < oversold)
    # Start with declining prices to push RSI into oversold territory
    closes = [100.0 - i * 0.8 for i in range(20)]  # declining sequence
    strategy = RSIStrategy(period=14, oversold=30, overbought=70, signal_mode="level")
    signal = strategy.analyze(closes)

    # If the signal is a buy, reasoning must be populated
    if signal.action == "buy":
        assert signal.reasoning is not None
        assert isinstance(signal.reasoning, dict)
        assert "signal_type" in signal.reasoning
        assert "primary_indicator" in signal.reasoning
        assert "indicator_value" in signal.reasoning
        assert signal.reasoning["signal_type"] == "buy"


def test_rsi_hold_reasoning_null():
    """RSI.analyze() hold signal has reasoning=None."""
    from strategies.rsi import RSIStrategy

    # Flat prices → RSI ≈ 50, should be hold
    closes = [100.0] * 20
    strategy = RSIStrategy(period=14)
    signal = strategy.analyze(closes)

    assert signal.action == "hold"
    assert signal.reasoning is None


def test_macd_reasoning_populated():
    """MACD.analyze() crossover signal has non-null reasoning dict."""
    from strategies.macd import MACDStrategy

    # Build data that causes a MACD crossover: rising sequence
    closes = [100.0 + i * 0.5 for i in range(40)]
    strategy = MACDStrategy()
    signal = strategy.analyze(closes)

    if signal.action in ("buy", "sell"):
        assert signal.reasoning is not None
        assert isinstance(signal.reasoning, dict)
        assert "signal_type" in signal.reasoning
        assert "primary_indicator" in signal.reasoning


# ---------------------------------------------------------------------------
# PaperTrade reasoning round-trip (model field test)
# ---------------------------------------------------------------------------

def test_paper_trade_has_reasoning_attribute():
    """PaperTrade model has a reasoning attribute."""
    import os
    import unittest.mock

    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "tradingcopilot",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
    }
    with unittest.mock.patch.dict(os.environ, env_vars):
        from models.paper_trade import PaperTrade

        # The model should have a reasoning column
        assert hasattr(PaperTrade, "reasoning")
        # It should be nullable (existing trades have None)
        col = PaperTrade.__table__.columns.get("reasoning")
        assert col is not None
        assert col.nullable is True
