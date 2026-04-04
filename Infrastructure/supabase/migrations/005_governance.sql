-- 005_governance.sql
-- Governance Committee + Dispute Resolution infrastructure
-- Phase 4 — W4

-- ---------------------------------------------------------------------------
-- 1. governance_committees
-- ---------------------------------------------------------------------------

CREATE TABLE governance_committees (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  description   TEXT,
  min_members   INTEGER NOT NULL DEFAULT 3,
  quorum_ratio  NUMERIC(3,2) NOT NULL DEFAULT 0.67,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. committee_members
-- ---------------------------------------------------------------------------

CREATE TABLE committee_members (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  committee_id  UUID NOT NULL REFERENCES governance_committees(id),
  orcid         TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('chair', 'member')),
  joined_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE(committee_id, orcid)
);

-- ---------------------------------------------------------------------------
-- 3. disputes
-- ---------------------------------------------------------------------------

CREATE TABLE disputes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  committee_id     UUID NOT NULL REFERENCES governance_committees(id),
  dispute_type     TEXT NOT NULL CHECK (dispute_type IN (
    'module_ownership', 'claim_validity', 'review_misconduct', 'policy_violation'
  )),
  title            TEXT NOT NULL,
  description      TEXT NOT NULL,
  requester_orcid  TEXT NOT NULL,
  respondent_orcid TEXT,
  module_id        TEXT,
  claim_id         TEXT,
  status           TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
    'open', 'under_review', 'resolved_for_requester', 'resolved_for_respondent',
    'escalated', 'dismissed'
  )),
  created_at       TIMESTAMPTZ DEFAULT now(),
  resolved_at      TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- 4. dispute_votes
-- ---------------------------------------------------------------------------

CREATE TABLE dispute_votes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dispute_id    UUID NOT NULL REFERENCES disputes(id),
  voter_orcid   TEXT NOT NULL,
  decision      TEXT NOT NULL CHECK (decision IN (
    'for_requester', 'for_respondent', 'escalate', 'dismiss'
  )),
  reasoning     TEXT,
  voted_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(dispute_id, voter_orcid)
);

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE governance_committees ENABLE ROW LEVEL SECURITY;
ALTER TABLE committee_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE disputes ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispute_votes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read committees" ON governance_committees FOR SELECT USING (true);
CREATE POLICY "Public read members" ON committee_members FOR SELECT USING (true);
CREATE POLICY "Public read disputes" ON disputes FOR SELECT USING (true);
CREATE POLICY "Authenticated vote" ON dispute_votes FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX idx_committee_members_committee ON committee_members(committee_id);
CREATE INDEX idx_committee_members_orcid ON committee_members(orcid);
CREATE INDEX idx_disputes_committee ON disputes(committee_id);
CREATE INDEX idx_disputes_status ON disputes(status);
CREATE INDEX idx_disputes_requester ON disputes(requester_orcid);
CREATE INDEX idx_dispute_votes_dispute ON dispute_votes(dispute_id);
