#!/usr/bin/env bash
# Provision Cloud Monitoring alert policies + a single email notification
# channel for the Fusion CRM ingestion pipeline (ENG-327).
#
# Scope:
#   * One email notification channel ("Fusion CRM ops — Eduard") that
#     fans out to eduard@drantipov.com.
#   * Per-job alert policies for the three recurring Cloud Run Jobs
#     fusion-job-cs-pull, fusion-job-sf-pull,
#     fusion-job-salesforce-token-keepalive:
#       (a) FAILED execution — fires on the first failed task attempt.
#       (b) NO SUCCESS within an SLO window — fires when no successful
#           task attempt has landed for longer than the job's normal
#           cadence + a safety factor (cs-pull 90m, sf-pull 45m,
#           keepalive 7h).
#   * A "freshness" alert tied to the per-tenant payment_freshness facet
#     of GET /health/ingest (ENG-327, Deliverable #2). Implemented as a
#     log-based metric on the structured access-log line that the API
#     emits when a freshness probe reports `status="stale"`, with the
#     alert filtered to OFF during clinic-closed hours documented inline.
#
# Idempotent: every notification-channel + alert-policy upsert uses
# describe-or-create against a stable display name. Re-runs converge.
#
# AUTHOR-ONLY: this script is repo-encoded infrastructure intended for an
# operator to run by hand. It is NOT wired into deploy-prod.yml — per
# docs/DEPLOYMENT_RULES.md §9 ("Keep feature work separate from
# infrastructure"), monitoring provisioning happens out-of-band.
#
# Usage:
#   ./infra/scripts/provision_monitoring.sh
#
# Re-run safely any time; idempotent.

set -euo pipefail

# Single global EXIT trap that cleans every temp file the script can
# create. Declared with `:-` defaults so the trap is safe under `set -u`
# even when it fires before the variable is assigned (e.g. an early
# gcloud failure aborts the script before `mktemp` runs). `payload_tmp`
# is reused per-job inside `provision_job_alerts` — that loop still owns
# its own `rm -f`, but the trap is the safety net under mid-loop abort.
CHANNEL_TMP=""
payload_tmp=""
FRESHNESS_PAYLOAD_TMP=""
trap 'rm -f "${CHANNEL_TMP:-}" "${payload_tmp:-}" "${FRESHNESS_PAYLOAD_TMP:-}"' EXIT

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ID="${PROJECT_ID:-fusioncrm-494201}"
REGION="${REGION:-us-west1}"
ALERT_EMAIL="${ALERT_EMAIL:-eduard@drantipov.com}"
CHANNEL_DISPLAY_NAME="${CHANNEL_DISPLAY_NAME:-Fusion CRM ops — Eduard}"

# Cloud Run Job names — match deploy_cloud_run.sh constants so the alert
# filters point at the exact resources the deploy script creates.
JOB_CS_PULL="${JOB_CS_PULL:-fusion-job-cs-pull}"
JOB_SF_PULL="${JOB_SF_PULL:-fusion-job-sf-pull}"
JOB_SF_KEEPALIVE="${JOB_SF_KEEPALIVE:-fusion-job-salesforce-token-keepalive}"

# Per-job SLO windows (minutes) for the "no success within N" alerts.
# Each is the job's scheduled cadence plus a safety factor large enough
# that a single missed run does not page.
CS_PULL_SLO_MIN="${CS_PULL_SLO_MIN:-90}"      # cadence */30 -> 90m tolerates two misses.
SF_PULL_SLO_MIN="${SF_PULL_SLO_MIN:-45}"      # cadence */15 -> 45m tolerates two misses.
KEEPALIVE_SLO_MIN="${KEEPALIVE_SLO_MIN:-420}" # cadence every 6h -> 7h tolerates one miss.

# Log-based metric for payment-freshness "stale" reports. The API logs a
# structured access entry on every /health/ingest probe (see
# apps/api/middleware.py RequestContextMiddleware). When the freshness
# block reports status="stale" we want a metric tick; the alert then
# fires when those ticks exceed zero in the rolling window.
FRESHNESS_METRIC="${FRESHNESS_METRIC:-fusion_payment_freshness_stale}"

