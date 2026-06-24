# ENG-498 — Prod notification delivery without an always-on worker

**Mission:** Mattermost prod bring-up v1
**Tickets:** ENG-498 (Cloud Scheduler + Cloud Run Jobs for the messenger engine), ENG-500 (enable on prod + smoke)
**Status:** DESIGN + DRAFTS ONLY. No gcloud mutation, no deploy, no `.env` edit, no commit.
**Author runtime:** worker (read-only research over the repo)

---

## 1. The gap

Production has **no always-on arq worker**. The `fusion-worker` Cloud Run *Service*
was decommissioned in ENG-172 (arq has no HTTP surface, so Cloud Run health checks
always failed — see `apps/worker/CLAUDE.md:7-23`). Recurring background work now runs
as **one-shot Cloud Run Jobs triggered by Cloud Scheduler**, reusing the API image
(`apps/api/Dockerfile` COPYs the whole `apps/` tree, so `apps.worker.jobs.*` is
importable — `deploy_cloud_run.sh:538-541`).

The messenger engine has two pieces that were authored as **arq crons** and therefore
have **nowhere to run in prod**:

| Cron coroutine | File | What it does | Cadence intent |
|---|---|---|---|
| `drain_notification_outbox(ctx)` | `apps/worker/jobs/notification_dispatch.py:82` | Locks pending `integrations.notification_outbox` rows (`FOR UPDATE SKIP LOCKED`), resolves the Mattermost provider, posts the card, marks `sent`/`failed`. | "~every 10s" in dev arq; **~1 min in prod** (min Scheduler granularity). |
| `scan_consultation_reminders(ctx)` | `apps/worker/jobs/consultation_reminders.py:117` **(ENG-486 — NOT on main yet)** | Every minute finds CONFIRMED consultations starting within 15m and `emit()`s a `consultation.reminder` event, dedup-keyed by consultation id. | every 1 min. |

**Solution:** wrap each cron in a thin one-shot `run()` entrypoint and run it as a
**scheduled Cloud Run Job**, exactly like `fusion-job-sf-pull` / `fusion-job-cs-pull` /
`fusion-job-marketing-pull`.

---

## 2. New Cloud Run Jobs + Cloud Scheduler entries

Two new recurring Jobs, each with its own Scheduler entry, following the
`JOB_*` / `SCHED_*` naming already in `deploy_cloud_run.sh`.

| Bash var | Resource name | Schedule (cron, UTC) | Command / args | Notes |
|---|---|---|---|---|
| `JOB_NOTIFICATION_DRAIN` | `fusion-job-notification-drain` | `* * * * *` (every 1 min) | `python -m apps.worker.jobs.notification_drain` | Drains the outbox -> posts to Mattermost. |
| `JOB_CONSULT_REMINDERS` | `fusion-job-consult-reminders` | `* * * * *` (every 1 min) | `python -m apps.worker.jobs.consult_reminder_scan` | T-15m reminder scan. **Blocked on ENG-486 reaching main.** |
| `SCHED_NOTIFICATION_DRAIN` | `fusion-sched-notification-drain` | `* * * * *` | -> `fusion-job-notification-drain:run` | |
| `SCHED_CONSULT_REMINDERS` | `fusion-sched-consult-reminders` | `* * * * *` | -> `fusion-job-consult-reminders:run` | |

**Cadence rationale:** Cloud Scheduler's minimum granularity is 1 minute, vs the 10s
arq cron the drain used in dev. 1-minute delivery latency is acceptable for the
clinic-facing notifications (lead/consult cards, T-15m reminders — the reminder
horizon is 15 min, `consultation_reminders.py:46`). No sub-minute path exists on
Cloud Scheduler without a self-rescheduling loop, which we explicitly avoid.

**Gate decision:** these two jobs are the **messenger runtime**, not external-integration
readers, so they MUST NOT sit behind `SCHEDULE_INTEGRATION_PULL` (that flag is the
emergency stop for CareStack/Salesforce/marketing *pulls*; halting messenger delivery
is a different operational concern). They deploy unconditionally inside the
`CI_MODE != 1` operator block. If a kill-switch is wanted, the natural lever is
`NOTIFICATIONS_ENABLED=false` (the jobs keep ticking but emit/post nothing — see §6),
or pausing the Scheduler entries; no new flag is required for V1.

