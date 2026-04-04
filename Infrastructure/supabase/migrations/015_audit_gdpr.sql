-- Migration 015: Audit Log + GDPR Data Requests
-- Phase 7 — Plugin SDK + Audit Trail + GDPR
--
-- audit_log: INSERT-only, append-only. No UPDATE or DELETE policies.
-- gdpr_data_requests: user-managed GDPR export/delete requests.

-- =========================================================================
-- 1. audit_log — append-only event log
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.audit_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id      UUID,                          -- nullable for system/daemon actions
    actor_type    TEXT NOT NULL DEFAULT 'system'
                  CHECK (actor_type IN ('user', 'system', 'federation', 'daemon')),
    action        TEXT NOT NULL
                  CHECK (action IN (
                      'claim.create', 'claim.endorse', 'claim.contest', 'claim.retract',
                      'citation.create', 'citation.remove',
                      'replication.submit', 'replication.complete', 'replication.fail',
                      'module.publish', 'module.deprecate',
                      'auth.login', 'auth.logout', 'auth.saml_login',
                      'gdpr.export_request', 'gdpr.delete_request', 'gdpr.delete_complete',
                      'federation.sync_push', 'federation.sync_pull',
                      'run.create', 'run.complete', 'run.fail'
                  )),
    resource_type TEXT NOT NULL
                  CHECK (resource_type IN (
                      'claim', 'citation', 'replication', 'module',
                      'session', 'gdpr_request', 'federation_sync', 'compute_run'
                  )),
    resource_id   TEXT,
    metadata      JSONB DEFAULT '{}',
    ip_address    INET,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_log_actor_id
    ON public.audit_log (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON public.audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource
    ON public.audit_log (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
    ON public.audit_log (created_at DESC);

-- RLS: admin reads all, user reads own, INSERT for all authenticated.
-- CRITICAL: No UPDATE or DELETE policies — append-only enforcement.
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

-- Allow INSERT for all authenticated users and service_role
CREATE POLICY audit_log_insert ON public.audit_log
    FOR INSERT
    TO authenticated, service_role
    WITH CHECK (true);

-- Users can read their own entries
CREATE POLICY audit_log_select_own ON public.audit_log
    FOR SELECT
    TO authenticated
    USING (actor_id = auth.uid());

-- Service role (admin) can read all
CREATE POLICY audit_log_select_admin ON public.audit_log
    FOR SELECT
    TO service_role
    USING (true);

-- NO UPDATE policy
-- NO DELETE policy


-- =========================================================================
-- 2. gdpr_data_requests — user GDPR export/delete tracking
-- =========================================================================

CREATE TABLE IF NOT EXISTS public.gdpr_data_requests (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id),
    request_type  TEXT NOT NULL CHECK (request_type IN ('export', 'delete')),
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    requested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    result_url    TEXT,
    error_detail  TEXT,
    deadline_at   TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 days')
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_gdpr_requests_user_id
    ON public.gdpr_data_requests (user_id);
CREATE INDEX IF NOT EXISTS idx_gdpr_requests_pending
    ON public.gdpr_data_requests (status)
    WHERE status IN ('pending', 'processing');

-- RLS
ALTER TABLE public.gdpr_data_requests ENABLE ROW LEVEL SECURITY;

-- Users manage their own requests
CREATE POLICY gdpr_requests_select_own ON public.gdpr_data_requests
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY gdpr_requests_insert_own ON public.gdpr_data_requests
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY gdpr_requests_update_own ON public.gdpr_data_requests
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid());

-- Service role reads all
CREATE POLICY gdpr_requests_select_admin ON public.gdpr_data_requests
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY gdpr_requests_update_admin ON public.gdpr_data_requests
    FOR UPDATE
    TO service_role
    USING (true);