# ---------------------------------------------------------------------------
# Helpers — mirror deploy_cloud_run.sh log/warn/ok/fail/require shape.
# ---------------------------------------------------------------------------

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m!! %s\033[0m\n" "$*" >&2; }
ok() { printf "   \033[0;32m✓ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31mxx %s\033[0m\n" "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

require gcloud
require python3

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

log "Setting active project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null
ok "active project: $(gcloud config get-value project)"

log "Enabling monitoring + logging APIs"
gcloud services enable \
  monitoring.googleapis.com \
  logging.googleapis.com \
  --quiet
ok "APIs enabled"

# ---------------------------------------------------------------------------
# Notification channel (describe-or-create by display name)
# ---------------------------------------------------------------------------
#
# `gcloud beta monitoring channels` does not support describe-by-name
# directly; we list, filter on displayName, then create when missing.

resolve_channel_id() {
  # Returns the full notification channel resource ID for the channel
  # matching ${CHANNEL_DISPLAY_NAME}, or the empty string when missing.
  gcloud beta monitoring channels list \
    --filter="displayName=\"$CHANNEL_DISPLAY_NAME\"" \
    --format='value(name)' 2>/dev/null | head -n1
}

log "Upserting email notification channel: $CHANNEL_DISPLAY_NAME"
CHANNEL_ID="$(resolve_channel_id || true)"

if [[ -z "$CHANNEL_ID" ]]; then
  CHANNEL_PAYLOAD="$(python3 - "$CHANNEL_DISPLAY_NAME" "$ALERT_EMAIL" <<'PY'
import json, sys
display, email = sys.argv[1], sys.argv[2]
print(json.dumps({
    "type": "email",
    "displayName": display,
    "description": "Fusion CRM ingestion alerts (ENG-327). Email-only.",
    "labels": {"email_address": email},
    "enabled": True,
}))
PY
)"
  CHANNEL_TMP="$(mktemp)"
  printf '%s' "$CHANNEL_PAYLOAD" >"$CHANNEL_TMP"
  gcloud beta monitoring channels create \
    --channel-content-from-file="$CHANNEL_TMP" \
    --quiet >/dev/null
  CHANNEL_ID="$(resolve_channel_id)"
  [[ -n "$CHANNEL_ID" ]] || fail "failed to create channel $CHANNEL_DISPLAY_NAME"
  ok "channel created: $CHANNEL_ID"
else
  ok "channel exists: $CHANNEL_ID"
fi

# ---------------------------------------------------------------------------
# Alert policy upsert helper
# ---------------------------------------------------------------------------
#
# Each alert policy is identified by displayName. We list-filter to find
# the existing policy, then create when missing. We do NOT auto-update
# policies in place: alert thresholds matter and silent edits would
# create a bad "I changed it but the policy still fires the old way"
# loop. Operators delete the policy in the Console (or via `policies
# delete`) when they want to re-provision with new defaults.

upsert_policy() {
  # upsert_policy <display-name> <policy-json-file>
  local display="$1"
  local payload_file="$2"
  local existing
  existing="$(gcloud alpha monitoring policies list \
    --filter="displayName=\"$display\"" \
    --format='value(name)' 2>/dev/null | head -n1 || true)"
  if [[ -n "$existing" ]]; then
    ok "policy exists: $display ($existing)"
    return 0
  fi
  log "Creating alert policy: $display"
  gcloud alpha monitoring policies create \
    --policy-from-file="$payload_file" \
    --quiet >/dev/null
  ok "policy created: $display"
}

emit_policy_json() {
  # emit_policy_json <display-name> <documentation> <channel-id> <conditions-json>
  python3 - "$1" "$2" "$3" "$4" <<'PY'
import json, sys
display, doc, channel, conditions_raw = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
print(json.dumps({
    "displayName": display,
    "documentation": {
        "content": doc,
        "mimeType": "text/markdown",
    },
    "combiner": "OR",
    "conditions": json.loads(conditions_raw),
    "notificationChannels": [channel],
    "enabled": True,
}))
PY
}

# ---------------------------------------------------------------------------
# Per-job alert policies — execution FAILED
# ---------------------------------------------------------------------------
#
# Metric: run.googleapis.com/job/completed_task_attempt_count, filtered
# to result="failed" and the specific job_name. Threshold > 0 over 1m
# fires immediately on any failed task attempt. Cloud Run Jobs retry
# per `--max-retries=1` in deploy_cloud_run.sh, so an attempt failure
# is the truthful signal — if both attempts fail the metric ticks twice.

