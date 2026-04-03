"""Integration tests for POST /backtest/optimize — happy-path grid search."""
from datetime import datetime, timezone, timedelta

import pytest

pytestmark = pytest.mark.integration


async def test_optimize_happy_path_combination_count(client, clean_db):
    """Seed AAPL price history, run optimize with 3 RSI period values, assert count."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200, f"Seed failed: {seed.text}"
    assert seed.json()["inserted"] > 0

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest/optimize", json={
        "symbol": "AAPL",
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "starting_capital": 1000.0,
        "strategy": "rsi",
        "parameter_ranges": {
            "period": [7, 9, 14],
        },
    })
    assert resp.status_code == 200, f"Optimize failed: {resp.text}"
    data = resp.json()
    assert data["combinations_tested"] == 3
    assert len(data["results"]) == 3


async def test_optimize_results_sorted_by_sharpe_descending(client, clean_db):
    """Results must be ordered sharpe_ratio descending; None values go last."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest/optimize", json={
        "symbol": "AAPL",
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "starting_capital": 1000.0,
        "strategy": "rsi",
        "parameter_ranges": {
            "period": [7, 9, 14],
        },
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    sharpe_values = [r["sharpe_ratio"] for r in results]

    # All non-None sharpe values must appear before None values and be descending
    non_none = [s for s in sharpe_values if s is not None]
    assert non_none == sorted(non_none, reverse=True), (
        f"Non-None sharpe values not sorted descending: {sharpe_values}"
    )
    # Any None values must come after all non-None values
    none_indices = [i for i, s in enumerate(sharpe_values) if s is None]
    non_none_indices = [i for i, s in enumerate(sharpe_values) if s is not None]
    if none_indices and non_none_indices:
        assert min(none_indices) > max(non_none_indices), (
            f"None sharpe value appears before a non-None value: {sharpe_values}"
        )


async def test_optimize_result_schema(client, clean_db):
    """Each result item must contain all required fields with correct types."""
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest/optimize", json={
        "symbol": "AAPL",
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "starting_capital": 1000.0,
        "strategy": "rsi",
        "parameter_ranges": {
            "period": [7, 9, 14],
        },
    })
    assert resp.status_code == 200
    for item in resp.json()["results"]:
        assert "parameters" in item
        assert "sharpe_ratio" in item
        assert "total_pnl" in item
        assert "win_rate" in item
        assert "num_trades" in item
        assert isinstance(item["parameters"], dict)
        assert "period" in item["parameters"]
        assert item["parameters"]["period"] in [7, 9, 14]
        assert isinstance(item["num_trades"], int) and item["num_trades"] >= 0
        if item["sharpe_ratio"] is not None:
            assert isinstance(item["sharpe_ratio"], float)
