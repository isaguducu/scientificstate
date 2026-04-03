-- 002_reviews.sql — Peer review table for ScientificState Web Portal
-- Phase 1-C: Open Source Governance Gate prerequisite

CREATE TABLE reviews (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id       TEXT NOT NULL,
  reviewer_orcid  TEXT NOT NULL,
  comment         TEXT NOT NULL,
  endorsement     TEXT NOT NULL CHECK (endorsement IN ('support', 'contest', 'neutral')),
  created_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

-- Authenticated users can insert their own reviews
CREATE POLICY "Authenticated write" ON reviews
  FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');

-- All reviews are publicly readable
CREATE POLICY "Public read" ON reviews
  FOR SELECT
  USING (true);

-- Index for fast lookups by report
CREATE INDEX idx_reviews_report_id ON reviews (report_id);

-- Index for reviewer history
CREATE INDEX idx_reviews_reviewer_orcid ON reviews (reviewer_orcid);
