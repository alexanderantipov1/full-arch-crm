# Morning Report — Mattermost prod bring-up (ENG-442)

**Session:** overnight 2026-06-17 · Orchestrator: Claude Code (inline)
**Outcome:** the ENG-442 chain could not be auto-executed (see "Why" below); instead the
session produced **review-and-execute-ready artifacts + the operator go/no-go memo**, so
your morning is *decide → approve → run*, not *start from scratch*. **Nothing was
provisioned, no secret stored, no deploy run, nothing committed.**

---

## TL;DR — what you decide this morning

1. **ENG-501 [8] PHI/BAA go/no-go** — the gate. Recommendation: **GO-with-conditions**.
   The existing **account-level Google BAA (from ENG-107) already covers** self-hosted
   Mattermost on GCP (GCE VM + Cloud SQL + GCS). **No new vendor BAA needed** — that is
   exactly why ADR-0006 rejected Slack/MM-Cloud (they put PHI on a third party). Sign the
   block in `artifacts/eng-501-phi-baa-decision-memo.md`. Instant downgrade lever if ever
   needed: `MESSENGER_PHI_FULL=false` → reverts to de-identified, non-PHI cards.

2. **ENG-494 [1] host** — approve the provisioning bundle, then run the 7-step checklist.
   Recommended shape: **GCE e2-small (us-west1-a)** running official `mattermost:10.5` +
   **Caddy/Let's-Encrypt TLS** for `chat.fusioncrm.app`; **dedicated Cloud SQL
   `fusion-mm-pg`** (NOT co-located, NOT a schema in the canonical DB); GCS filestore +
   backup into the existing `gs://fusion-crm-backups/` contour. Draft script + compose are
   in `artifacts/` (`.draft`, not on PATH, not executed).

3. **Sequencing correction (important):** standing up the host (ENG-494) alone delivers
   **nothing** — prod has no always-on worker (ENG-172), so the drains have nowhere to run.
   **ENG-498 [5] code must land first** (or in parallel) or you get a PHI-bearing server
   that posts nothing.

---

## Gate status (ENG-442 start conditions)

| Gate | Status |
|---|---|
| ADR-0006 = Accepted | ✅ Confirmed (status "Accepted", 2026-06-15) |
| DEPLOYMENT_RULES preflight | ⚠️ Partial — **must verify single alembic head on `main`**. Dev checkout shows 6 heads (multi-branch + known-local `b69bce1e2195`). Run `alembic heads` on a clean `main` checkout before deploy. |

## The chain — current state & what each needs

| # | Linear | State after tonight | Needs from you |
|---|--------|---------------------|----------------|
| [8] | ENG-501 | memo drafted, GO-with-conditions | **sign go/no-go** |
| [1] | ENG-494 | bundle + draft script/compose ready | **approve + run 7 steps** (spend, DNS, TLS) |
| [2] | ENG-495 | runbook ready (manual MM-UI steps) | run after [1] live; capture bot token + channel IDs |
| [3] | ENG-496 | runbook ready | store creds via `IntegrationCredentialService` (inside prod runtime) |
| [4] | ENG-497 | plan ready + **seeds.py trap fixed by design** | seed rules via `NotificationService.create_rule` (Option a) |
| [5] | ENG-498 | design + entrypoint skeleton ready | **code PR to main** (2 new Jobs), then deploy |
| [6] | ENG-499 | — | **BLOCKED: merge PR #168 (ENG-487) first** |
| [7] | ENG-500 | enable plan ready | env flip + deploy approval; set `NOTIFICATIONS_CUTOFF_AT` |

## Key technical findings (from the artifacts)

- **ENG-498 [5]:** add two scheduled Cloud Run Jobs on the existing `deploy_cloud_run.sh`
  pattern — `fusion-job-notification-drain` (wraps `drain_notification_outbox`) and
  `fusion-job-consult-reminders` (wraps `scan_consultation_reminders`), both cron
  `* * * * *`. Idempotency confirmed: drain uses `FOR UPDATE SKIP LOCKED`
  (`notification_repository.py:168`); reminders use a durable dedupe ledger
  (`notification_repository.py:224-252`). The existing `JOB_ENV_VARS` already carry
  `NOTIFICATIONS_ENABLED=false, MESSENGER_PHI_FULL=true` — no new env var needed.
  ⚠️ **`scan_consultation_reminders` is NOT on main yet** (only branch
  `eng-486-consult-reminders`) → deploy the drain Job first; the reminder Job waits on
  ENG-486 merge.
