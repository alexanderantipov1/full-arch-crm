#!/usr/bin/env bash
# Provision the Cloud Run foundation for the Fusion CRM production stack:
# VPC + Serverless VPC Access connector + Cloud SQL Private IP peering +
# Artifact Registry + Cloud Build deployer service account + Workload
# Identity Federation for GitHub Actions.
#
# Per ADR-0002 (docs/decisions/ADR-0002-cloud-run-prod-runtime.md),
# sections "Network", "CI/CD", and "Costs". This is the first of several
# bring-up scripts under the Cloud Run epic (ENG-113). This script ends
# with empty infrastructure: no Cloud Run services are deployed here.
# Deploying services is ENG-115; the GitHub Actions workflow that drives
# the deploy is ENG-117.
#
# Idempotent: re-run after any failure. Each step is independently guarded,
# either via gcloud's "describe || create" pattern or by tolerating an
# ALREADY_EXISTS-style error class.
#
# Prerequisites:
#   * gcloud installed and authenticated (`gcloud auth login`)
#   * Owner or Editor on project fusioncrm-494201
#   * `./infra/scripts/provision_cloudsql.sh` already executed (this script
#     adds a Private IP to the existing fusion-crm-pg instance and reuses
#     the fusion-api-sa / fusion-worker-sa it created)
#   * BAA accepted for the GCP account (already confirmed per ADR-0001)
#
# Usage:
#   ./infra/scripts/provision_cloud_run_foundation.sh
#
# What it does NOT do:
#   * Deploy Cloud Run services (apps/api, apps/web, apps/worker) — ENG-115.
#   * Create the GitHub Actions workflow file — ENG-117.
#   * Flip the Cloud SQL instance to private-only (--no-assign-ip). The
#     public IP is intentionally retained so the operator laptop's Cloud
#     SQL Auth Proxy keeps working. Flip to private-only later, once
#     Cloud Run is the only consumer.
#   * Touch any apps/ or packages/ code. This is scripts + docs only.
#
# Cost note: the Serverless VPC Access connector is the only resource
# created here that begins billing immediately (~$10/month for the
# min-instances=2 e2-micro shape). Everything else is free until Cloud
# Run services attach to it.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"

VPC_NAME="${VPC_NAME:-fusion-vpc}"
SUBNET_NAME="${SUBNET_NAME:-fusion-vpc-us-west1}"
SUBNET_RANGE="${SUBNET_RANGE:-10.0.0.0/24}"

CONNECTOR_NAME="${CONNECTOR_NAME:-fusion-vpc-connector}"
CONNECTOR_RANGE="${CONNECTOR_RANGE:-10.0.1.0/28}"
CONNECTOR_MIN_INSTANCES="${CONNECTOR_MIN_INSTANCES:-2}"
CONNECTOR_MAX_INSTANCES="${CONNECTOR_MAX_INSTANCES:-10}"
CONNECTOR_MACHINE_TYPE="${CONNECTOR_MACHINE_TYPE:-e2-micro}"

# Private Service Connection range for Cloud SQL (servicenetworking peering).
PSC_RANGE_NAME="${PSC_RANGE_NAME:-google-managed-services-fusion-vpc}"
PSC_RANGE_ADDRESS="${PSC_RANGE_ADDRESS:-10.10.0.0}"
PSC_RANGE_PREFIX="${PSC_RANGE_PREFIX:-24}"

CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-fusion-crm-pg}"

ARTIFACT_REPO="${ARTIFACT_REPO:-fusion-containers}"
ARTIFACT_DESCRIPTION="${ARTIFACT_DESCRIPTION:-Fusion CRM container images}"

# Cloud Build / CI deployer SA.
CB_DEPLOYER_SA="${CB_DEPLOYER_SA:-cloud-build-deployer-sa}"
CB_DEPLOYER_DISPLAY="${CB_DEPLOYER_DISPLAY:-Cloud Build deployer (CI/CD)}"

# Runtime SAs that the deployer is allowed to impersonate at deploy time.
# These are created by provision_cloudsql.sh; we only add policy bindings.
API_SA="${API_SA:-fusion-api-sa}"
WORKER_SA="${WORKER_SA:-fusion-worker-sa}"

