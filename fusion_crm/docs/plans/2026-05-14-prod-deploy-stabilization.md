# Production Deploy Stabilization Plan

- **Date:** 2026-05-14
- **Author:** Claude (audit & plan); reviewer: Codex
- **Status:** Draft for review
- **Scope:** Stop the "fix one variable, break another" cycle on production
  deploys. Audits 9 focus areas Codex flagged, identifies 3 root causes, and
  proposes a 5-phase execution order.

---

## 1. Background

We have been chasing one-variable production fixes for a week (ENG-156, -157,
-158, plus several env-only Cloud Run patches). Each fix surfaced the next
breakage. Codex compiled a 12-item list of suspected drift between
`packages/core/config.py`, `infra/env/production.env.reference`,
`infra/scripts/deploy_cloud_run.sh`, `.github/workflows/deploy-prod.yml`, and
`infra/docker/docker-compose*.yml`.

This document is the result of a parallel audit of all those areas. It
separates real bugs from false alarms, identifies what Codex missed, and
proposes a concrete order of work.

## 2. TL;DR

- **3 root causes**, not 12 independent problems:
  1. No single source of truth for prod env contract.
  2. CI workflow and manual deploy script deploy the same services with
     different `gcloud` flags. Workflow drops critical flags.
  3. No blocking verification of what was deployed (smoke is informational,
     `make verify` skips pytest, no preflight).
- **Phase 0** (1 PR, day 1) fixes the production-breaking items currently
  live: Alembic Job command, missing `OAUTH_REDIRECT_BASE_URL`, missing
  `API_CORS_ORIGINS` (with the prerequisite `Settings` refactor — see
  §3.2.1), and workflow stripping critical flags.
- **Codex reviewer amendment:** treat the GitHub Actions vs deploy script
  drift as a Phase 0 production bug, not a cleanup item. Prefer moving the
  workflow to the canonical script immediately; use inline flag duplication
  only as a short-lived fallback if script-call migration blocks the hotfix.
- **Phase 1–4** (5 PRs total, ~6 days) eliminates the drift permanently.
- **Cost ceiling adopted:** $100/mo target (per ADR-0002), with budget
  alerts at $100 and $150. No Memorystore, no always-on worker, evaluate
  Direct VPC egress in a separate spike. See §10.

## 3. Audit findings

### 3.1 What Codex flagged correctly

| # | Codex item | Status | Evidence |
|---|---|---|---|
| 1 | `GOOGLE_OAUTH_CLIENT_ID` vs `GOOGLE_WORKSPACE_CLIENT_ID` drift | CONFIRMED | `packages/core/config.py:148` declares alias `GOOGLE_OAUTH_CLIENT_ID`; `infra/env/production.env.reference:75` documents it as `GOOGLE_WORKSPACE_CLIENT_ID`. |
| 1 | `MICROSOFT_OAUTH_CLIENT_ID` vs `MICROSOFT_365_CLIENT_ID` drift | CONFIRMED | `config.py:154` vs `production.env.reference:77`. |
| 1 | `ENCRYPTION_KEY` vs `INTEGRATIONS_ENCRYPTION_KEY` drift | CONFIRMED | `config.py:105` vs `production.env.reference:81`. |
| 2 | arq worker does not listen on `$PORT` | CONFIRMED | `apps/worker/main.py:1-99` is pure arq pop-loop. `apps/api/Dockerfile:15-19` (worker reuses image) explicitly says "arq is a Redis pop-loop with no HTTP surface". `infra/scripts/deploy_cloud_run.sh:419-447` deploys it as a Cloud Run **Service** with `min=1, max=1` — health check fails. |
| 3 | Redis URL is a hardcoded placeholder, Memorystore not provisioned | CONFIRMED | `deploy_cloud_run.sh:65`: `REDIS_URL="${REDIS_URL:-redis://10.0.0.5:6379/0}"`. `infra/env/PRODUCTION.md:109-112` states Memorystore migration is ENG-112 future work. |
| 4 | Alembic Cloud Run Job command resolves `alembic.ini` from wrong dir | CONFIRMED | `packages/db/alembic.ini:2-3`: `script_location = alembic` and `prepend_sys_path = ../..` — both relative to the ini file's directory. `apps/api/Dockerfile:75` sets `WORKDIR /app`. `deploy_cloud_run.sh:499-500` runs `python -m alembic upgrade head` from `/app` — `alembic.ini` is at `/app/packages/db/alembic.ini`, not findable. Migrations either silently no-op or pick up the wrong config. |
| 8 | `make verify` does not run pytest, full suite is red | CONFIRMED | `Makefile:55`: `verify: lint typecheck`. The comment on lines 49-54 explicitly says tests are deferred to `make verify-full` "until test-suite collection errors are cleaned up". Neither `ci.yml:50` nor `deploy-prod.yml:88` calls `verify-full`. |
| 9 | Smoke is `continue-on-error: true` | CONFIRMED | `.github/workflows/deploy-prod.yml:543-545`. Auto-rollback on line 606 only fires if `smoke.outputs.rollback_needed == 'true'`, but `continue-on-error` swallows generic failures (auth, network) before they can set that output. A genuinely broken API can deploy and serve users for minutes. |
| 11 | Manual deploy script and GitHub Actions diverge | CONFIRMED — see §3.3 below; this is the **biggest** real problem. |

