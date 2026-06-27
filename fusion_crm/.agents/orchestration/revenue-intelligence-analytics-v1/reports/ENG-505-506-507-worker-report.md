# B0 Foundation Worker Report — ENG-505 / ENG-506 / ENG-507

**Mission:** Revenue Intelligence Analytics Platform (epic ENG-504)
**Worker:** claude-code · **Session:** 3f5d89cd5223 · **Date:** 2026-06-18
**Branch:** `eng-505-b0-foundation` · **Draft PR:** https://github.com/alexanderantipov1/fusion_crm/pull/185
**Status:** ✅ All three tickets built, verified on a scratch Postgres, committed, draft PR open. **DO NOT MERGE** (conditions below).

---

## Summary

Built the analytics **foundation** (B0.1–B0.3) on one branch, one migration chain:
new `analytics` read-model schema + `fact_patient_journey`, the person-anchored
fact builder + gated refresh job, and the shared filter/time-range/derived-metric
contract + one smoke endpoint. The 14 pages were intentionally **not** built.

3 commits (one per ticket), each with the Co-Authored-By trailer:
- `0b50983` ENG-505 — analytics schema + fact_patient_journey + provenance
- `c50266d` ENG-506 — fact builder + gated arq refresh job
- `b411b20` ENG-507 — shared filter/time-range + derived metrics + smoke endpoint

> **Note on inputs:** `market.md`, `.agents/strategy/REVENUE_INTELLIGENCE_ANALYTICS_PLATFORM_PLAN.md`,
> and the `.agents/orchestration/revenue-intelligence-analytics-v1/{goal,acceptance,contract,verification}.md`
> files referenced in the prompt **do not exist in this worktree**. The authoritative
> column lists + source mappings were taken from the **Linear issue descriptions**
> (ENG-505/506/507), which were complete — so this was not a blocker.

---

## ENG-505 — `analytics` schema + `fact_patient_journey`

- New schema `analytics` registered in `packages/db/alembic/env.py` `DOMAIN_SCHEMAS`
  + model import in `packages/db/registry.py`. Created in-migration via
  `CREATE SCHEMA IF NOT EXISTS` (mirrors the attribution-chain revision).
- `packages/analytics/models.py` — `FactPatientJourney`: `person_uid` UUID **PK**,
  every other column **nullable**; dimensions (campaign/source/vendor/caller/
  coordinator/doctor/`location_id`), stage timestamps (lead→…→first_payment),
  money (revenue/collected/marketing_cost), `field_provenance` JSONB (NOT NULL,
  default `'{}'`), `created_at`/`updated_at`. Plain UUID columns (no cross-domain FK).
- `packages/analytics/provenance.py` — typed `FieldProvenance`
  `{source, method: auto|manual|unresolved, confidence, resolved_at}` + merge with
  precedence **manual > auto > unresolved** (a rebuild never clobbers a manual value).
- One chained Alembic revision **`e5d4c3b2a190`** (down_revision `f6a7b8c9d0e1`).
- ADR **`docs/decisions/ADR-0007-analytics-read-model-schema.md`**; root `CLAUDE.md`
  invariant #1 note; `docs/data-model/CATALOG.md` entry.

## ENG-506 — fact builder + gated refresh job

- `packages/analytics/fact_builder.py` (`FactPatientJourneyBuilder`) — composes via
  domain **services** (ops/identity/interaction/attribution), **owns no SQL** (same
  pattern as `FullFunnelService`), writes only to its own schema via
  `packages/analytics/fact_repository.py` (idempotent `ON CONFLICT (person_uid) DO UPDATE`).
  Mapping per ENG-506: lead_date person-anchored (ENG-481), source from `ops.lead`,
  consult/show/location from `ops.consultation`, treatment_presented + first_payment
  from `interaction.event`, revenue/collected = Net-Collected (ENG-283), campaign/vendor
  from resolved `attribution.lead_attribution`. caller/coordinator/doctor, treatment_accepted,
  surgery_*, first_contact, marketing_cost → NULL with provenance `unresolved`.
- New per-person batch reads (service + repo, one GROUP BY each, no bound IN):
  `ops.analytics_lead_facts_by_person`, `ops.analytics_consultation_facts_by_person`,
  `interaction.analytics_event_milestones_by_person`,
  `attribution.analytics_attribution_by_person`.
- `apps/worker/jobs/fact_patient_journey_refresh.py` — `refresh_fact_patient_journey`
  (backfill + incremental `only_persons`) + `_for_all_tenants` fanout. Registered in
  `WorkerSettings.functions`, **NOT in `cron_jobs`** → gated OFF (no auto-run in prod).

## ENG-507 — derived metrics + global filter/time-range + smoke endpoint

- `packages/analytics/filters.py` — `AnalyticsFilters` DTO (date range, location,
  campaign, source, vendor, caller, coordinator, doctor) + tz-aware `resolve_time_range`
  (Today…Custom). `location_id=None` = aggregate; a value scopes per-location, window
  resolved in that location's tz (`timezone_override` ?? `tenant.timezone`).
