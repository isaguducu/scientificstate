"""Claim view and human endorsement endpoints (P7 — H1_human gate).

GET   /claims/{claim_id}              — claim detail + endorsement state
GET   /workspaces/{workspace_id}/claims — workspace claim list
PATCH /claims/{claim_id}/endorse      — log human endorsement (no state mutation)
GET   /runs/{run_id}/claim            — fetch the claim produced by a run
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.storage.schema import get_db_path

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
    return {
        "claim_id": row["claim_id"],
        "run_id": row["run_id"],
        "claim_json": json.loads(row["claim_json"] or "{}"),
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
    columns (added in Phase 9 migration) are written.
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

        await db.execute(
            """
            UPDATE claims
            SET endorsed_at = ?, endorsed_by = ?
            WHERE claim_id = ?
            """,
            (now, body.researcher_id, claim_id),
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