### 3.2 What Codex got wrong (false alarms)

| # | Codex claim | Reality |
|---|---|---|
| 6 | Public vs internal API URL confusion | Already correctly split as of ENG-158 (`apps/web/next.config.mjs:54-92`). `NEXT_PUBLIC_API_BASE_URL=https://fusioncrm.app` for browser; `INTERNAL_API_URL=<direct Cloud Run URL>` baked into rewrites at build time by `.github/workflows/deploy-prod.yml:281-282`. The remaining problem is unrelated — see §3.3 item 2. |

**Correction note (2026-05-14, post-Codex review):** I initially classified
the CSV/JSON parsing concern as a false alarm because the `_split_csv` field
validator (`packages/core/config.py:209-214`) is registered with
`mode="before"`. Codex pushed back: he had tested locally and seen Pydantic
crash. I re-verified empirically with a fresh `Settings()` construction
under three input shapes:

```
API_CORS_ORIGINS='https://fusioncrm.app,https://x.com'  → SettingsError
API_CORS_ORIGINS='["https://fusioncrm.app","https://x.com"]' → OK
API_CORS_ORIGINS='https://fusioncrm.app'                → SettingsError
```

`pydantic-settings` v2 `EnvSettingsSource.prepare_field_value()` calls
`json.loads()` for any field annotated as a complex type (list, dict, set)
**before** field validators run. The `mode="before"` validator only fires
at the model layer, after source decoding has already failed. **Codex was
right; my audit was wrong.** Item moved to §3.3 below.

### 3.2.1 What Codex got right that I initially dismissed

- **`API_CORS_ORIGINS` and `WEB_CORS_ORIGINS` parsing.** With the current
  `list[str]` annotation, the only acceptable env-var format is JSON
  (`'["a","b"]'`). Single values without brackets crash. The hand-written
  validator never runs for env-loaded values. **Real production-breaking
  bug**, currently masked only because the env var is unset (defaults to
  `[]`). Setting it via `--set-env-vars=API_CORS_ORIGINS=https://fusioncrm.app`
  in Phase 0 item 0.3 would crash the app on startup.

### 3.3 What Codex missed (worse than he flagged)

These were not in Codex's list but are the larger drivers of recent breakage:

1. **Workflow `deploy-api/web/worker` steps strip critical `gcloud` flags.**
   `.github/workflows/deploy-prod.yml:439-513` reimplements deploy inline
   instead of calling `infra/scripts/deploy_cloud_run.sh`. Side-by-side flags
   for `fusion-api`:

   | Flag | `deploy_cloud_run.sh` | `deploy-prod.yml` |
   |---|---|---|
   | `--service-account` | `fusion-api-sa@…` | (omitted → default) |
   | `--vpc-connector` | set | (omitted) |
   | `--vpc-egress` | `private-ranges-only` | (omitted) |
   | `--ingress` | `all` | (omitted) |
   | `--no-allow-unauthenticated` | yes | (omitted) |
   | `--min-instances` / `--max-instances` | 0 / 5 | (omitted → defaults) |
   | `--memory` / `--cpu` | 512Mi / 1 | (omitted) |
   | `--port` | 8080 | (omitted) |
   | `--set-env-vars` | 4 vars | 1 var (`APP_COMMIT_SHA` only) |
   | `--set-secrets` | **6 secrets** | **0 secrets** |

   The workflow does `--no-traffic` then `--to-latest` traffic flip. Each
   workflow-driven revision is created with **Cloud Run defaults plus
   `APP_COMMIT_SHA`**. It loses VPC, secrets, and identity. This is a silent
   configuration drift bomb. It is the main reason "manual deploy worked,
   then CI broke prod".

