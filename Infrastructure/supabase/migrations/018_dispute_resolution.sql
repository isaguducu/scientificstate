-- Phase 8: Dispute resolution, shared policies, cross-institutional reviews
-- Main_Source §9A.5 M3-G: institutional-level governance for quantum claims

CREATE TABLE IF NOT EXISTS federation_disputes (
    dispute_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id                UUID NOT NULL,
    initiator_institution_id UUID NOT NULL,
    respondent_institution_id UUID NOT NULL,
    dispute_type            TEXT NOT NULL
                            CHECK (dispute_type IN (
                                'result_mismatch', 'methodology_challenge',
                                'data_integrity', 'replication_failure'
                            )),
    status                  TEXT NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'under_review', 'resolved', 'escalated', 'closed')),
    evidence                JSONB NOT NULL DEFAULT '[]',
    resolution              JSONB,
    created_at              TIMESTAMPTZ DEFAULT now(),
    resolved_at             TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS federation_policies (
    policy_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name             TEXT NOT NULL,
    policy_type             TEXT NOT NULL
                            CHECK (policy_type IN (
                                'replication_threshold', 'dispute_resolution',
                                'trust_escalation', 'data_sharing'
                            )),
    policy_body             JSONB NOT NULL DEFAULT '{}',
    version                 INT NOT NULL DEFAULT 1,
    created_by_institution_id UUID NOT NULL,
    effective_from          TIMESTAMPTZ DEFAULT now(),
    status                  TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'active', 'deprecated'))
);

CREATE TABLE IF NOT EXISTS federation_reviews (
    review_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id                UUID NOT NULL,
    reviewer_institution_id UUID NOT NULL,
    review_type             TEXT NOT NULL
                            CHECK (review_type IN (
                                'endorsement_review', 'dispute_review', 'methodology_review'
                            )),
    verdict                 TEXT NOT NULL
                            CHECK (verdict IN ('approve', 'reject', 'request_changes')),
    comments                TEXT,
    created_at              TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_disputes_claim ON federation_disputes(claim_id);
CREATE INDEX IF NOT EXISTS idx_disputes_status ON federation_disputes(status);
CREATE INDEX IF NOT EXISTS idx_policies_type ON federation_policies(policy_type);
CREATE INDEX IF NOT EXISTS idx_policies_status ON federation_policies(status);
CREATE INDEX IF NOT EXISTS idx_reviews_claim ON federation_reviews(claim_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON federation_reviews(reviewer_institution_id);

-- RLS
ALTER TABLE federation_disputes ENABLE ROW LEVEL SECURITY;
ALTER TABLE federation_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE federation_reviews ENABLE ROW LEVEL SECURITY;

CREATE POLICY disputes_institution_read ON federation_disputes
    FOR SELECT USING (
        initiator_institution_id IN (
            SELECT institution_id FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
        OR respondent_institution_id IN (
            SELECT institution_id FROM institution_members WHERE orcid = (auth.jwt()->>'orcid')
        )
    );

CREATE POLICY disputes_initiator_insert ON federation_disputes
    FOR INSERT WITH CHECK (
        initiator_institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role IN ('admin', 'researcher')
        )
    );

CREATE POLICY policies_read_all ON federation_policies
    FOR SELECT USING (status = 'active');

CREATE POLICY policies_insert ON federation_policies
    FOR INSERT WITH CHECK (
        created_by_institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role = 'admin'
        )
    );

CREATE POLICY reviews_read ON federation_reviews
    FOR SELECT USING (true);

CREATE POLICY reviews_insert ON federation_reviews
    FOR INSERT WITH CHECK (
        reviewer_institution_id IN (
            SELECT institution_id FROM institution_members
            WHERE orcid = (auth.jwt()->>'orcid') AND role IN ('admin', 'researcher')
        )
    );
