"""Export route tests — 6 endpoints via TestClient."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure framework is importable
_FRAMEWORK_PATH = str(Path(__file__).parents[2] / "framework")
if _FRAMEWORK_PATH not in sys.path:
    sys.path.insert(0, _FRAMEWORK_PATH)


# ── Mock DB responses ────────────────────────────────────────────────────────

_MOCK_SSV = {
    "id": "ssv-export-001",
    "version": 1,
    "d": {"ref": "data-ref-1", "domain": "test_domain", "metadata": {}},
    "i": {"instrument_id": "inst-1"},
    "a": [{"assumption_id": "a1", "description": "test", "type": "bg"}],
    "t": [{"name": "test_method", "algorithm": "test", "parameters": {}, "software_version": "1.0"}],
    "r": {"quantities": {"mw": 50000.0, "pdi": 1.5}, "method": "test", "notes": ""},
    "u": {"measurement_error": {"mw": 500.0}},
    "v": {"conditions": ["T < 200C"]},
    "p": {
        "created_at": "2026-04-04T12:00:00+00:00",
        "researcher_id": "researcher-1",
        "execution_witness": {"compute_class": "classical", "backend_id": "test_domain"},
    },
}

_MOCK_RUN_ROW = {
    "run_id": "run-export-001",
    "workspace_id": "ws-1",
    "domain_id": "test_domain",
    "method_id": "test_method",
    "status": "succeeded",
    "started_at": "2026-04-04T12:00:00+00:00",
    "finished_at": "2026-04-04T12:00:05+00:00",
    "ssv_id": "ssv-export-001",
    "result_json": json.dumps({"mw": 50000.0}),
    "error_json": None,
    "created_at": "2026-04-04T12:00:00+00:00",
}


# ── Mock _load_run_and_ssv ───────────────────────────────────────────────────

async def _mock_load_run_and_ssv(run_id: str):
    if run_id == "not-found":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Run not found")
    return _MOCK_RUN_ROW, _MOCK_SSV


# ── Test client setup ────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Create TestClient with mocked DB access."""
    from fastapi.testclient import TestClient

    with patch("src.routes.export._load_run_and_ssv", side_effect=_mock_load_run_and_ssv):
        # Import after patch to ensure mock is applied
        from src.routes.export import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        yield TestClient(app)


# ── RO-Crate endpoint ────────────────────────────────────────────────────────

def test_export_rocrate(client):
    resp = client.get("/export/rocrate/run-export-001")
    assert resp.status_code == 200
    data = resp.json()
    assert "@context" in data
    assert "@graph" in data


def test_export_rocrate_not_found(client):
    resp = client.get("/export/rocrate/not-found")
    assert resp.status_code == 404


# ── PROV endpoint ─────────────────────────────────────────────────────────────

def test_export_prov(client):
    resp = client.get("/export/prov/run-export-001")
    assert resp.status_code == 200
    data = resp.json()
    assert "prefix" in data
    assert "entity" in data
    assert "activity" in data


def test_export_prov_not_found(client):
    resp = client.get("/export/prov/not-found")
    assert resp.status_code == 404


# ── OpenLineage endpoint ─────────────────────────────────────────────────────

def test_export_openlineage(client):
    resp = client.get("/export/openlineage/run-export-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["eventType"] == "COMPLETE"
    assert "run" in data
    assert "job" in data


def test_export_openlineage_not_found(client):
    resp = client.get("/export/openlineage/not-found")
    assert resp.status_code == 404


# ── CWL endpoint ──────────────────────────────────────────────────────────────

def test_export_cwl(client):
    resp = client.get("/export/cwl/run-export-001")
    assert resp.status_code == 200
    assert "v1.2" in resp.text
    assert "Workflow" in resp.text


def test_export_cwl_not_found(client):
    resp = client.get("/export/cwl/not-found")
    assert resp.status_code == 404


# ── Parquet endpoint (mock — tests import availability) ──────────────────────

def test_export_parquet_not_found(client):
    resp = client.get("/export/parquet/not-found")
    assert resp.status_code == 404


# ── Zarr endpoint (mock — tests import availability) ─────────────────────────

def test_export_zarr_not_found(client):
    resp = client.get("/export/zarr/not-found")
    assert resp.status_code == 404
