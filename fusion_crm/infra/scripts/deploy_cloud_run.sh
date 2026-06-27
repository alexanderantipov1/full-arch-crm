#!/usr/bin/env bash
# Deploy the two Fusion CRM Cloud Run services (api, web), plus the
# recurring Cloud Run Jobs (bounce poll, Salesforce token keepalive,
# Salesforce pull, CareStack pull, and the alembic upgrade one-shot)
# that replace the long-running arq worker.
# fusion-worker as a Cloud Run Service was decommissioned in ENG-172
# (Phase 1).
#
# Per ADR-0002 (docs/decisions/ADR-0002-cloud-run-prod-runtime.md),
# sections "Runtime", "Network", and "Secrets and config", and ENG-115
# (the issue tied to this script). Prereq: `provision_cloud_run_foundation.sh`
# (ENG-114) has been run — VPC, VPC connector, Cloud SQL Private IP,
# Artifact Registry, Cloud Build deployer SA, and WIF must already exist.
#
# Idempotent: every step uses `describe || create/deploy/update`, never
# interactive (`--quiet` everywhere). Re-runs converge to the desired
# state without errors.
#
# What this script does NOT do (intentional, future tickets):
#   * No GitHub Actions workflow — that's ENG-117.
#   * No Cloud IAP / Load Balancer — that's ENG-116.
#   * No service-account keys. Operator uses ADC; Cloud Run uses
#     attached SAs.
#   * No `--allow-unauthenticated`. IAP is wired by ENG-116.
#
# Usage:
#   ./infra/scripts/deploy_cloud_run.sh                 # full deploy
#   BUILD_ONLY=1 ./infra/scripts/deploy_cloud_run.sh    # build + push only
#   DEPLOY_ONLY=1 ./infra/scripts/deploy_cloud_run.sh   # skip rebuild, deploy latest
#   SERVICES="api web" ./infra/scripts/deploy_cloud_run.sh
#   IMAGE_TAG="$(git rev-parse --short HEAD)" ./infra/scripts/deploy_cloud_run.sh
#
# Operator one-shots (run once, manually, before the first deploy):
#   * Create the DSN secrets so Cloud Run can resolve them at runtime:
#       PRIV_IP=$(gcloud sql instances describe fusion-crm-pg \
#         --format='value(ipAddresses.filter("type:PRIVATE").extract(ipAddress))' \
#         | tr -d '[]')
#       PW=$(gcloud secrets versions access latest --secret=db-password)
#       printf 'postgresql+asyncpg://fusion:%s@%s:5432/fusion' "$PW" "$PRIV_IP" \
#         | gcloud secrets create db-url-asyncpg --data-file=- --replication-policy=automatic
#       printf 'postgresql+psycopg://fusion:%s@%s:5432/fusion'  "$PW" "$PRIV_IP" \
#         | gcloud secrets create db-url-psycopg  --data-file=- --replication-policy=automatic
#     The script auto-creates these on first run (see "DSN secrets" step).
#   * Grant `roles/secretmanager.secretAccessor` to fusion-api-sa and
#     fusion-worker-sa on every secret referenced below — the script
#     binds the new DSN secrets automatically, but pre-existing secrets
#     bound in provision_cloudsql.sh are out of scope here.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"

VPC_CONNECTOR="${VPC_CONNECTOR:-fusion-vpc-connector}"
ARTIFACT_REPO="${ARTIFACT_REPO:-fusion-containers}"
ARTIFACT_HOST="${REGION}-docker.pkg.dev"

CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-fusion-crm-pg}"
REDIS_URL="${REDIS_URL:-redis://10.0.0.5:6379/0}"   # placeholder; see note below

# Runtime SAs created by provision_cloudsql.sh.
API_SA="${API_SA:-fusion-api-sa}"
WORKER_SA="${WORKER_SA:-fusion-worker-sa}"

# Service names. fusion-worker was decommissioned in ENG-172 (Phase 1):
# arq has no HTTP surface and Cloud Run health checks always failed.
# One-shot Cloud Run Jobs (alembic, bounce-poll) cover the remaining
# scheduler workload and reuse the API image. The worker SA below
# (`fusion-worker-sa`) is kept as the Cloud Run Jobs runtime identity.
SVC_API="${SVC_API:-fusion-api}"
SVC_WEB="${SVC_WEB:-fusion-web}"

# Cloud Run Jobs.
JOB_ALEMBIC="${JOB_ALEMBIC:-fusion-job-alembic-upgrade}"
JOB_BOUNCE="${JOB_BOUNCE:-fusion-job-bounce-poll}"
JOB_SF_KEEPALIVE="${JOB_SF_KEEPALIVE:-fusion-job-salesforce-token-keepalive}"
JOB_SF_PULL="${JOB_SF_PULL:-fusion-job-sf-pull}"
JOB_CS_PULL="${JOB_CS_PULL:-fusion-job-cs-pull}"
# ENG-420 — weekly CareStack procedure-code (CDT) catalog sync into
# `catalog.procedure_code`. The catalog is small and static (ADA
# publishes annually); the weekly cadence is intentional.
JOB_CS_PROCEDURE_CODES="${JOB_CS_PROCEDURE_CODES:-fusion-job-cs-procedure-codes}"
# ENG-327 nightly reconciliation backfill. CI already retargets this
# job's image (`.github/workflows/deploy-prod.yml`); the script now owns
# the job definition + scheduler so the deploy contract is reproducible
# from the repo.
JOB_BACKFILL="${JOB_BACKFILL:-fusion-job-backfill}"
# ENG-493 — daily marketing/SEO pull (Google Ads, Meta Ads, GA4, Search
# Console). Production has no always-on arq worker, so the
# `pull_marketing_for_all_tenants` arq cron (04:43 local in dev/docker)
# never runs in prod — this Cloud Run Job + Scheduler entry is the prod
# runtime for it. Per-tenant credentials come from
# `tenant.integration_credential` (ENG-490), so NO marketing secrets are
# passed on the command line or via env.
JOB_MARKETING_PULL="${JOB_MARKETING_PULL:-fusion-job-marketing-pull}"
# ENG-493 — on-demand one-shot HISTORICAL marketing/SEO backfill
# (ENG-492). No scheduler entry; the operator runs it once after real
# credentials are entered via the ENG-491 Settings UI.
JOB_MARKETING_BACKFILL="${JOB_MARKETING_BACKFILL:-fusion-job-marketing-backfill}"
# ENG-510 — on-demand doctor-name backfill: pull the CareStack provider
# directory, then rename placeholder provider actors so consultation cards
# show real "Dr First Last". Both run the in-image infra/scripts/* directly.
JOB_PROVIDER_BACKFILL="${JOB_PROVIDER_BACKFILL:-fusion-job-provider-backfill}"
JOB_ACTOR_NAMES="${JOB_ACTOR_NAMES:-fusion-job-actor-names}"
# ENG-550 — on-demand identity dedup replay (ENG-541 epic). Re-evaluates the
# backlog of OPEN identity.match_candidate rows under the current (ENG-543)
# policy and dedup-merges the now-clear duplicates. Default DRY-RUN; the live
# pass is an explicit per-execution --args override (see the deploy summary).
JOB_IDENTITY_REPLAY="${JOB_IDENTITY_REPLAY:-fusion-job-identity-replay}"
# ENG-580 — on-demand attribution resolver. Attribution is NOT resolved at
# ingest time, so a fresh environment shows an empty attribution tree until this
# runs. Seeds the default chain nodes, then resolves every Salesforce-lead person
# under the current mapping rules. Idempotent (manual overrides preserved;
# per-batch commits). Baked args run the FIRST 200 leads; the full backfill is an
# explicit --args override (see the deploy summary). No scheduler today, so exempt
# from the SCHEDULE_INTEGRATION_PULL halt gate.
JOB_RESOLVE_ATTRIBUTION="${JOB_RESOLVE_ATTRIBUTION:-fusion-job-resolve-attribution}"
# ENG-498 — messenger runtime on prod (no always-on arq worker after
# ENG-172). These two run the notification crons as scheduled Cloud Run
# Jobs. They are NOT gated by SCHEDULE_INTEGRATION_PULL (that switch is the
# external-pull emergency stop); messenger delivery is gated by
# NOTIFICATIONS_ENABLED in JOB_ENV_VARS instead, so the jobs are cheap
# no-ops (one indexed SELECT) until ENG-500 flips notifications on.
JOB_NOTIFICATION_DRAIN="${JOB_NOTIFICATION_DRAIN:-fusion-job-notification-drain}"
JOB_CONSULT_REMINDERS="${JOB_CONSULT_REMINDERS:-fusion-job-consult-reminders}"
# ENG-555 — shared-contact-reuse alert scan (Layer D of ENG-552). Same messenger
# runtime as ENG-498: NOT gated by SCHEDULE_INTEGRATION_PULL; inert until the
# operator sets NOTIFICATIONS_ENABLED=true AND NOTIFICATIONS_CUTOFF_AT (the
# no-retro guard) and seeds the per-location leads channel.
JOB_SHARED_CONTACT_REUSE="${JOB_SHARED_CONTACT_REUSE:-fusion-job-shared-contact-reuse-scan}"

