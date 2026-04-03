"""Test workspace CRUD endpoints."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_workspace(client):
    resp = await client.post("/workspaces", json={"name": "My Lab"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Lab"
    assert "workspace_id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_list_workspaces_empty(client):
    resp = await client.get("/workspaces")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_workspaces_after_create(client):
    await client.post("/workspaces", json={"name": "W1"})
    await client.post("/workspaces", json={"name": "W2"})
    resp = await client.get("/workspaces")
    assert resp.status_code == 200
    names = {w["name"] for w in resp.json()}
    assert {"W1", "W2"} == names


@pytest.mark.asyncio
async def test_get_workspace(client):
    create = await client.post("/workspaces", json={"name": "Detail Test"})
    ws_id = create.json()["workspace_id"]

    resp = await client.get(f"/workspaces/{ws_id}")
    assert resp.status_code == 200
    assert resp.json()["workspace_id"] == ws_id
    assert resp.json()["name"] == "Detail Test"


@pytest.mark.asyncio
async def test_get_workspace_not_found(client):
    resp = await client.get("/workspaces/nonexistent-id-12345")
    assert resp.status_code == 404
