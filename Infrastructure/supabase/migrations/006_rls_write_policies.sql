-- 006_rls_write_policies.sql
-- Phase 4 gap fix: Add INSERT/UPDATE RLS policies for federation + governance tables.
-- Previously only SELECT policies existed — write operations were blocked by RLS.

-- ============================================================
-- Federation tables — authenticated INSERT + UPDATE
-- ============================================================

-- trust_policies: authenticated users can create/update trust policies
CREATE POLICY "Authenticated insert trust policies" ON trust_policies
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Authenticated update trust policies" ON trust_policies
  FOR UPDATE USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

-- identity_federations: authenticated users can create federation links
CREATE POLICY "Authenticated insert federations" ON identity_federations
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- cross_institutional_sessions: authenticated users can create sessions
CREATE POLICY "Authenticated insert sessions" ON cross_institutional_sessions
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- ============================================================
-- Governance tables — authenticated INSERT
-- ============================================================

-- disputes: authenticated users can create disputes
CREATE POLICY "Authenticated insert disputes" ON disputes
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');
