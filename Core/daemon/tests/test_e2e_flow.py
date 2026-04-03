"""E2E flow: ingest → workspace → run → result."""
from __future__ import annotations

import tempfile
import uuid

import pytest


@pytest.mark.asyncio
async def test_full_e2e_flow(client):
    """
    1. Ingest a file → get raw_data_id
    2. Create workspace → get workspace_id
    3. Submit run using dataset_ref=raw_data_id
    4. GET /runs/{run_id} → status in (succeeded, failed) + ssv_ref present on success
    """
    # 1. Create a temp file and ingest it
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        # Unique content per test run — ensures SHA-256 differs each time
        f.write(f"mz,intensity\n100.0,500.0\n101.0,300.0\nrun_id,{uuid.uuid4()}\n")
        tmp_path = f.name

    ingest_resp = await client.post(
        "/datasets/ingest",
        json={
            "data_path": tmp_path,
            "acquisition_timestamp": "2026-04-04T10:00:00Z",
            "instrument_id": "GC-MS-001",
            "domain_id": "polymer_science",
            "sample_id": "PS-E2E-001",
        },
    )
    assert ingest_resp.status_code == 201, ingest_resp.text
    raw_data_id = ingest_resp.json()["raw_data_id"]
    assert raw_data_id

    # 2. Create workspace
    ws_resp = await client.post("/workspaces", json={"name": "E2E Workspace"})
    assert ws_resp.status_code == 201
    ws_id = ws_resp.json()["workspace_id"]

    # 3. Submit run (polymer pca without blocks_data → will fail gracefully)
    run_resp = await client.post(
        "/runs",
        json={
            "workspace_id": ws_id,
            "domain_id": "polymer_science",
            "method_id": "pca",
            "dataset_ref": raw_data_id,
            "assumptions": [{"text": "sample_count_sufficient", "accepted": True}],
            "parameters": {},
        },
    )
    assert run_resp.status_code == 202, run_resp.text
    run_id = run_resp.json()["run_id"]
    assert run_id

    # 4. Get result
    result_resp = await client.get(f"/runs/{run_id}")
    assert result_resp.status_code == 200
    body = result_resp.json()
    assert body["run_id"] == run_id
    assert body["status"] in ("succeeded", "failed")

    # ssv_ref is present when status is succeeded
    if body["status"] == "succeeded":
        assert "ssv_ref" in body
        assert body["ssv_ref"].startswith("ssv-")

    # Verify previously P0 routes unaffected
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    domains = await client.get("/domains")
    assert domains.status_code == 200
    assert isinstance(domains.json(), list)
