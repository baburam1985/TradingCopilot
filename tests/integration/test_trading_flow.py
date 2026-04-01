import pytest

pytestmark = pytest.mark.integration


async def test_scrape_stores_price_row(client, scrape_symbol, clean_db):
    row = await scrape_symbol("AAPL")
    assert row is not None
    assert row["symbol"] == "AAPL"
    assert float(row["close"]) > 0
    assert row["sources_available"] == ["yahoo"]


async def test_latest_price_after_scrape(client, scrape_symbol, clean_db):
    await scrape_symbol("AAPL")
    resp = await client.get("/symbols/AAPL/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["symbol"] == "AAPL"
    assert float(data["close"]) > 0


async def test_create_session_and_query_trades(client, scrape_symbol, clean_db):
    await scrape_symbol("AAPL")
    session_resp = await client.post("/sessions", json={
        "symbol": "AAPL",
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 3, "long_window": 5},
        "starting_capital": 1000.0,
        "mode": "paper",
    })
    assert session_resp.status_code == 200
    session_id = session_resp.json()["id"]
    trades_resp = await client.get(f"/sessions/{session_id}/trades")
    assert trades_resp.status_code == 200
    assert isinstance(trades_resp.json(), list)


async def test_pnl_endpoint_returns_summary_structure(client, scrape_symbol, clean_db):
    await scrape_symbol("AAPL")
    session_resp = await client.post("/sessions", json={
        "symbol": "AAPL",
        "strategy": "moving_average_crossover",
        "strategy_params": {"short_window": 3, "long_window": 5},
        "starting_capital": 1000.0,
        "mode": "paper",
    })
    session_id = session_resp.json()["id"]
    pnl_resp = await client.get(f"/sessions/{session_id}/pnl")
    assert pnl_resp.status_code == 200
    data = pnl_resp.json()
    assert "all_time" in data
    summary = data["all_time"]
    for key in ("total_pnl", "num_trades", "num_wins", "num_losses", "win_rate", "ending_capital"):
        assert key in summary, f"Missing key: {key}"
