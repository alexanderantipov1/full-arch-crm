#!/usr/bin/env bash
# Provision the public HTTPS surface for the Fusion CRM production stack:
# global static IP + managed SSL certificate + serverless NEGs + IAP-enabled
# backend services + URL map + target HTTPS proxy + global forwarding rule
# + IAM allow-list bindings for roles/iap.httpsResourceAccessor.
#
# Per ADR-0002 (docs/decisions/ADR-0002-cloud-run-prod-runtime.md), sections
# "Access control: Cloud IAP in front of all services" and "Custom domain".
# This is the third of three bring-up scripts under the Cloud Run epic:
#   1. provision_cloud_run_foundation.sh  — ENG-114 (VPC, AR, WIF, etc.)
#   2. (Cloud Run service deploys)        — ENG-115 (fusion-api, fusion-web,
#                                                    fusion-worker)
#   3. provision_cloud_iap_lb.sh          — ENG-116 (THIS SCRIPT)
#
# This script makes the public surface real:
#   * Reserves the global static IP that DNS will point at.
#   * Issues a Google-managed SSL certificate for ${TENANT_DOMAIN}.
#   * Wires one Serverless NEG per public Cloud Run service (api + web).
#     The worker is internal-only — no NEG, no IAP, no public surface.
#   * Stands up two backend services with Cloud IAP enabled and attaches
#     the operator OAuth client.
#   * Path-routes /api/* to the API backend and /* to the web backend
#     via a single URL map so cookies stay single-origin.
#   * Adds the initial allow-list to roles/iap.httpsResourceAccessor on
#     each backend service.
#
# The script is **operator-runs-it**: it expects three secrets to be
# supplied via env vars (OAuth client ID + OAuth client secret + final
# tenant domain). It does NOT create the OAuth consent screen; that's a
# one-time manual click-through in the Cloud Console (see "OAuth consent
# screen" in infra/env/PRODUCTION.md).
#
# Idempotent: re-run after any failure. Each step is guarded with
# describe-or-create or tolerates ALREADY_EXISTS-style errors.
#
# Prerequisites:
#   * gcloud installed and authenticated (`gcloud auth login`).
#   * Owner or Editor on project fusioncrm-494201.
#   * `./infra/scripts/provision_cloud_run_foundation.sh` already executed
#     (this script does not enable APIs that the foundation already turned
#     on, but it does enable the LB- and IAP-specific ones).
#   * Cloud Run services `fusion-api` and `fusion-web` deployed in
#     ${REGION} (ENG-115). If they do not exist yet, the NEG creation step
#     will warn and the script will exit; deploy the services first, then
#     re-run.
#   * OAuth consent screen configured (Cloud Console → APIs & Services →
#     OAuth consent screen → user type **Internal**, organisation
#     `drantipov.com`). Internal type does not require a privacy-policy
#     URL or application-homepage URL.
#   * OAuth client of type "Web application" created. Authorised redirect
#     URI must be exactly
#     `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect`
#     — the Console pre-fills this once the client is saved. Copy the
#     client ID and client secret into the env vars listed below.
#
# Required env vars:
#   TENANT_DOMAIN       — final domain the LB serves. Operator must set this
#                         before the SSL cert can provision (DNS must point
#                         to the reserved static IP for Google to validate).
#                         Defaults to a placeholder so the script can be
#                         linted; the placeholder will NOT produce a working
#                         certificate.
#   IAP_OAUTH_CLIENT_ID — OAuth 2.0 client ID for the IAP brand.
#   IAP_OAUTH_CLIENT_SECRET — Matching client secret.
#
# Usage:
#   TENANT_DOMAIN=app.example.com \
#   IAP_OAUTH_CLIENT_ID=123-abc.apps.googleusercontent.com \
#   IAP_OAUTH_CLIENT_SECRET='GOCSPX-...' \
#     ./infra/scripts/provision_cloud_iap_lb.sh
#
# What it does NOT do:
#   * Create or modify the OAuth consent screen — operator click-through.
#   * Create the OAuth client — operator click-through (one-time).
#   * Touch DNS — operator points an A record at the reserved static IP
#     using their existing DNS provider (or Cloud DNS — see runbook).
#   * Deploy or modify Cloud Run services — ENG-115 owns that surface.
#   * Rotate or replace the managed SSL certificate — Google handles
#     renewal automatically as long as DNS keeps resolving to the LB IP.
#   * Delete any backend-service / URL-map / forwarding-rule resources.
#     Destructive ops are intentionally out of scope. If a misconfigured
#     resource needs to go, the operator runs the delete by hand.
#   * Touch any apps/ or packages/ code. Scripts + docs only.
#
# Cost note: the global forwarding rule + target HTTPS proxy + URL map
# combination starts billing the HTTPS LB (~$18/mo per ADR-0002 §Costs)
# the moment it serves a request. Cloud IAP is free under 1M
# authenticated requests/month, which is far above Phase 1 volume.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"