2. **`OAUTH_REDIRECT_BASE_URL` not set anywhere in prod.** Audit of
   `deploy_cloud_run.sh:351` and `deploy-prod.yml` confirms it is omitted. API
   boots with the default from `packages/core/config.py:165`:
   `http://127.0.0.1:8001`. Every Google/Microsoft OAuth callback will fail
   `redirect_uri_mismatch` AND state HMAC verification, because the redirect
   URI baked into the OAuth state was `127.0.0.1:8001/...`.

3. **`API_CORS_ORIGINS` not set in prod.** Defaults to `[]`. The web app
   making `https://fusioncrm.app/api/...` calls is rejected by the API CORS
   middleware. Browser fails preflight.

4. **`WEB_CORS_ORIGINS` and `TRACKING_BASE_URL` are completely missing
   from `production.env.reference`.** Operator has no way to know they exist.

5. **`fusion-worker` Cloud Run Service is currently in
   `READY=False`** (expected — arq has no HTTP server). Running it is also
   wasting `min=1` instance cost.

## 4. Root causes (3, not 12)

1. **No single source of truth for the prod env contract.**
   `packages/core/config.py` is typed and authoritative for the running app,
   but `production.env.reference`, `deploy_cloud_run.sh`, `deploy-prod.yml`,
   and `docker-compose*.yml` are filled in by hand and drift.

2. **CI workflow and manual deploy script deploy the same services
   differently.** Workflow inlines `gcloud run deploy` with a different,
   smaller set of flags than the script. Script keeps secrets/VPC/SA;
   workflow drops them.

3. **No blocking verification of what was actually deployed.**
   `make verify` skips pytest, smoke runs `continue-on-error: true`, no
   preflight script exists. A broken deploy reports green.

## 5. Recommended option per area

| Area | Codex options | Recommended | Rationale |
|---|---|---|---|
| Env contract | A: reference is truth / B: Settings is truth | **B** | Settings is already strictly typed (Pydantic v2). Reference becomes generated/checked-against-Settings. Code already wins at runtime; aligning docs to it is one-way work. |
| Worker runtime | A: drop Service, jobs only / B: HTTP shim / C: VM/GKE | **A for now**, C revisited after Memorystore decision | A is zero-incremental-risk: bounce-poll already runs as a one-shot Cloud Run Job triggered by Cloud Scheduler (`deploy_cloud_run.sh:584-601`). Outbound email queue drain is paused (we are marketing-first; no production outbound campaign yet). Saves cost and unblocks deploys. |
| Redis | A: provision Memorystore now / B: disable worker / C: sidecar VM | **B now**, A as a separate ADR | Same as above. Memorystore + VPC peering is a 2-day effort with $40/mo cost. Defer until a feature actually needs it. |
| Alembic Job | A: `sh -c "cd packages/db && alembic upgrade head"` / B: fix `alembic.ini` script_location | **A** | Mirrors `Makefile:76-77` (`make db-upgrade`), which is the version we know works. Option B requires touching `prepend_sys_path` for every container WORKDIR variant. |
| List env parsing | A: JSON in env / B: custom source / C: str + property | **C** | After empirical re-verification (see §3.2.1): the `mode="before"` validator does NOT save us under `pydantic-settings` source decoding. Option C (`str` field + property) is the simplest fix that survives all input shapes and all future refactors. Option A would force operators to write JSON in Cloud Run env vars (fragile, easy to break with a copy-paste). Option B introduces a custom settings source we then have to maintain. |
| URL ownership | (Codex has no enumerated options) | **Canonical contract**: `https://fusioncrm.app` everywhere public; direct Cloud Run URL only in `INTERNAL_API_URL` build arg; never `localhost` in prod | Implementation: set `OAUTH_REDIRECT_BASE_URL`, `WEB_APP_BASE_URL`, `API_CORS_ORIGINS` in deploy script + workflow. Add startup config logger. |
| Secrets | A: only `--set-secrets` on Cloud Run / B: app resolves `gcp-secret://` | **A on Cloud Run runtime, B for compose/operator paths** | Don't mix on the same prod path. Cloud Run already does A for 6 secrets in the script. Workflow needs to follow. |
| Tests in CI | A: fix tests, run full pytest / B: split blocking smoke from full suite | **B now, A later** | Full pytest collection is broken (ENG-123 tenant fixture not merged). Add 4 deploy-critical tests as a blocking subset; defer full suite to post-ENG-123. |
| Smoke | A: strict after IAM fix / B: leave informational | **A**, after Phase 0 fixes OAuth | Once OAuth works, the smoke runner can authenticate and the existing endpoint checks become trustworthy. Then drop `continue-on-error`. |
| Deploy script vs Actions | A: Actions calls one canonical script / B: keep separate | **A** | The script already supports CI mode (`SERVICES=` subset, env-driven config). One missing piece: `APP_COMMIT_SHA` env override. |
| Diagnostics endpoint | (Codex item 12) | **Startup log instead** | Achieves the same audit value (sanitized URL/env/secret-name dump at boot) without a new HTTP surface to lock down. |

