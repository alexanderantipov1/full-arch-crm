# CLAUDE.md — `infra/` (docker, scripts, env)

Operational surface: how the platform is built, deployed, backed up,
and restored. No application code lives here.

Before changing env vars, Secret Manager bindings, Cloud Run
services/jobs, deploy scripts, OAuth/CORS URLs, or production
hostnames, read and follow `docs/DEPLOYMENT_RULES.md`.
Google Cloud CLI is allowed for operator and agent workflows, but
repeatable production behavior must be captured in repo scripts, not
left as one-off `gcloud` command history.

## Layout

- **`docker/`** — `docker-compose.yml` (dev),
  `docker-compose.prod.yml` (prod, Cloud SQL),
  `init-schemas.sql`. Per-image Dockerfiles live next to their app
  (`apps/api/Dockerfile`, `apps/web/Dockerfile`,
  `apps/worker/Dockerfile`).
- **`scripts/`** — `backup.sh`, `restore.sh`,
  `provision_cloudsql.sh`, `cloudsql_bootstrap.sh`,
  `provision_cloud_run_foundation.sh`, `deploy_cloud_run.sh`,
  `provision_cloud_iap_lb.sh`, `provision_monitoring.sh`,
  `start_prod.sh`. Plain bash; idempotent; fail loudly.
- **`env/README.md`** — guidance for per-environment `.env` files.
- **`env/PRODUCTION.md`** — Cloud SQL + Cloud Run runbook (bring-up,
  rotate, restore drill, troubleshooting).

## docker-compose

- Services: `postgres`, `redis`, `api`, `worker`.
- Postgres + Redis bind to **127.0.0.1 only** — never expose them
  to the office LAN. Anything outside the host talks to the API.
- `init-schemas.sql` runs ONCE when the Postgres data dir is empty.
  If you add a new domain schema, you must (a) add it here AND
  (b) `CREATE SCHEMA` it manually on existing environments — the
  init script will not re-run.
- Backup volume is mounted into the worker at
  `/var/backups/fusion`. The host path is
  `docker volume backups`. For real production, replace with a
  bind mount to the office NAS.
- GCP service-account JSON is mounted **read-only** at
  `/secrets/gcp-sa.json`. Never bake it into an image. Never commit
  it. The mount line is commented out in compose; uncomment in the
  prod environment file.

## dev-up.sh (local dev supervisor)

`infra/scripts/dev-up.sh` starts and SUPERVISES the three local dev
services: API (`uvicorn --reload` on :8000), Web (`next dev` on :3000),
Worker (`arq apps.worker.main.WorkerSettings`). Each service runs inside
a `while true` respawn loop (restart 3s after exit) plus a 60s health
check. Logs: `/tmp/fusion-{api,web,worker}.log`.
`./infra/scripts/dev-up.sh --check` prints status without starting
anything.

Rules every agent must follow before touching local dev processes:

1. **Check for a running supervisor first:** `pgrep -fl dev-up.sh`.
   A supervisor can outlive the terminal/session that started it by
   days and will silently respawn anything you kill.
2. **Killing a supervised child does not stop it** — it is respawned
   in 3 seconds. If a "mystery" process keeps coming back, suspect the
   supervisor, not a bug.
3. **Killing the arq child IS the canonical code reload.** arq has no
   `--reload`; uvicorn reloads `apps/`+`packages/` and Next.js
   hot-reloads, but the worker keeps the code it imported at start.
   After changing worker/ingest code, `pkill -f "arq apps.worker"` and
   let the supervisor respawn it on the current checkout.
4. **To actually stop services**, TERM the `dev-up.sh` process tree
   (the EXIT trap kills its children), then verify with
   `pgrep -f "arq apps.worker"` / `lsof -i :8000 -i :3000` that the
   children are gone. Never just kill children and declare the stack
   down.
5. **Never start a second dev-up.sh while one runs.** Duplicate
   supervisors each respawn their own arq worker → duplicate scheduled
   ticks → duplicate `ingest.raw_event` rows (root cause of the
   2026-06-10 duplicate-worker incident, ENG-384).

## Cloud SQL (production)

Production Postgres lives on **Google Cloud SQL** in project
`fusioncrm-494201`, region `us-west1`, instance `fusion-crm-pg`.
Per ADR-0001 (`docs/decisions/ADR-0001-cloud-sql-prod-postgres.md`).

