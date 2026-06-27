#!/usr/bin/env bash
# Provision Cloud SQL for PostgreSQL + GCS backup bucket + service accounts +
# Secret Manager entries for the Fusion CRM production stack.
#
# Per ADR-0001 (docs/decisions/ADR-0001-cloud-sql-prod-postgres.md).
#
# Idempotent: re-run after any failure. Each step is independently guarded,
# either via gcloud's "describe || create" pattern or by tolerating the
# "ALREADY_EXISTS" error.
#
# Prerequisites:
#   * gcloud + gsutil installed and authenticated (`gcloud auth login`)
#   * Owner or Editor on project fusioncrm-494201
#   * BAA accepted for the GCP account (already confirmed 2026-05-08)
#
# Usage:
#   ./infra/scripts/provision_cloudsql.sh
#
# What it does NOT do:
#   * Create the GCP project (assumed to exist).
#   * Run `init-schemas.sql` or `alembic upgrade head`. That happens via
#     `infra/scripts/cloudsql_bootstrap.sh` after this script finishes
#     and after the operator has Auth Proxy running.
#
# Cost note: the instance starts billing immediately. Single-zone
# db-custom-1-3840 + 10 GB SSD is roughly $50/month.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"
ZONE="${ZONE:-us-west1-a}"

INSTANCE_NAME="${INSTANCE_NAME:-fusion-crm-pg}"
DB_NAME="${DB_NAME:-fusion}"
DB_USER="${DB_USER:-fusion}"
DB_TIER="${DB_TIER:-db-custom-1-3840}"
DB_STORAGE_SIZE="${DB_STORAGE_SIZE:-10}"
DB_VERSION="${DB_VERSION:-POSTGRES_16}"

BACKUP_BUCKET="${BACKUP_BUCKET:-fusion-crm-backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-90}"

API_SA="fusion-api-sa"
WORKER_SA="fusion-worker-sa"
MIGRATOR_SA="fusion-migrator-sa"

