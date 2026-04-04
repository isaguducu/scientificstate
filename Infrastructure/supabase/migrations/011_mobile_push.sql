-- 011_mobile_push.sql
-- Phase 6 W1: Push notification tokens and preferences for mobile companion app.
-- Push notifications are FIELD-BASED (domain/method), NOT person-based.

CREATE TABLE push_tokens (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  device_token TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, device_token)
);

CREATE TABLE push_preferences (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  domain_id TEXT NOT NULL,
  method_id TEXT,
  enabled BOOLEAN NOT NULL DEFAULT true,
  UNIQUE(user_id, domain_id, COALESCE(method_id, '__all__'))
);

-- RLS: users can only see/manage their own data
ALTER TABLE push_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own push tokens"
  ON push_tokens FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users manage own push preferences"
  ON push_preferences FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX idx_push_tokens_user ON push_tokens(user_id);
CREATE INDEX idx_push_preferences_domain ON push_preferences(domain_id, method_id);
