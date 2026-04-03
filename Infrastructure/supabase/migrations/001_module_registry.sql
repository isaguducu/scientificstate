-- Module Registry Tables
-- Phase 1: Module Store backend (Supabase)
-- Constitutional: public-read, maintainer-write, RLS enforced.

CREATE TABLE modules (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL UNIQUE,
  display_name TEXT,
  description  TEXT,
  author_orcid TEXT NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE module_versions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  module_id     UUID NOT NULL REFERENCES modules(id),
  version       TEXT NOT NULL,
  manifest_json JSONB NOT NULL,
  tarball_hash  TEXT NOT NULL,
  signature_hex TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated','revoked')),
  downloads     INTEGER DEFAULT 0,
  published_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(module_id, version)
);

CREATE TABLE module_maintainers (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  module_id UUID NOT NULL REFERENCES modules(id),
  orcid     TEXT NOT NULL,
  role      TEXT NOT NULL DEFAULT 'maintainer' CHECK (role IN ('owner','maintainer')),
  added_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(module_id, orcid)
);

ALTER TABLE modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_maintainers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read modules" ON modules FOR SELECT USING (true);
CREATE POLICY "Public read versions" ON module_versions FOR SELECT USING (true);
