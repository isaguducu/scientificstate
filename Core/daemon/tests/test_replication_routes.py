"""Replication route tests — 4 endpoints via TestClient."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create TestClient with fresh replication engine per test."""
    from src.main import app
    from src.routes import replication as rep_module
    from scientificstate.replication.engine import ReplicationEngine

    # Fresh engine per test to avoid cross-test state
    fresh_engine = ReplicationEngine()
    original = rep_module._engine
    rep_module._engine = fresh_engine
    try:
        with TestClient(app) as c:
            yield c
    finally:
        rep_module._engine = original


# ── POST /replication/request ────────────────────────────────────────────────


def test_create_request(client):
    resp = client.post("/replication/request", json={
        "claim_id": "claim-1",
        "source_institution_id": "inst-A",
        "target_institution_id": "inst-B",
        "method_id": "bell_state",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["claim_id"] == "claim-1"
    assert "request_id" in data


def test_create_request_with_tolerance(client):
    resp = client.post("/replication/request", json={
        "claim_id": "claim-2",
        "source_institution_id": "inst-A",
        "target_institution_id": "inst-C",
        "method_id": "test",
        "tolerance": {"absolute": 0.01, "relative": 0.05},
    })
    assert resp.status_code == 200
    assert resp.json()["tolerance"]["absolute"] == 0.01


def test_create_request_with_compute_class(client):
    resp = client.post("/replication/request", json={
        "claim_id": "claim-3",
        "source_institution_id": "inst-A",
        "target_institution_id": "inst-B",
        "method_id": "test",
        "compute_class": "quantum_hw",
    })
    assert resp.status_code == 200
    assert resp.json()["compute_class"] == "quantum_hw"


# ── GET /replication/status/{request_id} ─────────────────────────────────────


def test_get_status(client):
    create_resp = client.post("/replication/request", json={
        "claim_id": "c1",
        "source_institution_id": "a",
        "target_institution_id": "b",
        "method_id": "m",
    })
    request_id = create_resp.json()["request_id"]

    status_resp = client.get(f"/replication/status/{request_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "pending"


def test_get_status_not_found(client):
    resp = client.get("/replication/status/nonexistent-id")
    assert resp.status_code == 404


# ── POST /replication/submit-result ──────────────────────────────────────────


def test_submit_result_confirmed(client):
    from src.routes import replication as rep_module

    engine = rep_module._engine
    source_ssv = {
        "r": {"quantities": {"x": 1.0}, "method": "test"},
        "t": [{"algorithm": "test"}],
    }
    target_ssv = {
        "r": {"quantities": {"x": 1.0}, "method": "test"},
        "t": [{"algorithm": "test"}],
    }
    engine.register_ssv("ssv-source-1", source_ssv)

    create_resp = client.post("/replication/request", json={
        "claim_id": "claim-1",
        "source_ssv_id": "ssv-source-1",
        "source_institution_id": "a",
        "target_institution_id": "b",
        "method_id": "test",
    })
    request_id = create_resp.json()["request_id"]

    submit_resp = client.post("/replication/submit-result", json={
        "request_id": request_id,
        "target_ssv_id": "target-1",
        "target_ssv": target_ssv,
    })
    assert submit_resp.status_code == 200
    data = submit_resp.json()
    assert data["status"] == "confirmed"
    assert data["comparison_report"]["result_match"] is True


def test_submit_result_not_found(client):
    resp = client.post("/replication/submit-result", json={
        "request_id": "nonexistent",
        "target_ssv_id": "t1",
    })
    assert resp.status_code == 404


# ── GET /replication/history/{claim_id} ──────────────────────────────────────


def test_get_history(client):
    client.post("/replication/request", json={
        "claim_id": "claim-A",
        "source_institution_id": "a",
        "target_institution_id": "b",
        "method_id": "m1",
    })
    client.post("/replication/request", json={
        "claim_id": "claim-A",
        "source_institution_id": "a",
        "target_institution_id": "c",
        "method_id": "m2",
    })

    resp = client.get("/replication/history/claim-A")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(r["claim_id"] == "claim-A" for r in data)


def test_get_history_empty(client):
    resp = client.get("/replication/history/nonexistent")
    assert resp.status_code == 200
    assert resp.json() == []
