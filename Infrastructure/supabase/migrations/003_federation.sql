-- 003_federation.sql — Federation & Institutional tables for ScientificState Web Portal
-- Phase 3: Federation, Institutional SSO, Registry Mirrors, Trust Network

-- ============================================================
-- 1. Institutions
-- ============================================================
CREATE TABLE institutions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name           TEXT NOT NULL UNIQUE,
  domain         TEXT NOT NULL UNIQUE,  -- e.g., "mit.edu"
  sso_provider   TEXT CHECK (sso_provider IN ('saml', 'oidc')),
  sso_config     JSONB,
  trust_level    TEXT NOT NULL DEFAULT 'standard' CHECK (trust_level IN ('trusted', 'standard', 'probation')),
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 2. Registry Mirrors
-- ============================================================
CREATE TABLE registry_mirrors (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  UUID REFERENCES institutions(id),
  name            TEXT NOT NULL,
  url             TEXT NOT NULL,
  mode            TEXT NOT NULL CHECK (mode IN ('mirror', 'self-hosted', 'air-gapped')),
  sync_interval   INTERVAL DEFAULT '1 hour',
  last_synced_at  TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'syncing')),
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 3. Federation Trust
-- ============================================================
CREATE TABLE federation_trust (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_inst_id    UUID NOT NULL REFERENCES institutions(id),
  to_inst_id      UUID NOT NULL REFERENCES institutions(id),
  trust_type      TEXT NOT NULL CHECK (trust_type IN ('full', 'module-only', 'read-only')),
  established_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(from_inst_id, to_inst_id)
);

-- ============================================================
-- 4. Institution Members
-- ============================================================
CREATE TABLE institution_members (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  UUID NOT NULL REFERENCES institutions(id),
  orcid           TEXT NOT NULL,
  role            TEXT NOT NULL DEFAULT 'researcher' CHECK (role IN ('admin', 'maintainer', 'researcher')),
  department      TEXT,
  joined_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(institution_id, orcid)
);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE registry_mirrors ENABLE ROW LEVEL SECURITY;
ALTER TABLE federation_trust ENABLE ROW LEVEL SECURITY;
ALTER TABLE institution_members ENABLE ROW LEVEL SECURITY;

-- Public read for institutions and mirrors (discovery)
CREATE POLICY "Public read institutions" ON institutions FOR SELECT USING (true);
CREATE POLICY "Public read mirrors" ON registry_mirrors FOR SELECT USING (true);

-- Federation trust visible to members of involved institutions
CREATE POLICY "Public read federation trust" ON federation_trust FOR SELECT USING (true);

-- Institution members visible to authenticated users
CREATE POLICY "Authenticated read members" ON institution_members
  FOR SELECT USING (auth.role() = 'authenticated');

-- Only admins can insert members (enforced at application layer via RPC)
CREATE POLICY "Authenticated write members" ON institution_members
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_registry_mirrors_institution ON registry_mirrors (institution_id);
CREATE INDEX idx_registry_mirrors_mode ON registry_mirrors (mode);
CREATE INDEX idx_federation_trust_from ON federation_trust (from_inst_id);
CREATE INDEX idx_federation_trust_to ON federation_trust (to_inst_id);
CREATE INDEX idx_institution_members_institution ON institution_members (institution_id);
CREATE INDEX idx_institution_members_orcid ON institution_members (orcid);
