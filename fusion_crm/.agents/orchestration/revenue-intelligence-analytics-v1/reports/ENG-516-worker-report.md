# ENG-516 (B2.3) — Marketing Performance page — Worker Report

- **Linear:** ENG-516 — B2.3 Page: Marketing Performance
- **Mission:** revenue-intelligence-analytics-v1
- **Task class:** `normal` (read-model page; NO schema/migration added)
- **Branch / worktree:** `eng-516-eng-516` (isolated worktree off `main`)
- **Status:** ✅ Build complete. ⚠️ Automated verification (ruff/mypy/pytest/
  alembic, web lint) **could not be executed** — every binary invocation in
  this worker sandbox returned "requires approval" and was declined. The code
  was reviewed statically instead. **Do-not-merge until the verify suite is run
  green by the operator/reviewer** (commands below).

---

## What was built

A new read-model analytics page, `Marketing Performance`, mirroring the existing
B2 pages (Executive / Funnel / Revenue / Cohort) exactly — shared
`AnalyticsFilters` + time-range resolver + `safe_div` derived-metric layer,
thin route, logic in `packages/analytics`, Zod-mirrored contract.

Route: **`GET /dashboard/analytics/marketing-performance`** (+ nav entry).

### Data model / approach (honest, reconcilable)

- **Spend per group = `SUM(fact_patient_journey.marketing_cost_allocated)`** —
  the cost-per-lead allocation ENG-512 already writes (ad→campaign→$0). This is
  the spend that resolved to leads in the group, and it reconciles with the
  allocator.
- **Campaign + Source breakdowns** (required) resolve from the fact, each with
  the full metric set: **Spend, Leads, Consultations, Shows, Surgeries, Revenue,
  ROI** + cost-per-lead/consult/show/surgery. Counts are cohort-anchored on
  `lead_date` (same anchor as Funnel/Revenue), so the numbers reconcile across
  pages for a window.
- **Ad Set / Ad**: the fact carries **no** ad-set/ad dimension column, so
  outcomes cannot be tied to them — returned as `resolved=false` panels with an
  honest "no data" note (same pattern Revenue uses for vendor/caller/etc.). This
  is the in-scope honest answer; tying outcomes to ad-set/ad would need an
  `ad_id` on the fact (a builder/B-level change, out of scope here).
- **"Spend without leads"** is surfaced at the **window level**:
  `total_spend` (ground-truth ad spend from `MarketingService.ad_spend_totals`)
  − `allocated_spend` (Σ `marketing_cost_allocated`), floored at 0. This is the
  ad spend that produced no attributed leads — surfaced, not hidden.
- **Divide-by-zero → null** (never a fabricated 0) via the shared `safe_div`.
  `spend`, ROI, and every cost-per-X are `null` when no ad-spend source is
  connected for the window (UI renders "—").