# Secret names. Values are written interactively (or skipped if the secret
# already has a version).
SECRETS=(
  "db-password"
  "encryption-key"
  "salesforce-client-secret"
  "carestack-client-secret"
  "carestack-vendor-key"
  "carestack-account-key"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!! %s\033[0m\n" "$*" >&2; }
ok() { printf "   \033[0;32m✓ %s\033[0m\n" "$*"; }

require() {
  command -v "$1" >/dev/null 2>&1 || {
    warn "Required command not found: $1"
    exit 1
  }
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

require gcloud
require gsutil

log "Setting active project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null
ok "active project: $(gcloud config get-value project)"

# ---------------------------------------------------------------------------
# 1. Enable required APIs
# ---------------------------------------------------------------------------

log "Enabling required APIs"
gcloud services enable \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  servicenetworking.googleapis.com \
  storage.googleapis.com \
  --quiet
ok "APIs enabled"

# ---------------------------------------------------------------------------
# 2. Service accounts
# ---------------------------------------------------------------------------

create_sa() {
  local sa_id="$1"
  local display="$2"
  local email="${sa_id}@${PROJECT_ID}.iam.gserviceaccount.com"

  if gcloud iam service-accounts describe "$email" >/dev/null 2>&1; then
    ok "SA exists: $email"
  else
    gcloud iam service-accounts create "$sa_id" \
      --display-name="$display" \
      --quiet
    ok "SA created: $email"
  fi
}

grant_role() {
  local sa_email="$1"
  local role="$2"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${sa_email}" \
    --role="$role" \
    --condition=None \
    --quiet >/dev/null
  ok "  granted $role to $sa_email"
}

log "Creating service accounts"
create_sa "$API_SA"      "Fusion API runtime"
create_sa "$WORKER_SA"   "Fusion worker runtime"
create_sa "$MIGRATOR_SA" "Fusion DB migrator (operator laptop)"

API_EMAIL="${API_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_EMAIL="${WORKER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
MIGRATOR_EMAIL="${MIGRATOR_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

log "Granting IAM roles"
grant_role "$API_EMAIL"      "roles/cloudsql.client"
grant_role "$API_EMAIL"      "roles/secretmanager.secretAccessor"
grant_role "$WORKER_EMAIL"   "roles/cloudsql.client"
grant_role "$WORKER_EMAIL"   "roles/secretmanager.secretAccessor"
grant_role "$MIGRATOR_EMAIL" "roles/cloudsql.client"

# ---------------------------------------------------------------------------
# 3. Secret Manager (create empty placeholders; values added separately)
# ---------------------------------------------------------------------------

create_secret() {
  local name="$1"
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    ok "secret exists: $name"
  else
    gcloud secrets create "$name" \
      --replication-policy=automatic \
      --quiet
    ok "secret created: $name (no version yet — add via 'gcloud secrets versions add')"
  fi
}

log "Creating Secret Manager secrets"
for s in "${SECRETS[@]}"; do
  create_secret "$s"
done

cat <<EOF

To populate a secret:
  printf 'YOUR_VALUE' | gcloud secrets versions add db-password --data-file=-

For the DB password specifically, generate a strong one once and reuse.
NOTE: use hex (not base64) — base64's +/= characters break SQLAlchemy DSN parsing
when interpolated into postgresql+psycopg://USER:PASS@... URLs.

  openssl rand -hex 32 | gcloud secrets versions add db-password --data-file=-
EOF

# ---------------------------------------------------------------------------
# 4. GCS backup bucket
# ---------------------------------------------------------------------------

log "Creating GCS backup bucket gs://${BACKUP_BUCKET}"
if gsutil ls -b "gs://${BACKUP_BUCKET}" >/dev/null 2>&1; then
  ok "bucket exists: gs://${BACKUP_BUCKET}"
else
  gsutil mb -p "$PROJECT_ID" -l "$REGION" -b on "gs://${BACKUP_BUCKET}"
  ok "bucket created: gs://${BACKUP_BUCKET} (uniform bucket-level access ON)"
fi

log "Enabling object versioning on gs://${BACKUP_BUCKET}"
gsutil versioning set on "gs://${BACKUP_BUCKET}"
ok "versioning ON"

log "Applying lifecycle: delete objects older than ${BACKUP_RETENTION_DAYS} days"
LIFECYCLE_TMP="$(mktemp)"
trap 'rm -f "$LIFECYCLE_TMP"' EXIT
cat >"$LIFECYCLE_TMP" <<EOF
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": ${BACKUP_RETENTION_DAYS}}
    }
  ]
}
EOF
gsutil lifecycle set "$LIFECYCLE_TMP" "gs://${BACKUP_BUCKET}"
ok "lifecycle set"

# ---------------------------------------------------------------------------
# 5. Cloud SQL instance
# ---------------------------------------------------------------------------

log "Creating Cloud SQL instance $INSTANCE_NAME"
if gcloud sql instances describe "$INSTANCE_NAME" >/dev/null 2>&1; then
  ok "instance exists: $INSTANCE_NAME (skipping create)"
else
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
    --backup-start-time=10:00 \
    --enable-point-in-time-recovery \
    --retained-backups-count=7 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=10 \
    --maintenance-release-channel=production \
    --require-ssl \
    --database-flags=cloudsql.enable_pgaudit=on,log_min_duration_statement=500 \
    --quiet
  ok "instance created"
fi

# Note: backup-start-time and maintenance-window-hour are UTC.
# 10:00 UTC ≈ 03:00 PT (DST-aware via Cloud SQL maintenance scheduler).

# ---------------------------------------------------------------------------
# 6. Database + role
# ---------------------------------------------------------------------------

log "Creating database $DB_NAME"
if gcloud sql databases describe "$DB_NAME" --instance="$INSTANCE_NAME" >/dev/null 2>&1; then
  ok "database exists: $DB_NAME"
else
  gcloud sql databases create "$DB_NAME" --instance="$INSTANCE_NAME" --quiet
  ok "database created: $DB_NAME"
fi

log "Creating Postgres role $DB_USER (password from Secret Manager)"
if gcloud sql users list --instance="$INSTANCE_NAME" --format="value(name)" \
     | grep -qx "$DB_USER"; then
  ok "user exists: $DB_USER (skipping create — rotate via 'gcloud sql users set-password')"
else
  if ! gcloud secrets versions access latest --secret="db-password" >/dev/null 2>&1; then
    warn "Secret 'db-password' has no version yet. Add one and re-run, e.g.:"
    warn "  openssl rand -base64 32 | gcloud secrets versions add db-password --data-file=-"
    exit 1
  fi
  DB_PASSWORD="$(gcloud secrets versions access latest --secret=db-password)"
  gcloud sql users create "$DB_USER" \
    --instance="$INSTANCE_NAME" \
    --password="$DB_PASSWORD" \
    --quiet
  ok "user created: $DB_USER"
  unset DB_PASSWORD
fi

# ---------------------------------------------------------------------------
# 7. Output connection facts
# ---------------------------------------------------------------------------

CONNECTION_NAME="$(gcloud sql instances describe "$INSTANCE_NAME" \
  --format='value(connectionName)')"

cat <<EOF

================================================================
Cloud SQL provisioning complete.

Project ........... $PROJECT_ID
Region ............ $REGION
Instance .......... $INSTANCE_NAME
Connection name ... $CONNECTION_NAME
Database .......... $DB_NAME
DB user ........... $DB_USER (password in Secret Manager: db-password)
Backup bucket ..... gs://$BACKUP_BUCKET (retention $BACKUP_RETENTION_DAYS days)

Service accounts:
  api ........ $API_EMAIL
  worker ..... $WORKER_EMAIL
  migrator ... $MIGRATOR_EMAIL

Next steps:
  1. Download a key for the migrator SA (one-time, store at
     ~/.config/fusion-crm/fusion-migrator-sa.json, chmod 600):

       mkdir -p ~/.config/fusion-crm
       gcloud iam service-accounts keys create \\
         ~/.config/fusion-crm/fusion-migrator-sa.json \\
         --iam-account=$MIGRATOR_EMAIL
       chmod 600 ~/.config/fusion-crm/fusion-migrator-sa.json

  2. Run the bootstrap script to initialise schemas + alembic:

       CLOUDSQL_INSTANCE_CONNECTION_NAME=$CONNECTION_NAME \\
         ./infra/scripts/cloudsql_bootstrap.sh

================================================================
EOF