# Default placeholder per ADR-0002. Operator MUST set TENANT_DOMAIN to the
# real domain before DNS / certificate provisioning will succeed.
TENANT_DOMAIN="${TENANT_DOMAIN:-app.fusioncrm.example}"

# Cloud Run service names match those deployed by ENG-115.
API_SERVICE="${API_SERVICE:-fusion-api}"
WEB_SERVICE="${WEB_SERVICE:-fusion-web}"

# LB-level resource names. Keep the `fusion-lb-` prefix so a single
# `gcloud compute ... list | grep fusion-lb-` lists the whole surface.
STATIC_IP_NAME="${STATIC_IP_NAME:-fusion-lb-ip}"
SSL_CERT_NAME="${SSL_CERT_NAME:-fusion-lb-cert}"

API_NEG_NAME="${API_NEG_NAME:-fusion-lb-neg-api}"
WEB_NEG_NAME="${WEB_NEG_NAME:-fusion-lb-neg-web}"

API_BACKEND_NAME="${API_BACKEND_NAME:-fusion-lb-backend-api}"
WEB_BACKEND_NAME="${WEB_BACKEND_NAME:-fusion-lb-backend-web}"

URL_MAP_NAME="${URL_MAP_NAME:-fusion-lb-url-map}"
HTTPS_PROXY_NAME="${HTTPS_PROXY_NAME:-fusion-lb-https-proxy}"
FORWARDING_RULE_NAME="${FORWARDING_RULE_NAME:-fusion-lb-forwarding-rule}"

# IAP OAuth credentials. The script will refuse to enable IAP without both.
IAP_OAUTH_CLIENT_ID="${IAP_OAUTH_CLIENT_ID:-}"
IAP_OAUTH_CLIENT_SECRET="${IAP_OAUTH_CLIENT_SECRET:-}"

# Initial IAP allow-list. Per ADR-0002 §"Access control".
# Future: a Google Group (e.g. `group:clinic-staff@drantipov.com`) will
# replace the individual user bindings once Workspace groups are set up.
#
# The cloud-build-deployer-sa entry (ENG-178 Phase 4.2) is required so
# the deploy-prod workflow's post-deploy smoke can reach
# `https://fusioncrm.app/api/*` through IAP using a self-impersonated
# identity token (audience = IAP OAuth client ID). Without it, IAP
# returns 403 to the CI runner and traffic auto-rollback fires on every
# push. The grant is uniform across api + web backends; the web
# index-page smoke also benefits from authenticated access.
IAP_ALLOWED_PRINCIPALS_DEFAULT=(
  "user:drantipov@drantipov.com"
  "user:eduard@drantipov.com"
  "serviceAccount:cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com"
)
# Override via env: space-separated list, same prefixed format
# ("user:..." / "group:..." / "serviceAccount:...").
if [[ -n "${IAP_ALLOWED_PRINCIPALS:-}" ]]; then
  # shellcheck disable=SC2206
  IAP_ALLOWED_PRINCIPALS_ARR=( ${IAP_ALLOWED_PRINCIPALS} )
