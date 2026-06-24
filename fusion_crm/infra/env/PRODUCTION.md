# Production runbook — Cloud Run + Cloud SQL + Fusion stack

> Per ADR-0001 (`docs/decisions/ADR-0001-cloud-sql-prod-postgres.md`)
> and ADR-0002 (`docs/decisions/ADR-0002-cloud-run-prod-runtime.md`).
> Read those ADRs first; this runbook assumes their decisions are in force.

## Table of contents

**Runtime (Cloud Run, ENG-113 epic):**
- [Cloud Run runtime](#cloud-run-runtime) — overview, foundation, services, IAP/LB, CI/CD
  - Foundation (ENG-114): `provision_cloud_run_foundation.sh`
  - Services + cron Jobs (ENG-115): `deploy_cloud_run.sh`
  - Public surface, IAP, HTTPS LB (ENG-116): `provision_cloud_iap_lb.sh`
  - CI/CD via GitHub Actions + WIF (ENG-117): `.github/workflows/deploy-prod.yml`

**Data plane (Cloud SQL, ENG-105..109):**
- [What is provisioned](#what-is-provisioned) — project, instance, SAs, secrets, Cloud Run resources
- [First-time bring-up](#first-time-bring-up) — operator laptop sequence
- [Connecting interactively (psql against prod)](#connecting-interactively-psql-against-prod)
- [Running a migration on prod](#running-a-migration-on-prod)
- [Rotating the DB password](#rotating-the-db-password)
- [Rotating runtime integration credentials (ENG-125)](#rotating-runtime-integration-credentials-eng-125)

**Operations:**
- [Starting / stopping the prod stack](#starting--stopping-the-prod-stack)
- [Restore drill (monthly)](#restore-drill-monthly)
- [Monitoring](#monitoring)
- [Promotion to HA + CMEK (PHI go/no-go gate)](#promotion-to-ha--cmek-phi-gono-go-gate)
- [Troubleshooting](#troubleshooting)
- [Things this runbook does NOT cover](#things-this-runbook-does-not-cover)

## Cloud Run runtime

### Overview

ADR-0002 puts the three app workloads (`apps/api`, `apps/web`,
`apps/worker`) on Cloud Run in project `fusioncrm-494201`, region
`us-west1`. The foundation under that — VPC, Serverless VPC Access
connector, Cloud SQL Private IP peering, Artifact Registry, the Cloud
Build deployer SA, and Workload Identity Federation for GitHub
Actions — is provisioned by a single idempotent script
(ENG-114). Cloud Run *services* are deployed by a second idempotent
script (ENG-115); the GitHub Actions workflow that drives the deploy
is ENG-117.

Resources created by ENG-114:

| Resource | Name | Notes |
|---|---|---|
| VPC | `fusion-vpc` | custom subnet mode |
| Subnet | `fusion-vpc-us-west1` | `10.0.0.0/24` in `us-west1` |
| Serverless VPC Access connector | `fusion-vpc-connector` | `10.0.1.0/28`, `e2-micro`, min=2 / max=10 |
| Private Service Connection range | `google-managed-services-fusion-vpc` | `10.10.0.0/24`, for servicenetworking peering |
| Artifact Registry repo | `fusion-containers` | docker format, `us-west1-docker.pkg.dev/fusioncrm-494201/fusion-containers` |
| Cloud Build deployer SA | `cloud-build-deployer-sa` | CI/CD principal |
| Workload Identity pool | `github-actions` | OIDC |
| Workload Identity provider | `github` | locked to `FUSIONDENTALAI/fusion_crm` |

Cost: only the Serverless VPC Access connector starts billing
immediately (~$10/month at the configured shape). Everything else is
free until Cloud Run services attach to it. See ADR-0002 §"Costs" for
the full Phase 1 / Phase 2 breakdown.

### Provisioning the foundation

Prerequisites:
- `./infra/scripts/provision_cloudsql.sh` already executed. The Cloud
  Run script reuses `fusion-api-sa` / `fusion-worker-sa` and patches
  the existing `fusion-crm-pg` instance.
- Operator authenticated to `gcloud` with Owner or Editor on
  `fusioncrm-494201`.

```bash
./infra/scripts/provision_cloud_run_foundation.sh
```

The script is idempotent. Re-run after any failure; each step is
guarded with describe-or-create or tolerates `ALREADY_EXISTS`.

What it does, end-to-end:

1. Enables `compute`, `vpcaccess`, `artifactregistry`, `run`,
   `cloudbuild`, `iamcredentials`, `sts` APIs.
2. Creates VPC `fusion-vpc` + subnet `fusion-vpc-us-west1`
   (`10.0.0.0/24`) with Private Google Access enabled.
3. Creates Serverless VPC Access connector `fusion-vpc-connector`
   (`10.0.1.0/28`, `e2-micro`, min=2 / max=10).
4. **Cloud SQL Private IP migration** (the delicate step):
   - Reserves Private Service Connection range
     `google-managed-services-fusion-vpc` (`10.10.0.0/24`).
   - Establishes peering with
     `servicenetworking.googleapis.com`.
   - Patches `fusion-crm-pg` to attach to `fusion-vpc`. **Public IP
     is intentionally retained** so the operator laptop's Cloud SQL
     Auth Proxy continues to work without disruption. The Private IP
     is allocated alongside it.
   - Prints the Private IP at the end so it can be wired into Cloud
     Run env later.
5. Creates Artifact Registry repo `fusion-containers` (docker,
   `us-west1`).
6. Creates `cloud-build-deployer-sa` and grants
   `roles/artifactregistry.writer`, `roles/run.admin`,
   `roles/iam.serviceAccountUser` at project scope.
7. Workload Identity Federation:
   - Pool `github-actions`, provider `github` (OIDC, issuer
     `https://token.actions.githubusercontent.com`).
   - Attribute mapping
     `google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref`.
   - Attribute condition pins to
     `FUSIONDENTALAI/fusion_crm` — no other repo can mint tokens
     against this pool.
   - Binds the GitHub repo principal to
     `roles/iam.workloadIdentityUser` on `cloud-build-deployer-sa`.
8. Allows `cloud-build-deployer-sa` to impersonate
   `fusion-api-sa` and `fusion-worker-sa` via
   `roles/iam.serviceAccountUser` on each runtime SA.

### Verifying foundation health

After the script reports success:

```bash
# 1. VPC + subnet exist and are wired together.
gcloud compute networks describe fusion-vpc \
  --project=fusioncrm-494201
gcloud compute networks subnets describe fusion-vpc-us-west1 \
  --region=us-west1 --project=fusioncrm-494201

# 2. VPC connector is READY.
gcloud compute networks vpc-access connectors describe \
  fusion-vpc-connector \
  --region=us-west1 --project=fusioncrm-494201 \
  --format='value(state)'
# expected: READY

# 3. Cloud SQL has a Private IP.
gcloud sql instances describe fusion-crm-pg \
  --project=fusioncrm-494201 \
  --format='value(ipAddresses)'
# expected: both PRIMARY (public) and PRIVATE entries.

# 4. Operator laptop Auth Proxy still works against the public IP.
cloud-sql-proxy fusioncrm-494201:us-west1:fusion-crm-pg --port 5432 &
PGPASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=fusioncrm-494201) \
  psql -h 127.0.0.1 -U fusion -d fusion -c 'SELECT 1;'
kill %1

# 5. Artifact Registry is reachable.
gcloud artifacts repositories describe fusion-containers \
  --location=us-west1 --project=fusioncrm-494201

# 6. WIF provider is pinned to the expected repo.
gcloud iam workload-identity-pools providers describe github \
  --location=global --workload-identity-pool=github-actions \
  --project=fusioncrm-494201 \
  --format='value(attributeCondition)'
# expected: assertion.repository == "FUSIONDENTALAI/fusion_crm"
```

### Deploying Cloud Run services

Once the foundation is healthy, the actual workloads are deployed by a
second idempotent script (ENG-115):

```bash
./infra/scripts/deploy_cloud_run.sh
```

Prerequisites for the first run:
- The foundation script (`provision_cloud_run_foundation.sh`) has
  completed and the VPC connector is `READY`.
- `db-password` secret has at least one version (produced by the
  first-time bring-up below).
- Operator has Docker running locally — the script builds the three
  images on the workstation and pushes to Artifact Registry. CI/CD
  (ENG-117) will move builds to GitHub Actions later; this script is
  the manual fallback and the source of truth for the gcloud
  invocations.

What `deploy_cloud_run.sh` does, in order:

1. Verifies the foundation: VPC connector, Artifact Registry repo,
   and both runtime SAs exist.
2. Enables `run`, `cloudscheduler`, `secretmanager` APIs (no-op if
   already enabled).
3. **DSN secrets one-shot.** Resolves Cloud SQL's Private IP and
   reads the current `db-password`, composes the asyncpg + psycopg
   DSN strings, and stores them as `db-url-asyncpg` /
   `db-url-psycopg` in Secret Manager. Re-runs only add a new
   secret version when the composed string actually changes.
4. Grants `roles/secretmanager.secretAccessor` to `fusion-api-sa`
   and `fusion-worker-sa` on every secret the services reference:
   `app-secret-key`, `db-password`, `encryption-key`,
   `internal-credential-token`, `db-url-asyncpg`, `db-url-psycopg`.
5. Builds + pushes images to
   `us-west1-docker.pkg.dev/fusioncrm-494201/fusion-containers/{fusion-api,fusion-web,fusion-worker}:<tag>`.
   Tag defaults to the git short SHA; falls back to `latest` if not
   in a checkout. Both `:<tag>` and `:latest` are pushed.
6. Deploys two Cloud Run services (worker decommissioned in ENG-172):
   - **`fusion-api`** — FastAPI. `min=0 max=5`, `512Mi / 1 vCPU`,
     `--vpc-egress=private-ranges-only`,
     `--ingress=all` (IAP arrives in ENG-116),
     `--no-allow-unauthenticated`. Secrets:
     `SECRET_KEY`, `DB_PASSWORD`, `ENCRYPTION_KEY`,
     `INTERNAL_CREDENTIAL_TOKEN`, `DATABASE_URL`,
     `DATABASE_URL_SYNC`. Env: `APP_ENV=production`,
     `LOG_LEVEL=INFO`, `API_HOST=0.0.0.0`, `REDIS_URL=…`,
     `OAUTH_REDIRECT_BASE_URL=https://fusioncrm.app`,
     `WEB_APP_BASE_URL=https://fusioncrm.app`,
     `API_CORS_ORIGINS=https://fusioncrm.app`.
   - **`fusion-web`** — Next.js. `min=0 max=5`, `512Mi / 1 vCPU`,
     same network shape as the API. Points at the API via
     `NEXT_PUBLIC_API_BASE_URL` set to the API's Cloud Run URL.
     Only the `INTERNAL_CREDENTIAL_TOKEN` secret is wired.
   - **`fusion-worker`** *(decommissioned, ENG-172)*. arq has no HTTP
     surface; Cloud Run health checks always failed. Outbound queue
     drain (`drain_outbound_queue`) is paused until ENG-112 returns a
     real always-on background runtime + Memorystore. Bounce poll
     keeps working as a one-shot Cloud Run Job (see below).
7. Deploys Cloud Run Jobs (one-shot containers reusing the **API
   image** — it COPYs `apps/` wholesale so `apps.worker.jobs.*` is
   importable — with their entrypoint overridden by `--command` / `--args`):
   - **`fusion-job-alembic-upgrade`** — on-demand. CI/CD runs this
     between image push and service deploy:
     `gcloud run jobs execute fusion-job-alembic-upgrade --wait`.
   - **`fusion-job-bounce-poll`** — recurring (ENG-134). Cloud
     Scheduler triggers `*/15 * * * *`.
   - **`fusion-job-salesforce-token-keepalive`** — recurring
     (ENG-234). Cloud Scheduler triggers `7 */6 * * *` so active
     Salesforce OAuth credentials refresh every 6 hours.
   - **`fusion-job-sf-pull`** / **`fusion-job-cs-pull`** — recurring
     scheduled ingestion jobs. Cloud Scheduler triggers Salesforce
     every 15 minutes and CareStack every 30 minutes. Operators can
     set `SCHEDULE_INTEGRATION_PULL=0` during emergency deploys to
     leave those jobs and scheduler entries untouched.
   - **`fusion-job-marketing-pull`** — recurring daily marketing/SEO
     pull (Google Ads, Meta Ads, GA4, Search Console — all tenants),
     ENG-493. Cloud Scheduler triggers `43 11 * * *` (11:43 UTC =
     03:43 PST / 04:43 PDT, nighttime in America/Los_Angeles
     year-round). This IS an external integration reader, so it
     shares the `SCHEDULE_INTEGRATION_PULL=0` halt gate with sf-pull /
     cs-pull / backfill. Per-tenant credentials come from
     `tenant.integration_credential` (ENG-490); no marketing secret
     is passed via env or CLI, and providers with no credential
     short-circuit to `skipped` (a missing credential is not an
     error).
   - **`fusion-job-marketing-backfill`** — on-demand one-shot
     HISTORICAL marketing/SEO backfill (ENG-492 / ENG-493). No Cloud
     Scheduler entry; deployed unconditionally (like
     `fusion-job-alembic-upgrade`) so its definition is always present
     for an operator to run once after real credentials are entered
     via the Settings UI (ENG-491). Default window is ~365 days; pass
     `--args=--months,12` (or `--days` / `--providers`) to override.
     Same per-tenant credential resolution and graceful-skip
     semantics as the daily pull.
8. Creates Cloud Scheduler entries that POST to the Cloud Run Jobs
   API as `fusion-worker-sa`, which is granted `roles/run.invoker`
   on each scheduled job.

The script reports the api + web service URLs at the end. Capture them;
ENG-116 wires the external LB + IAP against the api/web URLs.

#### First-time DB DSN bootstrap (manual one-shot)

`deploy_cloud_run.sh` creates `db-url-asyncpg` / `db-url-psycopg`
secrets automatically on first run, provided `db-password` already has
a version. If for any reason the secrets need to be (re)created by
hand:

```bash
PRIV_IP=$(gcloud sql instances describe fusion-crm-pg \
  --project=fusioncrm-494201 \
  --format='value(ipAddresses.filter("type:PRIVATE").extract(ipAddress))' \
  | tr -d '[]')
PW=$(gcloud secrets versions access latest --secret=db-password \
  --project=fusioncrm-494201)

printf 'postgresql+asyncpg://fusion:%s@%s:5432/fusion' "$PW" "$PRIV_IP" \
  | gcloud secrets versions add db-url-asyncpg --data-file=- \
    --project=fusioncrm-494201
printf 'postgresql+psycopg://fusion:%s@%s:5432/fusion'  "$PW" "$PRIV_IP" \
  | gcloud secrets versions add db-url-psycopg --data-file=- \
    --project=fusioncrm-494201
unset PW
```

Rotating `db-password` later requires re-running
`deploy_cloud_run.sh`, which re-composes both DSN secrets and adds new
versions. Cloud Run picks up the new versions on the next revision
deploy (or immediately, if the secret reference uses `:latest`).

#### Verifying a deploy

```bash
# Service URLs.
gcloud run services list --region=us-west1 --project=fusioncrm-494201

# Smoke the API (you'll be redirected by IAP once ENG-116 lands; until
# then the service is private — invoke as a Cloud Run-authenticated
# user with run.invoker).
TOKEN=$(gcloud auth print-identity-token \
  --audiences="$(gcloud run services describe fusion-api \
                  --region=us-west1 --format='value(status.url)')")
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "$(gcloud run services describe fusion-api \
       --region=us-west1 --format='value(status.url)')/healthz"
# expected: {"status":"ok"}

# Worker liveness — check the latest revision is serving and look at
# the arq startup log.
gcloud run services describe fusion-worker --region=us-west1
gcloud beta run services logs read fusion-worker --region=us-west1 --limit=50

# Run Alembic against prod (the Cloud Run Jobs path).
gcloud run jobs execute fusion-job-alembic-upgrade \
  --region=us-west1 --wait
```

#### Build-only / deploy-only

The script honours two env flags so the build and deploy halves can run
on different machines (typical CI/CD pattern):

```bash
BUILD_ONLY=1   ./infra/scripts/deploy_cloud_run.sh   # build + push, no deploy
DEPLOY_ONLY=1  ./infra/scripts/deploy_cloud_run.sh   # skip build, deploy latest

# Subset of services. Defaults to "api web worker".
SERVICES="api"  ./infra/scripts/deploy_cloud_run.sh

# Pin a specific image tag (defaults to git short SHA).
IMAGE_TAG=v0.2.1 ./infra/scripts/deploy_cloud_run.sh
```

#### Marketing/SEO pull + historical backfill (ENG-493)

Production has no always-on arq worker, so the
`pull_marketing_for_all_tenants` arq cron (which fires daily at 04:43
local in dev/docker) never runs in prod. Two Cloud Run Jobs, both on
the **API image** running as `fusion-worker-sa`, cover prod:

- **`fusion-job-marketing-pull`** — the daily rolling pull. Deployed
  and scheduled by `deploy_cloud_run.sh` under the
  `SCHEDULE_INTEGRATION_PULL` gate. Cloud Scheduler
  (`fusion-sched-marketing-pull`) fires `43 11 * * *` (11:43 UTC,
  nighttime PT year-round). Re-reads a rolling 7-day window and dedupes
  on captured-payload identity, so re-runs are safe.
- **`fusion-job-marketing-backfill`** — the one-time deep history load
  (`apps.worker.jobs.marketing_backfill`, default ~365 days). No
  scheduler; run it once by hand after real per-tenant credentials are
  entered through the Settings → Integrations UI (ENG-491).

Both resolve credentials per tenant from `tenant.integration_credential`
(ENG-490): each tenant pulls with its own Google Ads / Meta Ads / GA4 /
Search Console account. A (tenant, provider) leg with no credential
short-circuits to `skipped` — a missing credential is **not** an error,
so running either job before credentials exist is a safe no-op. No
marketing secret is ever passed via env or on the command line.

Run the one-shot historical backfill on demand:

```bash
# Default ~12 months, all four providers, all tenants.
gcloud run jobs execute fusion-job-marketing-backfill \
  --region=us-west1 --project=fusioncrm-494201 \
  --args=--months,12 --wait

# Narrower window / provider subset (args are comma-joined):
gcloud run jobs execute fusion-job-marketing-backfill \
  --region=us-west1 --project=fusioncrm-494201 \
  --args=--days,90,--providers,google_ads,ga4 --wait
```

Verify / trigger the daily pull manually:

```bash
# Fire the daily pull off-schedule (same as the Scheduler trigger):
gcloud run jobs execute fusion-job-marketing-pull \
  --region=us-west1 --project=fusioncrm-494201 --wait

# Confirm the scheduler entry exists and its cadence:
gcloud scheduler jobs describe fusion-sched-marketing-pull \
  --location=us-west1 --project=fusioncrm-494201 \
  --format='value(schedule,state)'

# Tail the last execution's logs (counts only; no secret payloads logged):
gcloud beta run jobs executions list --job=fusion-job-marketing-pull \
  --region=us-west1 --project=fusioncrm-494201 --limit=1
```

To pause marketing along with all other external pulls during an
incident, deploy with `SCHEDULE_INTEGRATION_PULL=0` — that gate skips
sf-pull / cs-pull / backfill / cs-procedure-codes **and** marketing-pull
and leaves their scheduler entries untouched. (The on-demand
`fusion-job-marketing-backfill` is exempt: it has no scheduler so there
is nothing recurring to halt.)

### Provisioning the public surface (ENG-116)

Once Cloud Run services `fusion-api` and `fusion-web` are deployed
(ENG-115), the public surface — global HTTPS Load Balancer with a
Google-managed certificate, Cloud IAP gating, and a path-routed URL
map — is provisioned by a single idempotent script:

```bash
TENANT_DOMAIN=app.example.com \
IAP_OAUTH_CLIENT_ID=123-abc.apps.googleusercontent.com \
IAP_OAUTH_CLIENT_SECRET='GOCSPX-...' \
  ./infra/scripts/provision_cloud_iap_lb.sh
```

Resources the script creates / maintains (all idempotent — re-run
after any failure):

| Resource | Name | Role |
|---|---|---|
| Global static IP | `fusion-lb-ip` | DNS anchor (A record target) |
| Managed SSL certificate | `fusion-lb-cert` | TLS for `${TENANT_DOMAIN}`, Google-renewed |
| Serverless NEG (api) | `fusion-lb-neg-api` | LB pointer at `fusion-api` |
| Serverless NEG (web) | `fusion-lb-neg-web` | LB pointer at `fusion-web` |
| Backend service (api) | `fusion-lb-backend-api` | IAP toggle + IAM target for `/api/*` |
| Backend service (web) | `fusion-lb-backend-web` | IAP toggle + IAM target for `/*` |
| URL map | `fusion-lb-url-map` | path matcher: `/api/*` → api, `/*` → web |
| Target HTTPS proxy | `fusion-lb-https-proxy` | terminates TLS |
| Global forwarding rule | `fusion-lb-forwarding-rule` | binds static IP:443 to proxy |
| IAM bindings | `roles/iap.httpsResourceAccessor` on both backend services |

The `apps/worker` service is internal-only and intentionally gets no
NEG, no IAP, and no public surface. It reaches Cloud SQL + Redis via
`fusion-vpc-connector` only.

#### Step 1 — Choose the final tenant domain

The script accepts `TENANT_DOMAIN` as an env var. ADR-0002 lists the
final domain as an open question; the clinic owns the decision. The
default placeholder `app.fusioncrm.example` is intentionally fake so
the script can lint without committing a real domain — running the
script against the placeholder WILL create a static IP and resource
skeleton, but the managed certificate will sit in
`FAILED_NOT_VISIBLE` until DNS for a real domain resolves to the
reserved IP. Picking the final domain is a one-time decision; the
script tolerates re-runs with a different `TENANT_DOMAIN` only if the
operator first deletes the old `fusion-lb-cert` by hand (managed
certs are immutable on `domains`).

#### Step 2 — OAuth consent screen + OAuth client (one-time)

Cloud IAP needs an OAuth brand and client. This is a Cloud Console
click-through; do it once per project. The script does NOT create
these — it consumes the resulting IDs via env vars.

1. Cloud Console → APIs & Services → **OAuth consent screen**.
2. **User type: Internal** (only members of the `drantipov.com`
   Workspace org can sign in — exactly what IAP needs). Internal type
   does NOT require an application-homepage URL, privacy-policy URL,
   or terms-of-service URL — leave them blank.
3. App name: `Fusion CRM`. Support email: `eduard@drantipov.com` (or
   `drantipov@drantipov.com`). Developer contact: same.
4. Scopes: leave default (`openid`, `email`, `profile`). IAP only
   needs the identity claim.
5. Save and continue.
6. APIs & Services → **Credentials** → **Create credentials** →
   **OAuth client ID** → **Web application**. Name:
   `Fusion CRM IAP`.
7. Authorised redirect URI: leave blank for now and save. The Console
   then surfaces the IAP-bound redirect URI to add. Copy it back into
   the client and save again. (Format:
   `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect`.)
8. Copy the client ID and client secret into `IAP_OAUTH_CLIENT_ID` /
   `IAP_OAUTH_CLIENT_SECRET` env vars. Treat the secret like any
   Secret Manager entry; do not commit it. Optionally also push it
   into Secret Manager (`iap-oauth-client-secret`) for rotation later.

#### Step 3 — Run the script

```bash
TENANT_DOMAIN=app.example.com \
IAP_OAUTH_CLIENT_ID=123-abc.apps.googleusercontent.com \
IAP_OAUTH_CLIENT_SECRET='GOCSPX-...' \
  ./infra/scripts/provision_cloud_iap_lb.sh
```

Expect ~30–60 seconds end-to-end. The script prints the reserved
static IP address at the end — copy it; the next step needs it.

#### Step 4 — Point DNS at the static IP

If the operator uses Cloud DNS:

```bash
gcloud dns record-sets create app.example.com. \
  --rrdatas=<STATIC_IP_FROM_STEP_3> \
  --type=A --ttl=300 \
  --zone=<your-managed-zone> \
  --project=fusioncrm-494201
```

If the operator uses an external DNS provider (Cloudflare, Namecheap,
Route 53, etc.): create an `A` record for `${TENANT_DOMAIN}` pointing
to the reserved static IP. TTL 300 is fine. Do NOT enable
Cloudflare's orange-cloud proxy — IAP must see the real client IP
and the real Google-managed cert must terminate the TLS, not an
intermediate proxy.

#### Step 5 — Wait for the managed certificate to provision

Google validates the cert by checking that DNS for `${TENANT_DOMAIN}`
resolves to the LB IP, then issues a cert. This takes **15–60
minutes** in the common case; the rare slow case takes a few hours.

Check progress:

```bash
gcloud compute ssl-certificates describe fusion-lb-cert \
  --global --project=fusioncrm-494201 \
  --format='value(managed.status,managed.domainStatus)'
# PROVISIONING / PROVISIONING -> ACTIVE / ACTIVE
```

If after 24 hours the status is still not `ACTIVE`, the most common
cause is DNS — `dig +short app.example.com` from the operator laptop
should return the reserved static IP. If it doesn't, fix DNS; the
cert will pick up on its own once DNS propagates.

#### Step 6 — Smoke-test the public surface

Before sign-in (any unauthenticated client):

```bash
curl -sSI https://app.example.com/
# expected: HTTP/2 302
# expected: location: https://accounts.google.com/...
```

The 302 confirms three things at once: (a) DNS is resolving to the
LB, (b) the cert is ACTIVE, (c) IAP is enforcing the allow-list.
Without IAP the response would be the Cloud Run service's own status
code; without DNS / cert the request would not connect at all.

After sign-in, in a browser as an allow-listed user (e.g.
`eduard@drantipov.com`):

- `https://app.example.com/` → loads the Next.js dashboard (200).
- `https://app.example.com/api/healthz` → 200 from FastAPI.

The IAP cookie is HttpOnly and scoped to `${TENANT_DOMAIN}`. To repeat
the check from CLI, copy the `GCP_IAAP_AUTH_TOKEN_*` cookie from
DevTools and pass it via `curl -b`, or use
`gcloud auth print-identity-token --audiences=<oauth-client-id>` and
pass `-H "Authorization: Bearer ..."`. Both flows are documented at
cloud.google.com/iap/docs/authentication-howto.

#### Adding or removing allow-listed users later

The script binds the initial allow-list per ADR-0002 §"Access
control" (`drantipov@drantipov.com`, `eduard@drantipov.com`). To add
or remove users without re-running the full script:

```bash
# Add a user (run twice — once per backend service):
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --service=fusion-lb-backend-api \
  --member=user:new.staff@drantipov.com \
  --role=roles/iap.httpsResourceAccessor \
  --project=fusioncrm-494201
gcloud iap web add-iam-policy-binding \
  --resource-type=backend-services \
  --service=fusion-lb-backend-web \
  --member=user:new.staff@drantipov.com \
  --role=roles/iap.httpsResourceAccessor \
  --project=fusioncrm-494201

# Remove a user — same shape, `remove-iam-policy-binding`.
```

Once the clinic-staff Google Group exists in Workspace, replace the
per-user bindings with a single `group:clinic-staff@drantipov.com`
binding on each backend service. The script's `IAP_ALLOWED_PRINCIPALS`
env var accepts space-separated `group:` / `user:` principals for
that day.

#### Rotating the IAP OAuth secret

Re-run the script with new `IAP_OAUTH_CLIENT_SECRET`. The
`backend-services update --iap=enabled,oauth2-client-id=...,oauth2-client-secret=...`
call is idempotent and re-applies the secret on every run. There is
NO managed-cert-style waiting period — the new secret is live
immediately.

#### Troubleshooting (public surface)

- **`fusion-lb-cert` stuck in `PROVISIONING` after 1+ hour** — DNS
  has not propagated, or it's pointing at a different IP. Run
  `dig +short ${TENANT_DOMAIN}` and compare to the script's "static
  IP address" line. If DNS is right and the cert is still stuck, the
  Console shows the per-domain failure reason under
  Network Services → Load balancing → Frontend → `fusion-lb-cert`.
- **`fusion-lb-cert` status `FAILED_NOT_VISIBLE`** — `${TENANT_DOMAIN}`
  is not resolvable from the public internet at all. Confirm the
  zone is published (Cloud DNS) or the record is saved + propagated
  (external provider).
- **Browser returns `403 You don't have access`** — the user is
  authenticated but not on the allow-list. Add a
  `roles/iap.httpsResourceAccessor` binding on BOTH backend services
  (api + web) — IAP enforces the role per backend service, not per
  URL path.
- **Browser returns `IAP cannot enable Cloud IAP for an app behind
  Cloud Run`** — the OAuth client redirect URI is missing the
  `:handleRedirect` IAP suffix, or the client is type "Desktop"
  instead of "Web application". Re-do Step 2 with the right client
  type.
- **`gcloud iap web add-iam-policy-binding` fails with
  `INVALID_ARGUMENT: brand not found`** — the operator never
  completed Step 2's OAuth consent screen. The IAP brand is created
  implicitly the first time a Web-type OAuth client is saved with
  user type Internal. Re-do Step 2 and retry.
- **`curl` returns `HTTP 404` instead of `302`** — the URL map's
  path matcher is missing or pointing at the wrong host. Check:
  ```bash
  gcloud compute url-maps describe fusion-lb-url-map --global \
    --project=fusioncrm-494201 \
    --format='value(hostRules,pathMatchers)'
  ```
  Re-run the script — it re-applies the path-matcher idempotently
  IF the existing matcher's name matches; if the previous run was
  interrupted mid-`add-path-matcher`, delete the half-applied
  matcher in the Console and re-run.
- **Cert provisions, IAP works, but `/api/*` returns 502** — the
  `fusion-api` Cloud Run service is unhealthy. The LB does not
  health-check Serverless NEGs (Cloud Run handles that internally);
  the 502 is the Cloud Run side reporting back. Inspect
  `gcloud run services logs read fusion-api --region=us-west1`.

### Cloud SQL: public → private-only (later)

The foundation script keeps the Cloud SQL public IP attached so the
operator laptop's Cloud SQL Auth Proxy keeps working. Once all
production consumers are Cloud Run services on `fusion-vpc-connector`,
flip the instance to private-only:

```bash
gcloud sql instances patch fusion-crm-pg \
  --no-assign-ip \
  --project=fusioncrm-494201
```

After this, operator-laptop access requires either (a) a bastion in
`fusion-vpc`, or (b) the Cloud SQL Auth Proxy with the
`--private-ip` flag plus a VPN/IAP-tunnel into `fusion-vpc`. Don't
run this command until ENG-115 + ENG-117 are stable and verified.

### Troubleshooting (Cloud Run foundation)

- **VPC connector stuck in `CREATING` or `ERROR`** — the
  `10.0.1.0/28` range must not overlap any existing subnet in
  `fusion-vpc`. Re-running the script after deleting a broken connector
  is safe. Capacity-wise, `min-instances=2` is the floor; raising
  `max-instances` is the lever if connector saturation shows up in
  Cloud Run logs as `503` with `connection: throttled` (see Cloud
  Monitoring metric
  `run.googleapis.com/container/network/throttled_request_count`).
- **WIF token rejection in GitHub Actions** —
  `Permission 'iam.serviceAccounts.getAccessToken' denied`
  almost always means one of: (a) the `attribute.repository`
  condition on the provider does not match the workflow's repo, or
  (b) the `workloadIdentityUser` binding on
  `cloud-build-deployer-sa` is missing for the
  `principalSet://...attribute.repository/...` principal. Re-run the
  foundation script — it re-applies the binding idempotently.
- **Artifact Registry push fails with 403** — the workflow is
  authenticating as `cloud-build-deployer-sa` but missing
  `roles/artifactregistry.writer` on the project, or it's pushing to
  the wrong region/repo path. The repo path is
  `us-west1-docker.pkg.dev/fusioncrm-494201/fusion-containers/<image>:<tag>`.
- **`gcloud services vpc-peerings connect` fails with `RESOURCE_IN_USE`**
  — the peering already exists. The script lists peerings before
  connecting; if you ran ad-hoc `gcloud` commands before the script,
  delete the conflicting peering or skip step 4 by exporting
  `PSC_RANGE_NAME` to a name that doesn't exist yet.
- **Cloud SQL Private IP not appearing after `patch`** — Cloud SQL
  takes a few minutes to allocate the IP after the VPC attach. Re-run
  the script; the final `describe` step picks it up once available.

### Troubleshooting (Cloud Run services)

- **Service revision fails to start with `PERMISSION_DENIED` on a
  secret** — the runtime SA is missing
  `roles/secretmanager.secretAccessor` on that specific secret.
  `deploy_cloud_run.sh` re-binds the standard set; if you added a
  new secret, add the binding by hand or extend the script's
  `SECRETS_API` / `SECRETS_WORKER` arrays.
- **`fusion-worker` revision stays unhealthy / restarts** — this
  service should not exist in the current Cloud Run runtime. arq has
  no HTTP probe, so recurring production work runs as Cloud Run Jobs
  triggered by Cloud Scheduler.
- **`fusion-job-alembic-upgrade` returns non-zero** — the worker
  image was built before the latest revision was committed, so the
  migration is missing locally. Re-build with the head SHA:
  `IMAGE_TAG=$(git rev-parse --short HEAD) ./infra/scripts/deploy_cloud_run.sh`
  then `gcloud run jobs execute fusion-job-alembic-upgrade --wait`.
- **Cloud Scheduler trigger returns 403** — `fusion-worker-sa` is
  missing `roles/run.invoker` on the target Cloud Run Job. Re-run
  `deploy_cloud_run.sh` — it re-binds the role on every run.
- **Web image is large (>500 MB)** — next.config.mjs has not been
  switched to `output: "standalone"`. The runtime Dockerfile falls
  back to copying the full Next.js build (functionally fine, just
  bigger). Add `output: "standalone"` and re-build to drop the image
  size dramatically.

### CI/CD (ENG-117)

Production deploys are driven entirely from GitHub Actions via
Workload Identity Federation — no service-account JSON key is ever
downloaded to a CI runner. Two workflows live in `.github/workflows/`:

- **`deploy-prod.yml`** — push-to-`main` forward deploy.
  Shape: `verify` (lint + typecheck + tests) → `detect-changes`
  (paths-filter) + `auth` (WIF preflight) → `build-api` /
  `build-web` / `build-worker` (conditional) → `alembic-migrate`
  (Cloud Run Job, gates every service deploy) → `deploy-api` /
  `deploy-web` / `deploy-worker` (no-traffic, then `--to-latest`) →
  `post-deploy-comment` (summary on the merge commit).
- **`deploy-prod-rollback.yml`** — manual `workflow_dispatch`.
  Inputs: `service` (api/web/worker), `revision` (full Cloud Run
  revision name), `confirm` (must be `ROLLBACK`). Runs
  `gcloud run services update-traffic <svc>
  --to-revisions=<rev>=100` and prints the resulting traffic split.
  CLI equivalent is the same `update-traffic` command.

The full workflow contract and forbidden-pattern list lives in
`.github/CLAUDE.md`. Highlights that the operator should know:

- **`alembic upgrade head` runs as a one-shot Cloud Run Job
  (`fusion-job-alembic-upgrade`) before any service deploy.** If
  migration fails, no service is updated. The job is provisioned in
  ENG-115; the workflow only re-points it at the freshly built API
  image and executes it with `--wait`.
- **`--no-traffic` then `--to-latest`** is the zero-downtime path.
  The new revision must report healthy on its Cloud Run probe
  before any user traffic reaches it.
- **`environment: production`** is set on every job that mints a
  WIF token. Configure the `production` GitHub Actions environment
  with manual approvers (Cloud Console → GitHub → Settings →
  Environments) to gate the first few deploys after this lands.
- The workflow does NOT touch Secret Manager. Runtime secrets are
  resolved by the Cloud Run service itself via `gcp-secret://...`
  references (see `packages/core/secrets.py`).

Operator pre-flight checklist before the first push to `main`
hits `deploy-prod.yml`:

```bash
# 1. WIF provider is pinned to the right repo (foundation script's last step).
gcloud iam workload-identity-pools providers describe github \
  --location=global --workload-identity-pool=github-actions \
  --project=fusioncrm-494201 \
  --format='value(attributeCondition)'
# expected: assertion.repository == "FUSIONDENTALAI/fusion_crm"

# 2. Cloud Build deployer SA can be impersonated by the repo principal.
gcloud iam service-accounts get-iam-policy \
  cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com \
  --project=fusioncrm-494201 \
  --format='value(bindings)'
# expected: principalSet ... attribute.repository/FUSIONDENTALAI/fusion_crm
#           bound to roles/iam.workloadIdentityUser

# 3. Cloud Run Job exists (provisioned in ENG-115).
gcloud run jobs describe fusion-job-alembic-upgrade \
  --region=us-west1 --project=fusioncrm-494201 \
  --format='value(metadata.name,spec.template.spec.template.spec.serviceAccountName)'
# expected: fusion-job-alembic-upgrade ... fusion-api-sa@...

# 4. The three Cloud Run services exist (also ENG-115).
for svc in fusion-api fusion-web fusion-worker; do
  gcloud run services describe "$svc" \
    --region=us-west1 --project=fusioncrm-494201 \
    --format='value(metadata.name)' 2>/dev/null \
    || echo "MISSING: $svc"
done
```

If any of those four checks fail, fix in ENG-114 / ENG-115 before
landing a PR that triggers `deploy-prod.yml`.

---

## What is provisioned

- **GCP project:** `fusioncrm-494201`
- **Region:** `us-west1`
- **Cloud SQL instance:** `fusion-crm-pg` (PostgreSQL 16, single zone,
  PITR ON, 7-day backup retention)
- **Database:** `fusion`, role `fusion`
- **Backup bucket:** `gs://fusion-crm-backups`, lifecycle 90 days
- **Service accounts:**
  - `fusion-api-sa` — API runtime
  - `fusion-worker-sa` — worker runtime
  - `fusion-migrator-sa` — operator laptop, schema/migration work
  - `fusion-deployer-sa` — Cloud Build + GitHub Actions deploys
    (impersonated via WIF; no key)
- **Secret Manager entries:** `db-password`, `app-secret-key`,
  `encryption-key`, `internal-credential-token`,
  `salesforce-client-secret`, `carestack-client-secret`,
  `carestack-vendor-key`, `carestack-account-key`,
  `db-url-asyncpg`, `db-url-psycopg` (created by
  `deploy_cloud_run.sh` on first run)
- **Cloud Run services:** `fusion-api`, `fusion-web`
- **Cloud Run Jobs:** `fusion-job-alembic-upgrade`,
  `fusion-job-bounce-poll`, `fusion-job-salesforce-token-keepalive`,
  `fusion-job-sf-pull`, `fusion-job-cs-pull`,
  `fusion-job-marketing-pull` (Cloud Scheduler triggers),
  `fusion-job-marketing-backfill` (on-demand, no scheduler — ENG-493)
- **VPC + connector:** `fusion-vpc`, Serverless VPC Access connector
  `fusion-vpc-connector` (Cloud SQL Private IP reachable from
  Cloud Run)
- **Artifact Registry:** Docker repo `fusion-images` in `us-west1`
- **Workload Identity Federation:** pool `github-pool`, provider
  `github-provider` pinned to repository
  `FUSIONDENTALAI/fusion_crm` via `attribute.repository`
- **Public surface (ENG-116):** global static IP `fusion-lb-ip`,
  Google-managed SSL cert, Serverless NEGs, IAP-enabled backend
  services, URL map (`/api/*` → api, `/*` → web), target HTTPS
  proxy, global forwarding rule

The instance connection name is
`fusioncrm-494201:us-west1:fusion-crm-pg`.

## First-time bring-up

Run on the operator laptop, in order. Each step is idempotent.

```bash
# 1. Provision GCP resources (APIs, SAs, secrets, bucket, instance, db).
./infra/scripts/provision_cloudsql.sh

# 2. Populate db-password (one-time; pick something strong).
openssl rand -base64 32 \
  | gcloud secrets versions add db-password --data-file=- \
    --project=fusioncrm-494201

# 3. Populate the remaining secrets.
printf 'YOUR_FERNET_KEY' | gcloud secrets versions add encryption-key \
  --data-file=- --project=fusioncrm-494201
# Generate INTERNAL_CREDENTIAL_TOKEN once (shared API <-> Next.js):
python -c "import secrets; print(secrets.token_urlsafe(32))" \
  | gcloud secrets versions add internal-credential-token \
    --data-file=- --project=fusioncrm-494201
# ...repeat for app-secret-key, *_client_secret, *_vendor_key, *_account_key.

# 4. Download a key for the migrator SA (one-time).
mkdir -p ~/.config/fusion-crm
gcloud iam service-accounts keys create \
  ~/.config/fusion-crm/fusion-migrator-sa.json \
  --iam-account=fusion-migrator-sa@fusioncrm-494201.iam.gserviceaccount.com
chmod 600 ~/.config/fusion-crm/fusion-migrator-sa.json

# 5. Initialise schemas + run alembic.
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/fusion-crm/fusion-migrator-sa.json
export CLOUDSQL_INSTANCE_CONNECTION_NAME=fusioncrm-494201:us-west1:fusion-crm-pg
./infra/scripts/cloudsql_bootstrap.sh

# 6. Provision the Cloud Run foundation (VPC, VPC connector, Cloud SQL
#    Private IP peering, Artifact Registry, Cloud Build SA, WIF).
./infra/scripts/provision_cloud_run_foundation.sh

# 7. Deploy the three Cloud Run services + cron Jobs.
./infra/scripts/deploy_cloud_run.sh
```

After step 5 the `tenant_credentials_seed` migration (ENG-125) copies
the populated `SALESFORCE_*` and `CARESTACK_*` env values into
encrypted rows on `tenant.integration_credential`. Runtime callers
read from the DB; env values become **bootstrap-only** and may be
cleared after the first successful migration run.

## Connecting interactively (psql against prod)

```bash
cloud-sql-proxy fusioncrm-494201:us-west1:fusion-crm-pg --port 5432 &
PGPASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=fusioncrm-494201) \
  psql -h 127.0.0.1 -U fusion -d fusion
# When done:
kill %1
```

## Running a migration on prod

After committing a new Alembic revision locally:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/fusion-crm/fusion-migrator-sa.json
cloud-sql-proxy fusioncrm-494201:us-west1:fusion-crm-pg --port 5432 &
DB_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=fusioncrm-494201)
DATABASE_URL_SYNC="postgresql+psycopg://fusion:${DB_PASSWORD}@127.0.0.1:5432/fusion" \
DATABASE_URL="postgresql+asyncpg://fusion:${DB_PASSWORD}@127.0.0.1:5432/fusion" \
REDIS_URL="redis://127.0.0.1:6379/0" \
SECRET_KEY=migration-noop \
  python -m alembic upgrade head
kill %1
```

Or just re-run `./infra/scripts/cloudsql_bootstrap.sh` — it is
idempotent and ends with `alembic upgrade head`.

Once Cloud Run is the canonical runtime, the same upgrade is also
available via the `fusion-job-alembic-upgrade` Cloud Run Job:

```bash
gcloud run jobs execute fusion-job-alembic-upgrade \
  --region=us-west1 --project=fusioncrm-494201 --wait
```

The Job runs inside `fusion-vpc` and reaches Cloud SQL on the Private
IP; the operator-laptop path keeps working as a backup channel.

## Rotating the DB password

```bash
NEW=$(openssl rand -base64 32)
printf '%s' "$NEW" \
  | gcloud secrets versions add db-password --data-file=- \
    --project=fusioncrm-494201

# Update the Postgres role itself.
gcloud sql users set-password fusion \
  --instance=fusion-crm-pg \
  --password="$NEW" \
  --project=fusioncrm-494201

# Re-run the deploy script so db-url-asyncpg + db-url-psycopg pick up
# the new password and Cloud Run revisions are redeployed against them.
./infra/scripts/deploy_cloud_run.sh DEPLOY_ONLY=1

unset NEW
```

For the office docker-compose stack (if still running in parallel),
restart it to pick up the new password:

```bash
./infra/scripts/start_prod.sh down
./infra/scripts/start_prod.sh up -d
```

Old secret versions stay accessible until disabled — leave at
least one prior version around for rollback during a 24-hour window.

## Rotating runtime integration credentials (ENG-125)

Salesforce, CareStack, and (multi-mailbox) Google / Microsoft
credentials live encrypted in `tenant.integration_credential`. Update
them at runtime — never by editing `.env` and redeploying.

```bash
# Cloud SQL proxy in another terminal:
cloud-sql-proxy fusioncrm-494201:us-west1:fusion-crm-pg --port 5432 &
DB_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=fusioncrm-494201)
ENCRYPTION_KEY=$(gcloud secrets versions access latest \
  --secret=encryption-key --project=fusioncrm-494201)

# Salesforce — rotate the client_secret on a live Connected App:
DATABASE_URL="postgresql+asyncpg://fusion:${DB_PASSWORD}@127.0.0.1:5432/fusion" \
DATABASE_URL_SYNC="postgresql+psycopg://fusion:${DB_PASSWORD}@127.0.0.1:5432/fusion" \
REDIS_URL="redis://127.0.0.1:6379/0" \
SECRET_KEY=rotate-noop \
ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  python - <<'PY'
import asyncio, uuid
from packages.core.config import get_settings
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.tenant.credential_service import IntegrationCredentialService
from packages.tenant.service import TenantService

async def main():
    async with async_session() as s:
        tenant = await TenantService(s).resolve_default(
            get_settings().tenant_default_slug
        )
        svc = IntegrationCredentialService(s)
        await svc.upsert(
            TenantId(tenant.id),
            "salesforce",
            "api_key",
            {
                "client_id": "<unchanged>",
                "client_secret": "<NEW SECRET>",
                "callback_url": "<unchanged>",
                "domain": "login.salesforce.com",
            },
            principal=Principal(
                id=uuid.uuid4(),
                email="ops@example.com",
                tenant_id=TenantId(tenant.id),
                roles=frozenset({Role.ADMIN}),
            ),
            display_name="Salesforce production org",
            is_default=True,
        )
        await s.commit()
asyncio.run(main())
PY
kill %1
```

The audit log records `tenant.credential.upsert.update` with no
plaintext payload values. Restart the API + worker so cached payloads
flush:

```bash
./infra/scripts/start_prod.sh restart api worker
```

For multi-mailbox providers (`google_workspace`, `microsoft_365`)
pass `mailbox_email="me@domain.com"` to the same `upsert` call so the
key tuple includes the mailbox. The first credential per
`(tenant, provider)` should be `is_default=True`; subsequent mailboxes
attach as non-default rows and are routed by location / tags.

## Starting / stopping the prod stack

```bash
./infra/scripts/start_prod.sh up -d        # default
./infra/scripts/start_prod.sh logs -f api
./infra/scripts/start_prod.sh down
```

## Restore drill (monthly)

Per `infra/CLAUDE.md`, run a full restore into a scratch DB once a
month and spot-check a known row.

1. Create a scratch Cloud SQL instance in the same project, e.g.
   `fusion-crm-pg-drill`.
2. Pick a recent automated backup:
   ```bash
   gcloud sql backups list --instance=fusion-crm-pg \
     --project=fusioncrm-494201
   ```
3. Restore:
   ```bash
   gcloud sql backups restore <BACKUP_ID> \
     --restore-instance=fusion-crm-pg-drill \
     --backup-instance=fusion-crm-pg \
     --project=fusioncrm-494201
   ```
4. Connect via proxy and spot-check:
   ```bash
   cloud-sql-proxy fusioncrm-494201:us-west1:fusion-crm-pg-drill --port 5433 &
   psql -h 127.0.0.1 -p 5433 -U fusion -d fusion \
     -c "SELECT count(*) FROM identity.person;"
   ```
5. **Delete the drill instance** when done — it bills like the
   primary.
6. Record the date and outcome of the drill in your ops log.

## Monitoring

Cloud Monitoring alert policies for the ingestion pipeline are encoded
in `infra/scripts/provision_monitoring.sh` (ENG-327) — run it once per
project to provision the email channel, per-job FAILED + NO-SUCCESS
alerts for `fusion-job-cs-pull` / `fusion-job-sf-pull` /
`fusion-job-salesforce-token-keepalive`, and the payment-freshness
log-based metric + threshold alert.

```bash
./infra/scripts/provision_monitoring.sh
```

Idempotent: describe-or-create on the notification channel and every
alert policy. Re-run safely. See `infra/CLAUDE.md` →
"Monitoring (provision_monitoring.sh)" for the policy list, SLO
windows, and the clinic-hours-aware payment-freshness alert details.

Cloud SQL infrastructure alerts (separate from the ingestion pipeline)
are still set up by hand in the Cloud Console (one-time, see ADR-0001
FUS-M1):

| Metric                                | Threshold       | Action |
|---------------------------------------|-----------------|--------|
| `cloudsql.googleapis.com/database/cpu/utilization`         | >80% / 5 min  | page  |
| `cloudsql.googleapis.com/database/disk/utilization`        | >85%          | page  |
| `cloudsql.googleapis.com/database/postgresql/num_backends` | >80% of max   | warn  |
| Backup not run in 36h                  | any           | page  |

Slow query log: `log_min_duration_statement=500ms` is set as a
database flag; queries land in Cloud Logging under the instance.

## Promotion to HA + CMEK (PHI go/no-go gate)

Before any PHI lands in `phi.*`:

```bash
# Promote to high availability (regional).
gcloud sql instances patch fusion-crm-pg \
  --availability-type=REGIONAL \
  --project=fusioncrm-494201

# Enable customer-managed encryption keys (requires Cloud KMS setup;
# this is a non-trivial change — see future ADR-NNNN before running).
```

These steps are **deferred** until we ship the PHI runtime gate.
Track in the FUS-X3 go/no-go checklist.

## Troubleshooting

- **`could not connect to server: Connection refused`** in the proxy
  log — check the SA has `roles/cloudsql.client` on the project.
- **`PERMISSION_DENIED` from Secret Manager** — runtime SA missing
  `roles/secretmanager.secretAccessor`, or the secret is in a
  different project than the SA.
- **`alembic` reports tables exist** when bootstrapping — likely the
  init-schemas.sql ran but a previous bootstrap aborted mid-way.
  Re-run; it's idempotent.
- **App boots but DB calls fail with auth error** — `DB_PASSWORD`
  was not exported before docker compose started. Use
  `start_prod.sh`, which handles this.
- **`/_internal/credentials/...` returns 503 `internal_resolver_not_configured`**
  — `INTERNAL_CREDENTIAL_TOKEN` is unset on the API side. Set both
  the API env and the Next.js env to the same value, then restart.
- **`/_internal/credentials/...` returns 401** — the Next.js side
  has a different token than the API. Sync them via Secret Manager.
- **Next.js logs `falling back to env` for SF / CareStack** — the
  resolver could not reach the API or the row is missing. Fine in
  the short term (env-fallback covers it) but the bootstrap or last
  rotation should be re-run so the DB row exists.

## Things this runbook does NOT cover

- HA + CMEK promotion runbook (the PHI gate, ENG-110) — separate
  doc once Phase 5 lands; this runbook only states **when** to flip.
- Per-schema DB roles (ENG-111) — separate doc; until then app
  services connect as the `fusion` superuser inside the database.
- Memorystore (managed Redis) migration (ENG-112) — separate ADR;
  Redis is still co-located with the worker for now.
- Adding a brand-new integration provider beyond the ENG-125 set —
  extend `PROVIDER_KINDS` + a new alembic migration to widen the
  CHECK, then mirror the Zod schema on the frontend.

## Restore drill log

Per `infra/CLAUDE.md`: record the date of every successful restore
drill here. If this list goes stale by more than ~6 weeks, treat the
backups as untested until proven otherwise.

| Date (UTC) | Drill type | Operator | Notes |
|------------|------------|----------|-------|
| _pending_  | initial    | -        | first drill due once `fusion-crm-pg` has non-trivial data |
