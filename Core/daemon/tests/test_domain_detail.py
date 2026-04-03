"""Test GET /domains/{domain_id} endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_known_domain(client):
    resp = await client.get("/domains/polymer_science")
    assert resp.status_code == 200
    body = resp.json()
    assert body["domain_id"] == "polymer_science"
    assert "domain_name" in body
    assert "version" in body
    assert "supported_data_types" in body
    assert isinstance(body["methods"], list)
    assert len(body["methods"]) > 0
    # Each method must have at least method_id and name
    m = body["methods"][0]
    assert "method_id" in m


@pytest.mark.asyncio
async def test_get_unknown_domain_returns_404(client):
    resp = await client.get("/domains/does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_domains_still_works(client):
    resp = await client.get("/domains")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
