-- ScientificState SQLite schema v1
-- Authoritative source: Main_Source_desktop.md §5.1
-- Constitutional constraints: P1 (immutability), P2 (SSV immutability), P9 (reversibility)
-- All PRIMARY KEYs are TEXT (UUID strings) for portability.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Workspaces
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspaces (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  created_at  TEXT NOT NULL,  -- ISO 8601
  updated_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Raw datasets (P1 — immutable)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
  id            TEXT PRIMARY KEY,
  workspace_id  TEXT NOT NULL REFERENCES workspaces(id),
  filename      TEXT NOT NULL,
  content_hash  TEXT NOT NULL,  -- SHA-256, P1 immutability proof
  file_size     INTEGER NOT NULL,
  mime_type     TEXT,
  ingest_at     TEXT NOT NULL,
  profile_json  TEXT,           -- automatic data profile (nullable)
  UNIQUE(content_hash)          -- same file cannot be imported twice
);

-- ---------------------------------------------------------------------------
-- Scientific questions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
  id            TEXT PRIMARY KEY,
  workspace_id  TEXT NOT NULL REFERENCES workspaces(id),
  text          TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  dataset_ids   TEXT NOT NULL   -- JSON array of dataset IDs
);

-- ---------------------------------------------------------------------------
-- Assumptions (P3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assumptions (
  id            TEXT PRIMARY KEY,
  question_id   TEXT NOT NULL REFERENCES questions(id),
  text          TEXT NOT NULL,
  source        TEXT NOT NULL,  -- "user" | "cmre_suggested" | "domain_default"
  accepted      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Runs (compute executions)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
  id              TEXT PRIMARY KEY,
  question_id     TEXT NOT NULL REFERENCES questions(id),
  method_id       TEXT NOT NULL,
  status          TEXT NOT NULL,  -- "pending" | "running" | "completed" | "failed" | "cancelled"
  compute_class   TEXT NOT NULL DEFAULT 'classical',  -- "classical" | "quantum_sim" | "quantum_hw" | "hybrid"
  backend_id      TEXT,
  started_at      TEXT,
  completed_at    TEXT,
  ssv_id          TEXT REFERENCES ssvs(id),
  capsule_id      TEXT REFERENCES capsules(id),
  error_json      TEXT           -- null if success
);

-- ---------------------------------------------------------------------------
-- SSV instances (immutable — P2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ssvs (
  id              TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(id),
  parent_ssv_id   TEXT REFERENCES ssvs(id),  -- P9 reversibility
  version         INTEGER NOT NULL,
  d_ref           TEXT NOT NULL,  -- data reference
  i_json          TEXT NOT NULL,  -- interpretation
  a_json          TEXT NOT NULL,  -- assumptions (P3)
  t_json          TEXT NOT NULL,  -- transforms
  r_json          TEXT NOT NULL,  -- results
  u_json          TEXT NOT NULL,  -- uncertainty (P4)
  v_json          TEXT NOT NULL,  -- validity domains (P5)
  p_json          TEXT NOT NULL,  -- provenance + execution_witness
  created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Claims (lifecycle managed)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claims (
  id              TEXT PRIMARY KEY,
  question_id     TEXT NOT NULL REFERENCES questions(id),
  ssv_id          TEXT NOT NULL REFERENCES ssvs(id),
  status          TEXT NOT NULL,  -- "draft" | "under_review" | "provisionally_supported" | "endorsable" | "endorsed" | "contested" | "retracted"
  gate_e1         BOOLEAN,       -- evidence threshold met
  gate_u1         BOOLEAN,       -- uncertainty acceptable
  gate_v1         BOOLEAN,       -- validity scope defined
  gate_c1         BOOLEAN,       -- no unresolved contradiction
  gate_h1         BOOLEAN,       -- human endorsement received
  endorser_id     TEXT,
  endorsed_at     TEXT,
  created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Capsules (immutable run artifacts)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS capsules (
  id              TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(id),
  content_hash    TEXT NOT NULL,
  artifact_path   TEXT NOT NULL,  -- content-addressed filesystem path
  rocrate_path    TEXT,           -- RO-Crate metadata path (nullable)
  created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Events (lineage / audit — P9)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
  id              TEXT PRIMARY KEY,
  event_type      TEXT NOT NULL,  -- "ingest" | "run_start" | "run_complete" | "gate_eval" | "endorse" | "export" | "incident"
  entity_type     TEXT NOT NULL,  -- "dataset" | "run" | "ssv" | "claim" | "capsule"
  entity_id       TEXT NOT NULL,
  payload_json    TEXT,
  created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Incidents (P6 — negative knowledge)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents (
  id              TEXT PRIMARY KEY,
  run_id          TEXT REFERENCES runs(id),
  question_id     TEXT REFERENCES questions(id),
  incident_type   TEXT NOT NULL,  -- "failed_run" | "no_signal" | "ambiguous" | "contradiction"
  description     TEXT NOT NULL,
  created_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- CMRE resolutions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cmre_resolutions (
  id              TEXT PRIMARY KEY,
  question_id     TEXT NOT NULL REFERENCES questions(id),
  valid_methods   TEXT NOT NULL,        -- JSON array
  conditional_methods TEXT NOT NULL,    -- JSON array
  invalid_methods TEXT NOT NULL,        -- JSON array with reasons
  resolved_at     TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Governance policy
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS governance (
  id              TEXT PRIMARY KEY DEFAULT 'local',
  mode            TEXT NOT NULL DEFAULT 'sovereign',  -- "sovereign" | "managed"
  institution_id  TEXT,
  policy_json     TEXT,           -- gate thresholds, module trust list
  policy_synced_at TEXT,
  policy_expires_at TEXT
);
