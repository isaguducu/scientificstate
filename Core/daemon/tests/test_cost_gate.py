"""Cost gate enforcement tests — mandatory pre-run checks."""
import asyncio

import pytest
import aiosqlite


# ---------------------------------------------------------------------------
# Helper: create test DB with QPU tables
# ---------------------------------------------------------------------------

async def _create_test_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS qpu_price_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                backend_name TEXT NOT NULL,
                price_per_shot REAL,
                price_per_task REAL,
                currency TEXT NOT NULL DEFAULT 'USD',
                source TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                expires_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS qpu_usage_log (
                log_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                institution_id TEXT,
                provider TEXT NOT NULL,
                backend_name TEXT NOT NULL,
                shots INTEGER NOT NULL,
                estimated_cost TEXT NOT NULL,
                actual_cost TEXT,
                status TEXT NOT NULL DEFAULT 'estimated',
                price_snapshot_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS qpu_quotas (
                quota_id TEXT PRIMARY KEY,
                institution_id TEXT,
                user_id TEXT,
                period TEXT NOT NULL,
                shot_limit INTEGER NOT NULL,
                shot_used INTEGER NOT NULL DEFAULT 0,
                budget_limit TEXT,
                budget_used TEXT DEFAULT '{"amount": 0}',
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()


async def _seed_price(db_path: str, provider="ibm_quantum", backend="ibm_brisbane",
                      price_per_shot=0.01):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO qpu_price_snapshots
               (snapshot_id, provider, backend_name, price_per_shot,
                currency, source, effective_at)
               VALUES (?, ?, ?, ?, 'USD', 'manual', datetime('now', '-1 hour'))""",
            ("snap-1", provider, backend, price_per_shot),
        )
        await db.commit()


async def _seed_quota(db_path: str, user_id="user-1", shot_limit=10000, shot_used=0):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO qpu_quotas
               (quota_id, user_id, period, shot_limit, shot_used,
                period_start, period_end)
               VALUES (?, ?, 'monthly', ?, ?,
                       datetime('now', '-1 day'), datetime('now', '+30 days'))""",
            ("quota-1", user_id, shot_limit, shot_used),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestCostGate:

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_cost_gate_blocks_unknown_price(self, tmp_path):
        """No price snapshot -> run blocked (403)."""
        from src.runner.cost_gate import enforce_cost_gate, CostGateError

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                with pytest.raises(CostGateError) as exc_info:
                    await enforce_cost_gate(
                        db=db, run_id="run-1", user_id="user-1",
                        provider="ibm_quantum", backend_name="ibm_brisbane",
                        shots=1024,
                    )
                assert exc_info.value.http_status == 403

        self._run(_test())

    def test_cost_gate_blocks_hard_cap(self, tmp_path):
        """Estimated cost > hard cap -> blocked (403)."""
        from src.runner.cost_gate import enforce_cost_gate, CostGateError

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))
        self._run(_seed_price(db_path, price_per_shot=100.0))  # Very expensive

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                with pytest.raises(CostGateError) as exc_info:
                    await enforce_cost_gate(
                        db=db, run_id="run-1", user_id="user-1",
                        provider="ibm_quantum", backend_name="ibm_brisbane",
                        shots=1024,
                    )
                assert exc_info.value.http_status == 403
                assert "cap" in str(exc_info.value).lower()

        self._run(_test())

    def test_cost_gate_blocks_quota_exceeded(self, tmp_path):
        """Shot quota exceeded -> blocked (403)."""
        from src.runner.cost_gate import enforce_cost_gate, CostGateError

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))
        self._run(_seed_price(db_path))
        self._run(_seed_quota(db_path, shot_limit=100, shot_used=90))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                with pytest.raises(CostGateError) as exc_info:
                    await enforce_cost_gate(
                        db=db, run_id="run-1", user_id="user-1",
                        provider="ibm_quantum", backend_name="ibm_brisbane",
                        shots=1024,
                    )
                assert exc_info.value.http_status == 403

        self._run(_test())

    def test_cost_gate_blocks_duplicate_run_id(self, tmp_path):
        """Duplicate run_id -> 409 Conflict."""
        from src.runner.cost_gate import enforce_cost_gate, CostGateError

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))
        self._run(_seed_price(db_path))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                # First run OK
                await enforce_cost_gate(
                    db=db, run_id="run-dup", user_id="user-1",
                    provider="ibm_quantum", backend_name="ibm_brisbane",
                    shots=100,
                )
                # Same run_id -> 409
                with pytest.raises(CostGateError) as exc_info:
                    await enforce_cost_gate(
                        db=db, run_id="run-dup", user_id="user-1",
                        provider="ibm_quantum", backend_name="ibm_brisbane",
                        shots=100,
                    )
                assert exc_info.value.http_status == 409

        self._run(_test())

    def test_cost_gate_passes_valid_run(self, tmp_path):
        """All checks pass -> returns estimate."""
        from src.runner.cost_gate import enforce_cost_gate

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))
        self._run(_seed_price(db_path, price_per_shot=0.01))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                estimate = await enforce_cost_gate(
                    db=db, run_id="run-ok", user_id="user-1",
                    provider="ibm_quantum", backend_name="ibm_brisbane",
                    shots=100,
                )
                assert "min" in estimate
                assert "max" in estimate
                assert estimate["shots"] == 100

        self._run(_test())

    def test_cost_gate_logs_estimate(self, tmp_path):
        """Usage log should have INSERT after cost gate pass."""
        from src.runner.cost_gate import enforce_cost_gate

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))
        self._run(_seed_price(db_path))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                await enforce_cost_gate(
                    db=db, run_id="run-log", user_id="user-1",
                    provider="ibm_quantum", backend_name="ibm_brisbane",
                    shots=100,
                )
                cursor = await db.execute(
                    "SELECT * FROM qpu_usage_log WHERE run_id = ?", ("run-log",)
                )
                row = await cursor.fetchone()
                assert row is not None

        self._run(_test())

    def test_record_completion_updates_status(self, tmp_path):
        """Post-execution should update status."""
        from src.runner.cost_gate import enforce_cost_gate, record_completion

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))
        self._run(_seed_price(db_path))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                await enforce_cost_gate(
                    db=db, run_id="run-complete", user_id="user-1",
                    provider="ibm_quantum", backend_name="ibm_brisbane",
                    shots=100,
                )
                await record_completion(
                    db=db, run_id="run-complete",
                    actual_cost={"amount": 1.0, "currency": "USD"},
                    status="completed",
                )
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT status FROM qpu_usage_log WHERE run_id = ?",
                    ("run-complete",),
                )
                row = await cursor.fetchone()
                assert row["status"] == "completed"

        self._run(_test())

    def test_price_snapshot_versioning(self, tmp_path):
        """Should select most recent active price snapshot."""
        from src.runner.cost_gate import get_active_price_snapshot

        db_path = str(tmp_path / "test.db")
        self._run(_create_test_db(db_path))

        async def _test():
            async with aiosqlite.connect(db_path) as db:
                # Insert old price
                await db.execute(
                    """INSERT INTO qpu_price_snapshots
                       (snapshot_id, provider, backend_name, price_per_shot,
                        currency, source, effective_at)
                       VALUES (?, ?, ?, ?, 'USD', 'manual', datetime('now', '-2 hours'))""",
                    ("snap-old", "ibm_quantum", "ibm_brisbane", 0.005),
                )
                # Insert new price
                await db.execute(
                    """INSERT INTO qpu_price_snapshots
                       (snapshot_id, provider, backend_name, price_per_shot,
                        currency, source, effective_at)
                       VALUES (?, ?, ?, ?, 'USD', 'manual', datetime('now', '-1 hour'))""",
                    ("snap-new", "ibm_quantum", "ibm_brisbane", 0.01),
                )
                await db.commit()

                snapshot = await get_active_price_snapshot(db, "ibm_quantum", "ibm_brisbane")
                assert snapshot is not None
                assert snapshot["snapshot_id"] == "snap-new"
                assert snapshot["price_per_shot"] == 0.01

        self._run(_test())
