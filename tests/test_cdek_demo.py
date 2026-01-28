import pytest

import app.cdek as cdek


@pytest.mark.asyncio
async def test_get_cdek_client_returns_demo_without_creds(monkeypatch):
    # Ensure singleton is reset between tests
    cdek._cdek_client = None

    monkeypatch.delenv("CDEK_CLIENT_ID", raising=False)
    monkeypatch.delenv("CDEK_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("CDEK_DEMO_MODE", "true")

    client = cdek.get_cdek_client()
    assert client is not None
    assert isinstance(client, cdek.DemoCdekClient)

    cities = await client.search_cities("Моск", limit=10)
    assert any(city.code == 44 for city in cities)

    pvz = await client.get_pvz_list(44, limit=50)
    assert len(pvz) >= 5
    assert all(p.code and p.address and p.work_time for p in pvz)


def test_get_cdek_client_prefers_real_client_when_creds_exist(monkeypatch):
    cdek._cdek_client = None

    monkeypatch.setenv("CDEK_DEMO_MODE", "true")
    monkeypatch.setenv("CDEK_CLIENT_ID", "demo_id")
    monkeypatch.setenv("CDEK_CLIENT_SECRET", "demo_secret")
    monkeypatch.setenv("CDEK_TEST_MODE", "true")

    client = cdek.get_cdek_client()
    assert client is not None
    assert isinstance(client, cdek.CdekClient)

