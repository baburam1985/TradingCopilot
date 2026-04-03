"""Integration tests for POST /sessions/{session_id}/optimize.

Requires Docker stack running (./scripts/run-integration-tests.sh).
Seeds price history, creates a session, then calls the optimize endpoint.
"""
from datetime import datetime, timezone, timedelta

import pytest

pytestmark = pytest.mark.integration


async def _create_session(client, symbol="AAPL"):
    resp = await client.post("/sessions", json={
        "symbol": symbol,
        "strategy": "rsi",
        "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
        "starting_capital": 1000.0,
        "mode": "paper",
    })
    assert resp.status_code == 200, f"Session create failed: {resp.text}"
    return resp.json()["id"]


async def test_session_optimize_happy_path(client, clean_db):
    """Create session, seed price history, run optimizer with 3 RSI period values."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200, f"Seed failed: {seed.text}"
    assert seed.json()["inserted"] > 0

    session_id = await _create_session(client)

    resp = await client.post(f"/sessions/{session_id}/optimize", json={
        "param_grid": {
            "period": [7, 9, 14],
        },
        "metric": "sharpe",
    })
    assert resp.status_code == 200, f"Optimize failed: {resp.text}"
    data = resp.json()

    assert data["iterations_run"] == 3
    assert len(data["results"]) == 3
    assert "best_params" in data
    assert "period" in data["best_params"]


async def test_session_optimize_response_schema(client, clean_db):
    """Each result item must contain params, sharpe, total_return, win_rate."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    session_id = await _create_session(client)

    resp = await client.post(f"/sessions/{session_id}/optimize", json={
        "param_grid": {"period": [14]},
        "metric": "sharpe",
    })
    assert resp.status_code == 200
    item = resp.json()["results"][0]
    assert "params" in item
    assert "sharpe" in item
    assert "total_return" in item
    assert "win_rate" in item
    assert item["params"]["period"] == 14


async def test_session_optimize_rejects_over_100_combinations(client, clean_db):
    """Endpoint must 400 when param_grid product exceeds 100."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    session_id = await _create_session(client)

    resp = await client.post(f"/sessions/{session_id}/optimize", json={
        "param_grid": {
            "period": list(range(11)),      # 11 × 10 = 110 combos
            "overbought": list(range(10)),
        },
        "metric": "sharpe",
    })
    assert resp.status_code == 400
    assert "100" in resp.json()["detail"]


async def test_session_optimize_returns_404_for_unknown_session(client, clean_db):
    """Unknown session ID must return 404."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/sessions/{fake_id}/optimize", json={
        "param_grid": {"period": [14]},
        "metric": "sharpe",
    })
    assert resp.status_code == 404


async def test_session_optimize_best_params_matches_top_result(client, clean_db):
    """best_params must equal the params of the first (highest-ranked) result."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    session_id = await _create_session(client)

    resp = await client.post(f"/sessions/{session_id}/optimize", json={
        "param_grid": {"period": [7, 9, 14]},
        "metric": "sharpe",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["best_params"] == data["results"][0]["params"]