---

## 3. Entrypoint wrapper design

Mirror the existing one-module-per-Job pattern of `apps/worker/jobs/salesforce_pull.py`
(`run()` async wrapper + `main()` + `if __name__ == "__main__"`, with
`configure_logging()` called first because Cloud Run Jobs don't boot the API app).

Two new modules to add under `apps/worker/jobs/` (skeleton drafted in
`notification_jobs_entrypoint.py.draft` in this folder):

### 3a. `apps/worker/jobs/notification_drain.py` (NEW — landable now)

```python
async def run() -> dict[str, int]:
    configure_logging()
    summary = await drain_notification_outbox({})   # existing cron, ctx = {}
    log.info("notification_drain.complete", summary=summary)
    return summary

def main() -> None:
    asyncio.run(run())

if __name__ == "__main__":
    main()
```
- Imports `drain_notification_outbox` from `apps.worker.jobs.notification_dispatch`.
- No reimplementation; the cron already opens its own `async_session()` and owns its
  unit of work per row.

### 3b. `apps/worker/jobs/consult_reminder_scan.py` (NEW — blocked on ENG-486)

Identical shape, delegating to `scan_consultation_reminders({})` from
`apps.worker.jobs.consultation_reminders`. **Cannot be authored on `main` until ENG-486
merges** — `apps/worker/jobs/consultation_reminders.py` exists only on branch
`eng-486-consult-reminders` (worktree `/Users/eduardkarionov/Desktop/fusion_eng486`),
confirmed absent from `main` (§9).

> Both wrappers invoke via `python -m` (like `salesforce_pull` / `carestack_pull`),
> not `python -c`, because each cron lives in a dedicated entrypoint module. The
> `python -c` inline form (bounce-poll / marketing-pull) is only used where no
> module-level entrypoint exists; we add real modules here.

---

## 4. Precise additions to `infra/scripts/deploy_cloud_run.sh`

Diff-style description — **NOT applied**. Per DEPLOYMENT_RULES §9 this is the
"Production runtime change" step (6); it must be a separate, reviewable change.

**(a) Job name vars — after `JOB_MARKETING_BACKFILL` (~line 103):**
```bash
# ENG-498 — messenger engine runtime. Prod has no always-on arq worker
# (fusion-worker decommissioned in ENG-172), so the notification-outbox
# drain and the T-15m consult-reminder scan run as scheduled Cloud Run Jobs.
JOB_NOTIFICATION_DRAIN="${JOB_NOTIFICATION_DRAIN:-fusion-job-notification-drain}"
JOB_CONSULT_REMINDERS="${JOB_CONSULT_REMINDERS:-fusion-job-consult-reminders}"
```

**(b) Scheduler name vars — after `SCHED_MARKETING_PULL` (~line 114):**
```bash
# ENG-498 — messenger engine schedulers (every 1 min).
SCHED_NOTIFICATION_DRAIN="${SCHED_NOTIFICATION_DRAIN:-fusion-sched-notification-drain}"
SCHED_CONSULT_REMINDERS="${SCHED_CONSULT_REMINDERS:-fusion-sched-consult-reminders}"
```

**(c) `deploy_job` calls — inside the `CI_MODE != 1` block, NOT under the
`SCHEDULE_INTEGRATION_PULL` gate** (e.g. right after the alembic/bounce jobs,
~line 602). They reuse the existing `JOB_ENV_VARS` / `JOB_SECRETS` contract
(which already carries `NOTIFICATIONS_ENABLED=false`, `MESSENGER_PHI_FULL=true`,
`WEB_APP_BASE_URL`, and the DB DSN secrets — `deploy_cloud_run.sh:433-434`):
```bash
# ENG-498 — drain the notification outbox + post to Mattermost (~1 min).
deploy_job "$JOB_NOTIFICATION_DRAIN" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.notification_drain"
# ENG-498 — T-15m confirmed-consult reminder scan (~1 min). Requires ENG-486.
deploy_job "$JOB_CONSULT_REMINDERS" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.consult_reminder_scan"
```

**(d) `grant_job_invoker` calls — in the "Granting Cloud Scheduler invoker
permissions" block (~line 730-732), alongside the unconditional grants:**
```bash
grant_job_invoker "$JOB_NOTIFICATION_DRAIN" "$WORKER_EMAIL"
grant_job_invoker "$JOB_CONSULT_REMINDERS"  "$WORKER_EMAIL"
```

**(e) `upsert_scheduler` calls — alongside the unconditional schedulers
(`SCHED_BOUNCE` / `SCHED_SF_KEEPALIVE`, ~line 745-748):**
```bash
upsert_scheduler "$SCHED_NOTIFICATION_DRAIN" "* * * * *" "$JOB_NOTIFICATION_DRAIN" \
  "Drain notification_outbox + post to Mattermost every 1m (ENG-498)"
upsert_scheduler "$SCHED_CONSULT_REMINDERS" "* * * * *" "$JOB_CONSULT_REMINDERS" \
  "Scan confirmed consultations for T-15m reminders every 1m (ENG-486/ENG-498)"
```

**(f) Output `cat <<EOF` block — add the two jobs to the printed summary
(~line 805-808).**

No new env var or secret is introduced: both jobs ride the existing
`JOB_ENV_VARS` / `JOB_SECRETS`. So the DEPLOYMENT_RULES §10 new-env-var
checklist does NOT apply to the *deploy script* change. (It DOES apply at
enablement time when `NOTIFICATIONS_ENABLED` / `NOTIFICATIONS_CUTOFF_AT` are
flipped — §6.)

---

## 5. Cost / cadence + cold-start & locking safety

**Cost.** Each Job is invoked `60 * 24 = 1440` times/day per Job (2880 total).
Each invocation is a short-lived task at `--memory=1Gi --cpu=1`
(`deploy_cloud_run.sh:572-573`) that exits in seconds (an empty-outbox drain
returns immediately, `notification_dispatch.py:104-105`). Cloud Run Jobs bill
per task vCPU-second; a sub-second-to-few-second task at this cadence is a few
dollars/month — negligible vs the existing `*/15` and `*/30` pull jobs. There is
no `--min-instances` cost: Jobs are not Services, they spin up only when the
Scheduler fires.

**Cold start.** Each tick is a cold container boot (~import the API image,
construct the DB pool, run one pass). This adds a few seconds of latency to the
~1-minute cadence — acceptable for clinic notifications. The DSN is resolved from
the `db-url-asyncpg` secret like every other Job; the VPC connector + Cloud SQL
Private IP path is identical (`deploy_cloud_run.sh:564-575`).

**Locking / overlap safety.** A cold-start tick that overlaps the previous one (or
runs alongside a future second runner) is safe by construction:
- **Drain:** `lock_batch` claims rows with `.with_for_update(skip_locked=True)`
  (`notification_repository.py:168`) and `_process_one` only acts on rows where
  `status == 'locked'` (`notification_dispatch.py:127-129`); concurrent ticks skip
  each other's locked rows. Stale-lock reclaim (`locked_at < lease_cutoff`,
  `notification_repository.py:160-163`) guarantees forward progress if a tick dies
  mid-post — at the cost of **at-least-once** delivery (documented,
  `notification_dispatch.py:28-36`).
