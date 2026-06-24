-- Domain schemas. Created once when the Postgres data dir is empty.
-- Re-running is safe because of IF NOT EXISTS.
--
-- HIPAA note: in production, create dedicated DB roles and grant per-schema
-- privileges so that, e.g., a future "ops" role cannot read from "phi".
-- A starter recipe is included at the bottom (commented out).

CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS phi;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS ingest;

-- M1 vertical-slice schemas (added 2026-05-01).
-- IMPORTANT: this file runs ONCE on a fresh Postgres data dir.
-- On existing environments, run these statements manually.
CREATE SCHEMA IF NOT EXISTS actor;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS integrations;

-- Phase 1 slice — interaction (slim subset of v0.2 §5; full package M3).
-- Added 2026-05-05 alongside ENG-2 / D1.
CREATE SCHEMA IF NOT EXISTS interaction;

-- Multi-tenancy root (added 2026-05-09 with ENG-123 / ADR-0003).
-- Owns tenant, location, integration_credential, setting tables.
CREATE SCHEMA IF NOT EXISTS tenant;

-- Outreach (added 2026-05-10 with ENG-133 / ADR-0004).
-- Owns templates, campaigns, sends, suppression, outbound_queue.
CREATE SCHEMA IF NOT EXISTS outreach;

-- Insight (added 2026-06-02 with ENG-314).
-- Owns governed semantic analytics catalog proposals and approved versions.
CREATE SCHEMA IF NOT EXISTS insight;

-- Catalog (added 2026-06-13 with ENG-420).
-- Workspace-wide reference data: CareStack procedure-code (CDT/CPT) catalog.
CREATE SCHEMA IF NOT EXISTS catalog;

-- Enrichment (added 2026-06-15 with ENG-439 / Block F).
-- Manual-enrichment store: our own fields layered over canonical entities.
CREATE SCHEMA IF NOT EXISTS enrichment;

-- Attribution (added 2026-06-15 with ENG-446 / ENG-447).
-- Derived lead source distribution chain + per-lead attribution.
CREATE SCHEMA IF NOT EXISTS attribution;

-- Marketing (added 2026-06-15 with ENG-446-adjacent marketing-ingest slice).
-- Ad-spend + campaign metrics from Google/Meta/TikTok ads (read-only pull).
-- Aggregate (non-person) marketing data; person-linked sources stay in
-- identity/ops/interaction. See packages/marketing/CLAUDE.md.
CREATE SCHEMA IF NOT EXISTS marketing;

-- Useful extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------
-- PRODUCTION ROLE TEMPLATE — uncomment & adapt before going live
-- ---------------------------------------------------------------
-- CREATE ROLE fusion_app  LOGIN PASSWORD 'change-me';
-- CREATE ROLE fusion_phi  LOGIN PASSWORD 'change-me';
-- CREATE ROLE fusion_ops  LOGIN PASSWORD 'change-me';
--
-- GRANT USAGE ON SCHEMA identity, audit, ingest, tenant TO fusion_app, fusion_ops, fusion_phi;
-- GRANT USAGE ON SCHEMA ops      TO fusion_app, fusion_ops;
-- GRANT USAGE ON SCHEMA phi      TO fusion_app, fusion_phi;
-- GRANT USAGE ON SCHEMA outreach TO fusion_app, fusion_ops;
-- GRANT USAGE ON SCHEMA insight  TO fusion_app, fusion_ops;
--
-- -- Default privileges for future tables
-- ALTER DEFAULT PRIVILEGES IN SCHEMA ops      GRANT SELECT, INSERT, UPDATE ON TABLES TO fusion_ops;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA phi      GRANT SELECT, INSERT, UPDATE ON TABLES TO fusion_phi;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA outreach GRANT SELECT, INSERT, UPDATE ON TABLES TO fusion_ops;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA insight  GRANT SELECT, INSERT, UPDATE ON TABLES TO fusion_ops;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA audit    GRANT INSERT ON TABLES TO fusion_app, fusion_ops, fusion_phi;