failed_attempt_conditions() {
  local job_name="$1"
  local display="$2"
  python3 - "$job_name" "$display" <<'PY'
import json, sys
job_name, display = sys.argv[1], sys.argv[2]
print(json.dumps([{
    "displayName": display,
    "conditionThreshold": {
        "filter": (
            'metric.type="run.googleapis.com/job/completed_task_attempt_count" '
            'resource.type="cloud_run_job" '
            f'resource.label.job_name="{job_name}" '
            'metric.label.result="failed"'
        ),
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "60s",
        "aggregations": [{
            "alignmentPeriod": "60s",
            "perSeriesAligner": "ALIGN_SUM",
        }],
    },
}]))
PY
}

# ---------------------------------------------------------------------------
# Per-job alert policies — NO SUCCESS within SLO window
# ---------------------------------------------------------------------------
#
# Uses a "metric absence" condition on
# run.googleapis.com/job/completed_task_attempt_count filtered to
# result="succeeded". If no successful attempt lands inside the
# duration window, the condition fires. duration is expressed in
# seconds (Cloud Monitoring rejects bare minutes).

absence_conditions() {
  local job_name="$1"
  local display="$2"
  local window_seconds="$3"
  python3 - "$job_name" "$display" "$window_seconds" <<'PY'
import json, sys
job_name, display, window = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps([{
    "displayName": display,
    "conditionAbsent": {
        "filter": (
            'metric.type="run.googleapis.com/job/completed_task_attempt_count" '
            'resource.type="cloud_run_job" '
            f'resource.label.job_name="{job_name}" '
            'metric.label.result="succeeded"'
        ),
        "duration": f"{int(window) * 60}s",
        "aggregations": [{
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_SUM",
        }],
    },
}]))
PY
}

provision_job_alerts() {
  # provision_job_alerts <job-name> <slo-window-min>
  local job_name="$1"
  local window_min="$2"

  local failed_display="[Fusion] $job_name execution FAILED"
  local failed_doc
  failed_doc=$'Cloud Run Job '"$job_name"$' reported a FAILED task attempt.\n\nPlaybook: check the job logs in Cloud Logging ('"$job_name"$') and the most recent sync_run row in integrations.sync_run.\n\nSource: infra/scripts/provision_monitoring.sh (ENG-327).'
  # NOTE: intentionally NOT `local` — the file-scope `payload_tmp` is what the
  # global EXIT trap cleans, so a mid-function gcloud abort cannot leak it.
  payload_tmp="$(mktemp)"
  emit_policy_json "$failed_display" "$failed_doc" "$CHANNEL_ID" \
    "$(failed_attempt_conditions "$job_name" "$failed_display")" \
    >"$payload_tmp"
  upsert_policy "$failed_display" "$payload_tmp"
  rm -f "$payload_tmp"

  local absence_display
  absence_display="[Fusion] $job_name NO SUCCESS in ${window_min}m"
  local absence_doc
  absence_doc=$'Cloud Run Job '"$job_name"$' has not reported a successful task attempt within the SLO window.\n\nPlaybook: verify the Cloud Scheduler trigger is firing, check IAM for run.invoker, and inspect job logs for stuck runs.\n\nWindow: '"$window_min"$' minutes (set in provision_monitoring.sh — ENG-327).'
  payload_tmp="$(mktemp)"
  emit_policy_json "$absence_display" "$absence_doc" "$CHANNEL_ID" \
    "$(absence_conditions "$job_name" "$absence_display" "$window_min")" \
    >"$payload_tmp"
  upsert_policy "$absence_display" "$payload_tmp"
  rm -f "$payload_tmp"
}

log "Provisioning alert policies for the three ingestion jobs"
provision_job_alerts "$JOB_CS_PULL"      "$CS_PULL_SLO_MIN"
provision_job_alerts "$JOB_SF_PULL"      "$SF_PULL_SLO_MIN"
provision_job_alerts "$JOB_SF_KEEPALIVE" "$KEEPALIVE_SLO_MIN"

