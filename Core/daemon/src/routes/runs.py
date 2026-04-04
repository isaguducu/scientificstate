"""Compute run endpoints.

POST /runs           — submit a domain compute run (async, returns 202 + run_id)
GET  /runs/{run_id}  — get run status and result

Integrations:
  W3  — scientificstate.pipeline.execute_pipeline()  (pure coordinator)
  W4  — polymer_science.result_adapter.adapt_to_run_result()  (response formatter)
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.storage.schema import get_db_path

logger = logging.getLogger("scientificstate.daemon.runs")

router = APIRouter(prefix="/runs", tags=["compute"])

# ---------------------------------------------------------------------------
# W3 / W4 import helpers
# ---------------------------------------------------------------------------

_FRAMEWORK_PATH = str(Path(__file__).parents[4] / "Core" / "framework")
_POLYMER_PATH = str(Path(__file__).parents[4] / "Domains" / "polymer")

for _p in (_FRAMEWORK_PATH, _POLYMER_PATH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from scientificstate.pipeline import execute_pipeline  # W3

    _PIPELINE_AVAILABLE = True
except ImportError:
    _PIPELINE_AVAILABLE = False
    logger.warning("W3 pipeline not available — runs will be recorded but not executed")

try:
    from polymer_science.result_adapter import adapt_to_run_result  # W4

    _ADAPTER_AVAILABLE = True
except ImportError:
    _ADAPTER_AVAILABLE = False
    logger.warning("W4 result_adapter not available — response will be formatted inline")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ComputeRunRequest(BaseModel):
    """Matches ComputeRunRequest in daemon-api.yaml."""

    workspace_id: str
    domain_id: str
    method_id: str
    dataset_ref: str | None = Field(default=None)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    compute_class: str = Field(default="classical")


class RunAccepted(BaseModel):
    run_id: str


# ---------------------------------------------------------------------------
# DB helpers (runs + ssvs + claims)
# ---------------------------------------------------------------------------


async def _insert_run(
    db: aiosqlite.Connection,
    run_id: str,
    workspace_id: str,
    domain_id: str,
    method_id: str,
    status: str,
    started_at: str | None,
    finished_at: str | None,
    ssv_id: str | None,
    result_json: str | None,
    error_json: str | None,
) -> None:
    await db.execute(
        """
        INSERT INTO runs
            (run_id, workspace_id, domain_id, method_id, status,
             started_at, finished_at, ssv_id, result_json, error_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, workspace_id, domain_id, method_id, status,
            started_at, finished_at, ssv_id, result_json, error_json,
        ),
    )


async def _update_run_status(
    db: aiosqlite.Connection,
    run_id: str,
    status: str,
    finished_at: str,
    ssv_id: str | None,
    result_json: str | None,
    error_json: str | None,
) -> None:
    await db.execute(
        """
        UPDATE runs
        SET status=?, finished_at=?, ssv_id=?, result_json=?, error_json=?
        WHERE run_id=?
        """,
        (status, finished_at, ssv_id, result_json, error_json, run_id),
    )


