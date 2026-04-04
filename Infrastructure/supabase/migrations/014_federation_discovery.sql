-- 014_federation_discovery.sql — Federated Discovery tables
-- Phase 7: Discovery mirrors, cross-institutional endorsed claim sync, federated search
-- Depends on: 003_federation.sql (institutions, registry_mirrors)

-- ============================================================
-- 1. Discovery Mirrors — federated discovery endpoints
-- ============================================================
CREATE TABLE discovery_mirrors (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id          UUID NOT NULL REFERENCES institutions(id),
  mirror_url              TEXT NOT NULL,
  mirror_name             TEXT NOT NULL,
  public_key_ed25519      TEXT NOT NULL,  -- 64-char hex encoded Ed25519 public key
  sync_status             TEXT NOT NULL DEFAULT 'pending'
    CHECK (sync_status IN ('pending', 'active', 'syncing', 'error', 'disabled')),
  trusted                 BOOLEAN NOT NULL DEFAULT false,
  last_sync_at            TIMESTAMPTZ,
  last_sync_claim_count   INTEGER DEFAULT 0,
  sync_interval_minutes   INTEGER NOT NULL DEFAULT 60,
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now(),
  UNIQUE(institution_id, mirror_url)
);

-- ============================================================
-- 2. Federated Endorsed Claims — claims synced from remote mirrors
-- ============================================================
CREATE TABLE federated_endorsed_claims (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id                TEXT NOT NULL,
  source_institution_id   UUID NOT NULL REFERENCES institutions(id),
  source_mirror_id        UUID REFERENCES discovery_mirrors(id),
  domain_id               TEXT NOT NULL,
  title                   TEXT NOT NULL,
  researcher_orcid        TEXT,
  gate_status             JSONB NOT NULL DEFAULT '{}',
  ssv_hash                TEXT NOT NULL,
  ssv_signature           TEXT NOT NULL,
  endorsed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  synced_at               TIMESTAMPTZ DEFAULT now(),
  verified                BOOLEAN NOT NULL DEFAULT false,
  verification_error      TEXT,
  UNIQUE(claim_id, source_institution_id)
);

-- ============================================================
-- 3. Federation Sync Log — audit trail for sync operations
-- ============================================================
CREATE TABLE federation_sync_log (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mirror_id               UUID NOT NULL REFERENCES discovery_mirrors(id),
  direction               TEXT NOT NULL CHECK (direction IN ('push', 'pull')),
  claims_synced           INTEGER NOT NULL DEFAULT 0,
  claims_rejected         INTEGER NOT NULL DEFAULT 0,
  started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at            TIMESTAMPTZ,
  status                  TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'completed', 'failed')),
  error_detail            TEXT
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_discovery_mirrors_institution ON discovery_mirrors (institution_id);
CREATE INDEX idx_discovery_mirrors_status ON discovery_mirrors (sync_status);

CREATE INDEX idx_fed_claims_domain ON federated_endorsed_claims (domain_id);
CREATE INDEX idx_fed_claims_source_inst ON federated_endorsed_claims (source_institution_id);
CREATE INDEX idx_fed_claims_endorsed_at ON federated_endorsed_claims (endorsed_at DESC);
CREATE INDEX idx_fed_claims_verified ON federated_endorsed_claims (verified) WHERE verified = true;

CREATE INDEX idx_fed_sync_log_mirror ON federation_sync_log (mirror_id);
CREATE INDEX idx_fed_sync_log_status ON federation_sync_log (status);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE discovery_mirrors ENABLE ROW LEVEL SECURITY;
ALTER TABLE federated_endorsed_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE federation_sync_log ENABLE ROW LEVEL SECURITY;

-- Admin manages mirrors (institution admins via institution_members check)
CREATE POLICY "Authenticated read discovery mirrors" ON discovery_mirrors
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Admin manage discovery mirrors" ON discovery_mirrors
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM institution_members im
      WHERE im.institution_id = discovery_mirrors.institution_id
        AND im.orcid = auth.jwt()->>'orcid'
        AND im.role = 'admin'
    )
  );

-- All authenticated users can read verified federated claims
CREATE POLICY "Public read verified federated claims" ON federated_endorsed_claims
  FOR SELECT USING (true);

-- System (service_role) inserts federated claims during sync
CREATE POLICY "Service insert federated claims" ON federated_endorsed_claims
  FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service update federated claims" ON federated_endorsed_claims
  FOR UPDATE USING (auth.role() = 'service_role');

-- Sync log readable by authenticated users, writable by service
CREATE POLICY "Authenticated read sync log" ON federation_sync_log
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Service insert sync log" ON federation_sync_log
  FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service update sync log" ON federation_sync_log
  FOR UPDATE USING (auth.role() = 'service_role');
