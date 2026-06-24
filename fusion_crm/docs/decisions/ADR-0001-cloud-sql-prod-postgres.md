# ADR-0001: Cloud SQL for production PostgreSQL

**Status:** Accepted
**Date:** 2026-05-08
**Authors:** Claude Code (drafted), eduardk (decision)
**Workstreams affected:** backend, mcp, devops
**Related Linear issues:** (to be filed: FUS-G1..G5, FUS-C1..C3, FUS-S1..S3, FUS-A1..A5, FUS-B1..B3, FUS-M1..M3)

---

## Context

Today the platform's PostgreSQL 16 lives in a local Docker container
(`infra/docker/docker-compose.yml:38`). It is used for development on
the operator's workstation and is not suitable for production:

- Single host, no managed backups, no PITR.
- `init-schemas.sql` creates the 9 domain schemas only on a fresh data
  dir — there is no managed schema lifecycle.
- No HIPAA-shaped runtime: BAA coverage, encryption-at-rest with
  customer-managed keys, audit-grade backups all need to come from
  somewhere.

We need a production database that:

1. Holds real Salesforce lead data (Phase 1) and, in subsequent phases,
   CareStack appointment metadata (non-PHI subset first) and clinical
   PHI in `phi.*` schemas.
2. Operates inside an existing Google Cloud BAA (account-level,
   confirmed 2026-05-08).
3. Preserves the architectural invariants from root `CLAUDE.md`:
   one canonical DB, eight (now nine, with `interaction`) schemas,
   PHI/ops separation enforceable at the role level later.
4. Costs little while we are pre-PHI (Phase 1–4 read-only pull from
   prod SF/CareStack, no patient data yet — see memory
   `feedback_marketing_first_phase.md` and
   `feedback_production_readonly_pull.md`).
5. Can scale up to HA + customer-managed encryption keys (CMEK) when
   we light up `PhiService` runtime gating (deferred per
   `feedback_hipaa_runtime_deferred.md`).

GCP project for production: `fusioncrm-494201` (already created,
distinct from any dev playground project). Operator location: California.

## Decision

### Engine and managed offering

Use **Cloud SQL for PostgreSQL 16** — Google's managed Postgres.
HIPAA-eligible under our existing BAA. Drop-in compatible with our
current SQLAlchemy 2.0 + asyncpg + psycopg + Alembic stack (zero code
changes to ORM or migrations).

### Region and instance

- **Region:** `us-west1` (The Dalles, Oregon). ~25 ms RTT to the
  San Francisco Bay Area, ~30 ms to Los Angeles. GCP has no
  Northern-California region; `us-west1` and `us-west2` (LA) are the
  only Pacific options. `us-west1` is ~5–7% cheaper, has more zones
  for future HA, and is a mature default. The latency delta vs LA
  is not user-perceivable for a CRM.
- **Instance name:** `fusion-crm-pg`.
- **Edition:** `ENTERPRISE` (NOT `ENTERPRISE_PLUS`).
  ENTERPRISE supports custom tiers (`db-custom-N-MMMM`) and is
  significantly cheaper. ENTERPRISE_PLUS would force predefined
  performance tiers (`db-perf-optimized-N-*`) which start at
  ~$300/mo and are oversized for our workload. We can switch later
  if read latency demands it.
- **Tier (initial):** `db-custom-1-3840` — 1 vCPU, 3.75 GB RAM.
  Sized for Phase 1–2 (lead pull + CareStack non-PHI; expected
  <50 RPS, <5 GB working set). Estimated cost: ~$50/mo single-zone,
  ~$100/mo when promoted to HA.
- **Storage:** SSD, 10 GB, **storage auto-increase ON**.
- **High availability:** **OFF on first launch.** Promote to HA via
  `gcloud sql instances patch --availability-type=REGIONAL` before any
  PHI lands (FUS-X3 go/no-go gate).
- **Backups:** automated daily, **PITR ON**, retention 7 days.
- **Maintenance window:** Sundays 03:00 America/Los_Angeles.
- **Network:** **Public IP, no authorized networks, SSL required.**
  All access goes through Cloud SQL Auth Proxy (see below).
  No VPC peering / Private Service Connect at this stage — we add
  them only when API/worker move into GKE or Cloud Run.

### Connectivity

- **Pattern:** **Cloud SQL Auth Proxy** running as a sidecar.
  - Image: `gcr.io/cloud-sql-connectors/cloud-sql-proxy:2`.
  - Listens on `127.0.0.1:5432` inside the proxy container; in compose
    it is exposed to other services as host `postgres` so app code does
    not change between dev and prod.