- **ENG-495-497:** `seeds.py` hardcodes the **local** `#scheduls` channel id
  (`uap18hmdkbbqmm6sg1msapjjur`) and the other 5 rules store channel *names*. Recommended
  fix (Option a): create prod rules via `NotificationService.create_rule`, which resolves
  names → prod 26-char ids through the adapter (uses the ENG-496 credential, fails loud on
  bot-not-in-channel). 6 rules total: `lead.created`→`leads`, `lead.created`(no phone)→
  `leads-missing-info`, `consultation.scheduled`→`scheduls`, `opportunity.stage_changed`→
  `opportunities`, `ownership.changed`→`ownership`, `ingest.sync_failed`→`ingest-alerts`.
- **Prod tenant id:** resolve by **slug `fusion-dental-implants`** via
  `TenantService.resolve_default`, NOT the local seed UUID `11111111-…`. Confirm the real
  prod `t.id` before any write (runbook has a read-only snippet).
- **ENG-500 [7]:** set `NOTIFICATIONS_CUTOFF_AT=<enablement instant, UTC>` *before/with*
  `NOTIFICATIONS_ENABLED=true` on `fusion-api` + the emitting/draining Jobs, to suppress the
  ~27k historical entities from paging retroactively. Reminders are future-only by
  construction (no cutoff needed).

## Why this session did not auto-execute

Every step is gated: [8] is your decision; [1]/[7] are spend + outward-facing + deploy
needing explicit approval (CLAUDE.md invariant #3); [6] is blocked on a merge; [2]→[3]→[4]
depend on a live bot-token secret minted by hand. Standing up an unattended public
PHI-bearing host overnight is exactly what the mission posture forbids. Full rationale in
`decision-log.md`.

## Recommended morning order

`[8] sign go/no-go` → confirm single alembic head on `main` → `[5] open code PR (drain Job)`
→ `[1] provision host (approve+run)` → `[2] bot+channels` → `[3] store creds` →
`[4] seed rules` → deploy `[5] Jobs` → (merge PR #168 → `[6] backfill`) → `[7] enable+smoke`.

## Artifacts (all under `mattermost-prod-bringup-v1/artifacts/`)

- `eng-501-phi-baa-decision-memo.md` — the go/no-go + sign block
- `eng-494-host-provisioning-bundle.md` + `provision_mattermost_host.sh.draft` + `mattermost-host-compose.yml.draft`
- `eng-498-delivery-design.md` + `notification_jobs_entrypoint.py.draft`
- `eng-495-497-ops-runbook.md`
- `eng-442-preflight-evidence.md` (DEPLOYMENT_RULES preflight findings)

---

## ADDENDUM — session 2 (after "делай и продолжайся" + ENG-501 GO)

**Decisions/changes since the report above:**
- **ENG-501 [8] = GO** recorded (operator). Linear → **Done**. Gate [8] cleared.
- **ENG-498 [5] built + verified → draft PR #173** (Linear → **In Review**).
  Branch `eng-498-prod-notification-delivery` (worktree `/Users/eduardkarionov/Desktop/fusion_eng498`).
  2 Cloud Run Job entrypoints + deploy-script wiring + tests. ruff clean, 4 new tests pass,
  existing reminder tests pass, `bash -n` valid. **Inert until ENG-500 flips
  `NOTIFICATIONS_ENABLED`.** Correction to the design artifact: `scan_consultation_reminders`
  IS on main (ENG-486 merged) — both entrypoints built.
- **GCP unknowns resolved (read-only):** `fusioncrm.app` is on **Cloud DNS** (zone
  `fusioncrm-app`) → the `chat.fusioncrm.app` record is scriptable; `gs://fusion-crm-backups`
  exists; canonical region **us-west1** (`fusion-crm-pg` POSTGRES_16). The host provisioning
  draft can now be a fully-scripted, no-manual-DNS step.

**What I deliberately did NOT do (hold point):** provision the prod host. Even with broad
authorization, standing up a billable (~$40/mo), public, PHI-bearing host from an **unreviewed
`.draft`** script, unattended, is a confirm-first/hard-to-reverse action — and the very next
step (ENG-495: Mattermost admin-UI team/bot/token/channels) physically needs your hands.

**Morning path (revised):**
1. Review + merge draft **PR #173** (ENG-498) after a Codex cross-runtime pass.
2. Harden `provision_mattermost_host.sh.draft` → reviewed `infra/scripts/provision_mattermost_host.sh` (DNS now scriptable).
3. Supervised **[1] host → [2] bot/channels** (~20 min together; I drive gcloud, you do the MM-UI bot token + capture channel IDs).
4. **[3] credential → [4] rules** (I can do these once you hand me the bot token + channel IDs).
5. Verify single alembic head on `main`; deploy (ships PR #173's jobs, still inert).
6. (merge PR #168 → **[6] backfill**) → **[7] enable**: set `NOTIFICATIONS_CUTOFF_AT` + flip `NOTIFICATIONS_ENABLED=true` + e2e smoke.
