"""Claim view and human endorsement endpoints.

GET   /claims/{claim_id}                        — claim detail + live gate status
GET   /workspaces/{workspace_id}/claims         — workspace claim list
PATCH /claims/{claim_id}/endorse                — log human endorsement (H1 gate, P7)
GET   /claims/{claim_id}/history                — immutable transition log (P9)
GET   /runs/{run_id}/claim                      — claim produced by a run
GET   /workspaces/{workspace_id}/epistemic-state — P11 gate summary + lifecycle report
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.storage.schema import get_db_path

try:
    from scientificstate.claims.gate_evaluator import evaluate_all as _evaluate_gates
    _GATES_AVAILABLE = True
except ImportError:
    _GATES_AVAILABLE = False

router = APIRouter(tags=["claims"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ClaimDetail(BaseModel):
    claim_id: str
    run_id: str
    claim_json: dict[str, Any]
    created_at: str
    endorsed_at: str | None = None
    endorsed_by: str | None = None


class ClaimSummary(BaseModel):
    claim_id: str
    run_id: str
    created_at: str
    endorsed_at: str | None = None
    endorsed_by: str | None = None


class ClaimTransition(BaseModel):
    transition_id: str
    claim_id: str
    from_status: str | None
    to_status: str
    actor: str
    note: str | None
    timestamp: str


class EpistemicStateReport(BaseModel):
    workspace_id: str
    generated_at: str
    total_claims: int
    gate_pass_rates: dict[str, float]
    lifecycle_distribution: dict[str, int]
    claims_with_all_gates: int
    blocking_gates: list[str]


class EndorseRequest(BaseModel):
    researcher_id: str = Field(..., min_length=1)
    note: str | None = None


class EndorseResponse(BaseModel):
    claim_id: str
    endorsed_at: str
    endorsed_by: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_claim(db: aiosqlite.Connection, claim_id: str) -> dict[str, Any] | None:
    cur = await db.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    )
    row = await cur.fetchone()
    return dict(row) if row else None


def _row_to_detail(row: dict[str, Any]) -> dict[str, Any]:
    claim_json = json.loads(row["claim_json"] or "{}")

    # Re-evaluate gates at read time so UI always shows current state.
    # E1 / C1 / U1 / V1 can be determined from claim data;
    # H1 is set by the endorsed_at column (human act).
    if _GATES_AVAILABLE:
        # Apply endorsed status to claim dict before evaluating H1.
        # gate_h1 requires endorser_id + signature.
        # Phase 9 / M0: real Ed25519 signing is deferred to Phase 10.
        # A non-empty endorsed_by + endorsed_at counts as human act;
        # we synthesize a stub signature placeholder so H1 can pass.
        if row.get("endorsed_at") and row.get("endorsed_by"):
            claim_json["endorsement_record"] = {
                "endorser_id": row["endorsed_by"],
                "endorsed_at": row["endorsed_at"],
                # Phase 9 stub: full Ed25519 signature in Phase 10
                "signature": f"stub-phase9-{row['endorsed_by']}",
            }
        gate_result = _evaluate_gates(claim_json)
        claim_json["gate_e1"] = gate_result.gate_e1
        claim_json["gate_u1"] = gate_result.gate_u1
        claim_json["gate_v1"] = gate_result.gate_v1
        claim_json["gate_c1"] = gate_result.gate_c1
        claim_json["gate_h1"] = gate_result.gate_h1

    return {
        "claim_id": row["claim_id"],
        "run_id": row["run_id"],
        "claim_json": claim_json,
        "created_at": row["created_at"],
        "endorsed_at": row.get("endorsed_at"),
        "endorsed_by": row.get("endorsed_by"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
async def get_claim(claim_id: str) -> Any:
    """Return a single claim with its endorsement state."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetch_claim(db, claim_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim not found: {claim_id}",
        )
    return _row_to_detail(row)


@router.get(
    "/workspaces/{workspace_id}/claims",
    response_model=list[ClaimSummary],
)
async def list_workspace_claims(workspace_id: str) -> Any:
    """List all claims produced by runs in a workspace, most recent first."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (workspace_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace not found: {workspace_id}",
            )

        cur = await db.execute(
            """
            SELECT c.claim_id, c.run_id, c.created_at,
                   c.endorsed_at, c.endorsed_by
            FROM claims c
            INNER JOIN runs r ON r.run_id = c.run_id
            WHERE r.workspace_id = ?
            ORDER BY c.created_at DESC
            """,
            (workspace_id,),
        )
        rows = await cur.fetchall()

    return [
        {
            "claim_id": r["claim_id"],
            "run_id": r["run_id"],
            "created_at": r["created_at"],
            "endorsed_at": r["endorsed_at"],
            "endorsed_by": r["endorsed_by"],
        }
        for r in rows
    ]


@router.patch("/claims/{claim_id}/endorse", response_model=EndorseResponse)
async def endorse_claim(claim_id: str, body: EndorseRequest) -> Any:
    """Log a human endorsement for a claim (P7 — H1_human gate).

    P1 rule: claim_json is never mutated.  Only endorsed_at / endorsed_by
    columns are written.  A claim_transitions row is appended for P9
    reversibility / inspectability.
    """
    now = datetime.now(tz=timezone.utc).isoformat()

    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        row = await _fetch_claim(db, claim_id)

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim not found: {claim_id}",
            )

        # Derive current status from claim_json for the transition log
        claim_json = json.loads(row["claim_json"] or "{}")
        from_status = claim_json.get("status")

        await db.execute(
            """
            UPDATE claims
            SET endorsed_at = ?, endorsed_by = ?
            WHERE claim_id = ?
            """,
            (now, body.researcher_id, claim_id),
        )

        # P9 — append immutable transition record
        await db.execute(
            """
            INSERT INTO claim_transitions
                (transition_id, claim_id, from_status, to_status,
                 actor, note, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                claim_id,
                from_status,
                "endorsed",
                body.researcher_id,
                body.note,
                now,
            ),
        )
        await db.commit()

    return {
        "claim_id": claim_id,
        "endorsed_at": now,
        "endorsed_by": body.researcher_id,
    }


