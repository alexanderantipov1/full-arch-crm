#!/usr/bin/env bash
# Provision the DEDICATED Cloud SQL for PostgreSQL instance for the production
# Mattermost host (ENG-494 / Block I): instance `fusion-mm-pg`, the `mattermost`
# database, and the `mmuser` role. Mirrors infra/scripts/provision_cloudsql.sh.
#
# Per ADR-0006 (docs/decisions/ADR-0006-interactive-messenger-layer.md) and
# docs/DEPLOYMENT_RULES.md. The Mattermost store is a PHI system (ENG-460) → it
# gets a MANAGED instance with automated backups + PITR + encryption-at-rest,
# PHYSICALLY SEPARATE from the canonical `fusion-crm-pg` (invariant #1), never a
# co-located container on the VM and never a second DB inside the canonical
# instance. See the eng-494-host-provisioning bundle §2 decision #4.
#
# ✅ ENG-501 (PHI/BAA posture go/no-go) = GO (operator decision 2026-06-17).
#    This instance is APPROVED to create. It still stands up a PHI store, and it
#    begins billing immediately — keep the same-conversation approval discipline
#    for spend / hard-to-reverse actions (CLAUDE.md invariant #3).
#
# Idempotent: re-run after any failure. Each step is describe-or-create guarded.
#
# Prerequisites:
#   * gcloud installed and authenticated (`gcloud auth login`); Owner/Editor on
#     project fusioncrm-494201.
#   * `./infra/scripts/provision_cloud_run_foundation.sh` already ran — it
#     established the servicenetworking peering on `fusion-vpc` that this
#     instance's PRIVATE IP rides on. This script reuses that peering; it does
#     NOT create a new one.
#   * BAA accepted for the GCP account (confirmed per ADR-0001).
#
# Usage:
#   ./infra/scripts/provision_mattermost_cloudsql.sh
#
# What it does NOT do:
#   * Create the GCE VM / firewall / bucket / DNS — that is
#     ./infra/scripts/provision_mattermost_host.sh (run AFTER this).
#   * Invent or print the DB password value. The password is sourced from
#     Secret Manager secret `mattermost-db-password`; this script FAILS LOUDLY if
#     that secret has no `latest` version (DEPLOYMENT_RULES §6).
#   * Store the bot token / webhook secret (ENG-495/496, credential service).
#   * Flip the instance to private-only. A public IP is retained so the operator
#     laptop's Cloud SQL Auth Proxy can reach it for break-glass; the VM uses the
#     PRIVATE IP over fusion-vpc.
#
# Cost note: db-g1-small (shared-core) + 10 GB SSD, zonal, is roughly $9-15/month.
#   This is the Cloud SQL slice of the ~$40/mo all-in Mattermost host estimate.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"
ZONE="${ZONE:-us-west1-a}"

VPC_NAME="${VPC_NAME:-fusion-vpc}"

INSTANCE_NAME="${MM_INSTANCE_NAME:-fusion-mm-pg}"
DB_NAME="${MM_DB_NAME:-mattermost}"
DB_USER="${MM_DB_USER:-mmuser}"
# db-g1-small (shared-core) is ample for one clinic team (bundle §2 #4).
DB_TIER="${MM_DB_TIER:-db-g1-small}"
DB_STORAGE_SIZE="${MM_DB_STORAGE_SIZE:-10}"
DB_VERSION="${MM_DB_VERSION:-POSTGRES_16}"

# Secret Manager secret that holds the mmuser password. Created here if absent
# (a placeholder with NO version); the operator adds a hex value once. Never
# inline a password (DEPLOYMENT_RULES §6).
DB_PASSWORD_SECRET="${MM_DB_PASSWORD_SECRET:-mattermost-db-password}"

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

log "Enabling required APIs"
gcloud services enable \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com \
  compute.googleapis.com \
  --quiet
ok "APIs enabled"

EXPECTED_NETWORK="projects/${PROJECT_ID}/global/networks/${VPC_NAME}"

