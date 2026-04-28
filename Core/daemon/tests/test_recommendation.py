"""
Recommendation tests — Phase 7 domain suggestion + method recommendation.

Tests the /modules/suggest endpoint which implements P7 (Non-Delegation):
the system recommends domains for a file but never auto-executes.

Future: dedicated /recommendations endpoint with trending + personalisation.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_suggest_returns_200_for_csv(client: AsyncClient) -> None:
    """POST /modules/suggest with a CSV MIME type returns HTTP 200."""
    resp = await client.post(
        "/modules/suggest",
        json={"file_path": "sample.csv"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_suggest_response_has_suggested_domains(client: AsyncClient) -> None:
    """Response includes a suggested_domains list."""
    resp = await client.post(
        "/modules/suggest",
        json={"file_path": "data.csv"},
    )
    body = resp.json()
    assert "suggested_domains" in body
    assert isinstance(body["suggested_domains"], list)


@pytest.mark.asyncio
async def test_suggest_does_not_auto_execute(client: AsyncClient) -> None:
    """P7 — suggest never triggers a compute run automatically."""
    resp = await client.post(
        "/modules/suggest",
        json={"file_path": "spectrum.mzml"},
    )
    # No side-effects: body must not contain run_id
    body = resp.json()
    assert "run_id" not in body


@pytest.mark.asyncio
async def test_suggest_polymer_csv(client: AsyncClient) -> None:
    """CSV files with typical polymer names get polymer_science suggested."""
    resp = await client.post(
        "/modules/suggest",
        json={"file_path": "polymer_sample.csv"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # polymer_science should appear somewhere in the suggestions
    assert "polymer_science" in body.get("suggested_domains", [])