async def _load_run(run_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# POST /runs
# ---------------------------------------------------------------------------


@router.post("", response_model=RunAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_run(body: ComputeRunRequest, request: Request) -> Any:
    """
    Submit a compute run.

    Executes synchronously (Phase 1 — async queue is Phase 2).
    Returns run_id immediately; client polls GET /runs/{run_id} for result.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(tz=timezone.utc).isoformat()

    # Validate workspace exists
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (body.workspace_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace not found: {body.workspace_id}",
            )

    # Get domain from registry
    registry = getattr(request.app.state, "domain_registry", None)
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Domain registry not available",
        )
    domain = registry.get(body.domain_id)
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain not found: {body.domain_id}",
        )

    # Insert pending run
    async with aiosqlite.connect(get_db_path()) as db:
        await _insert_run(
            db, run_id, body.workspace_id, body.domain_id, body.method_id,
            "pending", started_at, None, None, None, None,
        )
        await db.commit()

    # Determine compute class and dispatch to appropriate backend
    compute_class = body.compute_class
    if compute_class in ("quantum_sim", "quantum_hw", "hybrid"):
        # Use orchestrator registry when available, fall back to direct import
        from src.runner.orchestrator import get_backend as _get_backend

        backend = _get_backend(compute_class)
        if backend is None:
            # Fall back to direct instantiation
            if compute_class == "quantum_sim":
                try:
                    from src.runner.backends.quantum_sim import QuantumSimBackend
                    backend = QuantumSimBackend()
                except ImportError:
                    raise HTTPException(
                        status_code=status.HTTP_501_NOT_IMPLEMENTED,
                        detail="Quantum simulator backend not available",
                    )
            elif compute_class == "quantum_hw":
                from src.runner.backends.quantum_hw import QuantumHWBackend
                backend = QuantumHWBackend()
            else:  # hybrid
                from src.runner.backends.hybrid import HybridBackend
                backend = HybridBackend(domain_registry=registry)

        # Execute via backend directly, then feed result to pipeline
        # Inject domain_id so ClassicalBackend can find the domain in registry
        backend_params = {**body.parameters, "domain_id": body.domain_id}
        backend_result = backend.execute(
            method_id=body.method_id,
            dataset_ref=body.dataset_ref or "",
            assumptions=body.assumptions,
            params=backend_params,
        )
        # Inject backend result into domain for pipeline consumption
        # The pipeline will pick up quantum_metadata and exploratory flags
        body.parameters["_backend_result"] = backend_result
        body.parameters["_compute_class"] = compute_class

    # Execute pipeline (W3)
    if not _PIPELINE_AVAILABLE:
        async with aiosqlite.connect(get_db_path()) as db:
            await _update_run_status(
                db, run_id, "failed",
                datetime.now(tz=timezone.utc).isoformat(),
                None, None,
                json.dumps({"error": "Pipeline not available"}),
            )
            await db.commit()
        return RunAccepted(run_id=run_id)

    try:
        pr = execute_pipeline(
            domain=domain,
            method_id=body.method_id,
            assumptions=body.assumptions,
            dataset_ref=body.dataset_ref,
            workspace_id=body.workspace_id,
            parameters=body.parameters,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Pipeline execution failed: %s", exc)
        async with aiosqlite.connect(get_db_path()) as db:
            await _update_run_status(
                db, run_id, "failed",
                datetime.now(tz=timezone.utc).isoformat(),
                None, None,
                json.dumps({"error": str(exc)}),
            )
            await db.commit()
        return RunAccepted(run_id=run_id)

    # Persist SSV (P2 — immutable record)
    ssv_id = pr.ssv.get("id", str(uuid.uuid4()))
    claim_id = pr.claim.get("id", str(uuid.uuid4()))
    now = datetime.now(tz=timezone.utc).isoformat()
    run_status = pr.run.status.value  # "succeeded" | "failed"
    result_json = json.dumps(pr.ssv.get("r", {}))

    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO ssvs (ssv_id, run_id, ssv_json) VALUES (?, ?, ?)",
            (ssv_id, run_id, json.dumps(pr.ssv)),
        )
        await db.execute(
            "INSERT INTO claims (claim_id, run_id, claim_json) VALUES (?, ?, ?)",
            (claim_id, run_id, json.dumps(pr.claim)),
        )
        await _update_run_status(
            db, run_id, run_status, now,
            ssv_id, result_json, None,
        )
        await db.commit()

    logger.info(
        "Run %s completed: status=%s ssv_id=%s", run_id, run_status, ssv_id
    )
    return RunAccepted(run_id=run_id)


# ---------------------------------------------------------------------------
# GET /runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/{run_id}")
async def get_run(run_id: str) -> Any:
    """
    Return run status and result (if completed).
    Response shape: ComputeRunResult (daemon-api.yaml).
    Uses W4 result_adapter to format the response.
    """
    row = await _load_run(run_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}",
        )

    run_status = row["status"]

    # Build method_output for W4 adapter
    result_data = json.loads(row["result_json"] or "{}")
    error_data = json.loads(row["error_json"] or "{}")

    method_output: dict[str, Any] = {
        "method_id": row["method_id"],
        "domain_id": row["domain_id"],
        "status": "ok" if run_status == "succeeded" else "error",
        "result": result_data,
        "diagnostics": {},
    }
    if run_status == "failed" and error_data:
        method_output["error_code"] = error_data.get("error", "EXECUTION_ERROR")
        method_output["error"] = error_data.get("error", "Unknown error")

    run_context: dict[str, Any] = {
        "run_id": row["run_id"],
        "workspace_id": row["workspace_id"],
        "started_at": row["started_at"] or row["created_at"],
    }

    if _ADAPTER_AVAILABLE:
        response = adapt_to_run_result(method_output, run_context)  # W4
    else:
        # Inline fallback (W4 not available)
        response = {
            "run_id": row["run_id"],
            "workspace_id": row["workspace_id"],
            "domain_id": row["domain_id"],
            "method_id": row["method_id"],
            "status": run_status,
            "started_at": row["started_at"] or row["created_at"],
            "finished_at": row["finished_at"],
        }
        if run_status == "succeeded":
            response["result"] = result_data
            response["execution_witness"] = {
                "compute_class": "classical",
                "backend_id": row["domain_id"],
            }
        elif run_status == "failed":
            response["error"] = error_data

    # Attach ssv_ref if available
    if row.get("ssv_id"):
        response["ssv_ref"] = f"ssv-{row['ssv_id']}"

    return response
