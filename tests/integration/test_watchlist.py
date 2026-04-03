import pytest

pytestmark = pytest.mark.integration

WATCHLIST_PAYLOAD = {
    "symbol": "GOOG",
    "strategy": "rsi",
    "strategy_params": {},
}


async def test_create_watchlist_item(client, clean_db):
    resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["symbol"] == "GOOG"
    assert data["strategy"] == "rsi"
    assert data["last_signal"] is None
    assert data["last_price"] is None


async def test_list_watchlist_contains_created(client, clean_db):
    await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    resp = await client.get("/watchlist")
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["symbol"] == "GOOG" for i in items)


async def test_get_watchlist_item_by_id(client, clean_db):
    create_resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    item_id = create_resp.json()["id"]
    resp = await client.get(f"/watchlist/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id


async def test_delete_watchlist_item(client, clean_db):
    create_resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    item_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/watchlist/{item_id}")
    assert del_resp.status_code == 200
    get_resp = await client.get(f"/watchlist/{item_id}")
    assert get_resp.status_code == 404


async def test_get_nonexistent_watchlist_item_returns_404(client, clean_db):
    resp = await client.get("/watchlist/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_watchlist_item_alert_threshold(client, clean_db):
    create_resp = await client.post("/watchlist", json=WATCHLIST_PAYLOAD)
    item_id = create_resp.json()["id"]
    patch_resp = await client.patch(f"/watchlist/{item_id}", json={"alert_threshold": 150.0})
    assert patch_resp.status_code == 200
    assert float(patch_resp.json()["alert_threshold"]) == 150.0