- Connectivity goes through **Cloud SQL Auth Proxy** (sidecar
  service in `docker-compose.prod.yml`, network alias `postgres`
  so app DSNs are identical between dev and prod).
- App services authenticate to the proxy via service-account keys
  (`fusion-api-sa`, `fusion-worker-sa`); the operator laptop uses
  `fusion-migrator-sa` for migrations / interactive `psql`.
- Postgres-level password for the `fusion` role lives in Secret
  Manager (`db-password`). App-level secrets (SECRET_KEY,
  ENCRYPTION_KEY, OAuth secrets) are referenced from env via
  `gcp-secret://` URLs and resolved at startup by
  `packages/core/secrets.py`.
- `init-schemas.sql` is the canonical schema set for dev AND prod.
  It runs automatically on a fresh Docker volume in dev; on Cloud
  SQL it must be applied explicitly via
  `infra/scripts/cloudsql_bootstrap.sh`. Do NOT rewrite the
  existing initial Alembic revision to create schemas — migrations
  are immutable once shipped.
- HA + CMEK are **off** during Phase 1. Promote both before any
  PHI lands in `phi.*` (FUS-X3 go/no-go gate).
- Backups: Cloud SQL automated backups + PITR is the **primary**
  layer (7-day retention, daily). `backup.sh` continues to run
  weekly as a **secondary** cold-storage layer to
  `gs://fusion-crm-backups` (90-day retention).

For step-by-step procedures (bring-up, rotate, restore drill,
monitoring), see `infra/env/PRODUCTION.md`.

## Cloud Run foundation

Production app runtime is **Cloud Run** in project
`fusioncrm-494201`, region `us-west1`. Per ADR-0002
(`docs/decisions/ADR-0002-cloud-run-prod-runtime.md`).

The foundation under that — VPC, Serverless VPC Access connector,
Cloud SQL Private IP peering, Artifact Registry, Cloud Build
deployer SA, and Workload Identity Federation for GitHub Actions —
is provisioned by `infra/scripts/provision_cloud_run_foundation.sh`
(ENG-114). The script is idempotent and creates no Cloud Run
*services*.

- The Cloud SQL Private IP migration in the foundation script
  **retains the public IP** so the operator laptop's Cloud SQL Auth
  Proxy keeps working. Flip to private-only only after Cloud Run is
  the sole DB consumer.
- WIF is pinned to `FUSIONDENTALAI/fusion_crm` via the
  `attribute.repository` condition; no other repo can mint tokens
  against the pool.
- Only the Serverless VPC Access connector starts billing
  immediately (~$10/month). Everything else is free until services
  attach.

For step-by-step bring-up, verification, and troubleshooting of the
Cloud Run foundation, see the "Cloud Run runtime" section in
`infra/env/PRODUCTION.md`.

## Cloud Run services (deploy_cloud_run.sh)

Once the foundation is healthy, the two Cloud Run services (`fusion-api`,
`fusion-web`) plus the recurring Cloud Run Jobs
(`fusion-job-alembic-upgrade`, `fusion-job-bounce-poll`,
`fusion-job-salesforce-token-keepalive`, the on-demand
`fusion-job-marketing-backfill`, and the gated
`fusion-job-sf-pull` / `fusion-job-cs-pull` /
`fusion-job-backfill` / `fusion-job-cs-procedure-codes` /
`fusion-job-marketing-pull`) are deployed by
`infra/scripts/deploy_cloud_run.sh` (ENG-115 / ENG-234 / ENG-327 /
ENG-493).
Idempotent; safe to re-run. The CareStack/Salesforce reader jobs
(`fusion-job-sf-pull`, `fusion-job-cs-pull`, and the nightly
`fusion-job-backfill` reconciliation) are deployed by default and can
all be halted as a group with `SCHEDULE_INTEGRATION_PULL=0` during
emergency deploys — the backfill shares the gate because it is also a
CareStack reader (it pulls cs_patients, cs_appointments,
cs_accounting_transactions). The nightly backfill job runs
`apps.worker.jobs.backfill_full` with default args
`--entities cs_patients cs_appointments cs_accounting_transactions` —
patients refresh first so the accounting re-emit can link payments to
the most recent person rows — and is idempotent end-to-end (raw capture
dedupes on `(id, lastUpdatedOn)`; events go through
`create_event_idempotent`; per-page commits land from ENG-326). The
scheduler entry (`fusion-sched-nightly-backfill`) fires once nightly
at 10:17 UTC (nighttime in America/Los_Angeles year-round —
03:17 PDT in summer, 02:17 PST in winter; Cloud Scheduler evaluates
the cron in UTC unless an explicit time zone is configured). The
GitHub Actions workflow that automates service deploys in CI/CD is
ENG-117; operator full deploys remain responsible for Cloud Scheduler /
Cloud Run Job reprovisioning.

