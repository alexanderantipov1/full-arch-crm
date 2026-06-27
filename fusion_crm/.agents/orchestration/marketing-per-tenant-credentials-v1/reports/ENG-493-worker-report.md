# ENG-493 — PROD Cloud Run Job + Scheduler for marketing/SEO pull

**Parent:** ENG-488 · **Mission:** marketing-per-tenant-credentials-v1
**Branch:** `eng-489-marketing-creds-provider-kinds` (no commit/push; no gcloud run)

## Problem

`pull_marketing_for_all_tenants` is an arq cron (fires 04:43 local in
dev/docker). Prod has no always-on arq worker (decommissioned in
ENG-172), so marketing/SEO data was never pulled in production. This
ticket adds the prod runtime: a scheduled Cloud Run Job for the daily
pull, plus an on-demand Job for the ENG-492 historical backfill —
mirroring the existing `fusion-job-cs-pull` / `fusion-job-backfill`
pattern.

## What was added

### `infra/scripts/deploy_cloud_run.sh`

Two new Cloud Run Jobs on the **API image** (COPYs `apps/` wholesale,
so `apps.worker.jobs.*` is importable), runtime SA `fusion-worker-sa`,
same `deploy_job` helper as every other job (VPC connector,
`--vpc-egress=private-ranges-only`, `JOB_ENV_VARS`, `JOB_SECRETS`,
`--max-retries=1`, `--task-timeout=1800s`, `1Gi`/`1cpu`):

1. **`fusion-job-marketing-pull`** — daily pull. Invoked one-shot via
   `python -c "import asyncio; from apps.worker.jobs.marketing_pull
   import pull_marketing_for_all_tenants; asyncio.run(
   pull_marketing_for_all_tenants({}))"` — `python -c` because the
   entrypoint is an arq cron function taking a `ctx` with no
   `__main__` (mirrors `fusion-job-bounce-poll`). Signature verified:
   `pull_marketing_for_all_tenants(ctx) -> dict`.
   - **Inside the `SCHEDULE_INTEGRATION_PULL` gate** (job deploy +
     `grant_job_invoker` + scheduler).
   - Scheduler `fusion-sched-marketing-pull`, cron `43 11 * * *`
     (11:43 UTC = 03:43 PST / 04:43 PDT — nighttime PT year-round; the
     same `:43` minute the dev cron uses, off-the-quarter to dodge the
     `*/15` and `*/30` schedulers). Invoker `fusion-worker-sa` with
     `roles/run.invoker`.

2. **`fusion-job-marketing-backfill`** — on-demand historical load.
   Invoked via `python -m,apps.worker.jobs.marketing_backfill` (the
   module has a `__main__` argparse entrypoint, exactly like
   `fusion-job-backfill` uses `-m apps.worker.jobs.backfill_full`).
   - **Deployed unconditionally** (like `fusion-job-alembic-upgrade`),
     NOT under the halt gate — it has no scheduler, so there is nothing
     recurring to halt. Operator runs it once after creds are entered.
   - No `grant_job_invoker` (no scheduler; operator executes with own
     ADC).
   - Default ~365 days; override with `--args=--months,12` etc.

Also updated: job-name + sched-name variable declarations, the
`SCHEDULE_INTEGRATION_PULL=0` skip `warn`, and both end-of-run summary
blocks.

### Docs
- `infra/env/PRODUCTION.md` — "What is provisioned" job list; the
  "Deploying Cloud Run services" job descriptions; a new
  "Marketing/SEO pull + historical backfill (ENG-493)" runbook
  subsection (what the jobs do, schedule, one-shot backfill commands,
  manual-trigger + verify commands, the halt-gate note).
- `infra/CLAUDE.md` — `deploy_cloud_run.sh` job enumeration + ENG-493.

## Decisions

- **Halt gate:** the daily marketing-pull **joins**
  `SCHEDULE_INTEGRATION_PULL` (not a separate gate). It is an external
  integration reader like sf-pull/cs-pull; one emergency switch should
  pause *all* external pulls, including marketing. The backfill is
  exempt because it has no scheduler (nothing to halt) and its
  definition must stay deployable for on-demand runs.
- **No marketing secrets on the deploy path.** Per ENG-490, both jobs
  resolve per-tenant creds from `tenant.integration_credential` via
  `IntegrationCredentialService` (needs only `DATABASE_URL` +
  `ENCRYPTION_KEY`, already in `JOB_SECRETS`). No Google/Meta
  client_id/secret is referenced on the command line or in env. Legs
  with no credential short-circuit to `skipped`, so running either job
  before creds exist is a safe no-op (matches the sf/cs contract).
- **Schedule:** fixed-UTC `43 11 * * *` matching the repo convention
  (Cloud Scheduler evaluates UTC; jobs above also bake UTC crons that
  land at PT night). Daily cadence because ad/analytics data has
  ~1-day latency and the pull re-reads a rolling 7-day window.

## Which DEPLOYMENT_RULES apply
- **§"Google Cloud Hosting Operating Model" (4)** — one-shot work is a
  Cloud Run Job, not a Service. Both new jobs are Jobs.
- **(5) One canonical deploy path** — job + scheduler live in
  `deploy_cloud_run.sh`, the canonical script (not one-off gcloud).
- **(3) Idempotent describe-or-create** — reuses `deploy_job` (gcloud
  run jobs deploy = create-or-update) and `upsert_scheduler`
  (describe → update/create). No deletes added; non-destructive.
- **§6 Secrets / tenant credentials** — tenant provider creds come from
  `tenant.integration_credential`, never modeled as Cloud Run env. No
  new secret added.
- **§9 Keep feature work separate from infra** — this change is
  infra-only (script + runbook); the worker jobs already landed in
  ENG-491/492.
- **§10 New env var checklist** — N/A: no new env var introduced (reuses
  existing `JOB_ENV_VARS` / `JOB_SECRETS`).

## Verification
- `bash -n infra/scripts/deploy_cloud_run.sh` → **SYNTAX OK**.
- Imported `pull_marketing_for_all_tenants` — callable, signature
  `(ctx) -> dict`, matching the `python -c` invocation.
- `marketing_backfill` confirmed to have a `__main__` argparse main(),
  matching `python -m`.
- Self-reviewed: new blocks use identical image (`$IMAGE_API`), SA
  (`$WORKER_EMAIL`), `deploy_job` flags, `grant_job_invoker`, and
  `upsert_scheduler` shapes as cs-pull/backfill; all under `CI_MODE != 1`.

## Risks / notes
- The operator must run the full `deploy_cloud_run.sh` (not CI_MODE) to
  create the new Job + Scheduler; CI only retargets existing service
  revisions. (Same as every other Job/Scheduler in the script.)
- `:43`-minute scheduler is unique among the existing entries — no
  collision with `*/15`/`*/30`/`17`/`23` crons.
- Backfill default window is 365 days; on a fresh tenant with creds this
  is a one-time heavier run — operator can narrow with `--days` /
  `--providers`. Chunked + idempotent, so safe to re-run.
- No Cloud Monitoring alert policy added for the marketing jobs
  (`provision_monitoring.sh` is operator-run, out of scope here); a
  follow-up could add a marketing-pull no-success alert mirroring the
  cs-pull policy.
