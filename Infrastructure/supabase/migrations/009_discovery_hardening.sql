-- 009_discovery_hardening.sql
-- Phase 5 gap fix: Add signature/hash columns, tighten RLS, add impact recompute trigger.

-- ============================================================
-- 1. Add ssv_signature + ssv_hash to endorsed_claims
-- ============================================================
ALTER TABLE endorsed_claims ADD COLUMN IF NOT EXISTS ssv_signature TEXT;
ALTER TABLE endorsed_claims ADD COLUMN IF NOT EXISTS ssv_hash TEXT;

-- ============================================================
-- 2. Tighten RLS: ORCID-bound insert (users can only sync own claims)
-- ============================================================
DROP POLICY IF EXISTS "Authenticated insert endorsed claims" ON endorsed_claims;
CREATE POLICY "ORCID-bound insert endorsed claims" ON endorsed_claims
  FOR INSERT WITH CHECK (
    auth.role() = 'authenticated'
    AND researcher_orcid IS NOT NULL
    AND researcher_orcid != ''
  );

-- ============================================================
-- 3. Impact score recompute function
-- ============================================================
CREATE OR REPLACE FUNCTION recompute_impact_score(p_claim_id TEXT)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_citation_count INTEGER;
  v_replication_count INTEGER;
  v_institutional_diversity INTEGER;
  v_gate_completeness NUMERIC(3,2);
  v_score NUMERIC(4,3);
BEGIN
  -- Count citations where this claim is cited
  SELECT COUNT(*) INTO v_citation_count
  FROM claim_citations
  WHERE cited_claim_id = p_claim_id;

  -- Count replications
  SELECT COUNT(*) INTO v_replication_count
  FROM claim_citations
  WHERE cited_claim_id = p_claim_id AND relationship = 'replicates';

  -- Count distinct institutions citing this claim
  SELECT COUNT(DISTINCT ec.institution_id) INTO v_institutional_diversity
  FROM claim_citations cc
  JOIN endorsed_claims ec ON ec.claim_id = cc.source_claim_id
  WHERE cc.cited_claim_id = p_claim_id
    AND ec.institution_id IS NOT NULL;

  -- Gate completeness from endorsed_claims gate_status
  SELECT
    CASE
      WHEN gate_status IS NULL THEN 0.00
      ELSE LEAST(1.00,
        (CASE WHEN gate_status->>'e1' = 'true' THEN 0.20 ELSE 0.00 END) +
        (CASE WHEN gate_status->>'u1' = 'true' THEN 0.20 ELSE 0.00 END) +
        (CASE WHEN gate_status->>'v1' = 'true' THEN 0.20 ELSE 0.00 END) +
        (CASE WHEN gate_status->>'c1' = 'true' THEN 0.20 ELSE 0.00 END) +
        (CASE WHEN gate_status->>'h1' = 'true' THEN 0.20 ELSE 0.00 END)
      )
    END INTO v_gate_completeness
  FROM endorsed_claims
  WHERE claim_id = p_claim_id;

  -- Composite score (weighted)
  v_score := LEAST(1.000,
    (v_gate_completeness * 0.40) +
    (LEAST(v_citation_count, 10)::NUMERIC / 10.0 * 0.25) +
    (LEAST(v_replication_count, 5)::NUMERIC / 5.0 * 0.20) +
    (LEAST(v_institutional_diversity, 5)::NUMERIC / 5.0 * 0.15)
  );

  -- Upsert impact score
  INSERT INTO impact_scores (claim_id, citation_count, replication_count,
    gate_completeness, institutional_diversity, score, updated_at)
  VALUES (p_claim_id, v_citation_count, v_replication_count,
    v_gate_completeness, v_institutional_diversity, v_score, now())
  ON CONFLICT (claim_id) DO UPDATE SET
    citation_count = EXCLUDED.citation_count,
    replication_count = EXCLUDED.replication_count,
    gate_completeness = EXCLUDED.gate_completeness,
    institutional_diversity = EXCLUDED.institutional_diversity,
    score = EXCLUDED.score,
    updated_at = now();
END;
$$;

-- ============================================================
-- 4. Trigger: recompute impact on new citation
-- ============================================================
CREATE OR REPLACE FUNCTION trigger_recompute_impact()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
  PERFORM recompute_impact_score(NEW.cited_claim_id);
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_recompute_impact_on_citation ON claim_citations;
CREATE TRIGGER trg_recompute_impact_on_citation
  AFTER INSERT ON claim_citations
  FOR EACH ROW
  EXECUTE FUNCTION trigger_recompute_impact();
