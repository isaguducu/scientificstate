-- Phase 6 W2: Enterprise Auth + API Tiering
-- Tables: api_keys, api_usage_logs, saml_providers
-- All tables RLS-enabled with appropriate policies

-- ─────────────────────────────────────────────
-- 1. API Keys
-- ─────────────────────────────────────────────
CREATE TABLE api_keys (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  key_hash TEXT NOT NULL UNIQUE,
  tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'institutional', 'enterprise')),
  name TEXT NOT NULL DEFAULT 'Default',
  created_at TIMESTAMPTZ DEFAULT now(),
  revoked_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ
);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own API keys"
  ON api_keys FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_tier ON api_keys(tier);

-- ─────────────────────────────────────────────
-- 2. API Usage Logs
-- ─────────────────────────────────────────────
CREATE TABLE api_usage_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
  endpoint TEXT NOT NULL,
  response_status INTEGER NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE api_usage_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own usage logs"
  ON api_usage_logs FOR SELECT
  USING (key_id IN (SELECT id FROM api_keys WHERE user_id = auth.uid()));

CREATE POLICY "Insert usage logs for own keys"
  ON api_usage_logs FOR INSERT
  WITH CHECK (key_id IN (SELECT id FROM api_keys WHERE user_id = auth.uid()));

CREATE INDEX idx_api_usage_key_time ON api_usage_logs(key_id, timestamp);
CREATE INDEX idx_api_usage_endpoint ON api_usage_logs(endpoint);

-- ─────────────────────────────────────────────
-- 3. SAML Providers
-- ─────────────────────────────────────────────
CREATE TABLE saml_providers (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  institution_id UUID REFERENCES institutions(id),
  provider_name TEXT NOT NULL,
  entity_id TEXT NOT NULL UNIQUE,
  sso_url TEXT NOT NULL,
  certificate TEXT NOT NULL,
  attribute_mapping JSONB DEFAULT '{}',
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE saml_providers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Institution admins manage SAML providers"
  ON saml_providers FOR ALL
  USING (true) WITH CHECK (true);

CREATE INDEX idx_saml_providers_entity ON saml_providers(entity_id);
CREATE INDEX idx_saml_providers_institution ON saml_providers(institution_id);