- **Reminder scan:** `emit()` takes the durable ledger claim
  `NotificationEmittedRepository.claim` =
  `INSERT ... ON CONFLICT (tenant_id, event_type, dedupe_key) DO NOTHING`
  against `uq_notification_emitted_tenant_event_key`
  (`notification_repository.py:224-252`), with `dedupe_key = consultation id`
  (`consultation_reminders.py:111`). A second/overlapping tick loses the claim and
  enqueues nothing (`event_service.py:215-217`). At-most-once per consultation.

So 1-minute Scheduler jitter, retries (`--max-retries=1`,
`deploy_cloud_run.sh:570`), and a brief two-task overlap are all safe.

---

## 6. ENG-500 — enablement plan (flip + smoke)

### 6.1 Flip mechanics (confirmed in code)
`NotificationEventService.emit` applies, in order (`event_service.py:159-172`):
1. **Enablement guard** — if `Settings.notifications_enabled` is False, emit is a
   no-op (`event_service.py:159`). Default False (`config.py:276-277`).
2. **Historical cutoff guard** — if `source_created_at` is supplied AND
   `Settings.notifications_cutoff_at` is set AND the entity predates the cutoff,
   suppress (`event_service.py:167-172`; `_as_utc` normalizes naive values,
   `event_service.py:77`). Default None = no cutoff (`config.py:286-288`).
