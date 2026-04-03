import pytest
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.integration


async def test_seed_endpoint_inserts_rows(client, clean_db):
    resp = await client.post("/backtest/seed/AAPL?days=90")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["inserted"] > 0
    assert data["skipped"] == 0


async def test_seed_endpoint_skips_duplicates(client, clean_db):
    resp1 = await client.post("/backtest/seed/AAPL?days=90")
    assert resp1.status_code == 200
    assert resp1.json()["inserted"] > 0

    resp2 = await client.post("/backtest/seed/AAPL?days=90")
    assert resp2.status_code == 200
    assert resp2.json()["inserted"] == 0
    assert resp2.json()["skipped"] > 0


async def test_rsi_backtest_returns_valid_structure(client, clean_db):
    seed = await client.post("/backtest/seed/AAPL?days=90")
    assert seed.status_code == 200

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest", json={
        "symbol": "AAPL",
        "strategy": "rsi",
        "strategy_params": {"period": 14, "oversold": 30, "overbought": 70, "signal_mode": "transition"},
        "starting_capital": 1000.0,
        "from_dt": start.isoformat(),
        "to_dt": end.isoformat(),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "trades" in data
    assert "summary" in data
    assert isinstance(data["trades"], list)
    assert isinstance(data["summary"], dict)


async def test_rsi_backtest_summary_has_required_keys(client, clean_db):
    await client.post("/backtest/seed/AAPL?days=90")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)

    resp = await client.post("/backtest", json={
        "symbol": "AAPL",
        "strategy": "rsi",
        "strategy_params": {"period": 14, "oversold": 30, "overbought": 70, "signal_mode": "transition"},
        "starting_capital": 1000.0,
        "from_dt": start.isoformat(),
        "to_dt": end.isoformat(),
    })
    summary = resp.json()["summary"]
    for key in ("total_pnl", "num_trades", "num_wins", "num_losses", "win_rate", "starting_capital", "ending_capital"):
        assert key in summary, f"Missing key: {key}"


async def test_rsi_strategy_appears_in_list(client):
    resp = await client.get("/strategies")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "rsi" in names
    assert "moving_average_crossover" in names


async def test_backtest_returns_400_for_unknown_strategy(client):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    resp = await client.post("/backtest", json={
        "symbol": "AAPL",
        "strategy": "nonexistent_strategy",
        "strategy_params": {},
        "starting_capital": 1000.0,
        "from_dt": start.isoformat(),
        "to_dt": end.isoformat(),
    })
    assert resp.status_code == 400
    assert "nonexistent_strategy" in resp.json()["detail"]
