"""Tests for registry mirror management routes."""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_list_mirrors(client):
    """GET /registry/mirrors returns the default mirror list."""
    resp = await client.get("/registry/mirrors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "id" in first
    assert "name" in first
    assert "url" in first
    assert first["mode"] in ("mirror", "self-hosted", "air-gapped")
    assert first["status"] in ("active", "inactive", "syncing")


@pytest.mark.anyio
async def test_sync_mirror(client):
    """POST /registry/sync triggers sync for a valid mirror."""
    resp = await client.post("/registry/sync", json={"mirror_id": "official-r2"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mirror_id"] == "official-r2"
    assert data["status"] == "synced"
    assert "synced_at" in data
    assert "message" in data


@pytest.mark.anyio
async def test_sync_mirror_not_found(client):
    """POST /registry/sync returns 404 for unknown mirror."""
    resp = await client.post("/registry/sync", json={"mirror_id": "nonexistent"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_registry_status(client):
    """GET /registry/status returns mode and protocol endpoints."""
    resp = await client.get("/registry/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] in ("online", "offline", "air-gapped")
    assert isinstance(data["mirrors_count"], int)
    assert data["mirrors_count"] >= 1
    assert isinstance(data["active_mirrors"], int)
    assert isinstance(data["protocol_endpoints"], list)
    assert len(data["protocol_endpoints"]) == 6
    # Verify standard protocol paths are listed
    endpoints_str = " ".join(data["protocol_endpoints"])
    assert "index.json" in endpoints_str
    assert "manifest.json" in endpoints_str
    assert "checksum.sha256" in endpoints_str