3. **Idempotency claim** (per-entity dedupe — §5).

Both are env-driven `Settings` fields:
- `NOTIFICATIONS_ENABLED` (bool, `config.py:276`)
- `NOTIFICATIONS_CUTOFF_AT` (ISO-8601 datetime, `config.py:286`)

### 6.2 Which services/jobs get the flips
The flags are read wherever `emit()` runs. That is:
- The **API** service (`fusion-api`) — emits `lead.created` at the route boundary
  (`apps/api/routers/ops.py::create_lead`; ops cannot import integrations).
- The **emitting Jobs** — `fusion-job-sf-pull`, `fusion-job-cs-pull`,
  `fusion-job-backfill` (they emit new-entity notifications, ENG-454), plus the new
  `fusion-job-consult-reminders` (emits reminders).
- The **`fusion-job-notification-drain`** Job — the **drain does NOT read the
  enablement flag**; it posts whatever rows exist. But with `NOTIFICATIONS_ENABLED=false`
  upstream, nothing is ever enqueued, so the drain stays a no-op. Enable it together
  with the rest so a row that IS enqueued gets delivered.

Because `API_ENV_VARS` and `JOB_ENV_VARS` are **separate strings** in the deploy
script, the flip must be applied to **both** the API service and every Job that
emits or drains. Cleanest path: change the two values in `deploy_cloud_run.sh`
(`API_ENV_VARS` line 423, `JOB_ENV_VARS` line 433) from `NOTIFICATIONS_ENABLED=false`
to `=true`, add `NOTIFICATIONS_CUTOFF_AT=<instant>`, and re-run the operator deploy.
A faster, non-rebuild option for the smoke is `gcloud run services update fusion-api
--update-env-vars=...` + `gcloud run jobs update <job> --update-env-vars=...` — but the
durable source of truth MUST be the script (DEPLOYMENT_RULES §1, §5), so the script
edit lands regardless.

### 6.3 `NOTIFICATIONS_CUTOFF_AT` — value + why
Set `NOTIFICATIONS_CUTOFF_AT = <the enablement instant>` (the UTC moment you flip
`NOTIFICATIONS_ENABLED=true`), timezone-aware ISO-8601 (e.g.
`2026-06-17T00:00:00Z`). Rationale: the new-entity emits pass
`source_created_at` (the provider `source_created_at`), so the cutoff suppresses the
**entire historical backfill** — ~27k bulk-loaded CareStack patients + the SF
2025-10 bulk + every pre-existing lead — from flooding Mattermost the moment delivery
turns on. Only entities created at/after the flip notify.

**Reminders are future-only by construction** and do NOT need the cutoff to be safe:
`scan_consultation_reminders` only matches consultations whose `scheduled_at` is in
`(now, now+15m]` (`consultation_reminders.py:75-77`, horizon `:46`), i.e. strictly
future appointments. It does not pass `source_created_at`, so guard 2 is inert for it
— correctly, since a reminder is about a future event, not a historical record. The
per-consultation dedupe ledger prevents repeats.

### 6.4 Ordered enable sequence
1. **Pre-reqs landed:** ENG-498 code PR merged to main (the two entrypoint modules);
   prod Mattermost bot credential present in `tenant.integration_credential`
   (`provider_kind="mattermost"`, ENG-496); prod notification rules seeded (ENG-497).
2. **Deploy the runtime:** operator runs `deploy_cloud_run.sh` (no `CI_MODE`) so the
   two new Jobs + Schedulers + invoker grants exist — **still dark**
   (`NOTIFICATIONS_ENABLED=false`). Confirm both Jobs deploy and Schedulers tick (the
   drain over an empty outbox is a clean no-op).
3. **Set the cutoff first, then enable:** apply `NOTIFICATIONS_CUTOFF_AT=<now>` AND
   `NOTIFICATIONS_ENABLED=true` to `fusion-api` + the emitting/draining Jobs in the
   same change, so there is never an enabled-without-cutoff window that could flush
   historical rows. Update the script values and re-run (or `gcloud run ... update`
   for the smoke, with the script edit as the durable record).
4. **Smoke (§6.5).**
5. **Watch** `notification.dispatch.sent` / `.failed` audit actions and the
   `notification_drain.complete` log summary for the first few ticks.

