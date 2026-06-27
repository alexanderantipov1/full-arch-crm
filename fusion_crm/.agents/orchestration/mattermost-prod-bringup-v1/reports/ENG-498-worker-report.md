# Worker report — ENG-498 [5] prod notification delivery

- **Task / title:** ENG-498 — Prod notification delivery without a worker: Cloud Scheduler + Cloud Run Jobs
- **Linear:** https://linear.app/fusion-dental-implants/issue/ENG-498
- **Role / agent:** worker / Claude Code (inline, orchestrator-driven)
- **Branch / worktree:** `eng-498-prod-notification-delivery` @ `/Users/eduardkarionov/Desktop/fusion_eng498` (off `origin/main` `ad30acd`)
- **PR:** #173 (DRAFT) — https://github.com/alexanderantipov1/fusion_crm/pull/173
- **Task class:** `contract_change` (touches the canonical deploy script) → cross-runtime review required.

## Scope (owned)
`apps/worker/jobs/notification_drain.py`, `apps/worker/jobs/consult_reminder_scan.py`,
`tests/worker/test_notification_jobs.py`, `infra/scripts/deploy_cloud_run.sh` (additive only).

## What changed
- Two Cloud-Run-Job entrypoints wrapping the existing arq crons (mirror `salesforce_pull.py`):
  `run()` → `drain_notification_outbox({})` and `run()` → `scan_consultation_reminders({})`.
- `deploy_cloud_run.sh`: `JOB_NOTIFICATION_DRAIN` + `JOB_CONSULT_REMINDERS` jobs + matching
  Cloud Scheduler entries at `* * * * *` (1/min). Placed with the always-on bounce/keepalive
  jobs, **not** under `SCHEDULE_INTEGRATION_PULL` — messenger delivery is gated by
  `NOTIFICATIONS_ENABLED` (already in `JOB_ENV_VARS=...,NOTIFICATIONS_ENABLED=false`), so both
  jobs are cheap no-ops until ENG-500 flips the flag.
- Test: wrappers funnel into the cron with empty ctx and return its summary; crons mocked.

## Correction to the prior design artifact
`eng-498-delivery-design.md` claimed `scan_consultation_reminders` was NOT on main (only the
`eng-486` worktree). **Wrong** — `git grep` against `origin/main` shows it in
`apps/worker/jobs/consultation_reminders.py:117` and wired in `apps/worker/main.py:36,144`.
ENG-486 is merged. Both entrypoints were therefore built (not just the drain).

## Tests run
- `ruff check` on all 3 new files → **All checks passed**
- `pytest tests/worker/test_notification_jobs.py` → **4 passed**
- `pytest tests/worker/test_consultation_reminders.py` (regression) → **4 passed**
- `bash -n infra/scripts/deploy_cloud_run.sh` → valid
(Run with the canonical `.venv` + throwaway non-connecting env vars; crons fully mocked, zero real I/O.)

## Verification status
PASS for unit + lint + syntax. Real-data e2e (enqueue → Mattermost post within ~1 min) is
deferred to **ENG-500** enablement, after the host + bot + credential + rules exist.

## Risks
- `contract_change`: the deploy-script edit changes the prod deploy contract → needs review.
- Cloud Scheduler floor is 1/min (local arq runs every 10s); acceptable per the ticket's "~1 min".
- The jobs reuse the API image + `WORKER_EMAIL` SA + existing `JOB_ENV_VARS`/`JOB_SECRETS` — no
  new env var or secret introduced.

## Do-not-merge conditions
- Cross-runtime review (Codex) of the deploy-script change.
- Confirm single alembic head on `main` for the overall ENG-442 deploy (not this PR's concern, but the deploy that ships these jobs).
- Do not deploy/enable until ENG-494/495/496/497 exist and ENG-500 sets `NOTIFICATIONS_CUTOFF_AT` + flips `NOTIFICATIONS_ENABLED=true`.

## Suggested next task
Harden `provision_mattermost_host.sh.draft` → reviewed `infra/scripts/provision_mattermost_host.sh`
(DNS now scriptable — fusioncrm.app is on Cloud DNS), then a supervised [1]→[2] host bring-up.