# ---------------------------------------------------------------------------
# 1. Secret Manager placeholder for the mmuser password
# ---------------------------------------------------------------------------
# Create the secret reference if it is missing, but NEVER write a value here.
# The operator populates it once (hex, not base64 — base64 +/= breaks DSN
# parsing) before the role is created below.

log "Ensuring Secret Manager secret $DB_PASSWORD_SECRET exists"
if gcloud secrets describe "$DB_PASSWORD_SECRET" >/dev/null 2>&1; then
  ok "secret exists: $DB_PASSWORD_SECRET"
else
  gcloud secrets create "$DB_PASSWORD_SECRET" \
    --replication-policy=automatic \
    --quiet
  ok "secret created: $DB_PASSWORD_SECRET (no version yet)"
  cat <<EOF

  Populate it ONCE with a strong hex password, then re-run this script:
    openssl rand -hex 32 | gcloud secrets versions add $DB_PASSWORD_SECRET --data-file=-
EOF
fi

# ---------------------------------------------------------------------------
# 2. Cloud SQL instance (dedicated, private IP into fusion-vpc)
# ---------------------------------------------------------------------------
# Same posture as the canonical instance in provision_cloudsql.sh: ENTERPRISE
# edition, ZONAL (no HA in this phase), SSD + auto-increase, daily automated
# --backup, PITR on, 7-day retained backups, production maintenance channel,
# require-ssl. Difference: a PRIVATE IP attached to fusion-vpc via the
# servicenetworking peering established by provision_cloud_run_foundation.sh, so
# the GCE VM in fusion-vpc reaches it directly (no Auth Proxy needed on the VM).
# The public IP is retained for operator break-glass via the laptop Auth Proxy.

log "Creating dedicated Cloud SQL instance $INSTANCE_NAME ($DB_TIER, $REGION, private IP on $VPC_NAME)"
if gcloud sql instances describe "$INSTANCE_NAME" >/dev/null 2>&1; then
  ok "instance exists: $INSTANCE_NAME (skipping create — patch by hand if config drifted)"
else
  if ! gcloud compute networks describe "$VPC_NAME" >/dev/null 2>&1; then
    fail "VPC $VPC_NAME not found. Run ./infra/scripts/provision_cloud_run_foundation.sh first."
  fi
  # The private-IP instance create below relies on the servicenetworking peering
  # that provision_cloud_run_foundation.sh establishes on $VPC_NAME. Without it,
  # `gcloud sql instances create --network=...` fails with a cryptic
  # "Failed to create subnetwork / no allocated range" error. Precheck so the
  # failure is actionable.
  if ! gcloud services vpc-peerings list --network="$VPC_NAME" \
        --service=servicenetworking.googleapis.com \
        --format='value(peering)' 2>/dev/null | grep -q .; then
    fail "No servicenetworking peering on $VPC_NAME. Run ./infra/scripts/provision_cloud_run_foundation.sh first (it allocates the private-IP range + peering)."
  fi
  gcloud sql instances create "$INSTANCE_NAME" \
    --database-version="$DB_VERSION" \
    --edition=ENTERPRISE \
    --tier="$DB_TIER" \
    --region="$REGION" \
    --storage-type=SSD \
    --storage-size="$DB_STORAGE_SIZE" \
    --storage-auto-increase \
    --availability-type=ZONAL \
    --backup \
    --backup-start-time=11:00 \
    --enable-point-in-time-recovery \
    --retained-backups-count=7 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=11 \
    --maintenance-release-channel=production \
    --network="$EXPECTED_NETWORK" \
    --require-ssl \
    --database-flags=cloudsql.enable_pgaudit=on,log_min_duration_statement=500 \
    --quiet
  ok "instance created: $INSTANCE_NAME (private IP on $VPC_NAME; public IP retained for break-glass)"
fi

# backup-start-time and maintenance-window-hour are UTC (offset from the
# canonical instance's 10:00 so the two windows do not overlap).