## 6. Execution order

User's original preference was 2 → 3 → 4 → 1 → 7 (worker, Redis, Alembic, env
contract, secrets). Audit suggests reordering by **what is currently broken in
production** rather than by topic priority:

### Phase 0 — STOP THE BLEED (1 PR, day 1)

Fix the production-breaking items currently live (six sub-items: 0.1, 0.2,
0.3a, 0.3b, 0.4, 0.5). Single PR so they ship together; partial fixes leave
prod in a half-broken state.

| # | Change | File:Line | Verification |
|---|---|---|---|
| 0.1 | Alembic Job command: `sh -c "cd packages/db && python -m alembic upgrade head"` | `infra/scripts/deploy_cloud_run.sh:499-500` | `gcloud run jobs execute fusion-job-alembic-upgrade --wait` succeeds, logs show migration revisions |
| 0.2 | Add `OAUTH_REDIRECT_BASE_URL=https://fusioncrm.app` to API env | `deploy_cloud_run.sh:351` (API_ENV_VARS) and `deploy-prod.yml` deploy-api step | `curl https://fusioncrm.app/integrations/google_workspace/connect/start` returns redirect URL with correct base |
| 0.3a | **Refactor `api_cors_origins` and `web_cors_origins` to `str` field + computed `list` property.** Without this, item 0.3b crashes the app on startup. See §3.2.1 for empirical proof. Edit `packages/core/config.py:58, 186, 209-214`: rename fields to `_raw` suffix, type as `str` with `default=""`, drop the `_split_csv` validator, add `@property` returning `list[str]` via `[v.strip() for v in self.X_raw.split(",") if v.strip()]`. Update every consumer (FastAPI CORS middleware in `apps/api/main.py`, any tests). | `packages/core/config.py`, `apps/api/main.py`, `tests/` (any test setting these fields) | New test in Phase 4 (`test_settings_resolves_from_cloud_run_env.py`) covers all three input shapes (CSV, JSON, single value). For Phase 0 acceptance, run `python -c "import os; os.environ['API_CORS_ORIGINS']='https://fusioncrm.app,https://x.com'; from packages.core.config import Settings; print(Settings().api_cors_origins)"` and see a clean list. |
| 0.3b | Add `API_CORS_ORIGINS=https://fusioncrm.app` to API env | `deploy_cloud_run.sh:351` (API_ENV_VARS) and `deploy-prod.yml` deploy-api step | OPTIONS preflight from web origin returns 204 with `access-control-allow-origin: https://fusioncrm.app` |
| 0.4 | Add `WEB_APP_BASE_URL=https://fusioncrm.app` to API env | same two places | Latent — covered by 0.2 in user-visible behavior |
| 0.5 | Workflow `deploy-api` and `deploy-web` steps must NOT strip flags. Preferred Phase 0 fix: replace the inline `gcloud run deploy` blocks with calls to the canonical `infra/scripts/deploy_cloud_run.sh` for the affected service. Fallback only if the script-call migration blocks the hotfix: inline the full missing flag set and open a same-day follow-up to delete the duplication. | `deploy-prod.yml:439-513`, `infra/scripts/deploy_cloud_run.sh` | `gcloud run services describe fusion-api --format=json` after a CI deploy shows all flags identical to a script-driven deploy |

### Phase 1 — Worker / Redis decommission (1 PR, day 2)

Remove `fusion-worker` Cloud Run Service. Keep one-shot Cloud Run Jobs.

Files to edit:
- `infra/scripts/deploy_cloud_run.sh`: lines 74, 112-115, 121-122, 354-355,
  419-447, 451 (remove `SVC_WORKER`, `WORKER_*`, `deploy_worker`,
  `WORKER_ENV_VARS`).
- `.github/workflows/deploy-prod.yml`: lines 62, 129-131, 293-331, 671-710,
  734-735, 749 (remove `WORKER_SERVICE`, worker path filter, `build-worker`,
  `deploy-worker`, post-deploy worker row).