# ---------------------------------------------------------------------------
# Payment-freshness log-based metric + alert
# ---------------------------------------------------------------------------
#
# We don't currently emit a custom metric from the API for the freshness
# probe — Phase 1 keeps custom metrics out of the runtime. Instead, we
# define a log-based COUNTER metric that ticks whenever the API access
# log shows a /health/ingest response carrying `payment_freshness.last_payment.status="stale"`.
# The structured access log (apps/api/middleware.py) emits jsonPayload
# entries; the filter below selects them.
#
# Clinic-hours awareness lives in the API code (the route reports
# `quiet-hours` instead of `stale` outside the clinic window), so the
# log-based metric is implicitly clinic-hours-aware: no `stale` line is
# logged overnight, no metric tick, no alert. Cloud Monitoring does not
# need to express the window itself.

log "Upserting log-based metric: $FRESHNESS_METRIC"
LOG_FILTER='resource.type="cloud_run_revision" resource.labels.service_name="fusion-api" jsonPayload.payment_freshness_status="stale"'

if gcloud logging metrics describe "$FRESHNESS_METRIC" >/dev/null 2>&1; then
  ok "metric exists: $FRESHNESS_METRIC"
else
  gcloud logging metrics create "$FRESHNESS_METRIC" \
    --description="Count of /health/ingest probes reporting payment_freshness=stale (ENG-327)." \
    --log-filter="$LOG_FILTER" \
    --quiet >/dev/null
  ok "metric created: $FRESHNESS_METRIC"
fi

FRESHNESS_DISPLAY="[Fusion] CareStack payment freshness STALE"
FRESHNESS_DOC=$'API /health/ingest reported payment_freshness.last_payment.status="stale" — the latest payment_recorded event is older than the 3h threshold AND the clinic is currently open.\n\nPlaybook: inspect fusion-job-cs-pull logs, verify the CareStack accounting pull is succeeding, and confirm interaction.event rows are landing for the affected tenant.\n\nNote: the API downgrades to status="quiet-hours" outside clinic hours, so this alert is implicitly silenced overnight — no Cloud Monitoring schedule is needed. (ENG-327, provision_monitoring.sh.)'

# Threshold condition on the log-based metric: any tick > 0 in a 10m
# window fires the alert. The metric ticks once per /health/ingest probe
# that reports `stale`; the staff frontend polls /health/ingest every
# 60s so a single sustained stale window produces many ticks. The 10m
# alignment smooths transient false positives.
freshness_conditions() {
  python3 - "$FRESHNESS_METRIC" "$FRESHNESS_DISPLAY" <<'PY'
import json, sys
metric_name, display = sys.argv[1], sys.argv[2]
print(json.dumps([{
    "displayName": display,
    "conditionThreshold": {
        "filter": (
            f'metric.type="logging.googleapis.com/user/{metric_name}" '
            'resource.type="cloud_run_revision"'
        ),
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "600s",
        "aggregations": [{
            "alignmentPeriod": "600s",
            "perSeriesAligner": "ALIGN_SUM",
        }],
    },
}]))
PY
}

FRESHNESS_PAYLOAD_TMP="$(mktemp)"
emit_policy_json "$FRESHNESS_DISPLAY" "$FRESHNESS_DOC" "$CHANNEL_ID" \
  "$(freshness_conditions)" >"$FRESHNESS_PAYLOAD_TMP"
upsert_policy "$FRESHNESS_DISPLAY" "$FRESHNESS_PAYLOAD_TMP"
rm -f "$FRESHNESS_PAYLOAD_TMP"

cat <<EOF

====================================================
Cloud Monitoring provisioning complete.

Project ............ $PROJECT_ID
Notification ....... $CHANNEL_DISPLAY_NAME  ($ALERT_EMAIL)
Channel ID ......... $CHANNEL_ID

Policies installed (describe-or-create):
  [Fusion] $JOB_CS_PULL execution FAILED
  [Fusion] $JOB_CS_PULL NO SUCCESS in ${CS_PULL_SLO_MIN}m
  [Fusion] $JOB_SF_PULL execution FAILED
  [Fusion] $JOB_SF_PULL NO SUCCESS in ${SF_PULL_SLO_MIN}m
  [Fusion] $JOB_SF_KEEPALIVE execution FAILED
  [Fusion] $JOB_SF_KEEPALIVE NO SUCCESS in ${KEEPALIVE_SLO_MIN}m
  [Fusion] CareStack payment freshness STALE
                (log-based metric: $FRESHNESS_METRIC)

Re-running this script is safe — every step is describe-or-create.
====================================================
EOF
