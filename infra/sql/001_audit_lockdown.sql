-- ─────────────────────────────────────────────────────────────────────────
-- Migration 001: Lock audit_logs to append-only at the database level.
-- ─────────────────────────────────────────────────────────────────────────
--
-- The application code today already only INSERTs into audit_logs — no
-- handler calls UPDATE or DELETE. This migration adds defense-in-depth so a
-- future bug, dependency vuln, or SQL injection cannot rewrite history.
--
-- HIPAA Security Rule §164.312(b) requires audit controls that "record and
-- examine activity in information systems." Append-only is the standard
-- interpretation of "tamper-evident". With this in place, even a fully
-- compromised application can be detected because audit rows can't be
-- altered or removed without DBA-level credentials.
--
-- ─────────────────────────────────────────────────────────────────────────
-- DEPLOYMENT
-- ─────────────────────────────────────────────────────────────────────────
--
-- This file is NOT applied by `drizzle-kit push`. Drizzle handles schema
-- DDL; this is a permissions migration that lives outside the ORM.
--
-- Apply manually after the audit_logs table exists, as a DB superuser, ONCE
-- per environment:
--
--     psql "$DATABASE_URL" -f infra/sql/001_audit_lockdown.sql
--
-- Track the application of this file alongside other infra migrations
-- (e.g. in deploy notes). Idempotent — safe to re-run; REVOKE on a
-- permission that was already revoked is a no-op.
--
-- ─────────────────────────────────────────────────────────────────────────
-- PREREQUISITES
-- ─────────────────────────────────────────────────────────────────────────
--
-- Production should run the application as a non-superuser role distinct
-- from the schema owner. Convention here: `app_role` for the runtime user.
-- If your prod uses a different name, adjust the role below. To check the
-- current connection role: `SELECT current_user;`
--
-- Local dev with one shared DB owner: this migration still works, but the
-- application also runs as the owner, which trivially bypasses the REVOKE.
-- That's acceptable for dev; production MUST use a non-owner role for the
-- guarantee to hold.

-- Revoke the dangerous DML on the audit_logs table. INSERT stays. SELECT
-- stays (operators + reporting need to read the log). TRUNCATE is part of
-- DELETE in PostgreSQL's grant model and is implicitly covered.
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM app_role;

-- Also revoke on any future role that might be granted blanket access via
-- GRANT ALL — belt-and-braces.
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT DISTINCT grantee
    FROM information_schema.table_privileges
    WHERE table_name = 'audit_logs'
      AND privilege_type IN ('UPDATE', 'DELETE', 'TRUNCATE')
      AND grantee NOT IN ('PUBLIC', current_user)
  LOOP
    EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_logs FROM %I', r.grantee);
  END LOOP;
END
$$;

-- Sanity check the result. Logged for the operator running the migration
-- so they can confirm the post-state.
SELECT grantee, privilege_type
FROM information_schema.table_privileges
WHERE table_name = 'audit_logs'
ORDER BY grantee, privilege_type;
