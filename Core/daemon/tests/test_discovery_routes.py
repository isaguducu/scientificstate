"""Tests for discovery sync endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_sync_endorsed_claim(client):
    """POST /discovery/sync accepts a valid endorsed claim."""
    payload = {
        "claim_id": "claim-polymer-001",
        "ssv_id": "ssv-001",
        "domain_id": "polymer_science",
        "method_id": "py_gc_ms",
        "title": "PCA reveals three distinct polymer clusters",
        "institution_id": "inst-001",
        "researcher_orcid": "0000-0002-1234-5678",
        "gate_status": {"reproducibility": "passed", "peer_review": "pending"},
        "ssv_signature": "deadbeef0123456789abcdef",
        "ssv_hash": "abc123hash",
    }
    resp = await client.post("/discovery/sync", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # In test env, portal is unreachable → "queued"; in production → "synced"
    assert data["status"] in ("synced", "queued")
    assert data["claim_id"] == "claim-polymer-001"


@pytest.mark.anyio
async def test_sync_minimal_payload(client):
    """POST /discovery/sync with minimal required fields."""
    payload = {
        "claim_id": "claim-min-001",
        "ssv_id": "ssv-min",
        "domain_id": "genomics",
        "title": "Minimal endorsed claim",
        "researcher_orcid": "0000-0001-0000-0001",
        "gate_status": {},
        "ssv_signature": "sig",
        "ssv_hash": "hash",
    }
    resp = await client.post("/discovery/sync", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] in ("synced", "queued")


@pytest.mark.anyio
async def test_sync_missing_required_field(client):
    """POST /discovery/sync with missing claim_id → 422."""
    payload = {
        "ssv_id": "ssv-bad",
        "domain_id": "test",
        "title": "Bad",
        "researcher_orcid": "0000-0001-0000-0000",
        "gate_status": {},
        "ssv_signature": "sig",
        "ssv_hash": "hash",
    }
    resp = await client.post("/discovery/sync", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_sync_returns_claim_id(client):
    """Response includes the claim_id from the request."""
    payload = {
        "claim_id": "claim-echo-123",
        "ssv_id": "ssv-e",
        "domain_id": "materials",
        "title": "Echo test",
        "researcher_orcid": "0000-0003-0000-0001",
        "gate_status": {"gate_a": "passed"},
        "ssv_signature": "abc",
        "ssv_hash": "def",
    }
    resp = await client.post("/discovery/sync", json=payload)
    assert resp.json()["claim_id"] == "claim-echo-123"
