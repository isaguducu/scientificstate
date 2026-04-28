"""
Trending tests — Phase 7 workspace activity metrics.

Tests derive trending information from existing endpoints:
  GET /workspaces/{id}/runs  — run history (basis for trending)
  GET /workspaces/{id}/claims — claim list
  GET /domains              — active domain list

Future: dedicated /trending endpoint with time-series activity data.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_domains_returns_active_domains(client: AsyncClient) -> None:
    """GET /domains returns the list of currently active domains."""
    resp = await client.get("/domains")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_domains_include_polymer_science(client: AsyncClient) -> None:
    """polymer_science domain is discoverable — confirms trending domain data."""
    resp = await client.get("/domains")
    assert resp.status_code == 200
    names = [d.get("domain_id") or d.get("name") for d in resp.json()]
    assert "polymer_science" in names


@pytest.mark.asyncio
async def test_workspace_runs_endpoint_available(client: AsyncClient) -> None:
    """GET /workspaces/{id}/runs exists — forms basis for activity trending."""
    # Create a workspace first so we have a valid ID
    ws_resp = await client.post("/workspaces", json={"name": "trending-test"})
    assert ws_resp.status_code == 201
    ws_id = ws_resp.json()["workspace_id"]

    runs_resp = await client.get(f"/workspaces/{ws_id}/runs")
    assert runs_resp.status_code == 200
    assert isinstance(runs_resp.json(), list)


@pytest.mark.asyncio
async def test_workspace_runs_failed_filter(client: AsyncClient) -> None:
    """?run_status=failed filter works — P6 negative-knowledge trending."""
    ws_resp = await client.post("/workspaces", json={"name": "trending-fail-test"})
    ws_id = ws_resp.json()["workspace_id"]

    resp = await client.get(f"/workspaces/{ws_id}/runs?run_status=failed")
    assert resp.status_code == 200
    # Empty list expected for fresh workspace
    assert resp.json() == []