- `packages/analytics/metrics.py` — pure functions: cost/revenue per stage, ROI,
  conversion ratios; **divide-by-zero OR missing spend → None** (never a fabricated 0).
- `FactPatientJourneyRepository.aggregate()` — filtered stage counts + money (cohort
  anchored on `lead_date`).
- `AnalyticsMetricsService` (`metrics_service.py`) → `JourneyMetricsOut`.
- Endpoint `GET /dashboard/analytics/journey-metrics` (`apps/api/routers/dashboard.py`)
  + dependency in `apps/api/dependencies.py`; Zod mirror
  `apps/web/lib/api/schemas/journeyMetrics.ts` (+ `index.ts` export).

---

## Changed files (33 files, +2862 / −2)

**packages/analytics:** models.py, provenance.py, fact_repository.py, fact_builder.py,
filters.py, metrics.py, metrics_service.py, schemas.py
**packages/db:** registry.py, alembic/env.py, alembic/versions/20260618_0100_e5d4c3b2a190_…py
**ops/interaction/attribution:** service.py + repository.py (additive batch-read methods each)
**apps:** worker/jobs/fact_patient_journey_refresh.py, worker/main.py, api/dependencies.py,
api/routers/dashboard.py, web/lib/api/schemas/journeyMetrics.ts, web/lib/api/schemas/index.ts
**docs:** decisions/ADR-0007-…md, data-model/CATALOG.md, root CLAUDE.md
**tests:** analytics/{test_provenance,test_fact_builder,test_time_range,test_metrics,test_filters_dto}.py,
integration/{test_fact_patient_journey_builder,test_journey_metrics}.py

---

## Tests run + results

Run against a **throwaway `docker run` Postgres 16** (port 5599) — **never the shared dev DB**.

- `ruff check` — clean on all touched files.
- `mypy` — clean on all touched packages/files (15 source files).
- Migration: `alembic upgrade head` + **`alembic check` → "No new upgrade operations
  detected"** (model ⇄ migration in sync); downgrade→upgrade round-trips; all columns
  nullable except `person_uid` PK verified via `information_schema`.
- Unit: provenance (15), fact builder (10), time-range (12), derived metrics (4),
  filters DTO (6) — **all pass**.
- Integration (real Postgres): fact builder (2) + journey-metrics (2) — **all pass**
  (one row/person, person-anchored dating, Net-Collected, attribution, provenance,
  idempotency, incremental refresh, per-location scoping, empty window).
- Regression: `tests/integration/test_full_funnel_v2.py` green (additive domain methods
  did not break existing reads). Live endpoint `TestClient` smoke → HTTP 200, correct shape.

**Pre-existing unrelated failures (NOT caused by this work):**
`tests/ops/test_covering_opportunity.py` — 2 MagicMock-based tests fail on
`ConsultationOut.source_status` inside `attach_consultation_to_opportunity` (code untouched
by this branch). Confirmed they fail identically with the ops files reverted to the
pre-ENG-506 base commit (`2c4b93a`). Flagging only; out of scope.

---

## Verification status: ✅ PASS (within sandbox limits)

All acceptance items achievable in this environment are met. The one item that
**cannot** be satisfied here is ENG-506's real-data (~27k persons) verification — see below.

## Risks

- **Read-side of incremental refresh is a full scan.** `only_persons` restricts which
  rows are *written* (correct "changed persons only"), but the canonical reads are still
  full-table GROUP BYs. Fine for B0; a per-person filtered read is a follow-up optimization.
- **revenue_amount == collected_amount** in B0 (both mapped to Net-Collected per ENG-506).
  A distinct gross-revenue signal is a B1 refinement.
- **`source` for CareStack-direct persons is NULL** with provenance `method=auto`
  (`source="carestack_direct:no_lead"`) — deliberate: "computed, canonical has no lead".

## Blockers / Needs decision

- **None blocked the build.** Open epic decisions noted upstream: CareStack
  acceptance/surgery signal (ENG-511) and operational cost basis (ENG-522) keep
  treatment_accepted / surgery_* / marketing_cost as `unresolved` for now.

## 🚫 Do-not-merge conditions

1. **Real-data verification pending (ENG-506 acceptance).** Run the backfill against the
   ~27k-person local/dev dataset and sanity-check counts/revenue **before merge**. Not
   possible in this sandbox (scratch DB empty; shared dev DB off-limits by policy).
   Enqueue `refresh_fact_patient_journey_for_all_tenants` (or per-tenant) on the dev stack.
2. **`infra/docker/init-schemas.sql` not updated** (forbidden path for this worker). Add
   `CREATE SCHEMA IF NOT EXISTS analytics;` there for consistency (the migration already
   creates it, so fresh upgrades work either way).
3. **Web `tsc` not run** (apps/web deps not installed). Zod parity hand-verified
   field-for-field; confirm with `cd apps/web && npm run lint`.
4. **Cross-runtime (Codex) review required** — contract change + new migration.
5. Do not enable a cron for the refresh job in prod without an explicit operator decision
   (it is intentionally gated OFF / on-demand only).
