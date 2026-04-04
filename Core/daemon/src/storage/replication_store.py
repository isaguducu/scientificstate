"""Daemon-side DB persistence for ReplicationEngine.

Uses aiosqlite with ? placeholders (daemon DB pattern).
Provides a sync wrapper that the framework engine can use.
"""
import uuid
import json
import asyncio
import logging



import aiosqlite

logger = logging.getLogger(__name__)


class DaemonReplicationStore:
    """Implements ReplicationStore protocol with aiosqlite.

    Methods are sync wrappers around async aiosqlite calls.
    Uses asyncio event loop from daemon context.
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _run(self, coro):
        """Run async coroutine synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def save_request(self, request: dict) -> str:
        return self._run(self._save_request(request))

    async def _save_request(self, request: dict) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO replication_requests
                   (request_id, claim_id, source_ssv_id, source_institution_id,
                    target_institution_id, method_id, compute_class,
                    tolerance_abs, tolerance_rel, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (request["request_id"], request["claim_id"], request["source_ssv_id"],
                 request["source_institution_id"], request["target_institution_id"],
                 request["method_id"], request["compute_class"],
                 request["tolerance_abs"], request["tolerance_rel"], request["status"]),
            )
            await db.commit()
        return request["request_id"]

    def save_result(self, result: dict) -> str:
        return self._run(self._save_result(result))

    async def _save_result(self, result: dict) -> str:
        result_id = str(uuid.uuid4())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO replication_results
                   (result_id, request_id, target_ssv_id, comparison_report,
                    confidence_score, status, institution_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (result_id, result["request_id"], result["target_ssv_id"],
                 json.dumps(result.get("comparison_report", {})),
                 result.get("confidence_score", 0.0),
                 result["status"], result["institution_id"]),
            )
            # Update request status
            await db.execute(
                "UPDATE replication_requests SET status = ? WHERE request_id = ?",
                (result["status"], result["request_id"]),
            )
            await db.commit()
        return result_id

    def get_requests_by_claim(self, claim_id: str) -> list[dict]:
        return self._run(self._get_requests_by_claim(claim_id))

    async def _get_requests_by_claim(self, claim_id: str) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM replication_requests WHERE claim_id = ?",
                (claim_id,),
            )
            return [dict(row) for row in await cursor.fetchall()]

    def get_results_by_request(self, request_id: str) -> list[dict]:
        return self._run(self._get_results_by_request(request_id))

    async def _get_results_by_request(self, request_id: str) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM replication_results WHERE request_id = ?",
                (request_id,),
            )
            return [dict(row) for row in await cursor.fetchall()]

    def update_request_status(self, request_id: str, status: str) -> None:
        self._run(self._update_request_status(request_id, status))

    async def _update_request_status(self, request_id: str, status: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE replication_requests SET status = ? WHERE request_id = ?",
                (status, request_id),
            )
            await db.commit()
