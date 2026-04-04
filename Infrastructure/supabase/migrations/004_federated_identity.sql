-- 004_federated_identity.sql — Federated Identity & Cross-Institutional Trust Chain
-- Phase 4: Identity federation, trust policies, cross-institutional sessions

-- ============================================================
-- 1. Identity Federations — cross-institutional identity mapping
-- ============================================================
CREATE TABLE identity_federations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  home_institution_id   UUID NOT NULL REFERENCES institutions(id),
  remote_institution_id UUID NOT NULL REFERENCES institutions(id),
  home_orcid            TEXT NOT NULL,
  remote_identifier     TEXT,
  trust_level           TEXT NOT NULL DEFAULT 'verified'
    CHECK (trust_level IN ('verified', 'provisional', 'revoked')),
  federated_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE(home_institution_id, remote_institution_id, home_orcid)
);

-- ============================================================
-- 2. Trust Policies — inter-institutional trust rules
-- ============================================================
CREATE TABLE trust_policies (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_institution_id UUID NOT NULL REFERENCES institutions(id),
  to_institution_id   UUID NOT NULL REFERENCES institutions(id),
  policy_type         TEXT NOT NULL CHECK (policy_type IN (
    'claim_sharing', 'review_acceptance', 'module_trust', 'replication_request'
  )),
  policy_config       JSONB NOT NULL DEFAULT '{}',
  active              BOOLEAN NOT NULL DEFAULT true,
  created_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE(from_institution_id, to_institution_id, policy_type)
);

-- ============================================================
-- 3. Cross-Institutional Sessions — visitor sessions
-- ============================================================
CREATE TABLE cross_institutional_sessions (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_orcid              TEXT NOT NULL,
  home_institution_id     UUID NOT NULL REFERENCES institutions(id),
  visiting_institution_id UUID NOT NULL REFERENCES institutions(id),
  session_token           TEXT NOT NULL,
  permissions             JSONB NOT NULL DEFAULT '["read", "review"]',
  expires_at              TIMESTAMPTZ NOT NULL,
  created_at              TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE identity_federations ENABLE ROW LEVEL SECURITY;
ALTER TABLE trust_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE cross_institutional_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated read federations" ON identity_federations
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read policies" ON trust_policies
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read sessions" ON cross_institutional_sessions
  FOR SELECT USING (auth.role() = 'authenticated');

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_identity_fed_home ON identity_federations (home_institution_id);
CREATE INDEX idx_identity_fed_remote ON identity_federations (remote_institution_id);
CREATE INDEX idx_identity_fed_orcid ON identity_federations (home_orcid);

CREATE INDEX idx_trust_policies_from ON trust_policies (from_institution_id);
CREATE INDEX idx_trust_policies_to ON trust_policies (to_institution_id);
CREATE INDEX idx_trust_policies_type ON trust_policies (policy_type);

CREATE INDEX idx_cross_sessions_orcid ON cross_institutional_sessions (user_orcid);
CREATE INDEX idx_cross_sessions_home ON cross_institutional_sessions (home_institution_id);
CREATE INDEX idx_cross_sessions_visiting ON cross_institutional_sessions (visiting_institution_id);
CREATE INDEX idx_cross_sessions_token ON cross_institutional_sessions (session_token);
CREATE INDEX idx_cross_sessions_expires ON cross_institutional_sessions (expires_at);
