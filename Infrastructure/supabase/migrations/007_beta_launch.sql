-- 007_beta_launch.sql
-- Phase 5 W1: Beta launch tables — researcher onboarding, onboarding steps, institution registration.

-- ── Beta researcher registrations ──────────────────────────────────────────
CREATE TABLE beta_registrations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  orcid             TEXT NOT NULL UNIQUE,
  email             TEXT NOT NULL,
  institution_name  TEXT,
  research_area     TEXT,
  default_domains   JSONB DEFAULT '[]',
  status            TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'verified', 'onboarded', 'deactivated')),
  registered_at     TIMESTAMPTZ DEFAULT now(),
  verified_at       TIMESTAMPTZ,
  onboarded_at      TIMESTAMPTZ
);

-- ── Onboarding step tracking ───────────────────────────────────────────────
CREATE TABLE onboarding_steps (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  registration_id   UUID NOT NULL REFERENCES beta_registrations(id),
  step              TEXT NOT NULL CHECK (step IN (
    'orcid_linked', 'email_verified', 'desktop_installed',
    'first_run_completed', 'first_claim_submitted', 'discovery_visited'
  )),
  completed_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(registration_id, step)
);

-- ── Institution registrations ──────────────────────────────────────────────
CREATE TABLE institution_registrations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_name  TEXT NOT NULL,
  domain            TEXT NOT NULL,
  it_contact_email  TEXT NOT NULL,
  it_contact_name   TEXT,
  oidc_client_id    TEXT,
  oidc_issuer_url   TEXT,
  status            TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'configuring', 'testing', 'active', 'suspended')),
  registered_at     TIMESTAMPTZ DEFAULT now(),
  activated_at      TIMESTAMPTZ
);

-- ── RLS ────────────────────────────────────────────────────────────────────
ALTER TABLE beta_registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE institution_registrations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated read registrations" ON beta_registrations
  FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Public insert registrations" ON beta_registrations
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Authenticated read onboarding steps" ON onboarding_steps
  FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated insert onboarding steps" ON onboarding_steps
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read institution regs" ON institution_registrations
  FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Public insert institution regs" ON institution_registrations
  FOR INSERT WITH CHECK (true);