- **Authentication:** dedicated GCP service accounts, **never** a
  long-lived password baked into a connection string from outside.
  - `fusion-api-sa` — `roles/cloudsql.client` + `roles/secretmanager.secretAccessor`
  - `fusion-worker-sa` — same
  - `fusion-migrator-sa` — `roles/cloudsql.client` (used from operator
    laptop for one-shot Alembic / `psql` work)
- **Database password:** stored in Secret Manager
  (`projects/fusioncrm-494201/secrets/db-password`), pulled at app
  boot via the new loader described below. The proxy uses the SA
  identity for IAM auth to Cloud SQL itself; the password is a
  separate Postgres-level credential for the `fusion` role.

### Schema bootstrap

Cloud SQL does not run `/docker-entrypoint-initdb.d/`, so
`init-schemas.sql` must be invoked explicitly on a fresh instance.
Per the immutability rule for migrations
(`CLAUDE.md` workflow: "Migrations are immutable once shipped"),
we **do not** rewrite the existing initial Alembic revision
`20260430_2330_af6c4e767923_initial.py` to create schemas — it has
shipped.

Instead:

1. `infra/scripts/cloudsql_bootstrap.sh` runs `init-schemas.sql` via
   `psql` (statements are `CREATE SCHEMA IF NOT EXISTS` —
   idempotent).
2. The same script then runs `alembic upgrade head`.
3. Smoke-check: `SELECT count(*) FROM pg_namespace WHERE nspname IN
   (...)` returning 9.

This keeps `init-schemas.sql` as the single source of truth for
schema set in both dev (Docker init dir) and prod (bootstrap script).

### Roles

Single Postgres role `fusion` for now (matches dev). The
`fusion_app` / `fusion_phi` / `fusion_ops` per-schema role split
described in `init-schemas.sql:31-42` is **deferred** until the PHI
runtime gate ships, per
`feedback_hipaa_runtime_deferred.md`. ADR-0001 covers schema
separation only; role enforcement is a follow-up ADR.

### Configuration loader

`packages/core/config.py` gains a `gcp-secret://` URL scheme. Any
setting whose env value matches `gcp-secret://<project>/<name>/<version>`
is resolved at startup via `google-cloud-secret-manager`. Plain
values pass through unchanged, so dev `.env` files keep working with
no modifications.

`google-cloud-secret-manager` is added to `pyproject.toml` as an
optional `[secrets]` extra (kept out of dev install to avoid
unnecessary GCP wheels in local environments).

### Environment files

- Local dev: existing `.env` continues to point at Docker.
- Production: new `.env.production.template` in repo (no real values),
  copied to `.env.production` on the operator laptop / future host
  with `gcp-secret://` URLs filled in. Never committed.

### Backup strategy reconciliation

- **Primary:** Cloud SQL automated backups with PITR (7-day retention).
- **Secondary (cold storage):** existing `infra/scripts/backup.sh`
  runs weekly via cron, dumps via the proxy to the existing GCS
  backup bucket, retention 90 days.
  - The bucket location is **TBD pending operator confirmation** —
    see Open Questions.

## Consequences

### What this enables

- HIPAA-eligible managed Postgres without standing up a VM.
- Identical SQLAlchemy/Alembic stack between dev and prod — no code
  forks for the ORM or migrations.
- Zero-trust connectivity (Auth Proxy + IAM + Secret Manager) — no
  long-lived DB credentials sitting on disk in plaintext.
- A clear go/no-go gate before PHI: flip HA on, flip CMEK on, create
  per-schema roles, stand up `PhiService` runtime check.
- Costs ~$50–60/mo at Phase 1 scale; ~$130–150/mo with HA.

### What this costs

- Operational complexity: a new sidecar (Auth Proxy) in the prod
  compose; new bootstrap script; new env file shape.
- A small Python dependency (`google-cloud-secret-manager`) that ships
  in the prod image.
- The `init-schemas.sql` workflow now diverges between environments
  (Docker init dir vs explicit script). The single source of truth is
  preserved (the SQL file itself), but the invocation path differs.

### Risks / open questions

- **Cloud SQL extension whitelist:** `pgcrypto` is on the whitelist;
  if a future feature needs an extension that is not (e.g.
  `pg_trgm` is OK; `pg_partman` is not), we must either request
  whitelisting or move to AlloyDB / self-managed.
- **CMEK not yet enabled.** Cloud SQL defaults to Google-managed
  encryption-at-rest. CMEK adds a Cloud KMS dependency and roughly
  doubles the IAM surface; deferred to the PHI go/no-go gate.
