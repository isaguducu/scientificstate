"""Mandatory QPU cost gate — runs BEFORE any quantum_hw/hybrid dispatch.

Cost gate is NOT optional. If price is unknown, run is BLOCKED.
If quota is exceeded, run is BLOCKED. If run_id already exists, 409.

Uses aiosqlite with ? placeholders (daemon DB pattern).
"""
import os
import json
import logging

import aiosqlite

logger = logging.getLogger(__name__)

RUN_HARD_CAP_USD = float(os.environ.get("QPU_RUN_HARD_CAP_USD", "50.0"))


class CostGateError(Exception):
    """Raised when cost gate blocks a run."""
    def __init__(self, message: str, http_status: int = 403):
        super().__init__(message)
        self.http_status = http_status


async def get_active_price_snapshot(db, provider: str, backend_name: str) -> dict | None:
    """Get most recent active price snapshot for provider+backend."""
    if db is None:
        return None
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        """SELECT * FROM qpu_price_snapshots
           WHERE provider = ? AND backend_name = ?
             AND effective_at <= datetime('now')
             AND (expires_at IS NULL OR expires_at > datetime('now'))
           ORDER BY effective_at DESC LIMIT 1""",
        (provider, backend_name),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


def estimate_run_cost(price_snapshot: dict, shots: int) -> dict:
    """Estimate min/max cost for a run."""
    unit = price_snapshot.get("price_per_shot") or 0.0
    task = price_snapshot.get("price_per_task") or 0.0
    cost = (unit * shots) + task
    return {
        "currency": price_snapshot.get("currency", "USD"),
        "min": round(cost * 0.9, 6),
        "max": round(cost * 1.1, 6),
        "unit_price": unit,
        "task_price": task,
        "shots": shots,
    }


async def enforce_cost_gate(
    db,
    run_id: str,
    user_id: str,
    provider: str,
    backend_name: str,
    shots: int,
    institution_id: str | None = None,
) -> dict:
    """Mandatory cost gate — called BEFORE QPU dispatch.

    Returns cost estimate dict on success.
    Raises CostGateError on failure.
    """
    # 1. Price snapshot — unknown price = BLOCK
    price = await get_active_price_snapshot(db, provider, backend_name)
    if price is None:
        raise CostGateError(
            f"QPU price unknown for {provider}/{backend_name} — run blocked",
            http_status=403,
        )

    # 2. Estimate cost
    estimate = estimate_run_cost(price, shots)

    # 3. Per-run hard cap
    if estimate["max"] > RUN_HARD_CAP_USD:
        raise CostGateError(
            f"Estimated cost ${estimate['max']:.2f} exceeds per-run cap ${RUN_HARD_CAP_USD}",
            http_status=403,
        )

    # 4. Quota check
    if db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM qpu_quotas
               WHERE (user_id = ? OR (institution_id = ? AND user_id IS NULL))
                 AND period_start <= datetime('now') AND period_end > datetime('now')
               ORDER BY user_id LIMIT 1""",
            (user_id, institution_id),
        )
        quota = await cursor.fetchone()
        if quota:
            if quota["shot_used"] + shots > quota["shot_limit"]:
                raise CostGateError(
                    f"Shot quota exceeded: {quota['shot_used']}/{quota['shot_limit']}",
                    http_status=403,
                )
            # Budget check
            if quota["budget_limit"]:
                budget_limit = json.loads(quota["budget_limit"]) if isinstance(quota["budget_limit"], str) else quota["budget_limit"]
                budget_used = json.loads(quota["budget_used"]) if isinstance(quota["budget_used"], str) else quota["budget_used"]
                if budget_used.get("amount", 0) + estimate["max"] > budget_limit.get("amount", float("inf")):
                    raise CostGateError(
                        "Budget quota exceeded",
                        http_status=403,
                    )

    # 5. Idempotency — run_id UNIQUE
    if db:
        cursor = await db.execute(
            "SELECT log_id FROM qpu_usage_log WHERE run_id = ?",
            (run_id,),
        )
        existing = await cursor.fetchone()
        if existing:
            raise CostGateError(
                f"Duplicate run_id {run_id} — double-charge prevention",
                http_status=409,
            )

    # 6. Log estimate (immutable INSERT)
    if db:
        await db.execute(
            """INSERT INTO qpu_usage_log
               (run_id, user_id, institution_id, provider, backend_name,
                shots, estimated_cost, status, price_snapshot_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'estimated', ?)""",
            (run_id, user_id, institution_id, provider, backend_name,
             shots, json.dumps(estimate), price.get("snapshot_id")),
        )
        await db.commit()

    logger.info(
        "Cost gate PASS: run=%s shots=%d est=$%.2f-%.2f",
        run_id, shots, estimate["min"], estimate["max"],
    )
    return estimate


async def record_completion(
    db, run_id: str, actual_cost: dict | None, status: str
):
    """Post-execution: update usage log status + actual cost."""
    if db:
        await db.execute(
            """UPDATE qpu_usage_log
               SET status = ?, actual_cost = ?
               WHERE run_id = ?""",
            (status, json.dumps(actual_cost) if actual_cost else None, run_id),
        )
        await db.commit()
