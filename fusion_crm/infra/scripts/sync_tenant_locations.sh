#!/usr/bin/env bash
# Fusion CRM — sync tenant.location from CareStack.
#
# Idempotent — safe to run after every CareStack schema change or when
# bootstrapping a fresh environment. The endpoint resolves the tenant
# from ``Settings.tenant_default_slug`` (Phase 1 single-tenant), so the
# ``TENANT_SLUG`` here is sent only as a defence-in-depth assertion
# that the script is targeting the expected tenant.
#
# Required env (loaded from project .env or the shell):
#   API_BASE_URL                 default http://127.0.0.1:8001
#   TENANT_SLUG                  default fusion-dental-implants
#
# Usage:
#   ./infra/scripts/sync_tenant_locations.sh
#
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8001}"
TENANT_SLUG="${TENANT_SLUG:-fusion-dental-implants}"

echo "Syncing tenant.location for slug=${TENANT_SLUG} from ${API_BASE_URL}..."

curl -sf -X POST "${API_BASE_URL}/tenant/locations/sync-from-carestack" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_slug\":\"${TENANT_SLUG}\"}" \
  | jq '.'
