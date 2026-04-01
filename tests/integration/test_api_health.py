import pytest
import uuid

pytestmark = pytest.mark.integration


async def test_strategies_returns_moving_average(client):
    resp = await client.get("/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    strategy = data[0]
    assert "name" in strategy
    assert "description" in strategy
    assert "parameters" in strategy
    assert strategy["name"] == "moving_average_crossover"


async def test_unknown_session_returns_404(client):
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/sessions/{fake_id}")
    assert resp.status_code == 404


async def test_latest_price_empty_db_returns_null(client, clean_db):
    resp = await client.get("/symbols/ZZZTEST/latest")
    assert resp.status_code == 200
    assert resp.json() is None