- **Global filters incl. location** (aggregate default + per-location; window
  resolved in the location's timezone) flow through the shared
  `_apply_dimension_filters`.

---

## Changed / added files

### Backend (`packages/analytics`, `apps/api`)
- `packages/analytics/schemas.py` — **added** `MarketingGroupOut`,
  `MarketingBreakdownOut`, `MarketingPerformanceOut`.
- `packages/analytics/queries.py` — **added** `MarketingGroupRow` dataclass,
  `_MARKETING_DIMENSION_COLUMNS` / `MARKETING_DIMENSIONS`, and
  `FactAnalyticsQueries.marketing_breakdown(window, filters, dimension)`
  (read-only group-by over the fact; campaign/source).
- `packages/analytics/metrics_service.py` — **added**
  `AnalyticsPagesService.marketing_performance(...)` + static
  `_marketing_group_out(...)` helper; module constants
  `_MARKETING_UNRESOLVED_DIMENSIONS` / `_MARKETING_UNRESOLVED_NOTE`; imports.
- `apps/api/routers/dashboard.py` — **added** the thin route
  `analytics_marketing_performance` (`GET /analytics/marketing-performance`) +
  `MarketingPerformanceOut` import. Composes only (reuses `_analytics_filters`).

### Frontend (`apps/web`)
- `apps/web/lib/api/schemas/marketingPerformance.ts` — **new** Zod schemas
  (`MarketingGroupSchema` / `MarketingBreakdownSchema` /
  `MarketingPerformanceSchema`), field-for-field parity with the `*Out`.
- `apps/web/lib/api/schemas/index.ts` — **added** export.
- `apps/web/lib/api/hooks/useMarketingPerformance.ts` — **new** TanStack Query
  hook (parses against the Zod schema).
- `apps/web/app/(staff)/analytics/marketing-performance/page.tsx` — **new** page
  (filter bar + totals cards + per-dimension tabs; reuses `MetricCard`,
  `AnalyticsFilterBar`, shared formatters; "—" for null per the cardinal rule).
- `apps/web/components/layout/AppShell.tsx` — **added** nav item
  "Marketing performance" (`Target` icon) under the analytics group.

No MSW handler added — the real backend endpoint ships in this same change
(per `apps/web/CLAUDE.md` rule 4, MSW handlers exist only until the backend
lands).

### Tests
- `tests/analytics/test_marketing_performance.py` — **new** pure-unit tests for
  `_marketing_group_out` (connected derived metrics; spend→null when not
  connected; div-by-zero→null).
- `tests/integration/test_analytics_pages.py` — **added**
  `test_marketing_performance_breakdowns` (real-PG: campaign/source breakdowns,
  spend reconciliation `total=800 / allocated=500 / without_leads=300`, ROI,
  ad_set/ad `resolved=false`) and `test_marketing_performance_no_spend_connected`
  (spend fields null when no `AdMetricDaily`). Skips cleanly without a test DB.

---

## Verification — NOT YET RUN (operator must run before merge)

Every command below was declined by the worker sandbox (approval-gated). Run
from the worktree with the canonical `.venv`:

```bash
.venv/bin/ruff check packages/analytics apps/api/routers/dashboard.py \
    tests/analytics/test_marketing_performance.py \
    tests/integration/test_analytics_pages.py
.venv/bin/mypy packages/analytics apps/api/routers/dashboard.py
.venv/bin/python -m pytest tests/analytics/test_marketing_performance.py \
    tests/integration/test_analytics_pages.py -q
cd packages/db && alembic check        # expect: no migration / no drift
cd apps/web && npm run lint             # eslint + tsc --noEmit (strict)
```

### Static review performed (in lieu of execution)
- **Ruff:** removed an unused import (`MARKETING_DIMENSIONS`) from the service;
  no other obvious lint issues; docstrings/line-length follow the surrounding
  style.
- **Mypy:** `spend_without_leads` uses `totals.spend` (always `float`) under the
  `connected` guard to avoid a `None`-subtraction; `safe_div` accepts
  `float | None` for spend/ROI; `sum(...)` patterns match existing service code
  that already type-checks.
- **Zod parity:** all three `*Out` ⇄ `*Schema` verified field-for-field
  (names, nullability, int vs number).
- **No migration:** only ORM reads added; no model/column/table changes →
  `alembic check` expected clean (please confirm).

---

## Real-data eyeball check — PENDING (acceptance gate)

Not performed (no DB access in this sandbox). Before merge, against dev/prod
data for one window, confirm:
- `total_spend` matches the existing Marketing dashboard
  (`/dashboard/analytics/marketing`) spend KPI for the same window.
- Campaign/source `leads`/`revenue` reconcile with the Revenue Intelligence
  page (`/dashboard/analytics/revenue`) for the same window (shared `lead_date`
  cohort anchor).
- `allocated_spend + spend_without_leads ≈ total_spend` (allocator
  reconciliation; equality holds when each ad rolls up to a campaign whose
  campaign total ≥ its ad total — the normal Meta case).

---

## Risks / notes
- **Ad Set / Ad outcomes are intentionally "no data"** (fact has no ad-set/ad
  dimension). If the operator expects per-ad-set/per-ad **spend** tables, that
  is a follow-up: it needs `ad_id`/`ad_set_id` on `fact_patient_journey` (a
  builder change) or a separate marketing-spend-only read that cannot tie to
  lead outcomes. Flagged, not silently dropped — `spend_without_leads` covers
  the reconciliation gap honestly.
- **Source vocabulary**: groups by the actual `fact.source` values present
  (NULL → "Unattributed"), not a hardcoded Facebook/Google/Organic/Referral/
  Direct/CallRail list — honest to the data, consistent with the Revenue page.
- **`marketing_cost_allocated`** is NULL on rows the builder hasn't allocated
  (pre-B1); `SUM` ignores NULLs (coalesced to 0), so a window with allocation
  not yet run shows allocated 0 and ROI "—" — honest, not an error.
- PHI-free: only campaign/source labels, counts, and money in
  logs/values — no patient identifiers.

## Do-not-merge conditions
1. Run the full verify suite (above) green — including web lint/typecheck.
2. Complete the real-data eyeball reconciliation for one window.
3. Cross-runtime (Codex) review (contract/new-endpoint surface).
4. Merge to `main` == prod deploy → operator-gated; do not merge without
   explicit operator go-ahead for a deploy this session.

## Out of scope (not done, by design)
- No commit / push / PR / merge / deploy (build only).
- No schema/migration, no spend mutation, no raw provider payloads exposed.