- `.github/workflows/deploy-prod-rollback.yml`: remove worker from service
  choice list.
- `infra/env/PRODUCTION.md` and any docs: mark outbound email queue drain
  and bounce poll-on-cron as paused. Bounce poll continues working as a
  one-shot Cloud Run Job (`fusion-job-bounce-poll`, runs every 15min via
  Cloud Scheduler).
- Linear: file ENG ticket "Outreach outbound queue drain blocked on
  Memorystore (ENG-112)" with explicit acceptance criteria.

Verification:
- `gcloud run services list` shows no `fusion-worker`.
- `gcloud run jobs executions list --job=fusion-job-bounce-poll --limit=3`
  shows recent successful runs.
- API and web continue to deploy and pass smoke.

### Phase 2 — Env contract normalization (1 PR, day 3)

Make `packages/core/config.py` the source of truth; align reference and add
generation/check.

Files to edit:
- `infra/env/production.env.reference`:
  - Rename `GOOGLE_WORKSPACE_CLIENT_ID/SECRET` → `GOOGLE_OAUTH_CLIENT_ID/SECRET` (lines 75-76).
  - Rename `MICROSOFT_365_CLIENT_ID/SECRET` → `MICROSOFT_OAUTH_CLIENT_ID/SECRET` (lines 77-78).
  - Rename `INTEGRATIONS_ENCRYPTION_KEY` → `ENCRYPTION_KEY` (line 81).
  - Add `WEB_CORS_ORIGINS=https://fusioncrm.app`.
  - Add `TRACKING_BASE_URL=https://fusioncrm.app`.
  - Add `OAUTH_REDIRECT_BASE_URL=https://fusioncrm.app` (now mandatory).
  - Add `WEB_APP_BASE_URL=https://fusioncrm.app`.
- `tests/core/test_env_reference_matches_settings.py` (NEW): introspect
  `Settings.model_fields`, derive expected env names from aliases, parse
  `production.env.reference`, assert sets match. Catches all future drift
  automatically.
- `apps/api/main.py`: add FastAPI lifespan startup log:
  ```python
  log.info(
      "startup.config",
      app_env=settings.app_env,
      app_commit_sha=settings.app_commit_sha,
      oauth_redirect_base_url=settings.oauth_redirect_base_url,
      web_app_base_url=settings.web_app_base_url,
      tracking_base_url=settings.effective_tracking_base_url,
      api_cors_origins=settings.api_cors_origins,
      web_cors_origins=settings.web_cors_origins,
      database_host=urlparse(settings.database_url).hostname,
      redis_host=urlparse(settings.redis_url).hostname if settings.redis_url else None,
  )
  ```
  No secrets, no full DSNs — only hostnames and public URLs.

Verification:
- New test passes locally.
- Cloud Run logs show `startup.config` event with prod values, no `127.0.0.1`.

### Phase 3 — Single source of truth for deploy (1 PR, day 4-5)

GitHub Actions calls the canonical script. Eliminate flag drift permanently.
If Phase 0 already moved API and web to the script, Phase 3 becomes a hardening
PR: remove any fallback inline deploy code, add no-prompt CI guards, and add
tests/checks that prevent the workflow from reintroducing raw `gcloud run
deploy` blocks for production services.

Files to edit:
- `infra/scripts/deploy_cloud_run.sh:357-381` (`deploy_api` and friends): add
  optional `APP_COMMIT_SHA` env var support, append to `--set-env-vars` when
  present.
- `.github/workflows/deploy-prod.yml:439-513`: replace any remaining inline
  production `gcloud run deploy` blocks with:
  ```yaml
  - name: Deploy fusion-api via canonical script
    run: |
      APP_COMMIT_SHA=${{ github.sha }} \
      IMAGE_TAG=${{ needs.build-api.outputs.image_sha }} \
      SERVICES=api \
      ./infra/scripts/deploy_cloud_run.sh
  ```
  Same for web. (Worker step gone after Phase 1.)
- `infra/scripts/deploy_cloud_run.sh`: ensure script does not prompt or `read`
  in CI mode (audit for `gcloud` interactive prompt traps per
  `feedback_gcloud_interactive_traps.md`).

Verification:
- After CI deploy, `gcloud run services describe fusion-api --format=json |
  diff` against a script-only deploy shows zero meaningful difference.

### Phase 4 — Tests + preflight + strict smoke (1 PR, day 6)

Add the missing safety net.

