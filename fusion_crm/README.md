# Fusion CRM — Platform

AI-native Dental Implant Clinic OS. Designed for HIPAA-aware operation
from day one: PHI lives in its own database schema, every PHI access
is gated by a service that checks authorisation and writes an audit
row, and AI agents talk to the system through a tool layer that NEVER
touches the database directly.

For the bigger picture — strategy, milestones, deferred decisions —
see [`docs/ROADMAP.md`](docs/ROADMAP.md) and the two whitepapers in
[`docs/`](docs/).

## Where to look first

- **`CLAUDE.md`** (root) — entry point for any Claude Code session.
  Every top-level area has its own `CLAUDE.md` with rules for that
  area. Read both when you work on a slice.
- **`AGENTS.md`** (root) — thin pointer for Codex. Mirrors the
  CLAUDE.md hierarchy. Every area has both files.
- **`docs/ROADMAP.md`** — milestones M1..M7 and what each ships.
- **`docs/WORKFLOW.md`** — how Claude + Codex + the operator
  collaborate (Linear handoff, ADRs, living docs).
- **`docs/architecture/GOVERNED_AGENT_LEARNING_STRATEGY.md`** —
  long-term doctrine for governed agent learning, workflow intelligence,
  taxonomy evolution, memory, evals, and phased adoption.
- **`docs/decisions/`** — ADRs. Currently 4:
  - ADR-0001 Cloud SQL prod Postgres
  - ADR-0002 Cloud Run prod runtime
  - ADR-0003 Tenant domain + multi-tenancy
  - ADR-0004 Operator-account email outreach
- **`docs/plans/`** — design docs. Currently full schema v0.2,
  Salesforce integration, Phase 1 vertical slice, agent-driven
  workflow.
- **`docs/data-model/CATALOG.md`** — every table by domain, what it
  holds, who can touch it.
- **`docs/integrations/`** — vendor API mirrors (e.g. CareStack v1.0.45
  spec) and provider notes. Always grep here before guessing an
  endpoint.
- **`infra/env/PRODUCTION.md`** — Cloud SQL + Cloud Run operator
  runbook (bring-up, deploy, rotate, restore drill, troubleshooting).

## Folder map

```
platform/
├── apps/
│   ├── api/                  FastAPI HTTP surface (uvicorn)
│   ├── web/                  Next.js staff frontend
│   ├── worker/               arq background-job runner
│   └── portal/               (reserved) future patient portal
├── packages/
│   ├── core/                 config, exceptions, logging, security, secrets
│   ├── db/                   declarative Base, async session, mixins, alembic
│   ├── identity/             global Person + PersonIdentifier
│   ├── actor/                first-class actors (human / AI / system)
│   ├── auth/                 credentials, sessions, API keys, portal accounts
│   ├── tenant/               multi-tenancy (tenant, location, credentials, settings)
│   ├── ops/                  Lead + FollowupTask (PHI-free)
│   ├── phi/                  PatientProfile + Consultation (PHI; gated)
│   ├── interaction/          interaction events (calls, messages, web)
│   ├── outreach/             templates, campaigns, sends, suppression
│   ├── integrations/         external provider state (Salesforce, CareStack, …)
│   ├── audit/                AccessLog (append-only)
│   ├── ingest/               RawEvent capture from external systems
│   └── tools/                AI-agent tool layer (services-only)
├── infra/
│   ├── docker/               docker-compose + init-schemas.sql
│   ├── scripts/              backup, restore, provision Cloud SQL / Cloud Run
│   └── env/                  per-environment guidance + PRODUCTION.md runbook
├── docs/
│   ├── ROADMAP.md, WORKFLOW.md
│   ├── decisions/            ADRs (ADR-0001 onward)
│   ├── plans/                design docs (dated)
│   ├── data-model/CATALOG.md
│   └── integrations/         vendor API mirrors
├── .codex/                   Codex-specific config + handoff scripts
├── .env.example
├── pyproject.toml
└── Makefile
```

## Architecture in one paragraph

