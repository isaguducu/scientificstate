"""Test /runs endpoints."""
from __future__ import annotations

import pytest


async def _make_workspace(client, name: str = "Test Workspace") -> str:
    resp = await client.post("/workspaces", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["workspace_id"]


@pytest.mark.asyncio
async def test_post_run_returns_202(client):
    ws_id = await _make_workspace(client)
    resp = await client.post(
        "/runs",
        json={
            "workspace_id": ws_id,
            "domain_id": "polymer_science",
            "method_id": "pca",
            "assumptions": [{"text": "sample_count_sufficient", "accepted": True}],
            "parameters": {},
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body
    assert isinstance(body["run_id"], str)


@pytest.mark.asyncio
async def test_get_run_returns_200(client):
    ws_id = await _make_workspace(client)
    post = await client.post(
        "/runs",
        json={
            "workspace_id": ws_id,
            "domain_id": "polymer_science",
            "method_id": "pca",
            "assumptions": [{"text": "sample_count_sufficient", "accepted": True}],
        },
    )
    run_id = post.json()["run_id"]

    get = await client.get(f"/runs/{run_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["run_id"] == run_id
    assert body["status"] in ("succeeded", "failed", "pending")


@pytest.mark.asyncio
async def test_get_run_not_found(client):
    resp = await client.get("/runs/nonexistent-run-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_run_unknown_workspace_returns_404(client):
    resp = await client.post(
        "/runs",
        json={
            "workspace_id": "does-not-exist",
            "domain_id": "polymer_science",
            "method_id": "pca",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_run_unknown_domain_returns_404(client):
    ws_id = await _make_workspace(client)
    resp = await client.post(
        "/runs",
        json={
            "workspace_id": ws_id,
            "domain_id": "unknown_domain",
            "method_id": "pca",
        },
    )
    assert resp.status_code == 404
