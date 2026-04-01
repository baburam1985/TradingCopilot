import pytest

pytestmark = pytest.mark.integration

SESSION_PAYLOAD = {
    "symbol": "INTC",
    "strategy": "moving_average_crossover",
    "strategy_params": {"short_window": 3, "long_window": 5},
    "starting_capital": 500.0,
    "mode": "paper",
}


async def test_create_session(client, clean_db):
    resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["symbol"] == "INTC"
    assert data["status"] == "active"
    assert data["mode"] == "paper"
    assert float(data["starting_capital"]) == 500.0


async def test_list_sessions_contains_created(client, clean_db):
    await client.post("/sessions", json=SESSION_PAYLOAD)
    resp = await client.get("/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    assert any(s["symbol"] == "INTC" for s in sessions)


async def test_get_session_by_id(client, clean_db):
    create_resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = create_resp.json()["id"]
    resp = await client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == session_id
    assert resp.json()["symbol"] == "INTC"


async def test_stop_session(client, clean_db):
    create_resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = create_resp.json()["id"]
    stop_resp = await client.patch(f"/sessions/{session_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "closed"


async def test_get_stopped_session_shows_closed(client, clean_db):
    create_resp = await client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = create_resp.json()["id"]
    await client.patch(f"/sessions/{session_id}/stop")
    resp = await client.get(f"/sessions/{session_id}")
    assert resp.json()["status"] == "closed"
