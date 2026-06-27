# Worker Prompt — Wave 3 / Worker D — ENG-511 + ENG-512 + ENG-508

Autonomous Claude Code Worker, Fusion CRM Revenue Intelligence Analytics (epic
ENG-504). Base = `main` (has B0 + B1: `analytics.fact_patient_journey`,
`FactPatientJourneyBuilder` with caller/coordinator/doctor + provenance
manual>auto>unresolved, `FactEnrichmentService`, `FactAnalyticsQueries`). Dev DB
backfilled (the orchestrator re-runs the backfill after review — you do NOT touch
the shared dev DB). When unsure, STOP and write `Blocked:`/`Needs decision:`.

## Tasks
### ENG-511 — treatment_accepted + surgery scheduled/completed
- The operator CONFIRMED surgery data is in scope. **Discovery first**: determine from `docs/integrations/carestack/` + `packages/ingest` (treatment-procedure / appointment raw payloads, `catalog.procedure_code` CDT) how (a) treatment-plan **acceptance** and (b) **surgery** scheduled/completed are represented. Document findings.
- Where a reliable signal exists: extract `treatment_accepted_date`, `surgery_scheduled_date`, `surgery_completed_date` (likely via `interaction.event` kinds and/or treatment-procedure status + procedure-code→surgery classification) and feed them into `FactPatientJourneyBuilder` with provenance `auto`.
- Where no reliable signal: leave NULL `unresolved` (manual fill already works via `FactEnrichmentService`) and record `Needs decision:` in the report. Do NOT guess a mapping.

### ENG-512 — marketing_cost_allocated
- Allocate ad spend (`marketing.ad_metric_daily`/`ad_campaign`, Google Ads live) to persons via resolved `attribution.*` campaign → pro-rata over persons attributed to that campaign in the window. Set `marketing_cost_allocated` + provenance `auto` (confidence from attribution); NULL where attribution unresolved.
- Reconcile: Σ allocated over a campaign-window ≈ that campaign's spend (within attributed share). Unit-test incl. zero-lead campaigns + reconciliation.

### ENG-508 — CSV/Excel export + drill-down
- Shared CSV + XLSX export honoring the active `AnalyticsFilters`, for the page result sets (at least Funnel + Marketing + one performance page). Replace the `export_available` stub with a real implementation.
- Drill-down endpoint: a metric → underlying `person_uid` set (filtered list for the person card). Bound/stream large results.

## Ownership / guardrails
- owned: `packages/analytics/{fact_builder.py,queries.py,metrics_service.py,export*.py}`, `packages/ingest/**` (read-only extraction additions), `apps/worker/jobs/fact_patient_journey_*.py`, `packages/db/alembic/versions/**` (≤1 new revision chained on head `a1b2c3d4e5f6`, test on SCRATCH DB only).
- shared (additive): `apps/api/routers/dashboard.py`, `apps/api/dependencies.py`, `packages/analytics/schemas.py`, `packages/marketing/service.py`.
- forbidden: `.env*`, `infra/**`, `.github/workflows/**`. **Do NOT touch the shared dev DB** (orchestrator runs the backfill). **Do NOT merge/push/deploy** — leave WIP in the worktree; orchestrator commits + merges.
- No direct DB from agents (services/repos). Logs PHI-free; no raw payloads in output/export.

## Verify + report
- `ruff`+`mypy` clean; migration (if any) `upgrade head`+`alembic check`+downgrade on a SCRATCH Postgres; unit tests (allocation reconciliation, export filter pass-through, any extraction logic).
- Write `reports/wave3-enablement-export-worker-report.md`: what landed per ticket, the ENG-511 acceptance/surgery findings (or blocker), touched files, tests+results, risks, do-not-merge conditions. Then STOP.
