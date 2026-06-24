#!/usr/bin/env bash
# Production deploy preflight (ENG-174 Phase 4 §A).
#
# Read-only safety net that runs BEFORE alembic-migrate + image build
# + service deploy on every push to main. Fails fast on any drift
# between Settings, production.env.reference, the canonical deploy
# script, and the live Cloud Run state.
#
# Closes the class of drift Phase 0–2 + the micro-fix all hit at
# different points:
#   * env contract drift (Phase 2 added a Python test for this; this
#     script ALSO runs it so a failure stops the workflow before
#     spending CI minutes on a doomed deploy);
#   * `localhost` / `http://` leaking into public production URLs;
#   * `fusion-worker` Cloud Run Service re-appearing after ENG-172;
#   * a Secret Manager secret renamed in code but not yet provisioned
#     in GCP;
#   * the alembic Cloud Run Job's `--command` / `--args` drifting from
#     the `sh -c "cd packages/db && python -m alembic upgrade head"`
#     contract we landed in ENG-161 Phase 0.
#
# Usage:
#   ./infra/scripts/preflight_prod.sh            # full check
#   STRICT=0 ./infra/scripts/preflight_prod.sh   # warn-only mode (CI bring-up)
#
# Exit codes:
#   0 — all checks pass
#   1 — at least one check failed; deploy must not proceed

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"

SVC_API="${SVC_API:-fusion-api}"
SVC_WORKER="${SVC_WORKER:-fusion-worker}"   # MUST NOT exist post-ENG-172
JOB_ALEMBIC="${JOB_ALEMBIC:-fusion-job-alembic-upgrade}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY_SCRIPT="${REPO_ROOT}/infra/scripts/deploy_cloud_run.sh"
ENV_REFERENCE="${REPO_ROOT}/infra/env/production.env.reference"
ENV_CONTRACT_TEST="${REPO_ROOT}/tests/core/test_env_reference_matches_settings.py"

# Public URLs that MUST be https://fusioncrm.app in prod.
# Mirrors REQUIRED_PRODUCTION_CONTRACT in the env contract test.
# NEXT_PUBLIC_API_BASE_URL is intentionally excluded — at runtime on
# fusion-web it points at the DIRECT fusion-api Cloud Run URL (the
# build-time bake-in via docker --build-arg is what's
# fusioncrm.app for the browser rewrite manifest, per ENG-158).
PUBLIC_URL_KEYS=(
  OAUTH_REDIRECT_BASE_URL
  WEB_APP_BASE_URL
  SALESFORCE_CALLBACK_URL
  TRACKING_BASE_URL
  API_CORS_ORIGINS
  WEB_CORS_ORIGINS
)

STRICT="${STRICT:-1}"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