The `fusion-worker` Cloud Run Service was decommissioned in ENG-172
(arq has no HTTP surface — Cloud Run health checks always failed).
Long-running outbound queue drain is paused until ENG-112 reintroduces
a real always-on background runtime + Memorystore.

- All services run as non-root (uid 10001 per `apps/CLAUDE.md`).
- All services attach to `fusion-vpc-connector` with
  `--vpc-egress=private-ranges-only`, reach Cloud SQL on its Private
  IP, and have `--no-allow-unauthenticated`. The Cloud IAP front
  door is wired by `provision_cloud_iap_lb.sh` (ENG-116) — see the
  "Public surface" section below.
- Secrets are passed by reference (`--set-secrets`); the script
  composes `db-url-asyncpg` and `db-url-psycopg` at deploy time
  from the Cloud SQL Private IP and `db-password`. No plaintext
  DSN ever appears on a command line or env var.
- Cron Jobs reuse the **API image** (`apps/api/Dockerfile` COPYs
  the whole `apps/` tree, so `apps.worker.jobs.*` is importable).
  They override `--command` / `--args` for the specific entrypoint.
  Cloud Scheduler entries authenticate as `fusion-worker-sa` with
  `roles/run.invoker` on the target Job — the SA name is kept for
  IAM continuity even though the long-running Service is gone.

For deploy steps, env flags, verification, and troubleshooting see
the "Deploying Cloud Run services" subsection in
`infra/env/PRODUCTION.md`.

## Public surface (HTTPS LB + Cloud IAP)

The public surface in front of Cloud Run — global static IP,
Google-managed SSL cert, Serverless NEGs, IAP-enabled backend
services, URL map with `/api/*` → api / `/*` → web routing, target
HTTPS proxy, and global forwarding rule — is provisioned by
`infra/scripts/provision_cloud_iap_lb.sh` (ENG-116). Per ADR-0002
§"Access control: Cloud IAP" and §"Custom domain".

- The script is **operator-runs-it**: it consumes `TENANT_DOMAIN`,
  `IAP_OAUTH_CLIENT_ID`, `IAP_OAUTH_CLIENT_SECRET` via env vars.
  These are not in any repo file and must not be.
- The OAuth consent screen + Web-type OAuth client are a one-time
  Cloud Console click-through. User type is **Internal** (the
  `drantipov.com` Workspace org); Internal type does NOT require a
  privacy-policy URL or homepage URL. Full walkthrough lives in
  `infra/env/PRODUCTION.md` → "Provisioning the public surface" →
  "Step 2 — OAuth consent screen + OAuth client".
- DNS is operator-managed: the script reserves the global static IP
  (`fusion-lb-ip`) but does not touch DNS. The operator points the
  A record (Cloud DNS or external provider) at the printed IP.
- Initial IAP allow-list: `drantipov@drantipov.com`,
  `eduard@drantipov.com`. Future Google Group
  (`group:clinic-staff@drantipov.com`) replaces both bindings when
  Workspace groups are set up.
- The worker has **no public surface** — no NEG, no IAP, no LB
  backend. It is reachable only inside `fusion-vpc`.
- The script is non-destructive by policy. It never deletes
  backend services, URL maps, or forwarding rules; misconfigured
  resources are removed by hand by the operator.
- Managed SSL certificate provisioning is async (15–60 min after
  DNS resolves to the reserved IP). Re-run the script any time;
  every step is describe-or-create idempotent.

## Monitoring (provision_monitoring.sh)