# ---------------------------------------------------------------------------
# 3. Database
# ---------------------------------------------------------------------------
# Keep the DB locale ENGLISH/C — a non-English Mattermost locale disables half
# of Mattermost's own indexes (see infra/docker/mattermost/README.md).

log "Creating database $DB_NAME on $INSTANCE_NAME"
if gcloud sql databases describe "$DB_NAME" --instance="$INSTANCE_NAME" >/dev/null 2>&1; then
  ok "database exists: $DB_NAME"
else
  gcloud sql databases create "$DB_NAME" --instance="$INSTANCE_NAME" --quiet
  ok "database created: $DB_NAME"
fi

# ---------------------------------------------------------------------------
# 4. Postgres role (mmuser), password sourced from Secret Manager
# ---------------------------------------------------------------------------

log "Creating Postgres role $DB_USER (password from Secret Manager: $DB_PASSWORD_SECRET)"
if gcloud sql users list --instance="$INSTANCE_NAME" --format="value(name)" \
     | grep -qx "$DB_USER"; then
  ok "user exists: $DB_USER (skipping create — rotate via 'gcloud sql users set-password')"
else
  if ! gcloud secrets versions access latest --secret="$DB_PASSWORD_SECRET" >/dev/null 2>&1; then
    fail "Secret '$DB_PASSWORD_SECRET' has no version yet. Add one and re-run:
  openssl rand -hex 32 | gcloud secrets versions add $DB_PASSWORD_SECRET --data-file=-"
  fi
  DB_PASSWORD="$(gcloud secrets versions access latest --secret="$DB_PASSWORD_SECRET")"
  gcloud sql users create "$DB_USER" \
    --instance="$INSTANCE_NAME" \
    --password="$DB_PASSWORD" \
    --quiet
  ok "user created: $DB_USER"
  unset DB_PASSWORD
fi

# ---------------------------------------------------------------------------
# 5. Output connection facts
# ---------------------------------------------------------------------------

CONNECTION_NAME="$(gcloud sql instances describe "$INSTANCE_NAME" \
  --format='value(connectionName)')"

PRIVATE_IP="$(gcloud sql instances describe "$INSTANCE_NAME" \
  --format='value(ipAddresses.filter("type:PRIVATE").extract(ipAddress))' \
  2>/dev/null | tr -d '[]' | head -n1 || true)"
if [[ -z "$PRIVATE_IP" ]]; then
  # Older gcloud format fallback.
  PRIVATE_IP="$(gcloud sql instances describe "$INSTANCE_NAME" \
    --format=json \
    | python3 -c 'import json,sys
d=json.load(sys.stdin)
for a in d.get("ipAddresses", []):
    if a.get("type")=="PRIVATE":
        print(a.get("ipAddress",""))
        break' 2>/dev/null || true)"
fi
if [[ -z "$PRIVATE_IP" ]]; then
  PRIVATE_IP="(not assigned yet — re-run after Cloud SQL settles)"
fi

cat <<EOF

================================================================
Dedicated Mattermost Cloud SQL provisioning complete.

Project ........... $PROJECT_ID
Region / Zone ..... $REGION / $ZONE
Instance .......... $INSTANCE_NAME ($DB_TIER, $DB_VERSION, ZONAL)
Connection name ... $CONNECTION_NAME
Private IP ........ $PRIVATE_IP   (on $VPC_NAME — the VM reaches this directly)
Database .......... $DB_NAME
DB user ........... $DB_USER (password in Secret Manager: $DB_PASSWORD_SECRET)
Backups ........... daily automated + PITR, 7 retained
Physically separate from canonical fusion-crm-pg (invariant #1).

Next:
  1. Put the PRIVATE IP into the VM env file as MM_DB_HOST:
       MM_DB_HOST=$PRIVATE_IP
  2. Run ./infra/scripts/provision_mattermost_host.sh (VM + firewall + bucket + DNS).
  3. See infra/docker/mattermost-host/README.md for the full ordered bring-up.
================================================================
EOF
