# Worker Prompt — B0 Foundation (ENG-505 → ENG-506 → ENG-507)

You are an autonomous Claude Code Worker for the Fusion CRM Revenue Intelligence
Analytics Platform mission (epic ENG-504). Build the analytics **foundation**
only — B0.1, B0.2, B0.3 — in sequence, on one branch, one migration chain.
You run unsupervised overnight. When in doubt, STOP and write a `Blocked:` /
`Needs decision:` line in your report rather than guessing.

## Read first
- `CLAUDE.md`, `apps/api/CLAUDE.md`, `packages/*/CLAUDE.md` for any area you touch.
- `.agents/orchestration/revenue-intelligence-analytics-v1/{goal,acceptance,contract,verification}.md`
- `.agents/strategy/REVENUE_INTELLIGENCE_ANALYTICS_PLATFORM_PLAN.md`
- `market.md` (the source spec).
- The three Linear issues: ENG-505, ENG-506, ENG-507 (read their full descriptions).
- `docs/analytics/full-funnel-v2-person-anchored.md` (reuse the person-anchored
  dating + status mapping + Net-Collected semantics).

## Ownership card
```yaml
task_id: ENG-505/506/507 (B0 foundation, sequential)
linear_issue_url: https://linear.app/fusion-dental-implants/issue/ENG-505
task_class: contract_change
worker_runtime: claude-code
branch: eng-504-revenue-intelligence-analytics-v1
workspace: isolated_worktree (provisioned by launcher)
owned_paths:
  - packages/analytics/**
  - apps/web/lib/api/schemas/**   # only if needed for the filter DTO Zod parity
  - docs/analytics/**
  - apps/worker/jobs/fact_patient_journey_*.py
  - packages/db/alembic/versions/**   # ONE new revision, chained
shared_paths (additive only, coordinate):
  - apps/api/routers/dashboard.py     # add shared filter DTO + one smoke endpoint
  - packages/db/__init__.py           # register the new `analytics` schema
  - docs/data-model/CATALOG.md
forbidden_paths:
  - .env*
  - infra/**
  - .github/workflows/**
integration_mode: draft_pr_only_no_merge
requires_cross_runtime_review: true
```

## What to build (in order)

### ENG-505 — `analytics` schema + `fact_patient_journey`
- New PostgreSQL schema `analytics`; register it wherever schemas are declared
  (`packages/db`), and add a one-line note to root `CLAUDE.md` invariant #1 that
  `analytics` is an operator-approved read-model schema (rebuildable projection,
  never a source of truth).
- SQLAlchemy 2.0 model + ONE new Alembic revision (chained on the current head)
  creating `analytics.fact_patient_journey`, one row per `person_uid`:
  columns per market.md PLUS `location_id`; **every column nullable except
  `person_uid` (UUID PK)**. No cross-domain Python FK (plain UUID columns).
- Provenance: add a JSONB `field_provenance` column storing, per field,
  `{source, method: auto|manual|unresolved, confidence, resolved_at}`.
- File an ADR under `docs/decisions/` recording the new-schema approval.
- Update `docs/data-model/CATALOG.md`.

### ENG-506 — fact builder + refresh job
- Service in `packages/analytics` that projects `fact_patient_journey` from
  canonical domains (mapping is in the ENG-506 Linear description — follow it
  exactly): person_uid, lead_date (person-anchored, reuse ENG-481 dating),
  consult_scheduled/show dates, treatment_presented, first_payment, revenue
  (Net-Collected, exclude `payment_applied`, ENG-283), source, location_id.
  Set caller/coordinator/doctor/treatment_accepted/surgery_*/marketing_cost to
  NULL with provenance method `unresolved`. campaign/vendor from `attribution.*`
  only if already resolved, else NULL.
- Idempotent backfill + incremental refresh. Register an arq job; it must be
  **gated OFF by default** (no auto-run in prod).

### ENG-507 — derived metrics + global filter/time-range contract
- Shared `AnalyticsFilters` (date range, location, campaign, source, vendor,
  caller, coordinator, doctor) + `TimeRange` resolver (Today…Custom, tz-aware),
  location supports aggregate (default) AND per-location.
- Derived-metric functions (cost-per-stage, revenue-per-stage, ROI, conversions)
  over fact + `marketing.*`; divide-by-zero → None.
- Add ONE smoke endpoint under `/dashboard/analytics/*` proving the filter DTO +
  a fact aggregate (typed `*Out` ⇄ Zod parity). Do not build the 14 pages.

## Hard guardrails (non-negotiable)
- **DO NOT merge. DO NOT push to main. Open a DRAFT PR only.** Migration +
  contract change requires the operator + cross-runtime review first.
- **DO NOT run the new migration against the shared dev database.** Test it on a
  throwaway/scratch Postgres (e.g. a temporary `docker run` Postgres or a
  disposable test DB) with `alembic upgrade head` + `alembic check`. The shared
  dev DB has a documented history of being wedged by migrations — never risk it.
- No `.env*`, no infra, no deploy, no GitHub Actions edits.
- No direct DB access from any agent/tool code — services/repositories only.
- Logs PHI-free; no raw provider payloads in any output.
- Stage only files you created/changed for B0; never `git add -A` (other
  sessions' uncommitted files are present in the canonical checkout — but you are
  in an isolated worktree, so just stage your explicit paths).
- Commit per ticket with clear English messages. End each commit message with the
  Co-Authored-By trailer for Claude.

## Verification (run before opening the draft PR)
- `ruff check .` and `mypy .` clean on touched files/packages.
- Migration: `cd packages/db && alembic upgrade head && alembic check` on a
  SCRATCH DB (not shared dev).
- Unit tests (mirror `tests/` layout): derived metrics incl. zero denominators;
  filter/time-range resolver for aggregate + per-location; provenance shape.
- If a real-PostgreSQL integration test for the builder is feasible against a
  scratch DB, add it; otherwise document why in the report.

## Report (mandatory)
Write `.agents/orchestration/revenue-intelligence-analytics-v1/reports/ENG-505-506-507-worker-report.md`
with: tickets, branch, touched files, what changed, tests run + results,
verification status, the draft PR URL, risks, blockers/`Needs decision:` items,
and explicit do-not-merge conditions. Then STOP — do not start B0.4 or any page.
