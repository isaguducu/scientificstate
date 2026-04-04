"""
SQLite schema — immutable ingest store.

Design principle (P1 — Immutability):
- Raw data records are NEVER updated or deleted.
- All writes are INSERT ONLY (no UPDATE, no DELETE).
- Provenance chain is append-only.

All tables use TEXT primary keys (UUID strings) for portability.

Schema alignment note (Phase 4):
  This file defines the DAEMON's working tables (runs, ssvs, claims).
  schema.sql defines the REFERENCE schema (with FK constraints to
  questions, capsules, etc.).  Column naming intentionally differs:
    - schema.py uses ``run_id`` as PK (daemon-friendly, no FK dependency)
    - schema.sql uses ``id`` as PK with FK to questions (full relational model)
  Both share the table names ``runs``, ``ssvs``, ``claims`` since Phase 4.
  VIEW aliases (compute_runs, ssv_records, claim_records) preserve backward
  compatibility with pre-Phase 4 code.
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

_CREATE_WORKSPACES = """
CREATE TABLE IF NOT EXISTS workspaces (
    -- Research workspaces — mutable metadata (not raw scientific data).
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    -- Daemon-level compute run records (maps to /runs endpoint).
    -- Aligned with schema.sql naming (Phase 4 table alignment).
    run_id        TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL,
    domain_id     TEXT NOT NULL,
    method_id     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    started_at    TEXT,
    finished_at   TEXT,
    ssv_id        TEXT,
    result_json   TEXT,
    error_json    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_CREATE_SSVS = """
CREATE TABLE IF NOT EXISTS ssvs (
    -- Serialised SSV dicts produced by the pipeline (P2 — immutable).
    -- Aligned with schema.sql naming (Phase 4 table alignment).
    ssv_id      TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    ssv_json    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

_CREATE_CLAIMS = """
CREATE TABLE IF NOT EXISTS claims (
    -- Draft claims produced by the pipeline (immutable provenance record).
    -- Aligned with schema.sql naming (Phase 4 table alignment).
    claim_id    TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    claim_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
"""

# Backward-compat VIEW aliases (old names → new tables, no breaking change)
_VIEW_ALIASES = """
CREATE VIEW IF NOT EXISTS compute_runs AS SELECT * FROM runs;
CREATE VIEW IF NOT EXISTS ssv_records  AS SELECT * FROM ssvs;
CREATE VIEW IF NOT EXISTS claim_records AS SELECT * FROM claims;
"""

_ALL_DDL = [
    _CREATE_INGEST_EVENTS,
    _CREATE_DOMAINS,
    _CREATE_COMPUTE_JOBS,
    _CREATE_WORKSPACES,
    _CREATE_RUNS,
    _CREATE_SSVS,
    _CREATE_CLAIMS,
]


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables if they don't exist. Idempotent.

    Phase 4 table alignment: migrates old names (compute_runs, ssv_records,
    claim_records) to new names (runs, ssvs, claims) if they exist.
    Old names are preserved as VIEWs for backward compatibility.
    """
    db_path = _get_db_path()
    logger.info("Initialising SQLite at: %s", db_path)
    async with aiosqlite.connect(db_path) as db:
        # Enable WAL mode for concurrent reads during writes
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        # Phase 4 migration: old table → new table + VIEW alias
        await _migrate_table_if_needed(db, "compute_runs", "runs")
        await _migrate_table_if_needed(db, "ssv_records", "ssvs")
        await _migrate_table_if_needed(db, "claim_records", "claims")

        # Create all tables (IF NOT EXISTS — idempotent)
        for ddl in _ALL_DDL:
            await db.execute(ddl)

        # Create backward-compat VIEW aliases
        for stmt in _VIEW_ALIASES.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await db.execute(stmt)

        await db.commit()
    logger.info("SQLite schema ready.")


async def _migrate_table_if_needed(
    db: aiosqlite.Connection, old_name: str, new_name: str
) -> None:
    """Migrate data from old_name to new_name if old table exists as a real table.

    Steps: (1) INSERT ... SELECT, (2) DROP old table, (3) VIEW created later.
    Skips if old_name doesn't exist or is already a VIEW.
    """
    cur = await db.execute(
        "SELECT type FROM sqlite_master WHERE name = ?", (old_name,)
    )
    row = await cur.fetchone()
    if row is None:
        return  # old table doesn't exist — fresh DB
    if row[0] == "view":
        return  # already migrated — old name is a VIEW

    # old_name is a real table — migrate data
    logger.info("Migrating table %s → %s", old_name, new_name)

    # Ensure new table exists before copying
    # (DDL runs after this, but we need the target now)
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (new_name,),
    )
    if await cur.fetchone() is None:
        # Get column info from old table and create new one with same schema
        cur = await db.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{old_name}'")  # noqa: S608
        schema_row = await cur.fetchone()
        if schema_row:
            create_sql = schema_row[0].replace(old_name, new_name, 1)
            await db.execute(create_sql)

    await db.execute(f"INSERT OR IGNORE INTO {new_name} SELECT * FROM {old_name}")  # noqa: S608
    await db.execute(f"DROP TABLE {old_name}")  # noqa: S608
    logger.info("Migration complete: %s → %s", old_name, new_name)


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


def get_db_path() -> Path:
    """Return the daemon database path (public API for routes)."""
    return _get_db_path()


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
