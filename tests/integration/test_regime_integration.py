"""
Integration tests for GET /analysis/regime

Requires the full Docker Compose stack to be running (via run-integration-tests.sh).
"""

import os
import pytest
import httpx

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

EXPECTED_STRATEGIES = {
    "rsi",
    "macd",
    "moving_average_crossover",
    "bollinger_bands",
    "breakout",
    "mean_reversion",
    "vwap",
}


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=30) as c:
        yield c


def test_regime_endpoint_returns_valid_structure(client):
    """GET /analysis/regime?symbol=AAPL returns 200 with regime + fitness_scores."""
    resp = client.get("/api/analysis/regime", params={"symbol": "AAPL"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert "symbol" in data
    assert data["symbol"] == "AAPL"
    assert "regime" in data
    assert data["regime"] in {
        "TRENDING_UP",
        "TRENDING_DOWN",
        "SIDEWAYS_HIGH_VOL",
        "SIDEWAYS_LOW_VOL",
    }
    assert "adx" in data
    assert "atr_pct" in data
    assert "confidence" in data
    assert "fitness_scores" in data
    assert 0 <= data["confidence"] <= 100


def test_regime_all_strategies_present(client):
    """fitness_scores in the response contains all 7 strategy keys."""
    resp = client.get("/api/analysis/regime", params={"symbol": "AAPL"})
    assert resp.status_code == 200, resp.text

    fitness = resp.json().get("fitness_scores", {})
    assert set(fitness.keys()) == EXPECTED_STRATEGIES, (
        f"Missing or extra strategies. Got: {set(fitness.keys())}"
    )
    for strategy, score in fitness.items():
        assert isinstance(score, int), f"{strategy} score should be int, got {type(score)}"
        assert 0 <= score <= 100, f"{strategy} score {score} out of range"