# Cloud Scheduler entries (one per recurring Job).
SCHED_BOUNCE="${SCHED_BOUNCE:-fusion-sched-bounce-poll}"
SCHED_SF_KEEPALIVE="${SCHED_SF_KEEPALIVE:-fusion-sched-salesforce-token-keepalive}"
SCHED_SF_PULL="${SCHED_SF_PULL:-fusion-sched-sf-pull}"
SCHED_CS_PULL="${SCHED_CS_PULL:-fusion-sched-cs-pull}"
SCHED_CS_PROCEDURE_CODES="${SCHED_CS_PROCEDURE_CODES:-fusion-sched-cs-procedure-codes}"
SCHED_NIGHTLY_BACKFILL="${SCHED_NIGHTLY_BACKFILL:-fusion-sched-nightly-backfill}"
# ENG-493 — daily marketing/SEO pull scheduler. (The historical backfill
# Job has NO scheduler — it is on-demand only.)
SCHED_MARKETING_PULL="${SCHED_MARKETING_PULL:-fusion-sched-marketing-pull}"
# ENG-498 — messenger crons, every minute (Cloud Scheduler's floor; the
# local arq cron runs every 10s but 1/min is the documented prod cadence).
SCHED_NOTIFICATION_DRAIN="${SCHED_NOTIFICATION_DRAIN:-fusion-sched-notification-drain}"
SCHED_CONSULT_REMINDERS="${SCHED_CONSULT_REMINDERS:-fusion-sched-consult-reminders}"
# ENG-555 — shared-contact-reuse scan, every 10m (not time-sensitive like the
# T-15m reminder; cheaper cadence). Inert until NOTIFICATIONS_ENABLED + cutoff.
SCHED_SHARED_CONTACT_REUSE="${SCHED_SHARED_CONTACT_REUSE:-fusion-sched-shared-contact-reuse-scan}"

# Image tag. Default to git short SHA when invoked inside a checkout;
# fall back to "latest" outside one (e.g. operator running ad-hoc).
if [[ -z "${IMAGE_TAG:-}" ]]; then
  if IMAGE_TAG="$(git rev-parse --short HEAD 2>/dev/null)"; then
    :
  else
    IMAGE_TAG="latest"
  fi
fi

IMAGE_API="${ARTIFACT_HOST}/${PROJECT_ID}/${ARTIFACT_REPO}/${SVC_API}:${IMAGE_TAG}"
IMAGE_WEB="${ARTIFACT_HOST}/${PROJECT_ID}/${ARTIFACT_REPO}/${SVC_WEB}:${IMAGE_TAG}"

# Service shapes. Conservative Phase 1 sizing per ADR-0002 §"Costs".
API_MIN="${API_MIN:-0}"
API_MAX="${API_MAX:-5}"
API_MEM="${API_MEM:-512Mi}"
API_CPU="${API_CPU:-1}"

WEB_MIN="${WEB_MIN:-0}"
WEB_MAX="${WEB_MAX:-5}"
WEB_MEM="${WEB_MEM:-512Mi}"
WEB_CPU="${WEB_CPU:-1}"

# Behaviour toggles.
BUILD_ONLY="${BUILD_ONLY:-0}"
DEPLOY_ONLY="${DEPLOY_ONLY:-0}"
# CI_MODE=1 → skip operator-only sections (DSN secret composition, Secret
# Manager IAM grants, Cloud Run Jobs / Scheduler reprovisioning). CI deploys
# revisions of existing services; the operator runs the script in full to
# bootstrap or re-bootstrap the deploy contract. Per `docs/DEPLOYMENT_RULES.md`
# §5 the workflow must use this script — the toggle keeps that path safe to
# run from a CI service account that lacks `secretmanager.admin`.
CI_MODE="${CI_MODE:-0}"
# Subset of services to deploy. fusion-worker dropped in ENG-172.
SERVICES_DEFAULT="api web"
SERVICES="${SERVICES:-$SERVICES_DEFAULT}"
# Salesforce/CareStack ingestion runs as scheduled Cloud Run Jobs by
# default. Operators can set SCHEDULE_INTEGRATION_PULL=0 to leave those
# Jobs/Scheduler entries untouched during emergency deploys.
SCHEDULE_INTEGRATION_PULL="${SCHEDULE_INTEGRATION_PULL:-1}"