log()  { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
ok()   { printf "   \033[0;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "   \033[1;33m!! %s\033[0m\n" "$*" >&2; }
fail() { printf "   \033[1;31mxx %s\033[0m\n" "$*" >&2; FAILED=$((FAILED + 1)); }

require() {
  command -v "$1" >/dev/null 2>&1 || { printf "Required command not found: %s\n" "$1" >&2; exit 1; }
}

FAILED=0

# -----------------------------------------------------------------------------
# Preflight checks
# -----------------------------------------------------------------------------

require gcloud
require python3

log "ENG-174 production deploy preflight"
ok "project: $PROJECT_ID  region: $REGION"

# ---------------------------------------------------------------------------
# Check 1 — env contract drift test
# ---------------------------------------------------------------------------
log "Check 1/6 — env contract drift test"
if [[ ! -f "$ENV_CONTRACT_TEST" ]]; then
  fail "env contract test missing: $ENV_CONTRACT_TEST"
else
  # Run the Phase 2 drift test directly. -q for compact output, no
  # warnings. Failure here = Settings drifted from production.env.reference
  # or from API_ENV_VARS in deploy_cloud_run.sh.
  if python3 -m pytest "$ENV_CONTRACT_TEST" -q --no-header 2>&1 | tail -3; then
    ok "env contract: Settings ↔ reference ↔ deploy script aligned"
  else
    fail "env contract drift — see pytest output above"
  fi
fi

# ---------------------------------------------------------------------------
# Check 2 — no localhost / http:// in public production URLs
# ---------------------------------------------------------------------------
log "Check 2/6 — public URL contract (no localhost, no http://)"
API_ENV_CSV="$(grep -E '^API_ENV_VARS=' "$DEPLOY_SCRIPT" | sed -E 's/^API_ENV_VARS="(.*)"$/\1/')"

for key in "${PUBLIC_URL_KEYS[@]}"; do
  value="$(printf '%s' "$API_ENV_CSV" | tr ',' '\n' | awk -F= -v k="$key" '$1==k {print $2; exit}')"
  if [[ -z "$value" ]]; then
    fail "$key not set in API_ENV_VARS in deploy_cloud_run.sh"
    continue
  fi
  case "$value" in
    *localhost*|*127.0.0.1*|*0.0.0.0*)
      fail "$key contains localhost/loopback: $value" ;;
    http://*)
      fail "$key uses http:// in prod: $value" ;;
    https://*)
      ok "$key = $value" ;;
    *)
      fail "$key has unexpected shape (not https://): $value" ;;
  esac
done

# ---------------------------------------------------------------------------
# Check 3 — fusion-worker Cloud Run Service must not exist (ENG-172)
# ---------------------------------------------------------------------------
log "Check 3/6 — fusion-worker Cloud Run Service is absent"
if gcloud run services describe "$SVC_WORKER" \
     --project="$PROJECT_ID" --region="$REGION" >/dev/null 2>&1; then
  fail "$SVC_WORKER still exists as a Cloud Run Service — ENG-172 operator step incomplete. Run: gcloud run services delete $SVC_WORKER --region=$REGION --project=$PROJECT_ID --quiet"
else
  ok "$SVC_WORKER is absent (correct)"
fi

# ---------------------------------------------------------------------------
# Check 4 — Secret Manager presence for every --set-secrets entry
# ---------------------------------------------------------------------------
log "Check 4/6 — Secret Manager presence for --set-secrets references"
# Match lines like:
#   API_SECRETS="SECRET_KEY=app-secret-key:latest,DB_PASSWORD=db-password:latest,..."
# Extract the GCP secret names (right side of each "=", before ":").
# Use a portable here-string loop instead of `mapfile` (bash 3.x on macOS
# does not have mapfile).
SECRET_REFS_OUT="$(
  grep -E '^(API_SECRETS|JOB_SECRETS|[[:space:]]*web_secrets)=' "$DEPLOY_SCRIPT" \
    | sed -E 's/^[[:space:]]*[A-Za-z_]+=//' \
    | tr -d '"' \
    | tr ',' '\n' \
    | awk -F= 'NF==2 {print $2}' \
    | awk -F: '{print $1}' \
    | sort -u
)"
if [[ -z "$SECRET_REFS_OUT" ]]; then
  warn "No --set-secrets references parsed from deploy script (skipping)"
else
  while IFS= read -r secret; do
    [[ -z "$secret" ]] && continue
    if gcloud secrets versions list "$secret" \
         --project="$PROJECT_ID" \
         --filter='state=ENABLED' \
         --format='value(name)' --limit=1 2>/dev/null | grep -q .; then
      ok "secret enabled: $secret"
    else
      fail "secret missing or no enabled version: $secret"
    fi
  done <<< "$SECRET_REFS_OUT"
fi

# ---------------------------------------------------------------------------
# Check 5 — alembic Job command shape
# ---------------------------------------------------------------------------
log "Check 5/6 — alembic Job command shape"
ALEMBIC_CMD_ARGS="$(gcloud run jobs describe "$JOB_ALEMBIC" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].command,spec.template.spec.template.spec.containers[0].args)' 2>/dev/null || true)"
if [[ -z "$ALEMBIC_CMD_ARGS" ]]; then
  fail "alembic Job $JOB_ALEMBIC missing or unreadable"
elif echo "$ALEMBIC_CMD_ARGS" | grep -q 'cd packages/db'; then
  ok "alembic Job command runs from packages/db (ENG-161 contract)"
else
  fail "alembic Job command does NOT contain 'cd packages/db' — re-run deploy_cloud_run.sh (without CI_MODE=1) to push the correct command, OR run the targeted gcloud run jobs update from PR #60. Current: $ALEMBIC_CMD_ARGS"
fi

# ---------------------------------------------------------------------------
# Check 6 — fusion-api dry-run describe
# ---------------------------------------------------------------------------
log "Check 6/6 — fusion-api describe sanity (VPC/SA still bound)"
API_DESCRIBE="$(gcloud run services describe "$SVC_API" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(spec.template.spec.serviceAccountName,spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector")' 2>/dev/null || true)"
if [[ -z "$API_DESCRIBE" ]]; then
  fail "$SVC_API describe failed — service missing or no read permission"
else
  if echo "$API_DESCRIBE" | grep -q 'fusion-api-sa'; then
    ok "$SVC_API still bound to fusion-api-sa"
  else
    fail "$SVC_API serviceAccount drifted (expected fusion-api-sa): $API_DESCRIBE"
  fi
  if echo "$API_DESCRIBE" | grep -q 'fusion-vpc-connector'; then
    ok "$SVC_API still attached to fusion-vpc-connector"
  else
    fail "$SVC_API VPC connector drifted (expected fusion-vpc-connector): $API_DESCRIBE"
  fi
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo
if [[ "$FAILED" -gt 0 ]]; then
  printf "\033[1;31mPREFLIGHT FAILED: %d check(s) reported a problem.\033[0m\n" "$FAILED" >&2
  if [[ "$STRICT" == "1" ]]; then
    exit 1
  else
    printf "\033[1;33mSTRICT=0 → exiting 0 anyway (CI bring-up mode).\033[0m\n" >&2
  fi
else
  printf "\033[1;32mPREFLIGHT OK: all checks passed.\033[0m\n"
fi
