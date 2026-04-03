"""
SQLite schema — immutable ingest store.

Design principle (P1 — Immutability):
- Raw data records are NEVER updated or deleted.
- All writes are INSERT ONLY (no UPDATE, no DELETE).
- Provenance chain is append-only.

All tables use TEXT primary keys (UUID strings) for portability.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger("scientificstate.daemon.storage")

# Database lives alongside the package in a local data directory.
# In production this would be configurable via settings.
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "daemon.db"


def _get_db_path() -> Path:
    path = _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_CREATE_INGEST_EVENTS = """
CREATE TABLE IF NOT EXISTS ingest_events (
    -- Immutable record of every dataset ingest attempt.
    -- P1: no UPDATE or DELETE ever touches this table.
    ingest_id     TEXT PRIMARY KEY,
    domain        TEXT NOT NULL,
    dataset_name  TEXT NOT NULL,
    format        TEXT NOT NULL,
    source_path   TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    timestamp     TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_CREATE_DOMAINS = """
CREATE TABLE IF NOT EXISTS domains (
    -- Registered domain plugins.
    -- Refreshed on each daemon start via discover_and_register().
    name         TEXT PRIMARY KEY,
    version      TEXT NOT NULL DEFAULT 'unknown',
    description  TEXT NOT NULL DEFAULT '',
    methods_json TEXT NOT NULL DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'active',
    registered_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_CREATE_COMPUTE_JOBS = """
CREATE TABLE IF NOT EXISTS compute_jobs (
    -- Immutable log of all compute jobs submitted.
    job_id       TEXT PRIMARY KEY,
    domain       TEXT NOT NULL,
    method       TEXT NOT NULL,
    backend_kind TEXT NOT NULL,
    params_json  TEXT NOT NULL DEFAULT '{}',
    input_refs   TEXT NOT NULL DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'queued',
    result_json  TEXT,
    error        TEXT,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    completed_at TEXT
);
"""

_ALL_DDL = [_CREATE_INGEST_EVENTS, _CREATE_DOMAINS, _CREATE_COMPUTE_JOBS]


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables if they don't exist. Idempotent."""
    db_path = _get_db_path()
    logger.info("Initialising SQLite at: %s", db_path)
    async with aiosqlite.connect(db_path) as db:
        for ddl in _ALL_DDL:
            await db.execute(ddl)
        # Enable WAL mode for concurrent reads during writes
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.commit()
    logger.info("SQLite schema ready.")


# ---------------------------------------------------------------------------
# Write helpers (INSERT ONLY — immutability enforced)
# ---------------------------------------------------------------------------


async def record_ingest_event(
    ingest_id: str,
    domain: str,
    dataset_name: str,
    format: str,
    source_path: str | None,
    metadata: dict[str, Any],
    timestamp: str,
) -> None:
    """
    Immutably record an ingest event.
    Raises on conflict — each ingest_id must be globally unique.
    """
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO ingest_events
                (ingest_id, domain, dataset_name, format, source_path, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ingest_id,
                domain,
                dataset_name,
                format,
                source_path,
                json.dumps(metadata),
                timestamp,
            ),
        )
        await db.commit()


async def upsert_domain(
    name: str,
    version: str,
    description: str,
    methods: list[str],
    status: str = "active",
) -> None:
    """
    Register or refresh a domain record.
    This is NOT raw scientific data — domain registry updates are allowed.
    """
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO domains (name, version, description, methods_json, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                version = excluded.version,
                description = excluded.description,
                methods_json = excluded.methods_json,
                status = excluded.status,
                registered_at = datetime('now', 'utc')
            """,
            (name, version, description, json.dumps(methods), status),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def list_ingest_events(domain: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List recent ingest events, optionally filtered by domain."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        if domain:
            cursor = await db.execute(
                "SELECT * FROM ingest_events WHERE domain=? ORDER BY created_at DESC LIMIT ?",
                (domain, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM ingest_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