### 6.5 End-to-end smoke
- **Happy path (drain):** enqueue one outbox row for the prod tenant (a real
  `lead.created` via the API, or a minimal seeded row), then confirm it appears in the
  target Mattermost channel **within ~1 min** (one Scheduler tick). Verify a
  `notification.dispatch.sent` audit row and `status='sent'` + a
  `provider_message_id` on the outbox row.
- **Reminder path (after ENG-486):** mark a consultation CONFIRMED with
  `scheduled_at` ~10 min out; on the next minute tick confirm one reminder card in
  `#consult-reminders` and exactly one `notification_emitted` ledger row; confirm a
  second tick does NOT repost.
- **Cutoff path:** confirm a historical/backfilled entity (pre-cutoff
  `source_created_at`) does NOT notify — look for the
  `notification.event.skipped_pre_cutoff` log line (`event_service.py:172`).

---

## 7. Dependencies & sequencing

- **Delivery cannot succeed without:** the **prod Mattermost credential** (ENG-496 —
  bot token in `tenant.integration_credential`, resolved by
  `chat/resolver.py`) and **prod notification rules** (ENG-497 — without a matching
  `integrations.notification_rule`, `emit()` enqueues nothing). The Jobs can deploy
  and tick before those land; they just stay no-ops.
- **`fusion-job-consult-reminders` depends on ENG-486** reaching `main` (the
  `consultation_reminders.py` module + its `consult_reminder_scan.py` wrapper). Until
  then, deploy only `fusion-job-notification-drain`; add the consult Job in a
  follow-up once ENG-486 merges. (The draft entrypoint guards this with a commented
  import + `NotImplementedError`.)
- **It is a code PR, merged to main, before deploy.** Per DEPLOYMENT_RULES §9, the new
  entrypoint modules (feature/worker-path code) land as a separate code PR; the
  `deploy_cloud_run.sh` change (production runtime, step 6) is its own reviewable
  change. The image must contain the new modules before the Jobs can run them (Jobs
  reuse the API image — `deploy_cloud_run.sh:538-541`).
- **Migration head check:** none introduced here (no schema change) — `notification_outbox`,
  `notification_rule`, and the `notification_emitted` ledger already shipped with the
  messenger layer (migration `a7b8c9d0e1f2` + the ledger constraint). Nothing to chain.

---

## 8. Open questions for the operator / strategist
- Confirm 1-minute delivery latency is acceptable (vs the 10s dev arq cadence).
- Confirm we do NOT want a dedicated messenger kill-switch flag (lean on
  `NOTIFICATIONS_ENABLED=false` or pausing the Schedulers instead).
- Pick the exact `NOTIFICATIONS_CUTOFF_AT` instant at flip time (recommend the
  enable moment, UTC, timezone-aware).

## 9. Verification log (what I read)
- `scan_consultation_reminders` is **NOT on main**: `ls` of
  `apps/worker/jobs/consultation_reminders.py` on the canonical checkout returns "No
  such file"; the file exists only on branch `eng-486-consult-reminders` (worktree
  `/Users/eduardkarionov/Desktop/fusion_eng486`), branch not merged.
- Idempotency confirmed by code:
  - Drain: `notification_repository.py:168` (`.with_for_update(skip_locked=True)`),
    `notification_dispatch.py:127-129` (only acts on `status=='locked'`),
    `notification_dispatch.py:28-36` (documented at-least-once + stale-lock reclaim).
  - Reminder: `notification_repository.py:224-252` (`claim` =
    `INSERT ... ON CONFLICT DO NOTHING` on `uq_notification_emitted_tenant_event_key`),
    `event_service.py:215-217` (lose-claim => suppress),
    `consultation_reminders.py:111` (`dedupe_key=str(consult.id)`).
- Flip mechanics: `config.py:276-288` (`NOTIFICATIONS_ENABLED`,
  `NOTIFICATIONS_CUTOFF_AT`), `event_service.py:159-172` (enablement + cutoff guards).
- Job/Scheduler contract: `deploy_cloud_run.sh:78-114` (`JOB_*`/`SCHED_*` vars),
  `:433-434` (`JOB_ENV_VARS`/`JOB_SECRETS` already carry the notify flags),
  `:548-579` (`deploy_job`), `:685-716` (`upsert_scheduler`), `:718-743` (invoker grants).