# Workload Identity Federation: GitHub Actions OIDC.
WIF_POOL_ID="${WIF_POOL_ID:-github-actions}"
WIF_POOL_DISPLAY="${WIF_POOL_DISPLAY:-GitHub Actions WIF Pool}"
WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-github}"
WIF_PROVIDER_DISPLAY="${WIF_PROVIDER_DISPLAY:-GitHub OIDC}"
WIF_ISSUER_URI="${WIF_ISSUER_URI:-https://token.actions.githubusercontent.com}"
GITHUB_REPO="${GITHUB_REPO:-FUSIONDENTALAI/fusion_crm}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!! %s\033[0m\n" "$*" >&2; }
ok() { printf "   \033[0;32m✓ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31mxx %s\033[0m\n" "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

require gcloud

log "Setting active project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null
ok "active project: $(gcloud config get-value project)"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" \
  --format='value(projectNumber)')"
if [[ -z "$PROJECT_NUMBER" ]]; then
  fail "Could not resolve project number for $PROJECT_ID"
fi
ok "project number: $PROJECT_NUMBER"

API_EMAIL="${API_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_EMAIL="${WORKER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
CB_DEPLOYER_EMAIL="${CB_DEPLOYER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

# ---------------------------------------------------------------------------
# 1. Enable required APIs
# ---------------------------------------------------------------------------

log "Enabling required APIs"
gcloud services enable \
  compute.googleapis.com \
  vpcaccess.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --quiet
ok "APIs enabled"

# ---------------------------------------------------------------------------
# 2. VPC + subnet
# ---------------------------------------------------------------------------

log "Creating VPC network $VPC_NAME (custom subnet mode)"
if gcloud compute networks describe "$VPC_NAME" >/dev/null 2>&1; then
  ok "VPC exists: $VPC_NAME"
else
  gcloud compute networks create "$VPC_NAME" \
    --subnet-mode=custom \
    --bgp-routing-mode=regional \
    --quiet
  ok "VPC created: $VPC_NAME"
fi

log "Creating subnet $SUBNET_NAME ($SUBNET_RANGE) in $REGION"
if gcloud compute networks subnets describe "$SUBNET_NAME" \
     --region="$REGION" >/dev/null 2>&1; then
  ok "subnet exists: $SUBNET_NAME"
else
  gcloud compute networks subnets create "$SUBNET_NAME" \
    --network="$VPC_NAME" \
    --range="$SUBNET_RANGE" \
    --region="$REGION" \
    --enable-private-ip-google-access \
    --quiet
  ok "subnet created: $SUBNET_NAME"
fi

# ---------------------------------------------------------------------------
# 3. Serverless VPC Access connector
# ---------------------------------------------------------------------------

log "Creating Serverless VPC Access connector $CONNECTOR_NAME ($CONNECTOR_RANGE)"
if gcloud compute networks vpc-access connectors describe "$CONNECTOR_NAME" \
     --region="$REGION" >/dev/null 2>&1; then
  ok "VPC connector exists: $CONNECTOR_NAME"
else
  gcloud compute networks vpc-access connectors create "$CONNECTOR_NAME" \
    --region="$REGION" \
    --network="$VPC_NAME" \
    --range="$CONNECTOR_RANGE" \
    --min-instances="$CONNECTOR_MIN_INSTANCES" \
    --max-instances="$CONNECTOR_MAX_INSTANCES" \
    --machine-type="$CONNECTOR_MACHINE_TYPE" \
    --quiet
  ok "VPC connector created: $CONNECTOR_NAME"
fi

# ---------------------------------------------------------------------------
# 4. Cloud SQL Private IP migration
# ---------------------------------------------------------------------------
#
# Three sub-steps:
#   4a. Reserve a /24 in fusion-vpc for the servicenetworking peering.
#   4b. Establish the VPC peering with servicenetworking.googleapis.com.
#   4c. Patch the existing fusion-crm-pg to attach to fusion-vpc.
#       PUBLIC IP IS KEPT (no --no-assign-ip) so operator-laptop Cloud SQL
#       Auth Proxy continues to work. Flip to private-only later.

log "Reserving Private Service Connection range $PSC_RANGE_NAME ($PSC_RANGE_ADDRESS/$PSC_RANGE_PREFIX)"
if gcloud compute addresses describe "$PSC_RANGE_NAME" \
     --global >/dev/null 2>&1; then
  ok "PSC range exists: $PSC_RANGE_NAME"
else
  gcloud compute addresses create "$PSC_RANGE_NAME" \
    --global \
    --purpose=VPC_PEERING \
    --addresses="$PSC_RANGE_ADDRESS" \
    --prefix-length="$PSC_RANGE_PREFIX" \
    --network="$VPC_NAME" \
    --quiet
  ok "PSC range reserved: $PSC_RANGE_NAME"
fi

log "Connecting servicenetworking peering to $VPC_NAME"
# `services vpc-peerings connect` is idempotent for an existing identical
# peering, but it errors loudly on conflicting configs. List first, then
# decide between connect (first time) and update (existing).
if gcloud services vpc-peerings list \
     --network="$VPC_NAME" \
     --service=servicenetworking.googleapis.com \
     --format='value(network)' 2>/dev/null \
     | grep -q "$VPC_NAME"; then
  ok "servicenetworking peering already present on $VPC_NAME"
else
  gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges="$PSC_RANGE_NAME" \
    --network="$VPC_NAME" \
    --quiet
  ok "servicenetworking peering established"
fi

log "Attaching $CLOUDSQL_INSTANCE to $VPC_NAME (Private IP added; public IP retained)"
if ! gcloud sql instances describe "$CLOUDSQL_INSTANCE" >/dev/null 2>&1; then
  warn "Cloud SQL instance $CLOUDSQL_INSTANCE not found."
  warn "Run ./infra/scripts/provision_cloudsql.sh first."
  exit 1
fi

EXISTING_PRIVATE_NETWORK="$(gcloud sql instances describe "$CLOUDSQL_INSTANCE" \
  --format='value(settings.ipConfiguration.privateNetwork)' 2>/dev/null || true)"
EXPECTED_NETWORK="projects/${PROJECT_ID}/global/networks/${VPC_NAME}"

if [[ "$EXISTING_PRIVATE_NETWORK" == "$EXPECTED_NETWORK" ]]; then
  ok "Cloud SQL instance already attached to $VPC_NAME"
else
  # NOTE: deliberately NOT passing --no-assign-ip. We keep the public IP so
  # the operator laptop's Cloud SQL Auth Proxy continues to work. Flip to
  # private-only via a separate operator action once Cloud Run services
  # are the only DB consumer.
  gcloud sql instances patch "$CLOUDSQL_INSTANCE" \
    --network="$EXPECTED_NETWORK" \
    --quiet
  ok "Cloud SQL instance attached to $VPC_NAME (public IP retained)"
fi

CLOUDSQL_PRIVATE_IP="$(gcloud sql instances describe "$CLOUDSQL_INSTANCE" \
  --format='value(ipAddresses.filter("type:PRIVATE").extract(ipAddress))' \
  2>/dev/null | tr -d '[]' | head -n1 || true)"
if [[ -z "$CLOUDSQL_PRIVATE_IP" ]]; then
  # Older gcloud format fallback.
  CLOUDSQL_PRIVATE_IP="$(gcloud sql instances describe "$CLOUDSQL_INSTANCE" \
    --format=json \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
for a in d.get("ipAddresses", []):
    if a.get("type")=="PRIVATE":
        print(a.get("ipAddress",""))
        break' 2>/dev/null || true)"
fi
if [[ -z "$CLOUDSQL_PRIVATE_IP" ]]; then
  CLOUDSQL_PRIVATE_IP="(not assigned yet — re-run after Cloud SQL settles)"
fi
ok "Cloud SQL private IP: $CLOUDSQL_PRIVATE_IP"

# ---------------------------------------------------------------------------
# 5. Artifact Registry repository
# ---------------------------------------------------------------------------

log "Creating Artifact Registry repository $ARTIFACT_REPO ($REGION, docker)"
if gcloud artifacts repositories describe "$ARTIFACT_REPO" \
     --location="$REGION" >/dev/null 2>&1; then
  ok "Artifact Registry repo exists: $ARTIFACT_REPO"
else
  gcloud artifacts repositories create "$ARTIFACT_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="$ARTIFACT_DESCRIPTION" \
    --quiet
  ok "Artifact Registry repo created: $ARTIFACT_REPO"
fi

ARTIFACT_REPO_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}"

# ---------------------------------------------------------------------------
# 6. Cloud Build deployer service account
# ---------------------------------------------------------------------------

log "Creating service account $CB_DEPLOYER_SA"
if gcloud iam service-accounts describe "$CB_DEPLOYER_EMAIL" >/dev/null 2>&1; then
  ok "SA exists: $CB_DEPLOYER_EMAIL"
else
  gcloud iam service-accounts create "$CB_DEPLOYER_SA" \
    --display-name="$CB_DEPLOYER_DISPLAY" \
    --quiet
  ok "SA created: $CB_DEPLOYER_EMAIL"
fi

grant_project_role() {
  local sa_email="$1"
  local role="$2"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${sa_email}" \
    --role="$role" \
    --condition=None \
    --quiet >/dev/null
  ok "  granted $role to $sa_email"
}

log "Granting deploy-time roles to $CB_DEPLOYER_EMAIL"
grant_project_role "$CB_DEPLOYER_EMAIL" "roles/artifactregistry.writer"
grant_project_role "$CB_DEPLOYER_EMAIL" "roles/run.admin"
# serviceAccountUser at project scope is the common Cloud Run pattern;
# we also pin it per runtime SA below for defence in depth.
grant_project_role "$CB_DEPLOYER_EMAIL" "roles/iam.serviceAccountUser"

# ---------------------------------------------------------------------------
# 7. Workload Identity Federation for GitHub Actions
# ---------------------------------------------------------------------------

log "Creating Workload Identity Pool $WIF_POOL_ID"
if gcloud iam workload-identity-pools describe "$WIF_POOL_ID" \
     --location=global >/dev/null 2>&1; then
  # Tolerate a previously-deleted pool that is still in the soft-delete window.
  POOL_STATE="$(gcloud iam workload-identity-pools describe "$WIF_POOL_ID" \
    --location=global --format='value(state)' 2>/dev/null || echo UNKNOWN)"
  if [[ "$POOL_STATE" == "DELETED" ]]; then
    warn "WIF pool $WIF_POOL_ID is in DELETED state; restoring"
    gcloud iam workload-identity-pools undelete "$WIF_POOL_ID" \
      --location=global \
      --quiet
    ok "WIF pool restored: $WIF_POOL_ID"
  else
    ok "WIF pool exists: $WIF_POOL_ID"
  fi
else
  gcloud iam workload-identity-pools create "$WIF_POOL_ID" \
    --location=global \
    --display-name="$WIF_POOL_DISPLAY" \
    --description="OIDC pool for GitHub Actions in $GITHUB_REPO" \
    --quiet
  ok "WIF pool created: $WIF_POOL_ID"
fi

log "Creating WIF OIDC provider $WIF_PROVIDER_ID (pinned to $GITHUB_REPO)"
if gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_ID" \
     --location=global \
     --workload-identity-pool="$WIF_POOL_ID" >/dev/null 2>&1; then
  ok "WIF provider exists: $WIF_PROVIDER_ID"
else
  gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER_ID" \
    --location=global \
    --workload-identity-pool="$WIF_POOL_ID" \
    --display-name="$WIF_PROVIDER_DISPLAY" \
    --issuer-uri="$WIF_ISSUER_URI" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository == \"${GITHUB_REPO}\"" \
    --quiet
  ok "WIF provider created: $WIF_PROVIDER_ID"
fi

WIF_POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_ID}"
WIF_PROVIDER_RESOURCE="${WIF_POOL_RESOURCE}/providers/${WIF_PROVIDER_ID}"
WIF_PRINCIPAL_REPO="principalSet://iam.googleapis.com/${WIF_POOL_RESOURCE}/attribute.repository/${GITHUB_REPO}"

