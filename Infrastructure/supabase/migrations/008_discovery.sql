-- 008_discovery.sql — Scientific Discovery Network
-- Phase 5: Endorsed claims, citations, impact, profiles, collections, subscriptions

-- ============================================================
-- 1. Endorsed Claims — core data source for discovery
-- ============================================================
CREATE TABLE endorsed_claims (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id          TEXT NOT NULL UNIQUE,
  ssv_id            TEXT NOT NULL,
  domain_id         TEXT NOT NULL,
  method_id         TEXT,
  title             TEXT NOT NULL,
  institution_id    UUID REFERENCES institutions(id),
  researcher_orcid  TEXT NOT NULL,
  gate_status       JSONB NOT NULL DEFAULT '{}',
  lifecycle_status  TEXT NOT NULL DEFAULT 'endorsed'
    CHECK (lifecycle_status IN ('endorsed', 'contested', 'retracted')),
  endorsed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  synced_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_endorsed_claims_domain ON endorsed_claims(domain_id);
CREATE INDEX idx_endorsed_claims_method ON endorsed_claims(domain_id, method_id);
CREATE INDEX idx_endorsed_claims_orcid ON endorsed_claims(researcher_orcid);
CREATE INDEX idx_endorsed_claims_institution ON endorsed_claims(institution_id);

-- ============================================================
-- 2. Researcher Profiles (ORCID-based)
-- ============================================================
CREATE TABLE researcher_profiles (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  orcid             TEXT NOT NULL UNIQUE,
  display_name      TEXT NOT NULL,
  bio               TEXT,
  institution_id    UUID REFERENCES institutions(id),
  research_areas    JSONB DEFAULT '[]',
  profile_visible   BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 3. Field Subscriptions (domain follow — NOT person follow)
-- ============================================================
CREATE TABLE field_subscriptions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  researcher_orcid  TEXT NOT NULL,
  domain_id         TEXT NOT NULL,
  method_id         TEXT,
  notify_email      BOOLEAN NOT NULL DEFAULT true,
  subscribed_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE(researcher_orcid, domain_id, method_id)
);

-- ============================================================
-- 4. Claim Citations (SSV-to-SSV chain)
-- ============================================================
CREATE TABLE claim_citations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_claim_id   TEXT NOT NULL REFERENCES endorsed_claims(claim_id),
  cited_claim_id    TEXT NOT NULL REFERENCES endorsed_claims(claim_id),
  relationship      TEXT NOT NULL CHECK (relationship IN (
    'builds_upon', 'extends', 'replicates', 'contradicts'
  )),
  cited_by_orcid    TEXT NOT NULL,
  cited_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE(source_claim_id, cited_claim_id),
  CHECK (source_claim_id != cited_claim_id)
);

-- ============================================================
-- 5. Claim Collections (presentation layer)
-- ============================================================
CREATE TABLE claim_collections (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_orcid      TEXT NOT NULL,
  title             TEXT NOT NULL,
  description       TEXT,
  claim_ids         JSONB NOT NULL DEFAULT '[]',
  status            TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'published')),
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 6. Impact Scores
-- ============================================================
CREATE TABLE impact_scores (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id                TEXT NOT NULL UNIQUE REFERENCES endorsed_claims(claim_id),
  replication_count       INTEGER NOT NULL DEFAULT 0,
  citation_count          INTEGER NOT NULL DEFAULT 0,
  gate_completeness       NUMERIC(3,2) NOT NULL DEFAULT 0.00,
  institutional_diversity INTEGER NOT NULL DEFAULT 0,
  score                   NUMERIC(4,3) NOT NULL DEFAULT 0.000,
  updated_at              TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE endorsed_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE researcher_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE impact_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read endorsed claims" ON endorsed_claims
  FOR SELECT USING (true);
CREATE POLICY "Authenticated insert endorsed claims" ON endorsed_claims
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Public read visible profiles" ON researcher_profiles
  FOR SELECT USING (profile_visible = true);
CREATE POLICY "Own profile update" ON researcher_profiles
  FOR UPDATE USING (orcid = auth.jwt() ->> 'orcid');

CREATE POLICY "Own subscriptions read" ON field_subscriptions
  FOR SELECT USING (researcher_orcid = auth.jwt() ->> 'orcid');
CREATE POLICY "Own subscriptions write" ON field_subscriptions
  FOR ALL USING (researcher_orcid = auth.jwt() ->> 'orcid');

CREATE POLICY "Public read citations" ON claim_citations
  FOR SELECT USING (true);
CREATE POLICY "Authenticated create citations" ON claim_citations
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Public read published collections" ON claim_collections
  FOR SELECT USING (status = 'published' OR author_orcid = auth.jwt() ->> 'orcid');
CREATE POLICY "Own collections write" ON claim_collections
  FOR ALL USING (author_orcid = auth.jwt() ->> 'orcid');

CREATE POLICY "Public read impact" ON impact_scores
  FOR SELECT USING (true);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_researcher_profiles_institution ON researcher_profiles(institution_id);
CREATE INDEX idx_field_subscriptions_orcid ON field_subscriptions(researcher_orcid);
CREATE INDEX idx_field_subscriptions_domain ON field_subscriptions(domain_id);
CREATE INDEX idx_claim_citations_source ON claim_citations(source_claim_id);
CREATE INDEX idx_claim_citations_cited ON claim_citations(cited_claim_id);
CREATE INDEX idx_claim_collections_author ON claim_collections(author_orcid);
CREATE INDEX idx_claim_collections_status ON claim_collections(status);
