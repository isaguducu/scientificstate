-- 013_discovery_intelligence.sql
-- Phase 6 W4: Discovery Intelligence tables
-- module_downloads, module_verified_badges, trending_snapshots

-- ── module_downloads ─────────────────────────────────────────────────

CREATE TABLE module_downloads (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  module_id TEXT NOT NULL,
  user_id UUID REFERENCES auth.users(id),
  version TEXT NOT NULL,
  downloaded_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE module_downloads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can log downloads"
  ON module_downloads FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Public can view download counts"
  ON module_downloads FOR SELECT USING (true);

CREATE INDEX idx_module_downloads_module ON module_downloads(module_id);
CREATE INDEX idx_module_downloads_date ON module_downloads(downloaded_at);

-- ── module_verified_badges ───────────────────────────────────────────

CREATE TABLE module_verified_badges (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  module_id TEXT NOT NULL UNIQUE,
  verified_at TIMESTAMPTZ DEFAULT now(),
  verified_by_orcid TEXT NOT NULL
);

ALTER TABLE module_verified_badges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view verified badges"
  ON module_verified_badges FOR SELECT USING (true);

-- ── trending_snapshots ───────────────────────────────────────────────

CREATE TABLE trending_snapshots (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  domain_id TEXT NOT NULL,
  method_id TEXT,
  snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
  endorsement_count INTEGER DEFAULT 0,
  replication_count INTEGER DEFAULT 0,
  citation_count INTEGER DEFAULT 0,
  trending_score NUMERIC(6,4) DEFAULT 0.0,
  UNIQUE(domain_id, COALESCE(method_id, '__all__'), snapshot_date)
);

ALTER TABLE trending_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view trending data"
  ON trending_snapshots FOR SELECT USING (true);

CREATE INDEX idx_trending_snapshots_date ON trending_snapshots(snapshot_date);
CREATE INDEX idx_trending_snapshots_domain ON trending_snapshots(domain_id, method_id);
