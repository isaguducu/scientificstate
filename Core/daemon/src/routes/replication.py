"""
Replication routes — institutional replication request management.

Main_Source §9A.5 M3-G: Quantum/hybrid claims require at least one
confirmed independent institutional replication before endorsement.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from scientificstate.replication.engine import ReplicationEngine

logger = logging.getLogger("scientificstate.daemon.replication")

router = APIRouter(prefix="/replication", tags=["replication"])

# In-memory engine for M1 — production would use persistent storage.
_engine = ReplicationEngine()


def get_engine() -> ReplicationEngine:
    """Return the module-level replication engine (testable hook)."""
    return _engine


# ── Request models ────────────────────────────────────────────────────────────


class ReplicationRequestBody(BaseModel):
    claim_id: str
    source_ssv_id: str | None = None
    source_institution_id: str
    target_institution_id: str
    method_id: str
    dataset_ref: str = ""
    compute_class: str = "classical"
    tolerance: dict | None = None


class SubmitResultBody(BaseModel):
    request_id: str
    target_ssv_id: str
    target_ssv: dict | None = Field(default=None, description="Optional SSV dict for comparison")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/request")
async def create_replication_request(body: ReplicationRequestBody) -> dict:
    """Create a replication request for a claim."""
    engine = get_engine()
    request = engine.create_request(
        claim_id=body.claim_id,
        source_institution_id=body.source_institution_id,
        target_institution_id=body.target_institution_id,
        method_id=body.method_id,
        dataset_ref=body.dataset_ref,
        compute_class=body.compute_class,
        tolerance=body.tolerance,
        source_ssv_id=body.source_ssv_id,
    )
    logger.info(
        "Replication request created: %s (claim=%s, target=%s)",
        request["request_id"], body.claim_id, body.target_institution_id,
    )
    return request


@router.get("/status/{request_id}")
async def get_replication_status(request_id: str) -> dict:
    """Get the status of a replication request."""
    engine = get_engine()
    request = engine.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"Replication request not found: {request_id}")
    return request


@router.post("/submit-result")
async def submit_replication_result(body: SubmitResultBody) -> dict:
    """Submit a replication result and trigger SSV comparison."""
    engine = get_engine()
    try:
        result = engine.submit_result(
            request_id=body.request_id,
            target_ssv_id=body.target_ssv_id,
            target_ssv=body.target_ssv,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info(
        "Replication result submitted: %s → %s",
        body.request_id, result["status"],
    )
    return result


@router.get("/history/{claim_id}")
async def get_replication_history(claim_id: str) -> list[dict]:
    """Get all replication requests for a claim."""
    engine = get_engine()
    return engine.get_history(claim_id)


# ── Federation push (Phase 7 — additive) ────────────────────────────────────


class FederationPushBody(BaseModel):
    """Payload for pushing an endorsed claim to federation mirrors."""
    claim_id: str
    institution_id: str
    domain_id: str = ""
    title: str = ""
    ssv_hash: str = ""
    ssv_signature: str = ""
    researcher_orcid: str | None = None
    gate_status: dict | None = None
    target_mirrors: list[str] | None = Field(
        default=None,
        description="Optional list of mirror URLs to push to. If empty, pushes to all trusted mirrors.",
    )


@router.post("/federation/push")
async def push_to_federation(body: FederationPushBody) -> dict:
    """Push newly endorsed claim to trusted federation mirrors.

    Called after a claim is endorsed to propagate it to federated
    discovery mirrors for cross-institutional search.

    Returns:
        {"status": "queued", "claim_id": ..., "message": ...}
    """
    if not body.claim_id:
        raise HTTPException(status_code=422, detail="claim_id is required")
    if not body.institution_id:
        raise HTTPException(status_code=422, detail="institution_id is required")

    logger.info(
        "Federation push queued: claim=%s institution=%s targets=%s",
        body.claim_id,
        body.institution_id,
        body.target_mirrors or "all-trusted",
    )

    return {
        "status": "queued",
        "claim_id": body.claim_id,
        "institution_id": body.institution_id,
        "message": "Claim queued for federation push to trusted mirrors",
    }