else
  IAP_ALLOWED_PRINCIPALS_ARR=( "${IAP_ALLOWED_PRINCIPALS_DEFAULT[@]}" )
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!! %s\033[0m\n" "$*" >&2; }
ok() { printf "   \033[0;32m+ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31mxx %s\033[0m\n" "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

require gcloud

log "Setting active project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID" --quiet >/dev/null
ok "active project: $(gcloud config get-value project)"

if [[ "$TENANT_DOMAIN" == "app.fusioncrm.example" ]]; then
  warn "TENANT_DOMAIN is still the placeholder 'app.fusioncrm.example'."
  warn "The managed certificate WILL NOT provision against a fake domain."
  warn "Re-run with TENANT_DOMAIN=<real-domain> once the operator has"
  warn "picked the final domain. Continuing so subsequent describe steps"
  warn "can prove idempotency, but the cert will stay in FAILED_NOT_VISIBLE."
fi

if [[ -z "$IAP_OAUTH_CLIENT_ID" || -z "$IAP_OAUTH_CLIENT_SECRET" ]]; then
  fail "IAP_OAUTH_CLIENT_ID and IAP_OAUTH_CLIENT_SECRET must be set.
       See the 'OAuth consent screen setup' section of
       infra/env/PRODUCTION.md for the one-time Console walkthrough."
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" \
  --format='value(projectNumber)')"
if [[ -z "$PROJECT_NUMBER" ]]; then
  fail "Could not resolve project number for $PROJECT_ID"
fi
ok "project number: $PROJECT_NUMBER"

# ---------------------------------------------------------------------------
# 1. Enable required APIs
# ---------------------------------------------------------------------------

log "Enabling required APIs"
gcloud services enable \
  compute.googleapis.com \
  iap.googleapis.com \
  certificatemanager.googleapis.com \
  --quiet
ok "APIs enabled (compute, iap, certificatemanager)"

# ---------------------------------------------------------------------------
# 2. Global static IP
# ---------------------------------------------------------------------------

log "Reserving global static IP $STATIC_IP_NAME"
if gcloud compute addresses describe "$STATIC_IP_NAME" \
     --global >/dev/null 2>&1; then
  ok "static IP exists: $STATIC_IP_NAME"
else
  gcloud compute addresses create "$STATIC_IP_NAME" \
    --global \
    --ip-version=IPV4 \
    --quiet
  ok "static IP reserved: $STATIC_IP_NAME"
fi

STATIC_IP_ADDR="$(gcloud compute addresses describe "$STATIC_IP_NAME" \
  --global --format='value(address)')"
if [[ -z "$STATIC_IP_ADDR" ]]; then
  fail "Could not resolve reserved IP address for $STATIC_IP_NAME"
fi
ok "static IP address: $STATIC_IP_ADDR"

# ---------------------------------------------------------------------------
# 3. Managed SSL certificate
# ---------------------------------------------------------------------------
#
# Google-managed certs provision asynchronously. The cert resource is
# created immediately, but the underlying certificate moves through
# PROVISIONING -> ACTIVE only after DNS for ${TENANT_DOMAIN} resolves to
# $STATIC_IP_ADDR and Google can complete the HTTP-01-style validation.
# Expect 15-60 minutes between DNS pointer and ACTIVE state. Re-run this
# script any time; the resource is idempotent.

log "Creating managed SSL certificate $SSL_CERT_NAME for $TENANT_DOMAIN"
if gcloud compute ssl-certificates describe "$SSL_CERT_NAME" \
     --global >/dev/null 2>&1; then
  EXISTING_DOMAINS="$(gcloud compute ssl-certificates describe "$SSL_CERT_NAME" \
    --global --format='value(managed.domains)' 2>/dev/null || true)"
  if [[ "$EXISTING_DOMAINS" != *"$TENANT_DOMAIN"* ]]; then
    warn "Existing cert $SSL_CERT_NAME covers domains: $EXISTING_DOMAINS"
    warn "Target domain $TENANT_DOMAIN is NOT among them."
    warn "Managed certs cannot be edited in place — to change the domain,"
    warn "the operator must (a) create a new cert resource under a"
    warn "different name, (b) swap it onto the target HTTPS proxy, and"
    warn "(c) delete the old cert by hand. This script does not perform"
    warn "destructive resource deletes."
  fi
  ok "SSL cert exists: $SSL_CERT_NAME (domains: $EXISTING_DOMAINS)"
else
  gcloud compute ssl-certificates create "$SSL_CERT_NAME" \
    --global \
    --domains="$TENANT_DOMAIN" \
    --quiet
  ok "SSL cert created: $SSL_CERT_NAME (domain: $TENANT_DOMAIN)"
fi

# ---------------------------------------------------------------------------
# 4. Serverless NEGs — one per public Cloud Run service
# ---------------------------------------------------------------------------
#
# A Serverless NEG is a *pointer* to a Cloud Run service. It costs nothing
# on its own; the LB references it through a backend service. Worker is
# internal-only and gets no NEG.

ensure_cloud_run_service_exists() {
  local service="$1"
  if ! gcloud run services describe "$service" \
        --region="$REGION" >/dev/null 2>&1; then
    warn "Cloud Run service $service not found in $REGION."
    warn "Deploy it via ENG-115 first, then re-run this script."
    return 1
  fi
  return 0
}

create_serverless_neg() {
  local neg_name="$1"
  local service="$2"

  log "Creating Serverless NEG $neg_name -> Cloud Run service $service ($REGION)"
  if ! ensure_cloud_run_service_exists "$service"; then
    fail "Pre-requisite Cloud Run service missing: $service"
  fi
  if gcloud compute network-endpoint-groups describe "$neg_name" \
       --region="$REGION" >/dev/null 2>&1; then
    ok "NEG exists: $neg_name"
  else
    gcloud compute network-endpoint-groups create "$neg_name" \
      --region="$REGION" \
      --network-endpoint-type=serverless \
      --cloud-run-service="$service" \
      --quiet
    ok "NEG created: $neg_name"
  fi
}

create_serverless_neg "$API_NEG_NAME" "$API_SERVICE"
create_serverless_neg "$WEB_NEG_NAME" "$WEB_SERVICE"

# ---------------------------------------------------------------------------
# 5. Backend services with Cloud IAP enabled
# ---------------------------------------------------------------------------
#
# Backend services are the LB-side object that:
#   * holds the NEG reference
#   * carries the IAP toggle + OAuth client credentials
#   * is the IAM target for roles/iap.httpsResourceAccessor
#
# `--iap=enabled,oauth2-client-id=...,oauth2-client-secret=...` is the
# single supported syntax for turning IAP on with a custom OAuth brand.

create_or_update_backend_service() {
  local backend_name="$1"
  local neg_name="$2"

  log "Creating/updating backend service $backend_name -> NEG $neg_name (IAP on)"
  if gcloud compute backend-services describe "$backend_name" \
       --global >/dev/null 2>&1; then
    ok "backend service exists: $backend_name"
  else
    # Serverless NEG-backed services don't accept a portName; passing
    # --protocol=HTTPS auto-resolves portName=https and the subsequent
    # add-backend call fails with "Port name is not supported for a
    # backend service with Serverless network endpoint groups."
    # Leave --protocol unset for serverless backends; gcloud defaults
    # correctly.
    gcloud compute backend-services create "$backend_name" \
      --global \
      --load-balancing-scheme=EXTERNAL_MANAGED \
      --quiet
    ok "backend service created: $backend_name"
  fi

  # Attach the NEG (no-op if already attached; tolerate error class).
  if gcloud compute backend-services describe "$backend_name" \
       --global --format='value(backends[].group)' 2>/dev/null \
       | grep -q "/$neg_name\b"; then
    ok "  NEG $neg_name already attached"
  else
    gcloud compute backend-services add-backend "$backend_name" \
      --global \
      --network-endpoint-group="$neg_name" \
      --network-endpoint-group-region="$REGION" \
      --quiet
    ok "  attached NEG $neg_name"
  fi

  # Enable IAP. The `update` call with --iap=... is idempotent — gcloud
  # diffs current vs desired and no-ops when they match. The OAuth client
  # ID + secret are re-applied on every run; this lets the operator rotate
  # the OAuth secret simply by re-running the script with new env vars.
  gcloud compute backend-services update "$backend_name" \
    --global \
    --iap="enabled,oauth2-client-id=${IAP_OAUTH_CLIENT_ID},oauth2-client-secret=${IAP_OAUTH_CLIENT_SECRET}" \
    --quiet
  ok "  IAP enabled on $backend_name"
}

create_or_update_backend_service "$API_BACKEND_NAME" "$API_NEG_NAME"
create_or_update_backend_service "$WEB_BACKEND_NAME" "$WEB_NEG_NAME"

# ---------------------------------------------------------------------------
# 6. URL map with path routing
# ---------------------------------------------------------------------------
#
# /api/*  -> backend-api
# /*      -> backend-web   (default backend)
#
# Single-origin cookies survive this because everything is served from
# ${TENANT_DOMAIN}. If a future split-domain layout is needed (e.g.
# api.${TENANT_DOMAIN}), this is the place to fork host rules.

log "Creating URL map $URL_MAP_NAME (default=web, /api/*=api)"
if gcloud compute url-maps describe "$URL_MAP_NAME" \
     --global >/dev/null 2>&1; then
  ok "URL map exists: $URL_MAP_NAME"
else
  gcloud compute url-maps create "$URL_MAP_NAME" \
    --default-service="$WEB_BACKEND_NAME" \
    --global \
    --quiet
  ok "URL map created: $URL_MAP_NAME (default=$WEB_BACKEND_NAME)"
fi

# The path-matcher rule routes /api/* to the API backend. Use
# `add-path-matcher` first time; on re-run we update the matcher in place
# via `remove-path-matcher` + `add-path-matcher` (safe — no live traffic
# is interrupted because the URL map is global and atomic on apply).
PATH_MATCHER_NAME="fusion-path-matcher"
EXISTING_HOST_RULES="$(gcloud compute url-maps describe "$URL_MAP_NAME" \
  --global --format='value(hostRules[].pathMatcher)' 2>/dev/null || true)"

if echo "$EXISTING_HOST_RULES" | grep -q "$PATH_MATCHER_NAME"; then
  ok "  path matcher $PATH_MATCHER_NAME already wired"
else
  gcloud compute url-maps add-path-matcher "$URL_MAP_NAME" \
    --global \
    --path-matcher-name="$PATH_MATCHER_NAME" \
    --default-service="$WEB_BACKEND_NAME" \
    --new-hosts="$TENANT_DOMAIN" \
    --backend-service-path-rules="/api/*=${API_BACKEND_NAME}" \
    --quiet
  ok "  path matcher $PATH_MATCHER_NAME added (/api/* -> $API_BACKEND_NAME)"
fi

# ---------------------------------------------------------------------------
# 7. Target HTTPS proxy + global forwarding rule
# ---------------------------------------------------------------------------

log "Creating target HTTPS proxy $HTTPS_PROXY_NAME"
if gcloud compute target-https-proxies describe "$HTTPS_PROXY_NAME" \
     --global >/dev/null 2>&1; then
  ok "HTTPS proxy exists: $HTTPS_PROXY_NAME"
else
  gcloud compute target-https-proxies create "$HTTPS_PROXY_NAME" \
    --url-map="$URL_MAP_NAME" \
    --ssl-certificates="$SSL_CERT_NAME" \
    --global \
    --quiet
  ok "HTTPS proxy created: $HTTPS_PROXY_NAME"
fi

log "Creating global forwarding rule $FORWARDING_RULE_NAME (port 443 -> proxy)"
if gcloud compute forwarding-rules describe "$FORWARDING_RULE_NAME" \
     --global >/dev/null 2>&1; then
  ok "forwarding rule exists: $FORWARDING_RULE_NAME"
else
  gcloud compute forwarding-rules create "$FORWARDING_RULE_NAME" \
    --address="$STATIC_IP_NAME" \
    --target-https-proxy="$HTTPS_PROXY_NAME" \
    --global \
    --ports=443 \
    --load-balancing-scheme=EXTERNAL_MANAGED \
    --quiet
  ok "forwarding rule created: $FORWARDING_RULE_NAME ($STATIC_IP_ADDR:443)"
fi

# ---------------------------------------------------------------------------
# 8. IAM allow-list bindings on each backend service
# ---------------------------------------------------------------------------
#
# roles/iap.httpsResourceAccessor on the backend-service resource is what
# IAP checks when a user shows up. We bind the initial allow-list per
# ADR-0002 §"Access control: Initial allow-list".

grant_iap_access() {
  local backend_name="$1"
  local principal="$2"
  gcloud iap web add-iam-policy-binding \
    --resource-type=backend-services \
    --service="$backend_name" \
    --member="$principal" \
    --role=roles/iap.httpsResourceAccessor \
    --quiet >/dev/null
  ok "  $principal -> roles/iap.httpsResourceAccessor on $backend_name"
}

log "Binding IAP allow-list to $API_BACKEND_NAME and $WEB_BACKEND_NAME"
for principal in "${IAP_ALLOWED_PRINCIPALS_ARR[@]}"; do
  grant_iap_access "$API_BACKEND_NAME" "$principal"
  grant_iap_access "$WEB_BACKEND_NAME" "$principal"
done

# ---------------------------------------------------------------------------
# 9. Output
# ---------------------------------------------------------------------------

CERT_STATE="$(gcloud compute ssl-certificates describe "$SSL_CERT_NAME" \
  --global --format='value(managed.status)' 2>/dev/null || echo UNKNOWN)"
CERT_DOMAIN_STATE="$(gcloud compute ssl-certificates describe "$SSL_CERT_NAME" \
  --global --format='value(managed.domainStatus)' 2>/dev/null || echo UNKNOWN)"

cat <<EOF

====================================================
Cloud IAP + HTTPS LB provisioning complete.

Static IP ............ $STATIC_IP_NAME ($STATIC_IP_ADDR)
SSL cert ............. $SSL_CERT_NAME ($TENANT_DOMAIN)
  cert status ........ $CERT_STATE
  domain status ...... $CERT_DOMAIN_STATE
Serverless NEGs ...... $API_NEG_NAME -> $API_SERVICE
                       $WEB_NEG_NAME -> $WEB_SERVICE
Backend services ..... $API_BACKEND_NAME (IAP on)
                       $WEB_BACKEND_NAME (IAP on)
URL map .............. $URL_MAP_NAME
  /api/* ............. $API_BACKEND_NAME
  /* ................. $WEB_BACKEND_NAME
HTTPS proxy .......... $HTTPS_PROXY_NAME
Forwarding rule ...... $FORWARDING_RULE_NAME ($STATIC_IP_ADDR:443)
IAP allow-list ....... ${IAP_ALLOWED_PRINCIPALS_ARR[*]}

Next steps for the operator:

  1. Point DNS at the static IP.
     Cloud DNS example:
       gcloud dns record-sets create $TENANT_DOMAIN. \\
         --rrdatas=$STATIC_IP_ADDR \\
         --type=A --ttl=300 \\
         --zone=<your-managed-zone> \\
         --project=$PROJECT_ID
     External DNS provider: create an A record for $TENANT_DOMAIN
     pointing to $STATIC_IP_ADDR (TTL 300).

  2. Wait 15-60 minutes for the managed cert to move
       PROVISIONING -> ACTIVE.
     Check with:
       gcloud compute ssl-certificates describe $SSL_CERT_NAME \\
         --global --project=$PROJECT_ID \\
         --format='value(managed.status,managed.domainStatus)'

  3. Smoke-test:
       curl -sSI https://$TENANT_DOMAIN/         # expect 302 -> Google Sign-In
       curl -sSI https://$TENANT_DOMAIN/api/healthz  # same 302 before auth

  4. Sign in via the browser as an allow-listed user. Re-issue the
     curl above with the IAP cookie / bearer token. Expect 200.

See infra/env/PRODUCTION.md -> "Provisioning the public surface" for
the full operator workflow.
====================================================
EOF