Files to add:
- `infra/scripts/preflight_prod.sh` (NEW). Runs from CI before
  `alembic-migrate`. Checks:
  1. All `gcloud secrets versions list` for required secret names succeed
     (and have a `latest` version).
  2. Required env names in `deploy_cloud_run.sh` are a superset of required
     `Settings` fields with no defaults.
  3. `OAUTH_REDIRECT_BASE_URL` value matches expected prod URL.
  4. `gcloud run jobs describe fusion-job-alembic-upgrade` command starts
     with `sh -c 'cd packages/db'`.
  5. (After Phase 1) no `fusion-worker` service exists; if present, fail.
- `tests/core/test_settings_resolves_from_cloud_run_env.py` (NEW): set the
  exact env vars our deploy script sets (with prod-shaped values), assert
  `Settings()` constructs without error and computed properties resolve.
- `tests/core/test_alembic_command.py` (NEW): subprocess-run
  `sh -c "cd packages/db && python -m alembic --config=alembic.ini current"`
  in a fresh shell, assert exit 0.
- `tests/core/test_oauth_redirect_url_construction.py` (NEW): set
  `OAUTH_REDIRECT_BASE_URL`, call `_redirect_uri_for("google_workspace")`,
  assert the resulting URL.
- `tests/core/test_secret_names_match_deploy_script.py` (NEW): parse
  `deploy_cloud_run.sh` `--set-secrets`, parse `Settings` aliases, assert the
  intersection covers everything the app actually needs.

Files to edit:
- `Makefile`: add a new target `verify-deploy` that runs only these 4 tests
  plus existing lint/typecheck. Wire into `.github/workflows/ci.yml` and
  `deploy-prod.yml`. Keep `verify-full` for the broken full suite.
- `.github/workflows/deploy-prod.yml:543-545`: drop `continue-on-error: true`
  from the smoke step. (Only do this AFTER Phase 0 fixed OAuth so the smoke
  runner can actually auth.)

Verification:
- Run preflight locally against prod GCP — should pass clean.
- Force-break one of the 4 tests (e.g., remove an env var from the script)
  and confirm CI goes red.
- Push a deliberate API regression and confirm smoke fails the workflow.

## 7. What is intentionally NOT in this plan

- **Memorystore provisioning** — separate ADR (ENG-112). Decide first
  whether real-time worker is in scope for marketing-first phase.
- **Reconciling `gcp-secret://` URIs and `--set-secrets`** — keep them on
  separate paths (compose/operator vs Cloud Run). Merging them adds surprise.
- **Full pytest collection fix** — Phase 4 only adds 4 deploy-critical
  tests. Full suite cleanup is a separate sprint, blocked on ENG-123 tenant
  schema.
- **Diagnostics HTTP endpoint** (Codex item 12) — startup log in Phase 2
  achieves the same audit value without adding an HTTP surface to lock down.
- **`fusion-web` flag audit** — same shape of drift as `fusion-api`; resolved
  by Phase 0.5 (script-call migration) for both services in the same PR, with
  Phase 3 acting as the hardening / no-regression check.

## 8. Open questions for review

1. **Order — RESOLVED 2026-05-14.** Confirmed `Phase 0 → 1 → 2 → 3 → 4`.
   Rationale (user + Codex): Phase 0 and Phase 1 both edit
   `.github/workflows/deploy-prod.yml` and
   `infra/scripts/deploy_cloud_run.sh` — keep that context warm. Removing
   `fusion-worker` (Phase 1) before normalizing env names (Phase 2) avoids
   churn and merge conflicts (no point renaming env vars for a runtime we
   are about to delete). Phase 0 still ships the URL/CORS env fixes
   (`OAUTH_REDIRECT_BASE_URL`, `WEB_APP_BASE_URL`, the `Settings` CORS
   refactor, `API_CORS_ORIGINS`) without waiting for Phase 2 — Phase 2 is
   for full normalization + drift-prevention test, not for unblocking prod.
   Linear ticket: ENG-161.
2. **Worker decommission scope:** removing `fusion-worker` Cloud Run Service
   means losing `drain_outbound_queue` (outbound email send). Bounce poll
   keeps working via Cloud Run Job. Confirm outbound send is OK to pause
   given `feedback_marketing_first_phase.md`.
3. **Secrets in workflow:** can Phase 0 move the workflow to the canonical
   script immediately, or do we need a temporary inline fallback for one PR?
   The preferred answer is script-call now; fallback only if it materially
   reduces hotfix risk.
