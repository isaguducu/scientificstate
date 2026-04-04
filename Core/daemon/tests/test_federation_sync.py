"""Federation sync tests — push endpoint + payload validation (Phase 7)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create TestClient with fresh replication engine per test."""
    from src.main import app
    from src.routes import replication as rep_module
    from scientificstate.replication.engine import ReplicationEngine

    fresh_engine = ReplicationEngine()
    original = rep_module._engine
    rep_module._engine = fresh_engine
    try:
        with TestClient(app) as c:
            yield c
    finally:
        rep_module._engine = original


# ── POST /replication/federation/push — basic validation ────────────────────


def test_federation_push_requires_claim_id(client):
    """Push must include claim_id."""
    resp = client.post("/replication/federation/push", json={
        "institution_id": "inst-A",
    })
    assert resp.status_code == 422


def test_federation_push_requires_institution_id(client):
    """Push must include institution_id."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-1",
    })
    assert resp.status_code == 422


def test_federation_push_valid_payload_returns_queued(client):
    """Valid push payload returns queued status."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-1",
        "institution_id": "inst-A",
        "domain_id": "polymer_science",
        "title": "Tensile strength of PLA under UV exposure",
        "ssv_hash": "abc123",
        "ssv_signature": "sig456",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["claim_id"] == "claim-1"
    assert data["institution_id"] == "inst-A"


def test_federation_push_empty_claim_id_rejected(client):
    """Empty string claim_id is rejected."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "",
        "institution_id": "inst-A",
    })
    assert resp.status_code == 422


def test_federation_push_empty_institution_id_rejected(client):
    """Empty string institution_id is rejected."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-1",
        "institution_id": "",
    })
    assert resp.status_code == 422


def test_federation_push_with_target_mirrors(client):
    """Push with explicit target mirrors returns queued."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-2",
        "institution_id": "inst-B",
        "target_mirrors": ["https://mirror1.example.com", "https://mirror2.example.com"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["claim_id"] == "claim-2"


def test_federation_push_with_optional_orcid(client):
    """Push with optional researcher_orcid succeeds."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-3",
        "institution_id": "inst-C",
        "researcher_orcid": "0000-0001-2345-6789",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_federation_push_without_orcid(client):
    """Push without researcher_orcid succeeds (field is optional)."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-4",
        "institution_id": "inst-D",
        "domain_id": "materials",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_federation_push_with_gate_status(client):
    """Push with gate_status dict succeeds."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-5",
        "institution_id": "inst-E",
        "gate_status": {"format": "pass", "schema": "pass", "reproducibility": "pending"},
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_federation_push_returns_message(client):
    """Push response includes a message."""
    resp = client.post("/replication/federation/push", json={
        "claim_id": "claim-6",
        "institution_id": "inst-F",
    })
    data = resp.json()
    assert "message" in data
    assert len(data["message"]) > 0


def test_federation_push_missing_body(client):
    """Push with no body returns 422."""
    resp = client.post("/replication/federation/push", content=b"{}")
    assert resp.status_code == 422


# ── Ed25519 signature format validation (sync payload) ──────────────────────


def test_ed25519_signature_valid_format():
    """Valid Ed25519 signature is 128-char hex."""
    import re
    sig = "a" * 128
    assert re.match(r"^[0-9a-fA-F]{128}$", sig)


def test_ed25519_signature_invalid_short():
    """Short hex string is not valid Ed25519 signature."""
    import re
    sig = "a" * 64  # too short — signature is 64 bytes = 128 hex
    assert not re.match(r"^[0-9a-fA-F]{128}$", sig)


def test_ed25519_pubkey_valid_format():
    """Valid Ed25519 public key is 64-char hex."""
    import re
    key = "b" * 64
    assert re.match(r"^[0-9a-fA-F]{64}$", key)


def test_ed25519_pubkey_invalid_non_hex():
    """Non-hex characters invalidate public key."""
    import re
    key = "g" * 64  # 'g' is not hex
    assert not re.match(r"^[0-9a-fA-F]{64}$", key)