log "Binding $GITHUB_REPO → $CB_DEPLOYER_EMAIL via workloadIdentityUser"
gcloud iam service-accounts add-iam-policy-binding "$CB_DEPLOYER_EMAIL" \
  --member="$WIF_PRINCIPAL_REPO" \
  --role="roles/iam.workloadIdentityUser" \
  --quiet >/dev/null
ok "  bound $WIF_PRINCIPAL_REPO → workloadIdentityUser on $CB_DEPLOYER_EMAIL"

# ---------------------------------------------------------------------------
# 8. Allow Cloud Build deployer SA to impersonate the runtime SAs
# ---------------------------------------------------------------------------

bind_sa_impersonation() {
  local target_email="$1"
  if ! gcloud iam service-accounts describe "$target_email" >/dev/null 2>&1; then
    warn "Runtime SA $target_email not found; skipping impersonation binding."
    warn "Run ./infra/scripts/provision_cloudsql.sh first to create it."
    return 0
  fi
  gcloud iam service-accounts add-iam-policy-binding "$target_email" \
    --member="serviceAccount:${CB_DEPLOYER_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --quiet >/dev/null
  ok "  $CB_DEPLOYER_EMAIL → serviceAccountUser on $target_email"
}

log "Allowing $CB_DEPLOYER_EMAIL to impersonate runtime SAs"
bind_sa_impersonation "$API_EMAIL"
bind_sa_impersonation "$WORKER_EMAIL"

# ---------------------------------------------------------------------------
# 9. Output
# ---------------------------------------------------------------------------

cat <<EOF

====================================================
Cloud Run foundation provisioning complete.

VPC ............... $VPC_NAME
Subnet ............ $SUBNET_NAME ($SUBNET_RANGE)
VPC connector ..... $CONNECTOR_NAME ($CONNECTOR_RANGE)
Artifact Registry . $ARTIFACT_REPO_PATH
Cloud SQL ......... $CLOUDSQL_INSTANCE (Private IP: $CLOUDSQL_PRIVATE_IP)
Cloud Build SA .... $CB_DEPLOYER_EMAIL
WIF Pool .......... $WIF_POOL_ID
WIF Provider ...... $WIF_PROVIDER_ID (locked to $GITHUB_REPO)

WIF provider resource (for GitHub Actions workflow):
  $WIF_PROVIDER_RESOURCE

Next: GitHub Actions workflow that authenticates via WIF, builds
containers, pushes to Artifact Registry, deploys to Cloud Run.
That's ENG-115 + ENG-117.
====================================================
EOF
