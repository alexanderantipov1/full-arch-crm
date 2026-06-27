#!/usr/bin/env bash
# Initialise schemas and run Alembic migrations against a fresh Cloud SQL
# instance via the Cloud SQL Auth Proxy.
#
# Idempotent: safe to re-run. CREATE SCHEMA statements use IF NOT EXISTS;
# `alembic upgrade head` is a no-op when already at head.
#
# Per ADR-0001 (docs/decisions/ADR-0001-cloud-sql-prod-postgres.md).
#
# Prerequisites:
#   * `cloud-sql-proxy` v2 in PATH (brew install cloud-sql-proxy, or
#     download from https://cloud.google.com/sql/docs/postgres/sql-proxy).
#   * `psql` and `python` (with the project venv active so alembic + the
#     project packages are importable).
#   * GOOGLE_APPLICATION_CREDENTIALS pointing at the migrator SA key.
#   * `db-password` secret populated in Secret Manager.
#   * Provisioning step (`provision_cloudsql.sh`) already complete.
#
# Usage:
#   CLOUDSQL_INSTANCE_CONNECTION_NAME=fusioncrm-494201:us-west1:fusion-crm-pg \
#     ./infra/scripts/cloudsql_bootstrap.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
DB_NAME="${DB_NAME:-fusion}"
DB_USER="${DB_USER:-fusion}"
PROXY_PORT="${PROXY_PORT:-5432}"

if [[ -z "${CLOUDSQL_INSTANCE_CONNECTION_NAME:-}" ]]; then
  echo "ERROR: set CLOUDSQL_INSTANCE_CONNECTION_NAME (e.g. ${PROJECT_ID}:us-west1:fusion-crm-pg)" >&2
  exit 1
fi

# Authentication: prefer Application Default Credentials (gcloud auth
# application-default login). The org-policy
# `constraints/iam.disableServiceAccountKeyCreation` blocks downloaded
# SA keys, so we authenticate as the operator and rely on their Owner
# role on the project. Set GOOGLE_APPLICATION_CREDENTIALS only if you
# really do have a key file (will override ADC).
if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json"
  if [[ ! -f "$ADC_FILE" ]]; then
    echo "ERROR: no ADC credentials at $ADC_FILE." >&2
    echo "Run: gcloud auth application-default login --no-launch-browser" >&2
    exit 1
  fi
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INIT_SQL="${REPO_ROOT}/infra/docker/init-schemas.sql"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
ok() { printf "   \033[0;32m✓ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m!! %s\033[0m\n" "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1 (see header)"
}

PROXY_PID=""
cleanup() {
  if [[ -n "$PROXY_PID" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
    log "Stopping Cloud SQL Auth Proxy (pid $PROXY_PID)"
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

require cloud-sql-proxy
require psql
require python
require gcloud

[[ -f "$INIT_SQL" ]] || fail "Cannot find $INIT_SQL"

log "Fetching db-password from Secret Manager"
DB_PASSWORD="$(gcloud secrets versions access latest \
  --secret=db-password --project="$PROJECT_ID")"
[[ -n "$DB_PASSWORD" ]] || fail "db-password is empty"
ok "secret fetched"

# ---------------------------------------------------------------------------
# Start the proxy
# ---------------------------------------------------------------------------

log "Starting Cloud SQL Auth Proxy on 127.0.0.1:${PROXY_PORT}"
cloud-sql-proxy "$CLOUDSQL_INSTANCE_CONNECTION_NAME" \
  --port "$PROXY_PORT" \
  --address 127.0.0.1 \
  >/tmp/cloud-sql-proxy.log 2>&1 &
PROXY_PID=$!

# Wait up to 15s for the proxy to become reachable.
for _ in $(seq 1 30); do
  if (echo > /dev/tcp/127.0.0.1/"$PROXY_PORT") 2>/dev/null; then
    ok "proxy ready (pid $PROXY_PID)"
    break
  fi
  sleep 0.5
done
(echo > /dev/tcp/127.0.0.1/"$PROXY_PORT") 2>/dev/null \
  || fail "proxy did not start; see /tmp/cloud-sql-proxy.log"

# ---------------------------------------------------------------------------
# Apply init-schemas.sql
# ---------------------------------------------------------------------------

export PGPASSWORD="$DB_PASSWORD"

log "Applying init-schemas.sql (CREATE SCHEMA IF NOT EXISTS — idempotent)"
psql \
  --host=127.0.0.1 \
  --port="$PROXY_PORT" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --set=ON_ERROR_STOP=1 \
  --file="$INIT_SQL" \
  >/dev/null
ok "schemas applied"

# ---------------------------------------------------------------------------
# Run Alembic migrations
# ---------------------------------------------------------------------------

log "Running alembic upgrade head"
# URL-encode the password — base64 secrets contain +/= which break DSN parsing.
DB_PASSWORD_ENC="$(python -c "import sys, urllib.parse; sys.stdout.write(urllib.parse.quote(sys.argv[1], safe=''))" "$DB_PASSWORD")"
(
  cd "${REPO_ROOT}/packages/db"
  PYTHONPATH="${REPO_ROOT}" \
  DATABASE_URL_SYNC="postgresql+psycopg://${DB_USER}:${DB_PASSWORD_ENC}@127.0.0.1:${PROXY_PORT}/${DB_NAME}" \
  DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD_ENC}@127.0.0.1:${PROXY_PORT}/${DB_NAME}" \
  REDIS_URL="redis://127.0.0.1:6379/0" \
  SECRET_KEY="bootstrap-noop-not-used-during-migration" \
  python -m alembic -c alembic.ini upgrade head
)
unset DB_PASSWORD_ENC
ok "migrations at head"

# ---------------------------------------------------------------------------
# Smoke check
# ---------------------------------------------------------------------------

log "Smoke-checking schema set"
EXPECTED="actor audit auth identity ingest integrations interaction ops phi"
ACTUAL="$(psql \
  --host=127.0.0.1 --port="$PROXY_PORT" \
  --username="$DB_USER" --dbname="$DB_NAME" \
  --tuples-only --no-align \
  --command="SELECT string_agg(nspname, ' ' ORDER BY nspname) FROM pg_namespace WHERE nspname IN ('actor','audit','auth','identity','ingest','integrations','interaction','ops','phi');")"

if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  fail "schema set mismatch — expected: [$EXPECTED]  actual: [$ACTUAL]"
fi
ok "all 9 schemas present"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

unset PGPASSWORD
unset DB_PASSWORD

cat <<EOF

================================================================
Bootstrap complete. Cloud SQL is initialised and at HEAD.

To open a psql session against prod from this laptop:
  cloud-sql-proxy $CLOUDSQL_INSTANCE_CONNECTION_NAME --port 5432 &
  PGPASSWORD=\$(gcloud secrets versions access latest --secret=db-password) \\
    psql -h 127.0.0.1 -U $DB_USER -d $DB_NAME

To run a future migration:
  cloud-sql-proxy $CLOUDSQL_INSTANCE_CONNECTION_NAME --port 5432 &
  DATABASE_URL_SYNC="postgresql+psycopg://...@127.0.0.1:5432/$DB_NAME" \\
    python -m alembic upgrade head

Or just re-run this script — it is idempotent.
================================================================
EOF
