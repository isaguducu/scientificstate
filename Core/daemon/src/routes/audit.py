"""Audit log endpoints — append-only event trail.

POST /audit/log      — append an audit entry (INSERT-only)
GET  /audit/log      — query entries with filters + cursor pagination
GET  /audit/log/actions — list valid action types

Design: INSERT-only — no UPDATE, no DELETE ever touches audit_log.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.storage.schema import get_db_path

router = APIRouter(prefix="/audit", tags=["audit"])

# ---------------------------------------------------------------------------
# Valid enumerations
# ---------------------------------------------------------------------------

VALID_ACTIONS = frozenset([
    "claim.create", "claim.endorse", "claim.contest", "claim.retract",
    "citation.create", "citation.remove",
    "replication.submit", "replication.complete", "replication.fail",
    "module.publish", "module.deprecate",
    "auth.login", "auth.logout", "auth.saml_login",
    "gdpr.export_request", "gdpr.delete_request", "gdpr.delete_complete",
    "federation.sync_push", "federation.sync_pull",
    "run.create", "run.complete", "run.fail",
])

VALID_RESOURCE_TYPES = frozenset([
    "claim", "citation", "replication", "module",
    "session", "gdpr_request", "federation_sync", "compute_run",
])

VALID_ACTOR_TYPES = frozenset(["user", "system", "federation", "daemon"])

# ---------------------------------------------------------------------------
# DDL — local SQLite mirror of the Supabase audit_log
# ---------------------------------------------------------------------------

_CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    id            TEXT PRIMARY KEY,
    actor_id      TEXT,
    actor_type    TEXT NOT NULL DEFAULT 'system',
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    ip_address    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log (actor_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action);",
    "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log (resource_type, resource_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at DESC);",
]


async def _ensure_table() -> None:
    """Create audit_log table if it doesn't exist."""
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(_CREATE_AUDIT_LOG)
        for idx in _CREATE_INDEXES:
            await db.execute(idx)
        await db.commit()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    actor_id: Optional[str] = None
    actor_type: str = "system"
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    ip_address: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: str
    actor_id: Optional[str]
    actor_type: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    metadata: dict
    ip_address: Optional[str]
    created_at: str


# ---------------------------------------------------------------------------
# POST /audit/log — append entry (INSERT-only)
# ---------------------------------------------------------------------------


@router.post("/log", status_code=201)
async def append_audit_entry(entry: AuditLogEntry) -> dict:
    """Append an audit log entry. INSERT-only — never updates or deletes."""
    # Validate action
    if entry.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{entry.action}'. Must be one of: {sorted(VALID_ACTIONS)}",
        )

    # Validate resource_type
    if entry.resource_type not in VALID_RESOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resource_type '{entry.resource_type}'. Must be one of: {sorted(VALID_RESOURCE_TYPES)}",
        )

    # Validate actor_type
    if entry.actor_type not in VALID_ACTOR_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid actor_type '{entry.actor_type}'. Must be one of: {sorted(VALID_ACTOR_TYPES)}",
        )

    await _ensure_table()

    entry_id = str(uuid.uuid4())
    created_at = datetime.now(tz=timezone.utc).isoformat()

    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO audit_log
                (id, actor_id, actor_type, action, resource_type, resource_id, metadata_json, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                entry.actor_id,
                entry.actor_type,
                entry.action,
                entry.resource_type,
                entry.resource_id,
                json.dumps(entry.metadata),
                entry.ip_address,
                created_at,
            ),
        )
        await db.commit()

    return {
        "id": entry_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "created_at": created_at,
    }


# ---------------------------------------------------------------------------
# GET /audit/log — query with filters + cursor pagination
# ---------------------------------------------------------------------------


@router.get("/log")
async def query_audit_log(
    action: Optional[str] = Query(None, description="Filter by action"),
    resource_type: Optional[str] = Query(None, description="Filter by resource_type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor_id"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    cursor: Optional[str] = Query(None, description="Cursor (created_at ISO) for pagination"),
) -> dict:
    """Query audit log entries with optional filters and cursor pagination."""
    await _ensure_table()

    conditions: list[str] = []
    params: list = []

    if action:
        conditions.append("action = ?")
        params.append(action)
    if resource_type:
        conditions.append("resource_type = ?")
        params.append(resource_type)
    if actor_id:
        conditions.append("actor_id = ?")
        params.append(actor_id)
    if cursor:
        conditions.append("created_at < ?")
        params.append(cursor)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    query = f"SELECT * FROM audit_log {where} ORDER BY created_at DESC LIMIT ?"  # noqa: S608
    params.append(limit)

    async with aiosqlite.connect(get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()

    entries = []
    for row in rows:
        r = dict(row)
        r["metadata"] = json.loads(r.pop("metadata_json", "{}"))
        entries.append(r)

    next_cursor = entries[-1]["created_at"] if entries else None

    return {
        "entries": entries,
        "count": len(entries),
        "next_cursor": next_cursor,
    }


# ---------------------------------------------------------------------------
# GET /audit/log/actions — list valid action types
# ---------------------------------------------------------------------------


@router.get("/log/actions")
async def list_actions() -> dict:
    """List all valid audit action types."""
    return {
        "actions": sorted(VALID_ACTIONS),
        "resource_types": sorted(VALID_RESOURCE_TYPES),
        "actor_types": sorted(VALID_ACTOR_TYPES),
    }
