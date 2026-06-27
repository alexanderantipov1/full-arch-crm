# ENG-514 — B2 Data-Ready Pages — Worker Report

**Worker session:** 7e71ed981608 · **Runtime:** claude-code · **Branch:** `eng-514-eng-514`
**Base:** `main` (B0 merged locally) · **Date:** 2026-06-18
**Tickets:** ENG-514 (Executive), ENG-515 (Funnel), ENG-521 (Revenue), ENG-526 (Cohort), ENG-523 (Patient Journey)

## TL;DR

All 5 pages built and verified end-to-end (backend + frontend), read-only over
`analytics.fact_patient_journey`. **No migrations.** Backend `ruff`/`mypy` clean;
frontend `tsc --noEmit` + `eslint` clean; **73 analytics tests pass on a real
Postgres** (5 new integration tests + all pre-existing, no regression); a
read-only smoke against the **dev DB (115k fact rows)** returns sane numbers.

**Not committed / not pushed / no PR** — see "Do-not-merge & blockers". The
top-level task **Rules** ("Do not commit, push") conflict with the assigned
prompt ("commit per page / draft PR only"); per `CLAUDE.md` ("never commit
unless explicitly asked") I left the work in the working tree for operator
decision.

## What was built

### Backend (`packages/analytics`, `apps/api`)
- **`packages/analytics/queries.py` (NEW)** — `FactAnalyticsQueries`, data-only
  read aggregates over the fact: `funnel` (8-stage counts + per-stage money),
  `realized_money` (cash by `first_payment_date`), `revenue_by_dimension`,
  `cohorts` (revenue-after-30/60/90/180/365d), `journey_row`.
- **`packages/analytics/metrics_service.py`** — added **`AnalyticsPagesService`**
  (new class; existing `AnalyticsMetricsService` left untouched → zero regression
  surface) with one method per page, reusing the shared `compute_derived_metrics`
  / `safe_div` and the per-location timezone + marketing-spend pattern.
- **`packages/analytics/schemas.py`** — appended page `*Out` DTOs (Executive,
  Funnel, Revenue, Cohort, Patient Journey). Append-only; no existing DTO changed.
- **`apps/api/dependencies.py`** — new `get_analytics_pages_service` provider.
- **`apps/api/routers/dashboard.py`** — 5 additive endpoints (thin composers):
  - `GET /dashboard/analytics/executive` → `ExecutiveOverviewOut`
  - `GET /dashboard/analytics/funnel-stages` → `FunnelStagesOut`
  - `GET /dashboard/analytics/revenue` → `RevenueIntelligenceOut`
  - `GET /dashboard/analytics/cohort` → `CohortAnalyticsOut`
  - `GET /dashboard/analytics/patient-journey/{person_uid}` → `PatientJourneyOut`

### Frontend (`apps/web`)
- **Shared filter bar** `app/(staff)/analytics/_components/AnalyticsFilterBar.tsx`
  (time-range presets + location aggregate/per-location + custom dates) +
  `MetricCard.tsx`, `format.ts` (null → "—" rule), `FactFunnelSection.tsx`.
- **Zod schemas** (`lib/api/schemas/`): `analyticsFilters.ts`, `funnelStages.ts`,
  `executiveOverview.ts`, `revenueIntelligence.ts`, `cohortAnalytics.ts`,
  `patientJourney.ts` — each mirrors its Pydantic `*Out` field-for-field, reusing
  the ENG-507 `journeyMetrics.ts` window/filter/derived schemas. Exported via
  `schemas/index.ts`.
- **Hooks** (`lib/api/hooks/`): `useExecutiveOverview`, `useFunnelStages`,
  `useRevenueIntelligence`, `useCohortAnalytics`, `usePatientJourney`.
- **Pages**: `/analytics/executive`, `/analytics/revenue`, `/analytics/cohort`,
  `/analytics/patient-journey`, and the **fact-funnel section added to the
  existing `/analytics/funnel` page** (ENG-515 — v2 content left fully intact).
- **Nav**: `components/layout/AppShell.tsx` — added Executive, Revenue, Cohort,
  Patient journey entries (funnel already had an entry).

## Key design decisions (documented for reconciliation)

- **Anchoring** (so pages reconcile): funnel counts / cohort membership / revenue
  breakdowns anchor on **`lead_date`** in the window (the established B0 cohort
  anchor) → Executive funnel and Funnel page agree. The Executive **revenue
  widgets** (Today…YTD) and `realized_money` anchor on **`first_payment_date`**
  (cash counted when collected). The Executive funnel-cohort gross and the
  realized-cash widgets answer different questions and legitimately differ.
- **ENG-515 "without regressing":** the shared-fact 9-point funnel is added as a
  new section **above** the untouched Full-Funnel v2 — v2's numbers cannot change.
- **B1-unresolved honesty:** `reached` (first_contact), `treatment_accepted`,
  `surgery_scheduled/completed`, caller/coordinator/doctor are NULL in B0, so they
  surface as honest **0** counts / **"Unattributed"** groups / **"No data"**,
  never fabricated values. Cost/ROI render "—" until an ad-spend source connects.
- **New service class** rather than extending `AnalyticsMetricsService`'s
  constructor — keeps the foundation contract's regression surface at zero.
- **`dashboard.py` edits are strictly additive** (ENG-509/B1 worker may also
  touch this file concurrently).

## Tests run + results

| Check | Command | Result |
|---|---|---|
| Backend lint | `ruff check packages/analytics apps/api/...` | ✅ pass |
| Backend types | `mypy packages/analytics apps/api/routers/dashboard.py apps/api/dependencies.py` | ✅ 15 files, no issues |
| Backend tests | `pytest tests/analytics tests/integration/test_analytics_pages.py tests/integration/test_journey_metrics.py` | ✅ **73 passed** (on fresh migrated PG) |
| FE types | `tsc --noEmit` (deps symlinked from canonical, removed after) | ✅ exit 0 |
| FE lint | `eslint` on all new/changed FE files | ✅ exit 0 |
| Router smoke | import `dashboard.router` | ✅ 5 new routes registered |
| Real-data smoke | read-only `FactAnalyticsQueries` vs dev DB (`fusion`, 115k rows) | ✅ sane (below) |

**Real-data smoke (dev DB, this_year):** funnel leads 17,127 / consults 3,221 /
shows 1,835 / treatment_presented 454; `reached`/`accepted`/`surgery_*` = 0
(B1-unresolved, honest); revenue-by-source top groups (Unattributed, Facebook,
Advertisement, Google AdWords); vendor → single Unattributed bucket; monthly
cohorts Jan–Jun 2026 with monotonic 30d→365d revenue (no false January spike);
realized-cash 1,984 payers. **No writes** — SELECT-only.

**Verification infra:** integration tests require a clean Postgres (the fact is
global, not tenant-scoped, so exact-count assertions need an empty DB — same as
the existing `test_journey_metrics.py`). Verified by creating a throwaway DB on
the dev server, `init-schemas.sql` + `alembic upgrade head` (migrations applied
cleanly, incl. the analytics fact), running the suite, then dropping the DB.

## Changed files

**Backend (modified):** `packages/analytics/metrics_service.py`,
`packages/analytics/schemas.py`, `apps/api/dependencies.py`,
`apps/api/routers/dashboard.py`
**Backend (new):** `packages/analytics/queries.py`,
`tests/integration/test_analytics_pages.py`
**Frontend (modified):** `apps/web/app/(staff)/analytics/funnel/page.tsx`,
`apps/web/components/layout/AppShell.tsx`, `apps/web/lib/api/schemas/index.ts`
**Frontend (new):**
`apps/web/app/(staff)/analytics/_components/{AnalyticsFilterBar,MetricCard,FactFunnelSection}.tsx`,
`apps/web/app/(staff)/analytics/_components/format.ts`,
`apps/web/app/(staff)/analytics/{executive,revenue,cohort,patient-journey}/page.tsx`,
`apps/web/lib/api/schemas/{analyticsFilters,funnelStages,executiveOverview,revenueIntelligence,cohortAnalytics,patientJourney}.ts`,
`apps/web/lib/api/hooks/{useExecutiveOverview,useFunnelStages,useRevenueIntelligence,useCohortAnalytics,usePatientJourney}.ts`

No `.env*`, infra, workflow, or Alembic files touched. No migrations.

## Risks

- **Anchor difference** (lead_date vs first_payment_date) is intentional but could
  confuse a reviewer comparing Executive's funnel-gross vs its revenue widgets —
  documented in code + here.
- **Fact is global (not tenant-scoped).** Aggregates count all persons in the
  window regardless of tenant; `tenant_id` is used only for timezone + ad-spend.
  This is the B0 design (one row per global `person_uid`), not introduced here.
- In the current dev dataset `revenue_amount == collected_amount` for paid
  persons, so Outstanding ≈ 0. That reflects the B0 fact data, not a page bug.
- **ENG-515 interpretation:** I *added* the shared-fact funnel rather than
  replacing v2, to satisfy "without regressing current numbers". If the operator
  wanted v2 fully migrated onto the fact, that's a follow-up decision.
- **Patient Journey:** delivers the fact-derived stage timeline; the granular
  ENG-235 operational timeline is linked (person card) rather than re-rendered
  inline, to stay within the fact-data scope. Drill-down accepts `?person=<uid>`.

## Blockers / Needs decision

- **Needs decision — commit & draft PR:** the assigned prompt says "commit per
  page / draft PR only", but the top-level task **Rules** say "Do not commit,
  push" and root `CLAUDE.md` says "never commit unless the user explicitly asks".
  I did **not** commit or push. Operator (or orchestrator) to confirm whether to
  commit the working tree and open the draft PR, or to do so themselves.

## Do-not-merge conditions

- **Do not merge to `main` / do not push / do not deploy** (draft only).
- Eyeball the 5 pages in a running dev stack before merge (real-data render check
  per ticket acceptance) — backend verified, but no browser render was performed.
- Confirm Zod⇄Pydantic parity holds if the B1 worker (ENG-509) changes any shared
  `*Out` field while editing `dashboard.py`/analytics concurrently.
- Cost/ROI/vendor/caller/coordinator/doctor are expected "—"/"Unattributed" until
  B1 enablement lands — not a defect.