# ---------------------------------------------------------------------------
# Helpers (mirror provision_cloud_run_foundation.sh)
# ---------------------------------------------------------------------------

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!! %s\033[0m\n" "$*" >&2; }
ok() { printf "   \033[0;32m✓ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31mxx %s\033[0m\n" "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

want_service() {
  local svc="$1"
  [[ " $SERVICES " == *" $svc "* ]]
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

require gcloud
require docker

log "Setting active project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null
ok "active project: $(gcloud config get-value project)"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" \
  --format='value(projectNumber)')"
[[ -n "$PROJECT_NUMBER" ]] || fail "Could not resolve project number for $PROJECT_ID"
ok "project number: $PROJECT_NUMBER"

API_EMAIL="${API_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_EMAIL="${WORKER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
VPC_CONNECTOR_PATH="projects/${PROJECT_ID}/locations/${REGION}/connectors/${VPC_CONNECTOR}"

if [[ "$CI_MODE" != "1" ]]; then
  # Foundation prereqs verification + API enable are operator-only:
  # the CI deployer SA (least-privilege per ADR-0002) intentionally lacks
  # `compute.networkViewer`, `iam.serviceAccountViewer`, and
  # `serviceusage.serviceUsageAdmin`. Operator runs the script in full to
  # validate foundation state; CI trusts it and goes straight to deploy.
  log "Verifying ENG-114 foundation"
  gcloud compute networks vpc-access connectors describe "$VPC_CONNECTOR" \
    --region="$REGION" >/dev/null 2>&1 \
    || fail "VPC connector $VPC_CONNECTOR not found — run provision_cloud_run_foundation.sh first"
  ok "VPC connector: $VPC_CONNECTOR"

  gcloud artifacts repositories describe "$ARTIFACT_REPO" \
    --location="$REGION" >/dev/null 2>&1 \
    || fail "Artifact Registry repo $ARTIFACT_REPO not found — run provision_cloud_run_foundation.sh first"
  ok "Artifact Registry: ${ARTIFACT_HOST}/${PROJECT_ID}/${ARTIFACT_REPO}"

  gcloud iam service-accounts describe "$API_EMAIL" >/dev/null 2>&1 \
    || fail "API SA $API_EMAIL not found — run provision_cloudsql.sh first"
  gcloud iam service-accounts describe "$WORKER_EMAIL" >/dev/null 2>&1 \
    || fail "Worker SA $WORKER_EMAIL not found — run provision_cloudsql.sh first"
  ok "Runtime SAs present"

  # Enable any APIs not enabled by the foundation script.
  log "Enabling deploy-time APIs"
  gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    --quiet
  ok "APIs enabled"
else
  ok "CI_MODE=1 → skipping operator foundation preflight (VPC/AR/SA describe, services enable)"
fi

# ---------------------------------------------------------------------------
# DSN secrets (one-shot, idempotent)
# ---------------------------------------------------------------------------
#
# Per ADR-0002 §"Secrets and config": app services receive DATABASE_URL
# and DATABASE_URL_SYNC by Secret Manager reference, not by env
# interpolation. We compute the secret VALUES here (private IP + db
# password) and create the secret containers if missing. The runtime SA
# bindings are also applied so Cloud Run can resolve the values.

ensure_secret_value() {
  # ensure_secret_value <secret-name> <plaintext-value>
  local name="$1"
  local value="$2"
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    ok "secret exists: $name"
  else
    gcloud secrets create "$name" \
      --replication-policy=automatic \
      --quiet >/dev/null
    ok "secret created: $name"
  fi

  # Always add a new version when the value differs from `latest`.
  local current=""
  current="$(gcloud secrets versions access latest --secret="$name" 2>/dev/null || true)"
  if [[ "$current" == "$value" ]]; then
    ok "secret $name already at desired value"
  else
    printf '%s' "$value" \
      | gcloud secrets versions add "$name" --data-file=- --quiet >/dev/null
    ok "secret $name: new version added"
  fi
}

grant_secret_accessor() {
  # grant_secret_accessor <secret-name> <sa-email>
  local name="$1"
  local sa="$2"
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${sa}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None \
    --quiet >/dev/null
  ok "  $sa → secretAccessor on $name"
}

grant_service_invoker() {
  # grant_service_invoker <service-name> <sa-email>
  local service="$1"
  local sa="$2"
  gcloud run services add-iam-policy-binding "$service" \
    --region="$REGION" \
    --member="serviceAccount:${sa}" \
    --role="roles/run.invoker" \
    --quiet >/dev/null
  ok "  $sa → roles/run.invoker on $service"
}

resolve_private_ip() {
  local ip=""
  ip="$(gcloud sql instances describe "$CLOUDSQL_INSTANCE" \
        --format='value(ipAddresses.filter("type:PRIVATE").extract(ipAddress))' \
        2>/dev/null | tr -d "[]'\"" | head -n1 || true)"
  if [[ -z "$ip" ]]; then
    # Older gcloud format fallback.
    ip="$(gcloud sql instances describe "$CLOUDSQL_INSTANCE" --format=json \
          | python3 -c 'import json,sys
d=json.load(sys.stdin)
for a in d.get("ipAddresses", []):
    if a.get("type")=="PRIVATE":
        print(a.get("ipAddress",""))
        break' 2>/dev/null || true)"
  fi
  printf '%s' "$ip"
}

if [[ "$CI_MODE" != "1" ]]; then
  log "Resolving Cloud SQL Private IP for $CLOUDSQL_INSTANCE"
  CLOUDSQL_PRIVATE_IP="$(resolve_private_ip)"
  [[ -n "$CLOUDSQL_PRIVATE_IP" ]] \
    || fail "Cloud SQL Private IP not assigned yet — re-run after the instance settles"
  ok "Cloud SQL private IP: $CLOUDSQL_PRIVATE_IP"

  log "Composing DSN secrets (db-url-asyncpg + db-url-psycopg)"
  DB_PASSWORD_VALUE="$(gcloud secrets versions access latest --secret=db-password 2>/dev/null || true)"
  [[ -n "$DB_PASSWORD_VALUE" ]] \
    || fail "db-password secret has no version — populate it before re-running"

  DSN_ASYNCPG="postgresql+asyncpg://fusion:${DB_PASSWORD_VALUE}@${CLOUDSQL_PRIVATE_IP}:5432/fusion"
  DSN_PSYCOPG="postgresql+psycopg://fusion:${DB_PASSWORD_VALUE}@${CLOUDSQL_PRIVATE_IP}:5432/fusion"

  ensure_secret_value "db-url-asyncpg" "$DSN_ASYNCPG"
  ensure_secret_value "db-url-psycopg" "$DSN_PSYCOPG"
  # Clear the value from the shell environment as soon as the secret is set.
  DB_PASSWORD_VALUE=""
  DSN_ASYNCPG=""
  DSN_PSYCOPG=""

  log "Granting runtime SAs read access to required secrets"
  SECRETS_API=(app-secret-key db-password encryption-key internal-credential-token db-url-asyncpg db-url-psycopg)
  SECRETS_WORKER=(app-secret-key db-password encryption-key internal-credential-token db-url-asyncpg db-url-psycopg)
  for s in "${SECRETS_API[@]}"; do
    grant_secret_accessor "$s" "$API_EMAIL"
  done
  for s in "${SECRETS_WORKER[@]}"; do
    grant_secret_accessor "$s" "$WORKER_EMAIL"
  done

  log "Granting service-to-service Cloud Run invoke permissions"
  grant_service_invoker "$SVC_API" "$API_EMAIL"
else
  ok "CI_MODE=1 → skipping DSN secret composition + secret IAM grants (operator-only)"
fi

# ---------------------------------------------------------------------------
# Build + push images
# ---------------------------------------------------------------------------

build_and_push() {
  # build_and_push <service-name> <dockerfile-path> <image-uri> [context-dir]
  local service="$1"
  local dockerfile="$2"
  local image="$3"
  local context="${4:-.}"

  log "Building image for $service → $image"
  # Default context is repo root so api/worker Dockerfiles can COPY
  # pyproject.toml / packages / apps. The web Dockerfile is built from
  # apps/web (self-contained Next.js) — caller passes the context.
  # Tag both the immutable tag and `:latest` so manual rollouts off
  # Artifact Registry can pin either.
  # --platform=linux/amd64 is mandatory: Cloud Run runs amd64 only, and
  # operators may build on arm64 (Apple Silicon). Without this flag an
  # arm64 image lands in AR and the deploy fails with "exec format error".
  local -a build_args=()
  if [[ "$service" == "$SVC_WEB" ]]; then
    local api_internal_url
    api_internal_url="$(gcloud run services describe "$SVC_API" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --format='value(status.url)' 2>/dev/null || true)"
    api_internal_url="${api_internal_url:-https://${SVC_API}-${PROJECT_NUMBER}.${REGION}.run.app}"
    build_args+=(
      --build-arg "COMMIT_SHA=${APP_COMMIT_SHA:-$IMAGE_TAG}"
      --build-arg "INTERNAL_API_URL=${api_internal_url}"
      --build-arg "NEXT_PUBLIC_API_BASE_URL=https://fusioncrm.app"
    )
  fi

  docker build \
    --platform=linux/amd64 \
    ${build_args[@]+"${build_args[@]}"} \
    --file "$dockerfile" \
    --tag "$image" \
    --tag "${image%:*}:latest" \
    "$context"
  ok "built $service"

  log "Pushing $image"
  docker push "$image"
  docker push "${image%:*}:latest"
  ok "pushed $service"
}

if [[ "$DEPLOY_ONLY" != "1" ]]; then
  log "Authenticating docker against $ARTIFACT_HOST"
  gcloud auth configure-docker "$ARTIFACT_HOST" --quiet
  ok "docker auth configured"

  want_service api && build_and_push "$SVC_API" "apps/api/Dockerfile" "$IMAGE_API"
  want_service web && build_and_push "$SVC_WEB" "apps/web/Dockerfile" "$IMAGE_WEB" "apps/web"
fi

if [[ "$BUILD_ONLY" == "1" ]]; then
  ok "BUILD_ONLY=1 → skipping deploy"
  exit 0
fi

# ---------------------------------------------------------------------------
# Cloud Run service deploys
# ---------------------------------------------------------------------------
#
# Shared invariants per ADR-0002:
#   * --no-allow-unauthenticated      → IAP gates ingress in ENG-116.
#   * --vpc-egress=private-ranges-only → outbound to Cloud SQL Private IP
#     and other RFC-1918 ranges only; public egress goes through the
#     Cloud Run default network (per ADR-0002 §"Network").
#   * --service-account                → attached SA, no key files.
#   * Secrets are passed via --set-secrets; DSN is one of those secrets,
#     so no plaintext password ever appears on the command line.

API_ENV_VARS="APP_ENV=production,LOG_LEVEL=INFO,API_HOST=0.0.0.0,REDIS_URL=${REDIS_URL},OAUTH_REDIRECT_BASE_URL=https://fusioncrm.app,WEB_APP_BASE_URL=https://fusioncrm.app,SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback,TRACKING_BASE_URL=https://fusioncrm.app,API_CORS_ORIGINS=https://fusioncrm.app,WEB_CORS_ORIGINS=https://fusioncrm.app,NOTIFICATIONS_ENABLED=false,MESSENGER_PHI_FULL=true"
API_SECRETS="SECRET_KEY=app-secret-key:latest,DB_PASSWORD=db-password:latest,ENCRYPTION_KEY=encryption-key:latest,INTERNAL_CREDENTIAL_TOKEN=internal-credential-token:latest,DATABASE_URL=db-url-asyncpg:latest,DATABASE_URL_SYNC=db-url-psycopg:latest"

# Cloud Run Jobs runtime contract. Jobs run one-shot entrypoints
# (alembic, bounce-poll, Salesforce token keepalive), not the arq pop
# loop. They still receive REDIS_URL because the shared Settings object
# validates it at import time before the job code can run.
# The scheduled SF/CS pull Jobs are the runtime that EMITS notifications
# (ENG-454), so they carry the same notify contract as the API. Lands dark
# (NOTIFICATIONS_ENABLED=false); WEB_APP_BASE_URL feeds the card deep links.
JOB_ENV_VARS="APP_ENV=production,LOG_LEVEL=INFO,REDIS_URL=${REDIS_URL},WEB_APP_BASE_URL=https://fusioncrm.app,NOTIFICATIONS_ENABLED=false,MESSENGER_PHI_FULL=true"
JOB_SECRETS="SECRET_KEY=app-secret-key:latest,DB_PASSWORD=db-password:latest,ENCRYPTION_KEY=encryption-key:latest,INTERNAL_CREDENTIAL_TOKEN=internal-credential-token:latest,DATABASE_URL=db-url-asyncpg:latest,DATABASE_URL_SYNC=db-url-psycopg:latest"

deploy_api() {
  log "Deploying Cloud Run service $SVC_API"
  # NO_TRAFFIC=1 → deploy a revision without serving traffic. CI uses this
  # so the workflow can run smoke checks before promotion (ENG-117/151).
  local -a traffic_args=()
  if [[ "${NO_TRAFFIC:-0}" == "1" ]]; then
    traffic_args+=(--no-traffic)
  fi
  # APP_COMMIT_SHA powers the VersionWatcher cache-busting hint (ENG-150).
  # When set, append it to the env-var list rather than baking into
  # API_ENV_VARS at the top of the file.
  local env_vars="$API_ENV_VARS"
  if [[ -n "${APP_COMMIT_SHA:-}" ]]; then
    env_vars+=",APP_COMMIT_SHA=${APP_COMMIT_SHA}"
  fi
  gcloud run deploy "$SVC_API" \
    --image="$IMAGE_API" \
    --region="$REGION" \
    --platform=managed \
    --service-account="$API_EMAIL" \
    --vpc-connector="$VPC_CONNECTOR_PATH" \
    --vpc-egress=private-ranges-only \
    --ingress=all \
    --no-allow-unauthenticated \
    --min-instances="$API_MIN" \
    --max-instances="$API_MAX" \
    --memory="$API_MEM" \
    --cpu="$API_CPU" \
    --port=8080 \
    --timeout=60s \
    --set-env-vars="$env_vars" \
    --set-secrets="$API_SECRETS" \
    ${traffic_args[@]+"${traffic_args[@]}"} \
    --quiet
  local url rev
  url="$(gcloud run services describe "$SVC_API" --region="$REGION" --format='value(status.url)')"
  rev="$(gcloud run services describe "$SVC_API" --region="$REGION" --format='value(status.latestCreatedRevisionName)')"
  ok "$SVC_API revision $rev: $url"
  API_URL="$url"
  API_REVISION="$rev"
}

deploy_web() {
  log "Deploying Cloud Run service $SVC_WEB"
  # The web service talks to the API via the API's URL. Cloud Run
  # service-to-service traffic stays on the Google fabric (no public
  # internet hop), even though --ingress=all on the API allows external
  # callers. ENG-116 will swap external for IAP-protected ingress.
  local api_internal_url="${API_URL:-}"
  if [[ -z "$api_internal_url" ]]; then
    api_internal_url="$(gcloud run services describe "$SVC_API" \
      --region="$REGION" \
      --project="$PROJECT_ID" \
      --format='value(status.url)' 2>/dev/null || true)"
  fi
  api_internal_url="${api_internal_url:-https://${SVC_API}-${PROJECT_NUMBER}.${REGION}.run.app}"
  local web_env_vars
  web_env_vars="APP_ENV=production,NEXT_TELEMETRY_DISABLED=1,NEXT_PUBLIC_API_BASE_URL=https://fusioncrm.app,NEXT_PUBLIC_ENVIRONMENT=production,NEXT_PUBLIC_API_MOCKING=disabled,INTERNAL_API_URL=${api_internal_url},INTERNAL_API_BASE_URL=${api_internal_url}"
  if [[ -n "${APP_COMMIT_SHA:-}" ]]; then
    web_env_vars+=",APP_COMMIT_SHA=${APP_COMMIT_SHA}"
  fi
  local web_secrets
  web_secrets="INTERNAL_CREDENTIAL_TOKEN=internal-credential-token:latest"
  local -a traffic_args=()
  if [[ "${NO_TRAFFIC:-0}" == "1" ]]; then
    traffic_args+=(--no-traffic)
  fi

  gcloud run deploy "$SVC_WEB" \
    --image="$IMAGE_WEB" \
    --region="$REGION" \
    --platform=managed \
    --service-account="$API_EMAIL" \
    --vpc-connector="$VPC_CONNECTOR_PATH" \
    --vpc-egress=private-ranges-only \
    --ingress=all \
    --no-allow-unauthenticated \
    --min-instances="$WEB_MIN" \
    --max-instances="$WEB_MAX" \
    --memory="$WEB_MEM" \
    --cpu="$WEB_CPU" \
    --port=8080 \
    --timeout=60s \
    --set-env-vars="$web_env_vars" \
    --set-secrets="$web_secrets" \
    ${traffic_args[@]+"${traffic_args[@]}"} \
    --quiet
  local url rev
  url="$(gcloud run services describe "$SVC_WEB" --region="$REGION" --format='value(status.url)')"
  rev="$(gcloud run services describe "$SVC_WEB" --region="$REGION" --format='value(status.latestCreatedRevisionName)')"
  ok "$SVC_WEB revision $rev: $url"
  WEB_URL="$url"
  WEB_REVISION="$rev"
}

want_service api && deploy_api
want_service web && deploy_web

# ---------------------------------------------------------------------------
# Cloud Run Jobs (one-shot + scheduled)
# ---------------------------------------------------------------------------
#
# Cloud Run Jobs reuse the API image (the worker image was retired with
# the Cloud Run Service in ENG-172; the API image already includes
# `apps/worker/jobs/*` because the runtime Dockerfile COPYs `apps/`
# wholesale, see apps/api/Dockerfile lines 82-83).
# Each Job overrides --command / --args to run a specific Python entry
# point instead of any long-running loop.
#
# `gcloud run jobs deploy` is idempotent (create-or-update). We use it
# uniformly.

deploy_job() {
  # deploy_job <name> <image> <sa-email> <command-json> <args-json>
  local name="$1"
  local image="$2"
  local sa="$3"
  local command_csv="$4"
  local args_csv="$5"

  log "Deploying Cloud Run Job $name"
  local -a extra=()
  if [[ -n "$command_csv" ]]; then
    extra+=(--command="$command_csv")
  fi
  if [[ -n "$args_csv" ]]; then
    extra+=(--args="$args_csv")
  fi
  gcloud run jobs deploy "$name" \
    --image="$image" \
    --region="$REGION" \
    --service-account="$sa" \
    --vpc-connector="$VPC_CONNECTOR_PATH" \
    --vpc-egress=private-ranges-only \
    --max-retries=1 \
    --task-timeout=1800s \
    --memory=1Gi \
    --cpu=1 \
    --set-env-vars="$JOB_ENV_VARS" \
    --set-secrets="$JOB_SECRETS" \
    ${extra[@]+"${extra[@]}"} \
    --quiet
  ok "Job $name deployed"
}

if [[ "$CI_MODE" == "1" ]]; then
  ok "CI_MODE=1 → skipping Cloud Run Jobs + Scheduler reprovisioning"
  ok "  Operator runs full script (without CI_MODE) to push job command/env changes"
else

# 1. Alembic upgrade — one-shot, no schedule. CI/CD invokes it via
#    `gcloud run jobs execute fusion-job-alembic-upgrade --wait` between
#    image push and service deploy.
#    The `sh -c "cd packages/db && ..."` wrapper is required because
#    `alembic.ini` (`script_location = alembic`, `prepend_sys_path = ../..`)
#    only resolves correctly when the working directory is `packages/db/`,
#    while the image WORKDIR is `/app`.
deploy_job "$JOB_ALEMBIC" "$IMAGE_API" "$WORKER_EMAIL" \
  "sh" "-c,cd packages/db && python -m alembic upgrade head"

# 2. Bounce poll — recurring. The worker module already exposes
#    `apps.worker.jobs.bounce_poll.poll_bounces` and is wired into the
#    arq cron in apps/worker/main.py. For Cloud Run Jobs we invoke a
#    thin one-shot entrypoint via `python -c` so the job runs the poll
#    once per scheduler tick and exits cleanly.
deploy_job "$JOB_BOUNCE" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-c,import asyncio; from apps.worker.jobs.bounce_poll import poll_bounces; asyncio.run(poll_bounces({}))"

# 2b. Marketing/SEO historical backfill — one-shot, NO schedule (ENG-493 /
#     ENG-492). Deployed unconditionally (like the alembic job) so its
#     definition is always present for on-demand operator runs; with no
#     Cloud Scheduler entry it never ticks on its own, so it is exempt from
#     the SCHEDULE_INTEGRATION_PULL halt gate (there is nothing recurring to
#     halt). `apps.worker.jobs.marketing_backfill` has a `__main__` argparse
#     entrypoint, so `python -m` runs it directly. Default window is ~365
#     days; the operator overrides per run, e.g.:
#       gcloud run jobs execute fusion-job-marketing-backfill --region=$REGION \
#         --args=--months,12 --wait
#     Per-tenant credentials come from tenant.integration_credential
#     (ENG-490); legs without a credential short-circuit to skipped, so a
#     run before real creds are entered is a safe no-op.
deploy_job "$JOB_MARKETING_BACKFILL" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.marketing_backfill"

# ENG-510 — on-demand doctor-name backfill (two ordered one-shots). No
# scheduler, so exempt from the SCHEDULE_INTEGRATION_PULL halt gate (nothing
# recurring to halt). The operator runs them in order after a deploy:
#   1) provider-backfill pulls the CareStack provider directory (defaults to
#      the single tenant; reads tenant.integration_credential, throttled);
#   2) actor-names renames placeholder provider/SF actors from data already in
#      the DB (idempotent, no external calls).
#     gcloud run jobs execute fusion-job-provider-backfill --region=$REGION --wait
#     gcloud run jobs execute fusion-job-actor-names      --region=$REGION --wait
# The scripts live in the image at infra/scripts/* (Dockerfile COPYs infra/).
deploy_job "$JOB_PROVIDER_BACKFILL" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "infra/scripts/backfill_providers.py"
deploy_job "$JOB_ACTOR_NAMES" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "infra/scripts/backfill_actor_names.py,--apply"

# ENG-550 — on-demand identity dedup replay (ENG-541 epic; the prod live pass of
# ENG-544). No scheduler, so exempt from the SCHEDULE_INTEGRATION_PULL halt gate
# (nothing recurring to halt). Baked args run the module in its DEFAULT dry-run
# mode (the module defaults dry_run=True), so a bare execute is a safe,
# read-only count:
#     gcloud run jobs execute fusion-job-identity-replay --region=$REGION --wait
# The LIVE pass (mutating ~315 dedup merges) is an explicit per-execution args
# override. `gcloud run jobs execute --args` REPLACES the container args (the
# --command stays `python`), so the full module path must be repeated alongside
# --live:
#     gcloud run jobs execute fusion-job-identity-replay --region=$REGION \
#       --args=-m,apps.worker.jobs.replay_identity_matches,--live --wait
# Every merge is append-only (identity.merge_event) and reversible; re-running is
# safe because decided candidates leave the status='open' work-list.
deploy_job "$JOB_IDENTITY_REPLAY" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.replay_identity_matches"

# ENG-580 — on-demand attribution resolver. Attribution is not resolved at
# ingest time, so a fresh prod shows an empty attribution tree until this runs.
# No scheduler, so exempt from the SCHEDULE_INTEGRATION_PULL halt gate. Baked
# args run the FIRST 200 leads, so a bare execute is a cheap smoke:
#     gcloud run jobs execute fusion-job-resolve-attribution --region=$REGION --wait
# The FULL backfill is an explicit per-execution args override. `--args` REPLACES
# the container args (the --command stays `python`), so repeat the module path:
#     gcloud run jobs execute fusion-job-resolve-attribution --region=$REGION \
#       --args=-m,apps.worker.jobs.resolve_attribution,--all --wait
# Idempotent: manual overrides (method=manual) are preserved and per-batch commits
# mean a timed-out run resumes coverage on the next execution.
deploy_job "$JOB_RESOLVE_ATTRIBUTION" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.resolve_attribution"

# 3. Salesforce token keepalive — recurring. This keeps active OAuth
#    credentials warm by using the stored refresh_token. The job is
#    safe before Salesforce is connected: tenants without an active
#    oauth_token are skipped.
deploy_job "$JOB_SF_KEEPALIVE" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-c,import asyncio; from apps.worker.jobs.salesforce_token_keepalive import refresh_salesforce_tokens; asyncio.run(refresh_salesforce_tokens({}))"

# 3b. ENG-498 messenger runtime — recurring, NOT gated by
#     SCHEDULE_INTEGRATION_PULL (that is the external-pull stop). Delivery
#     is gated by NOTIFICATIONS_ENABLED in JOB_ENV_VARS, so these are cheap
#     no-ops until ENG-500 flips the flag.
#     - notification-drain: one drain pass over integrations.notification_outbox.
#       Idempotent (FOR UPDATE SKIP LOCKED + status=="locked" guard).
#     - consult-reminders: T-15m reminder scan per tenant. At-most-once via
#       the durable dedupe ledger (key = consultation id).
deploy_job "$JOB_NOTIFICATION_DRAIN" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.notification_drain"
deploy_job "$JOB_CONSULT_REMINDERS" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.consult_reminder_scan"
# ENG-555 (Layer D) — scan new OPEN shared-contact-reuse match_candidates and emit
# a per-location leads-channel alert. Inert until NOTIFICATIONS_ENABLED + a
# NOTIFICATIONS_CUTOFF_AT (no-retro guard); dedup via the notification_emitted
# ledger (key = candidate id).
deploy_job "$JOB_SHARED_CONTACT_REUSE" "$IMAGE_API" "$WORKER_EMAIL" \
  "python" "-m,apps.worker.jobs.shared_contact_reuse_scan"

# 4. Salesforce + CareStack pull + nightly reconciliation backfill —
#    recurring CareStack/Salesforce readers gated by SCHEDULE_INTEGRATION_PULL.
#    The nightly backfill (fusion-job-backfill, ENG-327) is also a CareStack
#    reader — it pulls cs_patients, cs_appointments, cs_accounting_transactions
#    — so it shares the same emergency-stop switch as cs-pull / sf-pull. An
#    operator setting SCHEDULE_INTEGRATION_PULL=0 must be able to halt all
#    external-pull activity during an incident without leaving the nightly
#    reconciliation job ticking.
#
#    Backfill args are baked into the job's container spec (not passed by
#    the scheduler) because `upsert_scheduler` POSTs an empty body to the
#    Run `:run` endpoint. Baking the default args avoids introducing a
#    second scheduler variant just to carry overrides; ad-hoc operator
#    runs that need different entities go through
#    `gcloud run jobs execute fusion-job-backfill --args=... --update-env-vars=...`.
#    The Python entrypoint already supports the --entities flag
#    (apps/worker/jobs/backfill_full.py:84 / :402) and the path is
#    idempotent: raw capture dedupes on (id, lastUpdatedOn),
#    `create_event_idempotent` swallows the cross-pull UNIQUE conflict,
#    and per-page commits land from ENG-326.
if [[ "$SCHEDULE_INTEGRATION_PULL" == "1" ]]; then
  deploy_job "$JOB_SF_PULL" "$IMAGE_API" "$WORKER_EMAIL" \
    "python" "-m,apps.worker.jobs.salesforce_pull"
  deploy_job "$JOB_CS_PULL" "$IMAGE_API" "$WORKER_EMAIL" \
    "python" "-m,apps.worker.jobs.carestack_pull"
  deploy_job "$JOB_BACKFILL" "$IMAGE_API" "$WORKER_EMAIL" \
    "python" "-m,apps.worker.jobs.backfill_full,--entities,cs_patients,cs_appointments,cs_treatments,cs_accounting_transactions,merge_split_persons"
  # ENG-420 — weekly CareStack procedure-code catalog sync.
  # Shares the SCHEDULE_INTEGRATION_PULL gate so an emergency stop of
  # CareStack reads also pauses this job.
  deploy_job "$JOB_CS_PROCEDURE_CODES" "$IMAGE_API" "$WORKER_EMAIL" \
    "python" "-m,apps.worker.jobs.carestack_procedure_codes_pull"
  # ENG-493 — daily marketing/SEO pull. This IS an external integration
  # reader (Google Ads / Meta Ads / GA4 / Search Console), so it shares the
  # SCHEDULE_INTEGRATION_PULL halt gate with sf-pull / cs-pull / backfill:
  # an operator setting SCHEDULE_INTEGRATION_PULL=0 during an incident
  # pauses ALL external-pull activity, marketing included.
  # `pull_marketing_for_all_tenants` is an arq cron entry (takes a ctx and
  # has no `__main__`), so we invoke it one-shot via `python -c`, mirroring
  # the bounce-poll job. Per-tenant credentials come from
  # tenant.integration_credential (ENG-490); legs without a credential
  # short-circuit to skipped, so no marketing secret touches env/CLI.
  deploy_job "$JOB_MARKETING_PULL" "$IMAGE_API" "$WORKER_EMAIL" \
    "python" "-c,import asyncio; from apps.worker.jobs.marketing_pull import pull_marketing_for_all_tenants; asyncio.run(pull_marketing_for_all_tenants({}))"
else
  warn "Skipping fusion-job-sf-pull / fusion-job-cs-pull / fusion-job-backfill / fusion-job-cs-procedure-codes / fusion-job-marketing-pull"
  warn "  SCHEDULE_INTEGRATION_PULL=0"
fi

# ---------------------------------------------------------------------------
# Cloud Scheduler entries (HTTP triggers against the Cloud Run Jobs API)
# ---------------------------------------------------------------------------
#
# Cloud Scheduler authenticates as a service account that has
# `roles/run.invoker` on the target Job. We reuse the worker SA for
# trigger calls — Cloud Run Jobs are invoked with OAuth ID tokens
# scoped to the run.googleapis.com audience.

upsert_scheduler() {
  # upsert_scheduler <name> <cron> <job-name> <description>
  local name="$1"
  local schedule="$2"
  local job_name="$3"
  local desc="$4"
  local uri
  uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${job_name}:run"

  if gcloud scheduler jobs describe "$name" --location="$REGION" >/dev/null 2>&1; then
    log "Updating scheduler entry $name ($schedule)"
    gcloud scheduler jobs update http "$name" \
      --location="$REGION" \
      --schedule="$schedule" \
      --uri="$uri" \
      --http-method=POST \
      --oauth-service-account-email="$WORKER_EMAIL" \
      --description="$desc" \
      --quiet
  else
    log "Creating scheduler entry $name ($schedule)"
    gcloud scheduler jobs create http "$name" \
      --location="$REGION" \
      --schedule="$schedule" \
      --uri="$uri" \
      --http-method=POST \
      --oauth-service-account-email="$WORKER_EMAIL" \
      --description="$desc" \
      --quiet
  fi
  ok "scheduler $name: $schedule → $job_name"
}

grant_job_invoker() {
  # grant_job_invoker <job-name> <sa-email>
  local job_name="$1"
  local sa="$2"
  gcloud run jobs add-iam-policy-binding "$job_name" \
    --region="$REGION" \
    --member="serviceAccount:${sa}" \
    --role="roles/run.invoker" \
    --quiet >/dev/null
  ok "  ${sa} → roles/run.invoker on $job_name"
}

log "Granting Cloud Scheduler invoker permissions"
grant_job_invoker "$JOB_BOUNCE"  "$WORKER_EMAIL"
grant_job_invoker "$JOB_SF_KEEPALIVE" "$WORKER_EMAIL"
grant_job_invoker "$JOB_NOTIFICATION_DRAIN" "$WORKER_EMAIL"
grant_job_invoker "$JOB_CONSULT_REMINDERS" "$WORKER_EMAIL"
grant_job_invoker "$JOB_SHARED_CONTACT_REUSE" "$WORKER_EMAIL"
if [[ "$SCHEDULE_INTEGRATION_PULL" == "1" ]]; then
  grant_job_invoker "$JOB_SF_PULL" "$WORKER_EMAIL"
  grant_job_invoker "$JOB_CS_PULL" "$WORKER_EMAIL"
  grant_job_invoker "$JOB_BACKFILL" "$WORKER_EMAIL"
  grant_job_invoker "$JOB_CS_PROCEDURE_CODES" "$WORKER_EMAIL"
  # ENG-493 — Cloud Scheduler invokes the daily marketing/SEO pull as the
  # worker SA. The historical-backfill job (JOB_MARKETING_BACKFILL) has no
  # scheduler, so it needs no run.invoker grant — the operator executes it
  # directly with their own ADC credentials.
  grant_job_invoker "$JOB_MARKETING_PULL" "$WORKER_EMAIL"
fi

upsert_scheduler "$SCHED_BOUNCE" "*/15 * * * *" "$JOB_BOUNCE" \
  "Poll connected mailboxes for bounce NDRs every 15m (ENG-134)"
upsert_scheduler "$SCHED_SF_KEEPALIVE" "7 */6 * * *" "$JOB_SF_KEEPALIVE" \
  "Refresh active Salesforce OAuth access tokens every 6h (ENG-234)"
# ENG-498 — messenger crons every minute (Cloud Scheduler floor). Inert
# while NOTIFICATIONS_ENABLED=false; ENG-500 flips the flag to go live.
upsert_scheduler "$SCHED_NOTIFICATION_DRAIN" "* * * * *" "$JOB_NOTIFICATION_DRAIN" \
  "Drain integrations.notification_outbox → chat provider every 1m (ENG-498)"
upsert_scheduler "$SCHED_CONSULT_REMINDERS" "* * * * *" "$JOB_CONSULT_REMINDERS" \
  "Scan CONFIRMED consultations for T-15m reminders every 1m (ENG-498/486)"
upsert_scheduler "$SCHED_SHARED_CONTACT_REUSE" "*/10 * * * *" "$JOB_SHARED_CONTACT_REUSE" \
  "Scan new shared-contact-reuse match candidates → per-location leads alert every 10m (ENG-555); inert until NOTIFICATIONS_ENABLED + NOTIFICATIONS_CUTOFF_AT"

if [[ "$SCHEDULE_INTEGRATION_PULL" == "1" ]]; then
  upsert_scheduler "$SCHED_SF_PULL" "*/15 * * * *" "$JOB_SF_PULL" \
    "Pull recent Salesforce leads every 15m"
  upsert_scheduler "$SCHED_CS_PULL" "*/30 * * * *" "$JOB_CS_PULL" \
    "Pull recent CareStack patients + appointments every 30m"
  # Nightly reconciliation backfill (ENG-327). Cron `17 10 * * *` is
  # evaluated as 10:17 UTC by default (Cloud Scheduler uses UTC unless an
  # explicit time zone is configured on the job), which lands in the
  # middle of the night in America/Los_Angeles year-round (03:17 PDT in
  # summer, 02:17 PST in winter). The minute is off-the-quarter to dodge
  # collisions with the */15 and */30 pull schedulers above.
  upsert_scheduler "$SCHED_NIGHTLY_BACKFILL" "17 10 * * *" "$JOB_BACKFILL" \
    "Nightly reconciliation backfill: cs_patients + cs_appointments + cs_accounting_transactions (ENG-327)"
  # ENG-420 — weekly CareStack procedure-code catalog refresh. Cron
  # `23 11 * * 1` is Monday 11:23 UTC (03:23 PST / 04:23 PDT — nighttime
  # in America/Los_Angeles year-round). The minute is off-the-quarter to
  # dodge collisions with the */15 and */30 pull schedulers above. CDT
  # publishes annually; weekly is generous.
  upsert_scheduler "$SCHED_CS_PROCEDURE_CODES" "23 11 * * 1" "$JOB_CS_PROCEDURE_CODES" \
    "Weekly CareStack procedure-code (CDT) catalog refresh into catalog.procedure_code (ENG-420)"
  # ENG-493 — daily marketing/SEO pull. Ad/analytics data has ~1-day
  # latency so a daily cadence is enough; the job re-reads a rolling
  # 7-day window and dedupes on captured-payload identity. Cron
  # `43 11 * * *` is 11:43 UTC, which lands at night in
  # America/Los_Angeles year-round (03:43 PST winter / 04:43 PDT summer —
  # the same :43 minute the dev/docker arq cron uses). The off-the-quarter
  # minute dodges collisions with the */15 and */30 pull schedulers above.
  upsert_scheduler "$SCHED_MARKETING_PULL" "43 11 * * *" "$JOB_MARKETING_PULL" \
    "Daily marketing/SEO pull: Google Ads + Meta Ads + GA4 + Search Console, all tenants (ENG-493)"
else
  warn "Skipping SF + CS scheduler entries + nightly backfill scheduler + cs-procedure-codes scheduler (SCHEDULE_INTEGRATION_PULL=0)"
fi

fi  # end: CI_MODE != 1

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

cat <<EOF

====================================================
Cloud Run deploy complete.

Image tag .......... $IMAGE_TAG
Region ............. $REGION
Project ............ $PROJECT_ID
VPC connector ...... $VPC_CONNECTOR
Cloud SQL .......... $CLOUDSQL_INSTANCE (Private IP: ${CLOUDSQL_PRIVATE_IP:-<not resolved in CI_MODE>})

Services:
  $SVC_API ..... ${API_URL:-<not deployed>}
  $SVC_WEB ..... ${WEB_URL:-<not deployed>}

Jobs:
  $JOB_ALEMBIC (run on demand: gcloud run jobs execute $JOB_ALEMBIC --region=$REGION --wait)
  $JOB_BOUNCE  (Cloud Scheduler: $SCHED_BOUNCE  every 15m)
  $JOB_SF_KEEPALIVE (Cloud Scheduler: $SCHED_SF_KEEPALIVE every 6h at minute 7)
  $JOB_MARKETING_BACKFILL (run on demand: gcloud run jobs execute $JOB_MARKETING_BACKFILL --region=$REGION --args=--months,12 --wait — ENG-493)
  $JOB_PROVIDER_BACKFILL (run on demand, FIRST: gcloud run jobs execute $JOB_PROVIDER_BACKFILL --region=$REGION --wait — ENG-510)
  $JOB_ACTOR_NAMES (run on demand, AFTER provider-backfill: gcloud run jobs execute $JOB_ACTOR_NAMES --region=$REGION --wait — ENG-510)
  $JOB_IDENTITY_REPLAY (run on demand — ENG-550/ENG-541. DRY-RUN: gcloud run jobs execute $JOB_IDENTITY_REPLAY --region=$REGION --wait | LIVE: gcloud run jobs execute $JOB_IDENTITY_REPLAY --region=$REGION --args=-m,apps.worker.jobs.replay_identity_matches,--live --wait)
  $JOB_RESOLVE_ATTRIBUTION (run on demand — ENG-580. SMOKE (first 200): gcloud run jobs execute $JOB_RESOLVE_ATTRIBUTION --region=$REGION --wait | FULL BACKFILL: gcloud run jobs execute $JOB_RESOLVE_ATTRIBUTION --region=$REGION --args=-m,apps.worker.jobs.resolve_attribution,--all --wait)
  $JOB_NOTIFICATION_DRAIN (Cloud Scheduler: $SCHED_NOTIFICATION_DRAIN every 1m — ENG-498; inert until NOTIFICATIONS_ENABLED=true)
  $JOB_CONSULT_REMINDERS (Cloud Scheduler: $SCHED_CONSULT_REMINDERS every 1m — ENG-498/486; inert until NOTIFICATIONS_ENABLED=true)
  $JOB_SHARED_CONTACT_REUSE (Cloud Scheduler: $SCHED_SHARED_CONTACT_REUSE every 10m — ENG-555; inert until NOTIFICATIONS_ENABLED=true + NOTIFICATIONS_CUTOFF_AT set + leads channel seeded)
EOF

if [[ "$SCHEDULE_INTEGRATION_PULL" == "1" ]]; then
  cat <<EOF
  $JOB_SF_PULL (Cloud Scheduler: $SCHED_SF_PULL every 15m)
  $JOB_CS_PULL (Cloud Scheduler: $SCHED_CS_PULL every 30m)
  $JOB_BACKFILL (Cloud Scheduler: $SCHED_NIGHTLY_BACKFILL nightly at 10:17 UTC — ENG-327)
  $JOB_CS_PROCEDURE_CODES (Cloud Scheduler: $SCHED_CS_PROCEDURE_CODES weekly Monday 11:23 UTC — ENG-420)
  $JOB_MARKETING_PULL (Cloud Scheduler: $SCHED_MARKETING_PULL daily at 11:43 UTC — ENG-493)
EOF
else
  cat <<EOF
  $JOB_SF_PULL / $JOB_CS_PULL / $JOB_BACKFILL / $JOB_CS_PROCEDURE_CODES / $JOB_MARKETING_PULL  SKIPPED — SCHEDULE_INTEGRATION_PULL=0
EOF
fi

cat <<EOF

Next steps:
  * Verify api boots: gcloud run services describe $SVC_API --region=$REGION
  * Tail logs:        gcloud beta run services logs tail $SVC_API --region=$REGION
  * Run migrations:   gcloud run jobs execute $JOB_ALEMBIC --region=$REGION --wait
  * IAP + LB front door is ENG-116.
  * GitHub Actions automation is ENG-117.
====================================================
EOF
