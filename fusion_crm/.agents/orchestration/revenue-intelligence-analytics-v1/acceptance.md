# Acceptance Criteria — revenue-intelligence-analytics-v1 (ENG-504)

## B0 — Foundation
### ENG-505 — analytics schema + fact_patient_journey
- New `analytics` schema + `fact_patient_journey` (one row per `person_uid`) with
  all spec columns + `location_id`; every column nullable except `person_uid`.
- Per-field provenance (source, method `auto`/`manual`/`unresolved`, confidence,
  resolved_at).
- New Alembic revision; `alembic upgrade head` then `alembic check` clean on a
  fresh DB. `docs/data-model/CATALOG.md` + schema list + invariant #1 note updated.

### ENG-506 — fact builder/refresh job
- Backfill populates one row per person (union of SF leads + CareStack-direct);
  available fields filled, missing fields NULL with method `unresolved`.
- Idempotent; incremental refresh updates only changed persons; manual overrides
  preserved.
- Real-PostgreSQL integration test; verified against real local data before merge.

### ENG-507 — derived metrics + global filter/time-range contract
- Shared `AnalyticsFilters` (date range, location, campaign, source, vendor,
  caller, coordinator, doctor) + `TimeRange` resolver (Today…Custom), unit-tested
  for aggregate AND per-location.
- Derived metrics (cost-per-stage, revenue-per-stage, ROI, conversions) as typed
  service functions; divide-by-zero → null. One existing page refactored onto it.

### ENG-508 — export + drill-down
- CSV + XLSX download for ≥ Funnel + Marketing + one performance page, honoring
  filters. Drill-down endpoint returns the `person_uid` set behind a metric.

## B1 — Missing-field enablement (nullable + dual fill)
- ENG-509: SF Lead/Opportunity owners resolved to actors (auto) + manual override;
  fact carries caller_id/coordinator_id + provenance.
- ENG-510: CareStack providers resolved to actors (auto) + manual override;
  fact carries doctor_id + provenance.
- ENG-511: treatment-accepted + surgery definitions documented (or blocker
  recorded); auto-extract where a reliable signal exists; manual path otherwise.
- ENG-512: marketing_cost_allocated computed where attribution resolves;
  allocation reconciles to campaign spend; unit-tested.
- ENG-513: operator can set any not-yet-automatic field manually; value +
  provenance survive a fact rebuild (manual > auto > unresolved); audit row per edit.

## B2 — Pages (14): ENG-514..ENG-527
- Each page renders at its route with a nav entry, consumes the shared filter +
  derived metrics, supports aggregate + per-location, and shows honest "no data"
  for unresolved fields.
- Numbers reconcile with the existing Funnel / PM dashboards for at least one
  month + one location on real data.
- Typed FastAPI `*Out` ⇄ Zod parity for every new endpoint.

## B3 — Closeout
- ENG-528: documented AI-readiness (tool surface, features, guardrails); optional
  read-only stub tool through the service layer.
- ENG-529: full verify loop green or documented blockers; real-data reconciliation;
  Codex cross-runtime review sign-off; invariants confirmed (no agent DB, PHI-free
  logs, no raw payloads, manual-override survives rebuild, prod job gated off).

## Out of scope (do NOT build)
- ML models / live predictions (only AI-readiness hooks).
- Provider write-back (CareStack/Salesforce stay read-only).
- Production deploy of the fact-builder job by default (operator flips on deploy).
- Per-endpoint authn/authz and field redaction (pre-access-control phase).
