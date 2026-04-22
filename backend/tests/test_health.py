async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["db"] == "connected"
    assert "status" in data
    assert "data_ready" in data
    assert "core_counts" in data
