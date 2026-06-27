#!/usr/bin/env bash
# Start the Fusion CRM production stack via docker compose.
#
# Per ADR-0001 §"Configuration loader" — fetches the DB password from
# Secret Manager and exports it so DATABASE_URL{_SYNC} can interpolate
# it. App-level secrets (SECRET_KEY, ENCRYPTION_KEY, OAuth secrets) are
# resolved inside the app via packages/core/secrets.py.
#
# Usage:
#   ./infra/scripts/start_prod.sh [up|down|logs|...]
#
# Defaults to `up -d`.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker/docker-compose.prod.yml"
ENV_FILE="$(cd "$(dirname "$0")/../.." && pwd)/.env.production"

[[ -f "$COMPOSE_FILE" ]] || { echo "missing $COMPOSE_FILE" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE — copy from .env.production.template" >&2; exit 1; }

echo "==> Fetching DB password from Secret Manager"
DB_PASSWORD="$(gcloud secrets versions access latest \
  --secret=db-password --project="$PROJECT_ID")"
[[ -n "$DB_PASSWORD" ]] || { echo "db-password is empty" >&2; exit 1; }
export DB_PASSWORD

echo "==> Starting prod stack"
exec docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "${@:-up -d}"