A single PostgreSQL database is partitioned into **eleven live
schemas** today (M1 set + post-M1 additions): `identity`, `ops`,
`phi`, `audit`, `ingest`, `actor`, `auth`, `integrations`,
`interaction`, `tenant`, `outreach`. The full v0.2 design (see
`docs/plans/2026-04-30-full-schema-v0_2.md`) reserves further schemas
(`context`, `workflow`, `encounter`, `segmentation`, `insight`) for
milestones M3–M7. Every person in the world has exactly one
`identity.person` row whose UUID is the **`person_uid`** that every
other domain references. The **`ops`** schema holds non-clinical CRM
data and is the only domain that AI agents and front-desk staff can
read/write freely. The **`phi`** schema holds clinical data and is
reachable ONLY through `PhiService`, which checks the caller's roles
(`Principal.can_read_phi()`) and writes an `audit.access_log` row on
every read or write — denied or successful. AI agents call **tools**
in `packages/tools/`; tools receive a `ToolContext` (principal +
session) and delegate to services. Tools never touch repositories or
sessions directly.

## Current milestone — M1 vertical slice

End goal: **Salesforce + CareStack data flowing into the staff UI
end-to-end**, with the normalised pipeline (`ingest.raw_event` →
`IdentityService.resolve_or_create_person` → domain services) backing
every visible row.

Status snapshot (track live in Linear under team `ENG`, project
"Fusion CRM — Engineering"):
- ✅ Production data plane on Google Cloud SQL (ADR-0001).
- ✅ Production runtime on Cloud Run + Cloud IAP (ADR-0002).
- ✅ Multi-tenancy via `tenant` domain (ADR-0003).
- ✅ Operator-account email outreach via Google Workspace / M365
  (ADR-0004).
- 🟡 Salesforce Lead pull + UI surfacing — slice in progress.
- 🟡 CareStack patient + appointment search + pull — slice in
  progress.

## Cross-agent collaboration

Claude implements; Codex reviews + designs tests + sanity-checks
migrations. Linear is the handoff surface (team `ENG`, label
`agent:claude` / `agent:codex` / `agent:either`). Cross-cutting
decisions live in `docs/decisions/` as ADRs, dated design docs in
`docs/plans/`. The full collaboration model is in `docs/WORKFLOW.md`
§10.

## Quick start — local (no Docker)

```bash
cp .env.example .env
# 1) install
make install
. .venv/bin/activate

# 2) bring up just the stateful deps via docker-compose
docker compose -f infra/docker/docker-compose.yml up -d postgres redis

# 3) migrate
make db-revision M="initial"      # one-time, autogenerates from models
make db-upgrade

# 4) run services
make api          # FastAPI on http://127.0.0.1:8000  (docs at /docs)
make worker       # arq worker (separate terminal)
make web          # Next.js staff frontend on http://127.0.0.1:3000
```

Smoke test:

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/readyz
```

### Refresh local data (catch up to provider state)

A fresh checkout lags the live CareStack / Salesforce state because the
scheduled pulls are page-bounded and the arq cron only fires hourly (and
never while the Mac is asleep). To catch the local DB up on demand:

```bash
make sync-local            # drains all tenants + both providers
# or via the UI: /dev/inspector → "Sync data" button
```

Both paths call the same `run_local_sync`
(`apps/worker/jobs/sync_local_job.py`): it repeatedly runs the real
per-tenant pull until a full pass imports zero new rows. This works
because each CareStack pull resumes from the `lastUpdatedOn` high-watermark
(ENG-324), so successive passes advance forward instead of re-reading the
same oldest rows. **Local-dev only** — the `/dev/sync-local` endpoint
returns 404 in production. The drain runs **inside the API process**, so
the API must be on current code; the arq **worker is not required**.

> **Local-dev port tip.** Postgres binds to `127.0.0.1:5432` and Redis
> to `127.0.0.1:6379` by default. Use `127.0.0.1` (NOT `localhost`) in
> DSNs to avoid the IPv6/IPv4 collision documented in
> `feedback_dev_traps.md`. If you need to run a second instance
> alongside an existing local Postgres, override the host port in
> `infra/docker/docker-compose.yml` (e.g. `127.0.0.1:5434:5432`) — the
> in-container port stays 5432.

## Quick start — full Docker stack

```bash
cp .env.example .env
make build
make up
make logs        # tail
# inside the api container, run migrations once:
docker compose -f infra/docker/docker-compose.yml exec api \
    bash -lc "cd packages/db && alembic upgrade head"
