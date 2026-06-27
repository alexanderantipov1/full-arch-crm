# Worker Prompt — B2 Data-Ready Pages (ENG-514, 515, 521, 526, 523)

You are an autonomous Claude Code Worker for the Fusion CRM Revenue Intelligence
Analytics Platform (epic ENG-504). The B0 foundation is MERGED into `main` (your
base): `analytics.fact_patient_journey` (backfilled in dev — 115k rows), the
shared `AnalyticsFilters` + `TimeRange` resolver + derived metrics in
`packages/analytics`, and a working pattern endpoint
`GET /dashboard/analytics/journey-metrics` (`JourneyMetricsOut`) in
`apps/api/routers/dashboard.py`. Build **5 staff analytics pages** that need NO
B1 enablement, sequentially on one branch. When unsure, STOP and write
`Blocked:`/`Needs decision:` in your report.

## Read first
- `apps/api/CLAUDE.md`, `apps/web` conventions; the existing analytics pages under `apps/web/app/(staff)/analytics/*` (calls/sales/marketing/seo/funnel) for the exact FE pattern (TanStack hook + Zod schema + page + nav entry).
- `packages/analytics/` (filters, metrics, metrics_service, fact_repository) — reuse, do not redefine metrics.
- The `journey-metrics` endpoint + `JourneyMetricsOut` as the template for shape + Zod parity.
- Linear ENG-514, ENG-515, ENG-521, ENG-526, ENG-523 (full descriptions) + `market.md` pages 1,2,8,13,10.

## Ownership card
```yaml
task_class: normal (read-only over fact; NO migrations)
branch: eng-514-b2-dataready-pages   (launcher provisions the worktree from main)
owned_paths:
  - apps/web/app/(staff)/analytics/**
  - apps/web/lib/api/schemas/**
  - apps/web/lib/api/hooks/**
  - packages/analytics/metrics_service.py , packages/analytics/queries*.py  # read-only aggregates per page
shared_paths (additive — append only, a B1 worker may also touch dashboard.py):
  - apps/api/routers/dashboard.py              # add one endpoint per page under /analytics/*
  - apps/web/components/layout/AppShell.tsx     # add one nav entry per page
forbidden_paths: [ .env*, infra/**, .github/workflows/**, packages/db/alembic/versions/** ]
integration_mode: draft_pr_only_no_merge
```

## Pages (in order — commit per page)
1. **ENG-514 Executive Overview** `/analytics/executive` — revenue widgets (today…YTD), funnel counts, cost metrics, conversions, ROI. All from fact + derived metrics; honest "no data" for surgery/accepted/cost-until-B1.
2. **ENG-515 Funnel Analytics** `/analytics/funnel` — extend/align the existing funnel onto the shared fact + filters WITHOUT regressing current numbers; per-stage count/conversion/cost/revenue; new stages (accepted/surgery) show "no data".
3. **ENG-521 Revenue Intelligence** `/analytics/revenue` — revenue by source/location (+ campaign where resolved); gross/collected/outstanding/avg-case-value. Dimensions needing B1 (vendor/caller/coordinator/doctor) render "no data"/"Unattributed".
4. **ENG-526 Cohort** `/analytics/cohort` — group by lead-creation month (person-anchored); revenue after 30/60/90/180/365 days from collected_amount + payment dates. No false bulk-import spike.
5. **ENG-523 Patient Journey** `/analytics/patient-journey` — per-person timeline from fact dates (+ existing operational-timeline ENG-235); responsible employee = caller/coordinator/doctor → "no data" until B1.

Every page: global filter bar incl. **location (aggregate + per-location)**, the supported time-range presets, typed FastAPI `*Out` ⇄ Zod parity, nav entry. Reuse the shared filter/metrics — do not reinvent.

## Hard guardrails
- Base = `main` (has B0). **DO NOT merge / push to main / deploy. Draft PR only.**
- **NO migrations** (pages are read-only over the fact table). If you think you need one, STOP and report.
- No `.env*`/infra/deploy. No business logic in routes (compose in `packages/analytics`). No direct DB from agents. Logs PHI-free; no raw payloads.
- Stage only your files; commit per page with the Claude Co-Authored-By trailer.

## Verify + report
- Backend: `ruff check .`, `mypy .` clean; unit tests for each page's aggregate. Web: `pnpm -C apps/web tsc --noEmit` (or the repo's typecheck) + lint clean; Zod ⇄ Pydantic parity.
- If the dev API/web is running you may eyeball a page render, but do not depend on it.
- Write `reports/ENG-514-pages-worker-report.md`: pages done, branch, touched files, tests + results, draft PR URL, risks, blockers, do-not-merge conditions. Then STOP.
