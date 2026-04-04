-- Phase 8: QPU cost tracking — BYOT + Institutional Broker maliyet modeli
-- Compute authority local daemon'da kalir, platform QPU maliyeti tasimaz
-- Bu Supabase migration sadece Web portal QPU admin UI icin gereklidir
-- Daemon'da RLS yok — daemon local-only (localhost:9473)

-- Immutable price versioning (INSERT-only)
CREATE TABLE IF NOT EXISTS qpu_price_snapshots (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL CHECK (provider IN ('ibm_quantum', 'ionq')),
    backend_name    TEXT NOT NULL,
    price_per_shot  FLOAT,
    price_per_task  FLOAT,
    currency        TEXT NOT NULL DEFAULT 'USD',
    source          TEXT NOT NULL CHECK (source IN ('manual', 'api_fetch', 'provider_docs')),
    effective_at    TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Immutable usage log (INSERT-only, UPDATE only for status/actual_cost)
CREATE TABLE IF NOT EXISTS qpu_usage_log (
    log_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL UNIQUE,
    user_id             TEXT NOT NULL,
    institution_id      UUID,
    provider            TEXT NOT NULL CHECK (provider IN ('ibm_quantum', 'ionq')),
    backend_name        TEXT NOT NULL,
    shots               INT NOT NULL,
    estimated_cost      JSONB NOT NULL,
    actual_cost         JSONB,
    status              TEXT NOT NULL DEFAULT 'estimated'
                        CHECK (status IN ('estimated', 'running', 'completed', 'failed', 'refunded')),
    price_snapshot_id   UUID REFERENCES qpu_price_snapshots(snapshot_id),
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Quota enforcement
CREATE TABLE IF NOT EXISTS qpu_quotas (
    quota_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id  UUID,
    user_id         TEXT,
    period          TEXT NOT NULL CHECK (period IN ('daily', 'monthly')),
    shot_limit      BIGINT NOT NULL,
    shot_used       BIGINT NOT NULL DEFAULT 0,
    budget_limit    JSONB,
    budget_used     JSONB DEFAULT '{"amount": 0}',
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_usage_run_id ON qpu_usage_log(run_id);
CREATE INDEX IF NOT EXISTS idx_usage_user ON qpu_usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_institution ON qpu_usage_log(institution_id);
CREATE INDEX IF NOT EXISTS idx_usage_status ON qpu_usage_log(status);
CREATE INDEX IF NOT EXISTS idx_price_provider ON qpu_price_snapshots(provider, backend_name);
CREATE INDEX IF NOT EXISTS idx_price_effective ON qpu_price_snapshots(effective_at);
CREATE INDEX IF NOT EXISTS idx_quota_user ON qpu_quotas(user_id);
CREATE INDEX IF NOT EXISTS idx_quota_institution ON qpu_quotas(institution_id);
CREATE INDEX IF NOT EXISTS idx_quota_period ON qpu_quotas(period_start, period_end);

-- RLS (Supabase portal icin — institution_members.orcid kullanir, user_id YOKTUR)
ALTER TABLE qpu_usage_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE qpu_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE qpu_price_snapshots ENABLE ROW LEVEL SECURITY;

-- Users can see their own usage (orcid mapping via auth.jwt())
CREATE POLICY usage_user_read ON qpu_usage_log
    FOR SELECT USING (
        user_id IN (
            SELECT orcid FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
    );

-- Institution admins can see all institution usage
CREATE POLICY usage_institution_read ON qpu_usage_log
    FOR SELECT USING (
        institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role = 'admin'
        )
    );

-- Users can see their own quotas
CREATE POLICY quota_user_read ON qpu_quotas
    FOR SELECT USING (
        user_id IN (
            SELECT orcid FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
        OR user_id IS NULL
    );

-- Institution admins can manage quotas
CREATE POLICY quota_admin_manage ON qpu_quotas
    FOR ALL USING (
        institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role = 'admin'
        )
    );

-- Price snapshots readable by all authenticated users
CREATE POLICY price_read_all ON qpu_price_snapshots
    FOR SELECT USING (true);

-- Only admins can insert price snapshots
CREATE POLICY price_admin_insert ON qpu_price_snapshots
    FOR INSERT WITH CHECK (
        (auth.jwt()->>'orcid') IN (
            SELECT orcid FROM institution_members WHERE role = 'admin'
        )
    );

-- Updated_at trigger for quotas
CREATE OR REPLACE FUNCTION update_quota_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_quota_updated
    BEFORE UPDATE ON qpu_quotas
    FOR EACH ROW
    EXECUTE FUNCTION update_quota_updated_at();