```

The compose file binds Postgres (5432), Redis (6379), and the API
(8000) to **127.0.0.1 only** — never expose them to the office LAN;
route through the API.

## Production deployment

Production runs on Google Cloud Run (apps) + Cloud SQL (data) +
Cloud IAP (access control) in project `fusioncrm-494201`, region
`us-west1`. Full operator runbook — bring-up, deploys, rotation,
restore drill, troubleshooting — is in
[`infra/env/PRODUCTION.md`](infra/env/PRODUCTION.md). CI/CD goes
through GitHub Actions with Workload Identity Federation
(`.github/workflows/deploy-prod.yml`); no service-account keys live in
the repo or anywhere on disk.

## Backups

`infra/scripts/backup.sh` does the actual work; the worker invokes it
via the `run_backup` job so backups don't block API requests.

What it does:

1. `pg_dump --format=custom --compress=9` → `BACKUP_LOCAL_DIR/fusion_<host>_<utc>.dump`
2. If `GCS_BUCKET` is set and `gsutil` is on `PATH`, uploads to
   `gs://$GCS_BUCKET/<host>/<YYYY>/<MM>/`
3. Prunes local dumps older than `BACKUP_RETENTION_DAYS`

Required env: `DATABASE_URL_SYNC`, optional `GCS_BUCKET`,
`GOOGLE_APPLICATION_CREDENTIALS`, `BACKUP_LOCAL_DIR`,
`BACKUP_RETENTION_DAYS`.

Run it:

```bash
# manually (outside Docker)
DATABASE_URL_SYNC=postgresql+psycopg://fusion:fusion@127.0.0.1:5432/fusion \
    ./infra/scripts/backup.sh

# or, via the worker:
docker compose -f infra/docker/docker-compose.yml exec worker \
    arq apps.worker.main.WorkerSettings --check  # sanity check the worker
# then enqueue from a Python REPL or via your scheduler:
#   await arq_pool.enqueue_job("run_backup")
```

In production, Cloud SQL automated backups + PITR are the **primary**
layer (7-day retention, daily). `backup.sh` continues to run weekly
as a **secondary** cold-storage layer to `gs://fusion-crm-backups`
(90-day retention). See `infra/env/PRODUCTION.md` for the schedule.

## Restore

```bash
# from local file
./infra/scripts/restore.sh /var/backups/fusion/fusion_office_20260420T000000Z.dump

# directly from GCS
./infra/scripts/restore.sh gs://my-bucket/office/2026/04/fusion_office_20260420T000000Z.dump
```

The script uses `pg_restore --clean --if-exists`, so the target
database is overwritten. It refuses to run non-interactively unless
you set `FORCE=1`.

## Adding a new domain

1. Create `packages/<domain>/` with `models.py`, `schemas.py`,
   `repository.py`, `service.py`.
2. Set `__table_args__ = {"schema": "<domain>"}` on every model and
   add the schema name to `infra/docker/init-schemas.sql` plus
   `DOMAIN_SCHEMAS` in `packages/db/alembic/env.py`.
3. Import the new `models` module from `packages/db/registry.py` so
   Alembic sees it.
4. Generate a migration: `make db-revision M="add <domain>"`.
5. Add a `CLAUDE.md` + `AGENTS.md` in the new package directory
   before the first feature lands.

## Adding a new AI tool

1. Add an `async def my_tool(ctx: ToolContext, **kwargs) -> dict` in
   `packages/tools/<area>_tools.py`.
2. Register it in `packages/tools/registry.py`.
3. The tool MUST call services, NEVER repositories or
   `session.execute(...)` directly. The unit-of-work commits at the
   API or job boundary.

## Production hardening checklist

* Replace `Principal.GUEST` default with a real auth dependency
  (OIDC/JWT) and set `request.state.principal`.
* Create per-domain DB roles (template at the bottom of
  `init-schemas.sql`) and use distinct role connection strings for
  the API vs. read-only reporting. (Tracked as ENG-111.)
* Mount the GCP service-account JSON read-only into the worker
  container; never bake it into the image. In Cloud Run, use the
  service account binding instead of a JSON file.
* Set `APP_ENV=production` to disable `/docs` and `/openapi.json`.
* Put the API behind Cloud IAP (prod) or a TLS-terminating reverse
  proxy (Caddy / nginx) on the office server; never expose 8000
  directly.
* Schedule `backup.sh` nightly + verify weekly with a
  `pg_restore --list` smoke check on a scratch database. Cloud SQL
  PITR handles point-in-time recovery; the GCS layer is the cold
  backup of last resort.
* Forward Docker logs to a log store (the JSON renderer activates
  automatically when `APP_ENV=production`).
* Promote Cloud SQL to HA + CMEK before any real PHI lands in
  `phi.*` (tracked as ENG-110).
