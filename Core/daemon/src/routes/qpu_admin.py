"""QPU administration routes — quota management, usage reports, price snapshots, broker grants."""
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qpu", tags=["qpu-admin"])


# --- Models ---

class QuotaCreate(BaseModel):
    institution_id: str | None = None
    user_id: str | None = None
    period: str = Field(..., pattern="^(daily|monthly)$")
    shot_limit: int
    budget_limit: dict | None = None
    period_start: str
    period_end: str


class PriceSnapshotCreate(BaseModel):
    provider: str = Field(..., pattern="^(ibm_quantum|ionq)$")
    backend_name: str
    price_per_shot: float | None = None
    price_per_task: float | None = None
    currency: str = "USD"
    source: str = Field(..., pattern="^(manual|api_fetch|provider_docs)$")
    effective_at: str
    expires_at: str | None = None


class BrokerGrantRequest(BaseModel):
    user_id: str
    institution_id: str
    provider: str = Field(..., pattern="^(ibm_quantum|ionq)$")
    max_shots: int
    expires_in_minutes: int = 60


# --- Helpers ---

def _get_db(request: Request):
    return request.app.state.db


# --- Routes ---

@router.post("/quotas")
async def create_quota(body: QuotaCreate, request: Request):
    """Create or update quota (institution admin only)."""
    db = _get_db(request)
    quota_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO qpu_quotas
           (quota_id, institution_id, user_id, period, shot_limit,
            budget_limit, period_start, period_end)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (quota_id, body.institution_id, body.user_id, body.period,
         body.shot_limit, json.dumps(body.budget_limit) if body.budget_limit else None,
         body.period_start, body.period_end),
    )
    await db.commit()
    return {"quota_id": quota_id, "status": "created"}


@router.get("/quotas")
async def get_quotas(request: Request, user_id: str | None = None, institution_id: str | None = None):
    """Get quota status."""
    db = _get_db(request)
    db.row_factory = aiosqlite.Row
    if user_id:
        cursor = await db.execute(
            "SELECT * FROM qpu_quotas WHERE user_id = ? AND period_end > datetime('now')",
            (user_id,),
        )
    elif institution_id:
        cursor = await db.execute(
            "SELECT * FROM qpu_quotas WHERE institution_id = ? AND period_end > datetime('now')",
            (institution_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM qpu_quotas WHERE period_end > datetime('now')"
        )
    rows = await cursor.fetchall()
    return {"quotas": [dict(r) for r in rows]}


@router.get("/usage")
async def get_usage(request: Request, user_id: str | None = None, institution_id: str | None = None):
    """Usage report (user/institution based, date filter)."""
    db = _get_db(request)
    db.row_factory = aiosqlite.Row
    if user_id:
        cursor = await db.execute(
            "SELECT * FROM qpu_usage_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user_id,),
        )
    elif institution_id:
        cursor = await db.execute(
            "SELECT * FROM qpu_usage_log WHERE institution_id = ? ORDER BY created_at DESC LIMIT 100",
            (institution_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM qpu_usage_log ORDER BY created_at DESC LIMIT 100"
        )
    rows = await cursor.fetchall()
    return {"usage": [dict(r) for r in rows]}


@router.get("/usage/summary")
async def get_usage_summary(request: Request, user_id: str | None = None):
    """Monthly summary (shots, cost, provider breakdown)."""
    db = _get_db(request)
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        """SELECT provider, COUNT(*) as run_count, SUM(shots) as total_shots,
           status
           FROM qpu_usage_log
           WHERE (user_id = ? OR ? IS NULL)
             AND created_at >= datetime('now', '-30 days')
           GROUP BY provider, status""",
        (user_id, user_id),
    )
    rows = await cursor.fetchall()
    return {"summary": [dict(r) for r in rows]}


@router.post("/price-snapshots")
async def create_price_snapshot(body: PriceSnapshotCreate, request: Request):
    """Add price snapshot (admin only). INSERT-only, immutable."""
    db = _get_db(request)
    snapshot_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO qpu_price_snapshots
           (snapshot_id, provider, backend_name, price_per_shot, price_per_task,
            currency, source, effective_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (snapshot_id, body.provider, body.backend_name, body.price_per_shot,
         body.price_per_task, body.currency, body.source,
         body.effective_at, body.expires_at),
    )
    await db.commit()
    return {"snapshot_id": snapshot_id, "status": "created"}


@router.get("/price-snapshots/active")
async def get_active_prices(request: Request):
    """Get active price snapshots for all providers/backends."""
    db = _get_db(request)
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        """SELECT * FROM qpu_price_snapshots
           WHERE effective_at <= datetime('now')
             AND (expires_at IS NULL OR expires_at > datetime('now'))
           ORDER BY provider, backend_name, effective_at DESC"""
    )
    rows = await cursor.fetchall()
    return {"prices": [dict(r) for r in rows]}


@router.post("/broker/grant")
async def create_broker_grant(body: BrokerGrantRequest, request: Request):
    """Create signed grant for institutional broker (Tier 2).

    Grant is short-lived (max 1 hour), single-use.
    Institution admin creates grant for user -> user submits to broker.
    """
    grant_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=min(body.expires_in_minutes, 60))

    grant = {
        "grant_id": grant_id,
        "user_id": body.user_id,
        "institution_id": body.institution_id,
        "provider": body.provider,
        "max_shots": body.max_shots,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # TODO: Ed25519 sign the grant with institution admin key
    return grant