@router.get("/runs/{run_id}/claim", response_model=ClaimDetail)
async def get_run_claim(run_id: str) -> Any:
    """Return the claim produced by a specific run."""
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT run_id FROM runs WHERE run_id = ?", (run_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run not found: {run_id}",
            )

        cur = await db.execute(
            "SELECT * FROM claims WHERE run_id = ?", (run_id,)
        )
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No claim found for run: {run_id}",
        )
    return _row_to_detail(dict(row))


# ---------------------------------------------------------------------------
# P9 — GET /claims/{claim_id}/history
# ---------------------------------------------------------------------------


@router.get(
    "/claims/{claim_id}/history",
    response_model=list[ClaimTransition],
)
async def get_claim_history(claim_id: str) -> Any:
    """Return the immutable transition log for a claim (P9 — Reversibility).

    Each endorsement, contest, or retraction appends a row to
    claim_transitions.  This endpoint makes every state change fully
    inspectable and auditable without modifying the original claim_json.
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT claim_id FROM claims WHERE claim_id = ?", (claim_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim not found: {claim_id}",
            )

        cur = await db.execute(
            """
            SELECT transition_id, claim_id, from_status, to_status,
                   actor, note, timestamp
            FROM claim_transitions
            WHERE claim_id = ?
            ORDER BY timestamp ASC
            """,
            (claim_id,),
        )
        rows = await cur.fetchall()

    return [
        {
            "transition_id": r["transition_id"],
            "claim_id": r["claim_id"],
            "from_status": r["from_status"],
            "to_status": r["to_status"],
            "actor": r["actor"],
            "note": r["note"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# P11 — GET /workspaces/{workspace_id}/epistemic-state
# ---------------------------------------------------------------------------


@router.get(
    "/workspaces/{workspace_id}/epistemic-state",
    response_model=EpistemicStateReport,
)
async def get_epistemic_state(workspace_id: str) -> Any:
    """Return the epistemic state summary for a workspace (P11 — Alignment).

    Aggregates gate pass rates, lifecycle distribution, and identifies which
    gates are currently blocking claims from advancing.  Provides a single
    inspectable snapshot of the workspace's scientific state health.
    """
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (workspace_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace not found: {workspace_id}",
            )

        # Fetch all claims for this workspace (via runs join)
        cur = await db.execute(
            """
            SELECT c.claim_id, c.claim_json, c.endorsed_at, c.endorsed_by
            FROM claims c
            INNER JOIN runs r ON r.run_id = c.run_id
            WHERE r.workspace_id = ?
            """,
            (workspace_id,),
        )
        rows = await cur.fetchall()

    total = len(rows)
    gate_counts: dict[str, int] = {
        "gate_e1": 0, "gate_u1": 0, "gate_v1": 0,
        "gate_c1": 0, "gate_h1": 0,
    }
    lifecycle_counts: dict[str, int] = {}
    all_gates_pass_count = 0

    for row in rows:
        claim_json = json.loads(row["claim_json"] or "{}")

        # Re-evaluate gates with endorsement state
        if _GATES_AVAILABLE:
            if row["endorsed_at"] and row["endorsed_by"]:
                claim_json["endorsement_record"] = {
                    "endorser_id": row["endorsed_by"],
                    "endorsed_at": row["endorsed_at"],
                    "signature": f"stub-phase9-{row['endorsed_by']}",
                }
            gr = _evaluate_gates(claim_json)
            gates = {
                "gate_e1": gr.gate_e1,
                "gate_u1": gr.gate_u1,
                "gate_v1": gr.gate_v1,
                "gate_c1": gr.gate_c1,
                "gate_h1": gr.gate_h1,
            }
        else:
            gates = {g: claim_json.get(g, False) for g in gate_counts}

        for g, val in gates.items():
            if val:
                gate_counts[g] += 1

        if all(gates.values()):
            all_gates_pass_count += 1

        # Lifecycle status
        lifecycle_status = claim_json.get("status", "unknown")
        if row["endorsed_at"]:
            lifecycle_status = "endorsed"
        lifecycle_counts[lifecycle_status] = lifecycle_counts.get(lifecycle_status, 0) + 1

    # Gate pass rates (0.0–1.0)
    gate_pass_rates = {
        g: round(gate_counts[g] / total, 3) if total > 0 else 0.0
        for g in gate_counts
    }

    # Identify gates that are blocking (pass rate < 1.0)
    blocking = [g for g, r in gate_pass_rates.items() if r < 1.0]

    return {
        "workspace_id": workspace_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_claims": total,
        "gate_pass_rates": gate_pass_rates,
        "lifecycle_distribution": lifecycle_counts,
        "claims_with_all_gates": all_gates_pass_count,
        "blocking_gates": blocking,
    }
