# Acceptance — full-fidelity-ingestion-v1

The mission is accepted when:

1. **Schema registry (A / ENG-426)** — a new `ingest` table records, per
   `(provider, object, field)`: api name, type, readable flag, first_seen,
   last_seen, active. Service upserts from a describe result (SF) or observed
   payload keys (REST). Drift shape (new/removed/type-changed) defined and
   surfaced via structured log + `sync_run.meta`. Alembic migration present.

2. **Salesforce dynamic projection (B / ENG-427)** — every static
   `_SF_*_PROJECTION` is replaced by a describe-driven builder that selects all
   queryable fields. Tooling-API field listing (non-FLS-filtered) added; the
   FLS-gap detector diffs Tooling vs describe and records the blocked-field list.
   A completeness check fails if capture silently narrows.

3. **Schema-refresh + drift job (C / ENG-428)** — a low-cadence cron re-derives
   schemas, updates the registry, emits drift events, and (SF) absorbs new fields
   into the next pull with no code change. A simulated new field is detected and
   absorbed in a test.

4. **CareStack/REST audit (D / ENG-429)** — every CareStack endpoint confirmed to
   request full objects (no field restriction) with verbatim nested capture;
   observed-key snapshots flow into the registry.

5. **Salesforce 2026-YTD backfill (E / ENG-430)** — SF objects re-pulled for 2026
   YTD through the dynamic projection; spot-check confirms previously-missing
   fields (e.g. `CreatedById`) now present in raw; idempotency verified.

6. **Governance (F / ENG-431)** — ADR recorded; root `CLAUDE.md` and
   `packages/ingest/CLAUDE.md` updated with the full-fidelity invariant; raw-access
   gating and PHI boundaries reaffirmed.

7. **Verification** — full verify loop green (ruff, mypy, pytest, alembic check,
   and FE checks where touched). Salesforce-touching blocks verified against real
   data before merge per the verify-with-real-data rule.
