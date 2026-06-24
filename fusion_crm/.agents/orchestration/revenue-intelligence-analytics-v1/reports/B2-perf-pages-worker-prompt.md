# Worker Prompt — Wave 3 / Worker C — remaining 9 pages

Autonomous Claude Code Worker, Fusion CRM Revenue Intelligence Analytics (epic
ENG-504). Base = `main`, which ALREADY has: `analytics.fact_patient_journey`
(backfilled in dev — 115k rows, caller/coordinator/doctor now populated by B1),
the shared `AnalyticsFilters`+`TimeRange`+derived metrics, `FactAnalyticsQueries`
(`packages/analytics/queries.py`), `AnalyticsPagesService`
(`packages/analytics/metrics_service.py`), the shared FE `AnalyticsFilterBar` +
`MetricCard` + `format.ts`, and 5 shipped pages (executive/funnel/revenue/cohort/
patient-journey) under `apps/web/app/(staff)/analytics/`. **Reuse those patterns
exactly.** When unsure, STOP and write `Blocked:`/`Needs decision:` in the report.

## Build these 9 pages (market.md pages 3,4,5,6,7,9,11,12,14), commit-grouped per page
1. **ENG-516 Marketing Performance** `/analytics/marketing-performance` — Campaign/AdSet/Ad/Source breakdown: spend, leads, consults, shows, surgeries, revenue, ROI (join fact + `marketing.*`). AdSet/Ad where attribution resolves; else "no data".
2. **ENG-517 Vendor Performance** `/analytics/vendor` — group by `vendor_id` (attribution); ranking table: spend-managed, leads, consults, shows, surgeries, revenue, ROI. Unresolved → "Unattributed" bucket.
3. **ENG-518 Caller Performance** `/analytics/caller` — group by `caller_id`: leads assigned, (calls/reached = "no data" until telephony), consults booked; conversions lead→contact/consult; revenue influenced / per lead / per consult.
4. **ENG-519 Coordinator Performance** `/analytics/coordinator` — group by `coordinator_id`; ranking: consults assigned, shows, plans presented, surgeries sched/completed, revenue; conversions scheduled→show, show→surgery, show→revenue. (coordinator sparse in data — render honestly.)
5. **ENG-520 Doctor Performance** `/analytics/doctor` — group by `doctor_id`: consults, plans, accepted, surgeries, revenue; conversions consult→accepted, accepted→surgery; revenue per consult / per surgery. (accepted/surgery NULL until ENG-511 → "no data".)
6. **ENG-522 Cost Intelligence** `/analytics/cost` — marketing cost-per-lead/consult/show/surgery (from `marketing.*`/derived metrics). Operational cost-per-conversion: **"no data"** — flag `Needs decision:` (no staff-cost basis yet).
7. **ENG-524 Bottleneck Detection** `/analytics/bottlenecks` — deterministic rule-based detector over fact aggregates (conversion vs baseline/threshold): description, est. revenue loss (= gap × avg case value, documented), severity, suggested action. NOT AI. Only resolved dimensions.
8. **ENG-525 Attribution Analytics** `/analytics/attribution` — revenue-by Campaign/Vendor/Caller/Coordinator/Doctor over completed/revenue-positive cases. Unresolved grouped honestly.
9. **ENG-527 Revenue Influence Matrix** `/analytics/revenue-influence` — employee × role (Vendor/Caller/Coordinator/Doctor) × revenue-influenced (= sum collected where they held the role; document the per-role, non-additive model). Unresolved excluded.

Every page: shared `AnalyticsFilterBar` (location aggregate + per-location, time presets), typed FastAPI `*Out` ⇄ Zod parity, TanStack hook, page, nav entry. Backend in `AnalyticsPagesService`/`FactAnalyticsQueries` (read-only over fact + `marketing.*`); routes compose only.

## Ownership / guardrails
- owned: `apps/web/app/(staff)/analytics/**`, `apps/web/lib/api/{schemas,hooks}/**`, `packages/analytics/{queries.py,metrics_service.py}`; shared (additive, append): `apps/api/routers/dashboard.py`, `apps/api/dependencies.py`, `packages/analytics/schemas.py`, `apps/web/components/layout/AppShell.tsx`.
- forbidden: `.env*`, `infra/**`, `.github/workflows/**`, `packages/db/alembic/versions/**` (NO migrations — pages are read-only).
- **Do NOT merge/push/deploy.** Leave work in the worktree (the orchestrator commits + merges). No business logic in routes. No direct DB from agents. Logs PHI-free; no raw payloads. Honest "no data"/"Unattributed" — never fabricate.

## Verify + report
- `ruff`+`mypy` clean; FE `tsc --noEmit`+`eslint` clean; unit/integration tests per page on real PG where feasible; reuse existing test patterns (`tests/integration/test_analytics_pages.py`).
- Write `reports/wave3-pages-worker-report.md`: pages done, touched files, tests+results, risks, `Needs decision:` items (esp. ENG-522 operational cost). Then STOP.
