-- Phase 8: Replication persistence tables for M3-G institutional quantum replication
-- Main_Source §9A.5: M3-G quantum claims require independent institutional replication

CREATE TABLE IF NOT EXISTS replication_requests (
    request_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id      UUID NOT NULL,
    source_ssv_id UUID NOT NULL,
    source_institution_id UUID NOT NULL,
    target_institution_id UUID NOT NULL,
    method_id     TEXT NOT NULL,
    compute_class TEXT NOT NULL CHECK (compute_class IN ('quantum_hw', 'hybrid')),
    tolerance_abs FLOAT DEFAULT 1e-6,
    tolerance_rel FLOAT DEFAULT 1e-4,
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'in_progress', 'confirmed',
                         'partially_confirmed', 'not_confirmed', 'expired')),
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    CHECK (source_institution_id != target_institution_id)
);

CREATE TABLE IF NOT EXISTS replication_results (
    result_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id        UUID NOT NULL REFERENCES replication_requests(request_id),
    target_ssv_id     UUID NOT NULL,
    comparison_report JSONB NOT NULL DEFAULT '{}',
    confidence_score  FLOAT NOT NULL DEFAULT 0.0,
    status            TEXT NOT NULL CHECK (status IN ('confirmed', 'partially_confirmed', 'not_confirmed')),
    institution_id    UUID NOT NULL,
    executed_at       TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_repl_req_claim ON replication_requests(claim_id);
CREATE INDEX IF NOT EXISTS idx_repl_req_source ON replication_requests(source_institution_id);
CREATE INDEX IF NOT EXISTS idx_repl_req_target ON replication_requests(target_institution_id);
CREATE INDEX IF NOT EXISTS idx_repl_req_status ON replication_requests(status);
CREATE INDEX IF NOT EXISTS idx_repl_res_request ON replication_results(request_id);
CREATE INDEX IF NOT EXISTS idx_repl_res_institution ON replication_results(institution_id);

-- RLS
ALTER TABLE replication_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE replication_results ENABLE ROW LEVEL SECURITY;

-- Institution members can see their own requests (as source or target)
CREATE POLICY repl_req_institution_read ON replication_requests
    FOR SELECT USING (
        source_institution_id IN (
            SELECT institution_id FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
        OR target_institution_id IN (
            SELECT institution_id FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
    );

CREATE POLICY repl_req_source_insert ON replication_requests
    FOR INSERT WITH CHECK (
        source_institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role IN ('admin', 'researcher')
        )
    );

CREATE POLICY repl_res_institution_read ON replication_results
    FOR SELECT USING (
        institution_id IN (
            SELECT institution_id FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
    );

CREATE POLICY repl_res_target_insert ON replication_results
    FOR INSERT WITH CHECK (
        institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role IN ('admin', 'researcher')
        )
    );

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_replication_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_repl_req_updated
    BEFORE UPDATE ON replication_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_replication_updated_at();