- **Backup bucket project/location TBD** (see below).
- **Migrations remain operator-driven.** Per `infra/CLAUDE.md`, the
  API container does **not** run `alembic upgrade head` on boot.
  The operator runs it via `cloudsql_bootstrap.sh` or, for
  subsequent revisions, via the migrator SA from the laptop. This
  ADR does not change that rule.

## Alternatives considered

### Option A: AlloyDB for PostgreSQL

- **Approach:** Use Google's premium PG-compatible managed engine.
- **Pros:** Faster on heavy OLTP, columnar engine for analytics,
  full HIPAA eligibility.
- **Cons:** ~2.5–3× the cost of Cloud SQL at our scale; minimum
  instance sizes are larger; introduces more vendor-specific
  behavior; operationally heavier than Cloud SQL.
- **Why rejected:** Premature for Phase 1–4 traffic. Re-evaluate when
  read load on `interaction.event` or analytics on `audit.*`
  measurably exceeds Cloud SQL's headroom.

### Option B: Self-managed Postgres on a GCE VM

- **Approach:** Run Postgres 16 ourselves on a Compute Engine VM
  inside `fusioncrm-494201`.
- **Pros:** Full control of roles (including the
  `fusion_app/_phi/_ops` split with cluster-level enforcement),
  arbitrary extensions, exact PG version pinning.
- **Cons:** We become responsible for OS patching, PG upgrades,
  HA setup, backup tooling, monitoring agent installation. Solo dev
  + AI-generated code; operational toil is the highest-cost
  category for us per memory `feedback_solo_dev_no_iteration.md`.
- **Why rejected:** Operational burden outweighs the role-flexibility
  gain at this stage. Reconsider only if Cloud SQL's role/extension
  whitelist blocks a HIPAA gate we cannot work around.

### Option C: Stay on local Docker for production

- **Approach:** Run the same `docker-compose.yml` on the office
  workstation, expose API on the LAN.
- **Pros:** Zero new infrastructure, same code path as dev.
- **Cons:** No managed backups (we'd write our own), no PITR, no HA,
  no audit-grade encryption-at-rest, BAA does not cover anything
  on the workstation. Catastrophic disk failure = total data loss.
- **Why rejected:** Not viable for any data we cannot afford to
  lose, and certainly not for PHI. Acceptable only as a dev posture.

### Option D: Private IP via VPC peering / PSC instead of Auth Proxy

- **Approach:** Cloud SQL with Private IP; API/worker run inside a
  VPC-peered network; no proxy.
- **Pros:** Slightly lower per-connection latency; cleaner security
  story (no public IP at all).
- **Cons:** Requires us to first decide where API/worker run
  (GKE? Cloud Run? Compute Engine?) and stand up a VPC. None of that
  is decided yet. Cloud SQL Auth Proxy is the standard "before we
  pick a runtime" answer.
- **Why rejected (for now):** Premature. Re-evaluate as part of the
  ADR that picks the prod app runtime.

## Resolved decisions (closed 2026-05-08)

1. **Backup bucket.** No bucket exists yet. Create
   `gs://fusion-crm-backups` in project `fusioncrm-494201`,
   region `us-west1` (co-located with Cloud SQL — zero egress on
   cross-service traffic), uniform bucket-level access enabled,
   object versioning ON, lifecycle rule: delete objects older than
   `BACKUP_RETENTION_DAYS` (default 90).
2. **Service-account keys.** The organisation enforces
   `constraints/iam.disableServiceAccountKeyCreation` — downloading
   SA-key JSON is **not allowed**. Confirmed at provisioning time
   2026-05-08; the policy blocked
   `gcloud iam service-accounts keys create`. Adopt the modern
   posture instead:
   - The **operator laptop** uses Application Default Credentials
     (`gcloud auth application-default login`) signed in as
     `eduard@drantipov.com`. Owner role on the project gives the
     necessary access to Cloud SQL Auth Proxy + Secret Manager for
     manual `psql` / Alembic / Secret Manager work.
   - **Cloud-deployed runtime** (api, worker) — when we move to
     GKE / Cloud Run / GCE, attach the relevant SA via Workload
     Identity (no key file).
   - On-prem / Docker-on-VM runtime stays on the open question
     list; revisit when we pick the prod runtime.

## References

- Linear issue(s): TBD (filed after this ADR is Accepted)
- Related ADRs: none (first real ADR)
- Source whitepapers / docs:
  - `infra/CLAUDE.md` (operational invariants)
  - `infra/docker/docker-compose.yml`
  - `infra/docker/init-schemas.sql`
  - `packages/core/config.py`
  - `packages/db/alembic/env.py`
- External references:
  - GCP HIPAA Implementation Guide (BAA-covered services list)
  - Cloud SQL Auth Proxy v2 docs