4. **Linear epic structure:** one epic with 5 sub-issues (one per phase), or
   5 independent ENG tickets?

## 9. Codex reviewer discussion log

This section is the working journal for review comments before they become
implementation tickets or ADRs.

### 2026-05-14 — Deploy stabilization review

1. **Do not treat deploy workflow drift as cleanup.** The workflow/script
   mismatch is a production bug because it creates revisions without the same
   service account, VPC, env vars, secrets, resource limits, ingress, and auth
   settings as the manual deploy path. It should be fixed in Phase 0.
2. **Fix `Settings` parsing before adding CORS env vars.** Adding
   `API_CORS_ORIGINS=https://fusioncrm.app` before changing the field away
   from `list[str]` can crash startup under `pydantic-settings` v2.
3. **Prefer one canonical deploy path immediately.** Calling
   `infra/scripts/deploy_cloud_run.sh` from GitHub Actions is less risky than
   duplicating every Cloud Run flag in YAML. If a fallback inline fix is used,
   it must be explicitly temporary and removed in the next PR.
4. **Keep cost decisions separate from hotfixes.** Removing the broken
   `fusion-worker` service is both a deploy fix and a cost fix. Direct VPC
   egress is a cost optimization only and should stay out of Phase 0.
5. **Use this plan as the discussion journal.** Once a point becomes a durable
   architecture decision, promote it into `docs/decisions/ADR-*.md` instead of
   leaving it only in this plan.
6. **Durable deploy/env rules now live in `docs/DEPLOYMENT_RULES.md`.**
   Agents must use that document before changing `Settings`, env vars, secrets,
   Cloud Run, OAuth/CORS URLs, or CI/CD deploy behavior.
7. **Google Cloud CLI is acceptable only through a reproducible operating
   model.** Agents may use `gcloud` for inspection and approved recovery, but
   repeatable production changes must be captured in repo scripts and verified
   with preflight, `gcloud ... describe`, and smoke checks.
8. **Provider ingestion is a separate controlled pipeline.** Salesforce and
   CareStack data must follow `docs/PROVIDER_INGESTION_STRATEGY.md`: raw event,
   hydration when needed, canonical projection, semantic context, then audited
   workflow/action. Speed-to-lead may be live early, but only as a narrow
   `Lead.created` path with its own runtime decision.
9. **Taxonomy and strategy learning require approval.** Agents may summarize,
   classify, and propose taxonomy or workflow-strategy improvements, but
   production behavior changes must follow
   `docs/governance/TAXONOMY_GOVERNANCE.md`.
10. **Tenant-owned credentials belong in company settings.** Secret Manager is
    for platform runtime secrets. Provider credentials owned by a tenant
    (Salesforce, CareStack, Twilio, HubSpot, mailbox, payments, AI vendors)
    should be entered through Settings / Integrations and stored encrypted in
    `tenant.integration_credential`.

## 10. Cost-control decisions

Adopted after Codex's review pass on 2026-05-14. Anchor:
`docs/decisions/ADR-0002-cloud-run-prod-runtime.md:125` estimates ~$100/mo
without Memorystore and ~$145/mo with Memorystore. Reviewed bottom-up:

| Component | Estimated cost/mo | Decision |
|---|---:|---|
| Cloud SQL 1 vCPU / 3.75 GiB (db-custom-1-3840), HA off | $50–55 | Keep. Required for prod. |
| HTTPS Load Balancer | ~$18 | Keep. Required for fusioncrm.app TLS termination. |
| Cloud DNS managed zone | <$1 | Keep. |
| Cloud Run `fusion-api` + `fusion-web`, `min-instances=0` | $0–15 | Keep. Cold start is acceptable for clinic-staff usage pattern (no public traffic; ~10 operators). |
| Cloud Run Jobs (alembic, bounce-poll) | $1–3 | Keep. Already structured as one-shot. |
| Serverless VPC Access connector | $10–15 | **Evaluate replacing with Direct VPC egress** — see decision below. |
| `fusion-worker` always-on Cloud Run Service | $5–15 (currently broken, but burning min=1) | **Remove (Phase 1).** Unblocks deploys AND saves cost. |
| Memorystore (Redis) | $36–47 | **Do NOT provision yet.** No production-critical worker / outbound queue / live Salesforce push subscriber needs it in Phase 1 marketing-first scope. ADR-0002 already lists Memorystore as deferred (`infra/env/PRODUCTION.md:109-112`, ENG-112). |

### 10.1 Direct VPC egress vs Serverless VPC Access connector