Cloud Monitoring alert policies for the ingestion pipeline are
provisioned by `infra/scripts/provision_monitoring.sh` (ENG-327). The
script is **operator-runs-it** and intentionally NOT wired into the
GitHub Actions deploy workflow — per `docs/DEPLOYMENT_RULES.md` §9
("Keep feature work separate from infrastructure"), monitoring changes
happen out-of-band.

What it creates (describe-or-create, idempotent):

- One email notification channel ("Fusion CRM ops — Eduard") fanning out
  to `eduard@drantipov.com`. Re-runs reuse the existing channel.
- Per-job alert policies for `fusion-job-cs-pull`, `fusion-job-sf-pull`,
  and `fusion-job-salesforce-token-keepalive`:
  - **execution FAILED** — metric
    `run.googleapis.com/job/completed_task_attempt_count` filtered to
    `result="failed"`, threshold > 0 over a 60s window.
  - **NO SUCCESS in N min** — metric-absence on the same metric filtered
    to `result="succeeded"`, with a per-job window
    (cs-pull 90m, sf-pull 45m, keepalive 7h).
- A log-based COUNTER metric `fusion_payment_freshness_stale` plus a
  threshold alert on it. The metric ticks whenever an API access-log
  entry shows `payment_freshness_status="stale"`; the clinic-hours
  awareness lives in the API (`apps/api/routers/health.py` reports
  `quiet-hours` overnight instead of `stale`), so the alert is
  implicitly silenced outside the clinic window without any Cloud
  Monitoring schedule.

Re-run the script after editing job names, SLO windows, or the alert
email. The script never auto-edits an existing policy (silent threshold
changes would be a bad signal) — to re-provision with new defaults,
delete the policy in the Cloud Console first, then re-run.

## backup.sh

What it does:
1. `pg_dump --format=custom --compress=9` →
   `BACKUP_LOCAL_DIR/fusion_<host>_<utc>.dump`
2. Sanity check: refuses to continue on empty file.
3. If `GCS_BUCKET` set and `gsutil` on PATH → upload to
   `gs://$GCS_BUCKET/<host>/<YYYY>/<MM>/`.
4. Prune local files older than `BACKUP_RETENTION_DAYS`.

Hard rules:
- The script MUST stay idempotent and safe to invoke from cron.
- Do not log the dump file's contents or the connection URL.
- Exit 0 only on full success (dump + upload if requested + prune).
- Wire production scheduling through host cron OR an `arq` cron job
  that enqueues `run_backup`. Today host cron is the simplest.

## restore.sh

- Requires interactive confirmation by default
  (`type 'RESTORE' to proceed`); `FORCE=1` skips for automation.
- Uses `pg_restore --clean --if-exists` — the target DB IS
  overwritten. Never run against the wrong env.
- Accepts a local file OR a `gs://` URL.
- After every restore, **verify** by spot-reading a small audit
  query and confirming row counts; do not trust silent success.

## Hard rules for this folder

- **The deployment contract is centralized.** Follow
  `docs/DEPLOYMENT_RULES.md`; do not introduce a second production
  deploy path or a second spelling for the same env value.
- **CLI changes must become scripts.** Use raw `gcloud` freely for
  inspection and approved emergency recovery, but any repeatable
  production change belongs in `infra/scripts/` with preflight and
  verification.
- **Secrets stay in env files / mounted files.** Never in compose,
  never in scripts, never in the repo.
- **Changes to docker-compose.yml** affecting the prod office server
  require an explicit user OK before applying — restarts can drop
  active connections.
- **Migrations are run by the operator**, not by the API container
  on boot. Do not add an `alembic upgrade head` call to the API's
  startup — surprises here can corrupt data.
- **GCS bucket** must be in a BAA-covered project and have:
  uniform bucket-level access, object versioning, lifecycle rules
  matching `BACKUP_RETENTION_DAYS`. Document any deviation here.
- **Public-surface scripts MUST stay non-destructive.** Never add a
  `gcloud compute backend-services delete`, `url-maps delete`, or
  `forwarding-rules delete` to `provision_cloud_iap_lb.sh`. If a
  resource needs to go, the operator deletes it by hand.

## Restore drill cadence

- Weekly: `pg_restore --list <latest>.dump` smoke check.
- Monthly: full restore into a scratch DB; spot-check a known
  `person` + `consultation` round-trip.
- Record the date of the last successful drill in your runbook.
