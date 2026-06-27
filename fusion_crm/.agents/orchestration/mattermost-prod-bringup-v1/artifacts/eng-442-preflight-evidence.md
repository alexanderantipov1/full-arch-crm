# ENG-442 — DEPLOYMENT_RULES preflight evidence

Read-only evaluation run during the overnight 2026-06-17 session. This is the start-gate
evidence for ENG-442 ("do NOT start until ADR-0006 Accepted **and** DEPLOYMENT_RULES
preflight passes"). Items marked ⚠️ must be closed on the deploy branch before go-live.

## Start-gate

| Gate | Result | Evidence |
|---|---|---|
| ADR-0006 = Accepted | ✅ PASS | `docs/decisions/ADR-0006-interactive-messenger-layer.md` line 3: `**Status:** Accepted`, dated 2026-06-15. |
| Single alembic head | ⚠️ VERIFY ON MAIN | Dev checkout (`eng-481-full-funnel-v2-backend`) reports **6 heads**: `e6f7a8b9c0d1, a7b8c9d0e1f2, 4fe9f2b9f55a, 37f5ec4af909, b69bce1e2195, e3c4d5f6a7b8`, plus a "revision b69bce1e2195 present more than once" warning. Per memory `blocker_alembic_broken_chain_main.md` this is a **local multi-branch artifact**, not a real main-branch defect. **Action:** run `alembic heads` on a clean `main` checkout + fresh DB; the messenger chain itself is single-headed at `b69bce1e2195` (RUNBOOK §5.2). Reconcile any cross-epic heads (lead-attribution, full-funnel) to one head before the prod migration Job runs. |

## DEPLOYMENT_RULES spot checks (read-only)

| Rule | Result | Note |
|---|---|---|
| §Operating-model — repeatable ops via repo scripts | ✅ Available | `infra/scripts/deploy_cloud_run.sh`, `provision_cloudsql.sh`, `provision_cloud_run_foundation.sh`, `provision_cloud_iap_lb.sh`, `preflight_prod.sh` all present. ENG-494/498 drafts follow this convention. |
| §4 / §7 — non-HTTP work as Cloud Run **Jobs**, not Services | ✅ Pattern exists | `deploy_cloud_run.sh` already defines one-shot + scheduled Jobs (`JOB_ALEMBIC`, `JOB_SF_PULL`, `JOB_CS_PULL`, …) + Cloud Scheduler entries. ENG-498 [5] (drain + reminder Jobs) maps directly onto `deploy_job()`. |
| §6 — secrets via Secret Manager / tenant.integration_credential | ✅ Honored by design | `JOB_SECRETS` uses `…:latest` refs; the MM bot token / webhook secret go in `tenant.integration_credential` (ENG-496), never Cloud Run env. |
| Messenger env already wired into prod Jobs | ✅ Present | `JOB_ENV_VARS` already carries `NOTIFICATIONS_ENABLED=false, MESSENGER_PHI_FULL=true`. ENG-500 [7] only flips `NOTIFICATIONS_ENABLED=true` + sets `NOTIFICATIONS_CUTOFF_AT`. |
| §4 (no-localhost in prod URLs) for new `chat.*` host | ⚠️ To enforce | New public hostname `chat.fusioncrm.app` must use `https://`; the inbound `action_callback_base` must be the public API host, not `host.docker.internal` (local default). Covered in the ENG-494 bundle + ENG-496 runbook. |
| §9 — feature work separate from infra | ✅ Planned | ENG-498 code (entrypoints) is a code PR to main; ENG-494 host provisioning is its own infra PR; they do not mix. |
| Prod always-on worker present? | ❌ ABSENT (known) | `fusion-worker` decommissioned in ENG-172 — this is the ENG-498 gap; drains must run as scheduled Jobs. |

## Net

Start-gate is **one item from green**: confirm a single alembic head on a clean `main`
checkout. Everything else the preflight touches is either already satisfied by the existing
deploy contract or scoped into the child tickets' artifacts. No blocking DEPLOYMENT_RULES
violation was found in the planned approach.

## GCP read-only inventory (2026-06-17) — resolves ENG-494 unknowns

| Unknown (flagged in host bundle) | Resolved value |
|---|---|
| DNS provider for fusioncrm.app | **Cloud DNS** managed zone `fusioncrm-app` (`fusioncrm.app.`) → `chat.fusioncrm.app` A-record is **scriptable** via `gcloud dns record-sets`, not a manual registrar step. |
| Backup contour bucket | `gs://fusion-crm-backups` exists → MM DB dump target `gs://fusion-crm-backups/mattermost/`. |
| Canonical region | **us-west1** (Cloud SQL `fusion-crm-pg`, POSTGRES_16) → VM + `fusion-mm-pg` go in us-west1. |
| MM DB placement | A new dedicated Cloud SQL instance `fusion-mm-pg` keeps MM physically separate from `fusion-crm-pg` (canonical) — matches ADR-0006. |

Net: the host provisioning draft can be hardened into a fully-scripted, idempotent
`infra/scripts/provision_mattermost_host.sh` with no manual DNS step. Only the Mattermost
admin-UI workspace setup (ENG-495: team/bot/token/channels) genuinely needs operator hands.
