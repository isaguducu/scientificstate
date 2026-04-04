-- 010_publish_review_alignment.sql
-- Phase 5 gap fix: Align module_versions + reviews tables with API routes.

-- ============================================================
-- 1. Extend module_versions status CHECK to include review lifecycle
-- ============================================================
ALTER TABLE module_versions DROP CONSTRAINT IF EXISTS module_versions_status_check;
ALTER TABLE module_versions ADD CONSTRAINT module_versions_status_check
  CHECK (status IN ('active', 'deprecated', 'revoked', 'pending_review', 'changes_requested', 'rejected', 'published'));

-- ============================================================
-- 2. Add module review columns to reviews table
-- ============================================================
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS module_id UUID REFERENCES modules(id);
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS version TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS decision TEXT
  CHECK (decision IN ('approve', 'reject', 'request_changes'));

-- ============================================================
-- 3. RLS for module review inserts
-- ============================================================
DROP POLICY IF EXISTS "Authenticated write" ON reviews;
CREATE POLICY "Authenticated write reviews" ON reviews
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');