Google Cloud added Direct VPC egress for Cloud Run Services and Jobs
([docs](https://cloud.google.com/run/docs/configuring/vpc-direct-vpc)). It
removes the connector resource entirely (~$10–15/mo saved) and one piece of
infrastructure to maintain. Trade-offs:
- **Pros:** lower cost, simpler topology, no separate connector to size or
  monitor, faster cold-start network attach.
- **Cons:** newer feature; cold-start latency can be slightly higher on the
  first request after a scale-to-zero; requires more careful startup probe
  configuration; Cloud SQL Private IP path needs the same VPC peering, no
  free lunch there.
- **Decision:** evaluate as a **Phase 5** candidate (after Phase 0–4
  stabilize). Do not bundle into deploy stabilization — it is an
  infrastructure swap, not a code fix, and would conflate concerns. Track as
  a separate ENG ticket with a 1-day spike: deploy `fusion-api` to a
  throwaway revision with Direct VPC egress, hit Cloud SQL, measure cold
  start, decide.

### 10.2 Phase 0 cost-control add-ons

In addition to the breakage fixes already listed in §6 Phase 0:

| Action | Where | Effect |
|---|---|---|
| Verify `fusion-api` and `fusion-web` keep `--min-instances=0` after Phase 0.5 (script-call migration, or inline-flag fallback) | `deploy_cloud_run.sh` already sets `API_MIN=0`; if the inline-fallback path is used in 0.5, ensure those flags carry `--min-instances=0` too | Avoid accidental always-on charge if workflow defaults differ from script defaults |
| Add a billing budget alert at $100/mo (warning) and $150/mo (critical) | GCP Console → Billing → Budgets, OR `gcloud billing budgets create` | Catches scope creep early; both thresholds chosen against the ADR-0002 baseline |
| Document the cost ceiling in this plan and ADR-0002 | this file + `docs/decisions/ADR-0002-cloud-run-prod-runtime.md` | Future PRs that add infra (Memorystore, multi-region, GKE) must justify against the ceiling |

### 10.3 Re-examine after Phase 4

When Phase 4 lands, revisit:
- Does outbound email send (`drain_outbound_queue`) need to come back? If
  yes → ENG-112 Memorystore ADR + new worker runtime model (long-running VM
  or GKE Autopilot, not Cloud Run Service).
- Does live Salesforce push (CDC) become a Phase 2 requirement? If yes →
  same trigger.
- Are cold-start metrics on `fusion-api` causing operator-perceived latency?
  If yes → consider `--min-instances=1` (~$10/mo) before any larger changes.

## 11. References

- Codex's original 12-item proposal — see chat handoff dated 2026-05-14.
- Recent URL/rewrite fixes:
  - `1e05cc1` ENG-158 — bake `INTERNAL_API_URL` into rewrites at build time.
  - `3e7a55f` ENG-156 — rewrite GW/MS OAuth callback path.
  - `f41db1e` ENG-157 — DELETE Salesforce response carries uuid id.
  - `a9355ba` ENG-155 — remove shadowing Next.js OAuth proxy handlers.
- Audit notes on `feedback_gcloud_interactive_traps.md` (do not let scripts
  prompt in CI), `feedback_marketing_first_phase.md` (outbound outreach is
  not yet a hard requirement), `feedback_pr_granularity.md` (bundle phases
  into single PRs, do not thin-slice).
- Cost baseline: `docs/decisions/ADR-0002-cloud-run-prod-runtime.md:125`
  ($100/mo without Memorystore, $145/mo with).
- Deployment/env rules: `docs/DEPLOYMENT_RULES.md`.
- Provider ingestion strategy: `docs/PROVIDER_INGESTION_STRATEGY.md`.
- Context architecture: `docs/architecture/CONTEXT_ARCHITECTURE.md`.
- Semantic interpretation: `docs/architecture/SEMANTIC_INTERPRETATION.md`.
- Taxonomy governance: `docs/governance/TAXONOMY_GOVERNANCE.md`.
- Pricing references for §10 cost-control:
  - Cloud Run pricing: https://cloud.google.com/run/pricing
  - Cloud Run billing settings:
    https://cloud.google.com/run/docs/configuring/billing-settings
  - Cloud SQL pricing: https://cloud.google.com/sql/pricing
  - Memorystore pricing: https://cloud.google.com/memorystore/docs/redis/pricing
  - Direct VPC egress: https://cloud.google.com/run/docs/configuring/vpc-direct-vpc
