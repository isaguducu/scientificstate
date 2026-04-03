"""Workspace CRUD endpoints.

GET  /workspaces            — list all workspaces
POST /workspaces            — create workspace
GET  /workspaces/{id}       — get workspace by id (404 if not found)

Response shapes match daemon-api.yaml WorkspaceSummary / WorkspaceDetail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.storage.schema import get_db_path

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class WorkspaceSummary(BaseModel):
    workspace_id: str
    name: str
    created_at: str


class WorkspaceDetail(BaseModel):
    workspace_id: str
    name: str
    description: str | None = None
    created_at: str
    updated_at: str
    ssv_count: int = 0
    claim_count: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspace_id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "ssv_count": 0,
        "claim_count": 0,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=WorkspaceDetail, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: CreateWorkspaceRequest) -> Any:
    workspace_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            "INSERT INTO workspaces (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (workspace_id, body.name, now, now),
        )
        await db.commit()
    return {
        "workspace_id": workspace_id,
        "name": body.name,
        "created_at": now,
        "updated_at": now,
        "ssv_count": 0,
        "claim_count": 0,
    }


@router.get("", response_model=list[WorkspaceSummary])
async def list_workspaces() -> Any:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, created_at FROM workspaces ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
    return [
        {"workspace_id": r["id"], "name": r["name"], "created_at": r["created_at"]}
        for r in rows
    ]


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(workspace_id: str) -> Any:
    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found: {workspace_id}",
        )
    return _row_to_detail(dict(row))
