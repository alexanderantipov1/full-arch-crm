# Terminal Agent Report

Task ID: A2-live
Linear issue: ENG-178 / ENG-180
Agent role: Claude Code explorer (read-only, live evidence pass)
Status: complete
Branch: read-only (`main`, HEAD `cb4d37e`)
Worktree: primary repo

## Summary

Live read-only evidence for deploy-prod run `25982799094` is now collected.
Deploy itself succeeded; the workflow failed at the deep IAP-fronted smoke
step. The new revision `fusion-api-00053-ssf` was built, deployed, and
took 100% LATEST traffic with `APP_COMMIT_SHA == github.sha ==
cb4d37ec67fc08e5d9800089d341ad284f8ee38c`. The anonymous boot smoke
`GET https://fusioncrm.app/api/healthz` returned HTTP 302 (IAP login
redirect) and was accepted as "boot OK" because the script only rejects
5xx/empty. The deep smoke then minted an identity token via
WIF + SA impersonation, hit the same URL with `Authorization: Bearer
<token>`, and the very first `BODY=$(check "/healthz")` exited with
status 1 ~225 ms later. No `::error::smoke fail:` annotation was emitted
— ENG-178's diagnostic-visibility defect is still live at `cb4d37e`.
Cloud Run application logs show no request handled by `fusion-api`
between `05:56:07Z` and `05:56:09Z`, which means the request was
rejected at the IAP edge and never reached the app. Auto-rollback then
restored traffic to `fusion-api-00052-xb7` (the previous primary
revision).

## Files Changed

- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/A2-live.md`: this report (only write).

## Git State

- Current branch: `main`, HEAD `cb4d37ec67fc08e5d9800089d341ad284f8ee38c`, tracking `origin/main`.
- Dirty files (pre-existing, owned by B1 per mission `ownership.md`):
  - `.claude/scheduled_tasks.lock`
  - `.github/workflows/deploy-prod.yml` (workflow file dirty but not edited by this task; ownership belongs to A1 mission)
  - `apps/api/routers/tenant.py`
  - `packages/tenant/credential_service.py`
  - `packages/tenant/schemas.py`
  - `tests/tenant/test_credential_service.py`
  - Untracked: `.agents/`, `.claude/commands/orchestrator.md`,
    `Agent_Orchestration_Playbook_RU.md`,
    `tests/api/test_tenant_credential_routes.py`,
    `tests/core/test_deploy_prod_smoke_logging.py`
- Commits made: none.
- Push status: none.

## Tests / Checks

All commands read-only. No write or mutate command was issued.

| Command | Result |
| --- | --- |
| `gh run view 25982799094 --json conclusion,status,createdAt,updatedAt,headSha,event,url` | OK |
| `gh run view 25982799094 --json jobs --jq '.jobs[] \| {name,conclusion,startedAt,completedAt,url}'` | OK |
| `gh run view --job 76374767866 --log` (smoke job) | OK |
| `gh run view --job 76374714494 --log` (deploy-api job) | OK |
| `gh run list --workflow deploy-prod.yml --branch main --limit 8 --json …` | OK |
| `gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="fusion-api" AND timestamp>="2026-05-17T05:55:00Z" AND timestamp<="2026-05-17T05:57:00Z"' --project=fusioncrm-494201 --limit=30 --order=asc --format=…` | OK (results below) |
| `gcloud logging read 'resource.type="http_load_balancer" AND timestamp>="2026-05-17T05:55:00Z" AND timestamp<="2026-05-17T05:57:00Z"' --project=fusioncrm-494201 …` | OK, **empty result** (LB access logging appears not enabled) |
| `gcloud logging read 'protoPayload.serviceName="iap.googleapis.com" AND timestamp>="2026-05-17T05:55:00Z" AND timestamp<="2026-05-17T05:57:00Z"' --project=fusioncrm-494201 …` | OK, **empty result** (IAP data-access audit logs not enabled) |
| `gcloud logging read 'resource.type="iap_web" AND …'` | OK, **empty result** |
| `gcloud logging read 'httpRequest.requestUrl=~"healthz" AND timestamp>="2026-05-17T05:55:00Z" AND timestamp<="2026-05-17T05:57:00Z"' --project=fusioncrm-494201` | OK, **empty result** — no `/healthz` request log anywhere in project window |
| `gcloud logging read 'protoPayload.serviceName="iamcredentials.googleapis.com" AND protoPayload.methodName="GenerateIdToken" AND timestamp>="2026-05-17T05:56:00Z" AND timestamp<="2026-05-17T05:56:15Z"' --project=fusioncrm-494201 --format=json` | OK — captures the explicit `audience` and `granted:true` for the smoke step's mint (see below) |
| `gh run list --workflow deploy-prod.yml --branch main --limit 10 --json …` | OK — confirms 8 consecutive failures on main since 2026-05-16T18:00:56Z (last green = `bc27223a`) |
| `gh run view 25981424237 --json jobs --jq …` (ENG-178 run) | OK — failed at "Verify traffic is actually on the new revision" |
| `gh run view 25981937992 --json jobs --jq …` (ENG-179 run) | OK — failed at "Resolve IAP OAuth Client ID for smoke audience" |
| `gcloud run services describe fusion-api --region=us-west1 --format='value(status.traffic,status.latestReadyRevisionName,status.url)'` | OK — current state: 100% on `fusion-api-00052-xb7`, latestReady=`fusion-api-00053-ssf` |
| `gcloud run revisions describe fusion-api-00053-ssf --region=us-west1 --project=fusioncrm-494201 --format=json` | OK — image `…fusion-api:cb4d37e…`, env `APP_COMMIT_SHA=cb4d37e…`, serving SA `fusion-api-sa@…`, generation 1, ready |
| `gcloud compute backend-services list --project=fusioncrm-494201 …` | DENIED by harness allowlist (`compute` not authorized). Would need this to confirm `iap.oauth2ClientId` binding. |
| `gcloud iap web get-iam-policy --resource-type=backend-services --service=fusion-api-backend --project=fusioncrm-494201` | DENIED by harness allowlist (`iap` not authorized). Would need this to confirm deployer SA has `roles/iap.httpsResourceAccessor`. |
| `gcloud iap settings get --resource-type=backend-services --service=fusion-api-backend --project=fusioncrm-494201` | DENIED by harness allowlist. |

### Additional cross-verification captured in this session

**`GenerateIdToken` audit detail** (`logName=projects/fusioncrm-494201/logs/cloudaudit.googleapis.com%2Fdata_access`):

- `protoPayload.serviceName`: `iamcredentials.googleapis.com`
- `protoPayload.methodName`: `GenerateIdToken`
- `protoPayload.authenticationInfo.principalEmail`: `cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com`
- `protoPayload.request.audience`: **`800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess.apps.googleusercontent.com`** — bit-for-bit equal to the workflow-env `IAP_OAUTH_CLIENT_ID` / smoke-step `IAP_AUDIENCE`
- `protoPayload.authorizationInfo[0].granted`: `true`
- `protoPayload.status`: `{}` (success)
- Two audit rows at `05:56:08.095Z` and `05:56:08.161Z` (both granted, same audience) — explains why the smoke step's stdout silence is purely diagnostic-routing, not a mint failure.

**Cloud Run service-level audit timeline for `fusion-api`** (resource.type=`cloud_run_revision`, service `fusion-api`, ascending):

| Timestamp (UTC) | Event |
| --- | --- |
| 05:55:09.292Z | `Services.ReplaceService` initiated by `cloud-build-deployer-sa` via WIF (deploy no-traffic) |
| 05:55:18.158Z | `Services.ReplaceService` (image swap) |
| 05:55:21.574Z | New revision `fusion-api-00053-ssf` begins start (`DEPLOYMENT_ROLLOUT`) |
| 05:55:26.674–26.682Z | Uvicorn `Started server process`, `Application startup complete`, `0.0.0.0:8080` |
| 05:55:26.682Z | `Default STARTUP TCP probe succeeded after 1 attempt for container fusion-api-1 on port 8080` |
| 05:55:26.736Z | Revision Ready |
| 05:55:28.010Z | Traffic set to `latestRevision=true, percent=100` (= `fusion-api-00053-ssf`) |
| 05:55:33.452Z | `Services.ReplaceService` (Restore latestRevision invariant, ENG-174 §C) |
| 05:56:09.971Z | `Services.ReplaceService` (rollback initiated) |
| 05:56:13.242Z | Rollback target revision name on response: `fusion-api-00052-xb7` |
| 05:56:14.504Z | Final `Services.ReplaceService` response: `traffic = [{percent:100, revisionName:'fusion-api-00052-xb7'}, … pr-tag entries…]`, `latestReadyRevisionName: fusion-api-00053-ssf` |

**Deployment context: 8 consecutive failed deploy-prod runs on main since the last green at `bc27223a` (2026-05-16T18:00:56Z)**. Each fix peeled back one layer of failure:

- `008c3c5` — pre-ENG-174 (first failure mode)
- `a599b74`, `e5e08e4`, `8b74852`, `a4aa78d` — earlier deploy script issues
- `7473ada` (ENG-178 deep-smoke route) — failed at `Verify traffic is actually on the new revision`
- `7e09c0a` (ENG-179 traffic filter) — failed at `Resolve IAP OAuth Client ID for smoke audience`
- **`cb4d37e` (ENG-180 pinned IAP client) — failed at `Hit smoke endpoints` (this run, `25982799094`)** — the *first* run whose failure is at IAP-edge response, not at workflow plumbing.

This sequence demonstrates each ENG-17x merge progressed the failure surface one step closer to the real production IAP boundary. The remaining issue is now at the IAP boundary itself, not in the workflow.

### Live evidence

**Run 25982799094** (push, branch `main`):

| Field | Value |
| --- | --- |
| `conclusion` | `failure` |
| `status` | `completed` |
| `createdAt` | `2026-05-17T05:50:35Z` |
| `updatedAt` | `2026-05-17T05:56:19Z` |
| `headSha` | `cb4d37ec67fc08e5d9800089d341ad284f8ee38c` (ENG-180 merge) |
| `event` | `push` |
| `url` | https://github.com/alexanderantipov1/fusion_crm/actions/runs/25982799094 |

**Job-level pass/fail**:

| Job | Conclusion | Notes |
| --- | --- | --- |
| WIF preflight (Workload Identity Federation) | success | |
| Lint + typecheck + tests | success | |
| Detect changed apps | success | |
| Build apps/web | success | |
| Build apps/api | success | |
| Production deploy preflight | success | STRICT=1 (ENG-174 §A) |
| Run alembic upgrade head (Cloud Run Job) | success | |
| Deploy fusion-api | success | Deployed `fusion-api-00053-ssf` and verified traffic via `pick_primary_revision` (ENG-179). |
| Deploy fusion-web | success | |
| Post deploy summary | success | |
| **Smoke fusion-api + auto-rollback on fail** | **failure** | Exit code 1 at the "Hit smoke endpoints" step; auto-rollback to `fusion-api-00052-xb7` then `exit 1` per ENG-174 §B. |

**Smoke job step trace** (`76374767866`):

1. `Run google-github-actions/auth@v2` — success.
2. `Run google-github-actions/setup-gcloud@v2` — success.
3. `Anonymous /healthz boot smoke (blocking)` — success.
   - `PUBLIC_HEALTHZ_URL: https://fusioncrm.app/api/healthz`
   - Output: `##[notice]anonymous https://fusioncrm.app/api/healthz returned 302 (boot OK)`
   - The script only fails on empty status or 5xx, so an IAP login redirect (302) passes the boot gate.
4. `Hit smoke endpoints` — **failure (exit 1, silent)**.
   - Env confirmed `IAP_AUDIENCE=800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess.apps.googleusercontent.com`, `SMOKE_BASE_URL=https://fusioncrm.app/api`, `EXPECTED_SHA=cb4d37ec67fc08e5d9800089d341ad284f8ee38c`.
   - Impersonation warning printed at `05:56:07.1359075Z` — token mint via WIF + SA impersonation succeeded (no `Invalid account type` or audience error).
   - `--- /healthz ---` echo printed at `05:56:08.2958981Z`.
   - `##[error]Process completed with exit code 1.` at `05:56:08.5209804Z` (~225 ms after the `--- /healthz ---` echo).
   - **No `::error::smoke fail:` annotation appears** — confirms `BODY=$(check "/healthz")` is still capturing the diagnostic lines as part of the BODY substitution. This is the same ENG-178 visibility defect identified in the prior session.
5. `Auto-rollback on smoke failure` — `::warning::Rolling fusion-api traffic back to fusion-api-00052-xb7`, traffic flipped, then `::error::Smoke check failed and traffic was rolled back to fusion-api-00052-xb7. Marking workflow as failed.` Final state observed in the same step's traffic dump:
   - `0%   fusion-api-00049-xiw` (tag `pr-57`)
   - `100% fusion-api-00052-xb7` (rollback target — previous primary)
   - `0%   fusion-api-00053-ssf` (the just-deployed revision, now demoted)
   - other tagged PR-preview entries at 0%

**Deploy-api job evidence** (`76374714494`):

- `Promote revision to 100% traffic` printed `100% LATEST (currently fusion-api-00053-ssf)`.
- `Verify traffic is actually on the new revision` step:
  - `Expected revision: fusion-api-00053-ssf`
  - `Active   revision: fusion-api-00053-ssf`
  - `##[notice]traffic on fusion-api-00053-ssf`
- `Restore latestRevision invariant (ENG-174 §C)` — succeeded; `spec.traffic[0].latestRevision == True` invariant restored.

So at the moment the smoke step ran, traffic was definitively on the
new revision built from `github.sha`. There is no "stale revision"
case here.

**Cloud Run application logs (`fusion-api`) around the failure**:

```
2026-05-17T05:55:21Z  INFO  Starting new instance. Reason: DEPLOYMENT_ROLLOUT ...
2026-05-17T05:55:26.674Z  INFO:     Started server process [1]
2026-05-17T05:55:26.674Z  INFO:     Waiting for application startup.
2026-05-17T05:55:26.675Z  INFO:     Application startup complete.
2026-05-17T05:55:26.682Z  INFO:     Uvicorn running on http://0.0.0.0:8080 ...
2026-05-17T05:55:26.682Z  INFO  Default STARTUP TCP probe succeeded after 1 attempt for container "fusion-api-1" on port 8080.
2026-05-17T05:55:33Z    NOTICE  (traffic flip completion)
2026-05-17T05:56:09.97Z NOTICE  (auto-rollback traffic flip)
2026-05-17T05:56:13Z    INFO
2026-05-17T05:56:14Z    INFO
```

The application was healthy and serving from `05:55:26Z`. **Crucially,
between `05:56:07Z` (smoke job mint complete) and `05:56:09Z`
(rollback start) there is no `fusion-api` request entry for `/healthz`.**
That is the strongest available signal that the smoke request was
rejected at the IAP edge and was never forwarded to Cloud Run.

**Load-balancer / IAP audit logs**: empty for the window. LB access
logging and IAP data-access audit logs are not currently enabled on
this project, so the exact HTTP status returned by IAP cannot be
read back from Cloud Logging right now.

## Answers to the brief's questions

- **Which job/step failed in run 25982799094?**
  Job `Smoke fusion-api + auto-rollback on fail` (id `76374767866`),
  step `Hit smoke endpoints`. Auto-rollback then ran and the workflow
  was failed explicitly per ENG-174 §B.

- **What commit SHA and Cloud Run revision were involved?**
  - Commit `cb4d37ec67fc08e5d9800089d341ad284f8ee38c` (the ENG-180
    pinned-IAP-client-ID merge).
  - Deployed revision `fusion-api-00053-ssf`, traffic was on it at
    smoke time, rolled back to `fusion-api-00052-xb7` (previous
    primary) on smoke fail.

- **Did token minting and pinned IAP audience work?**
  Token minting via WIF + SA impersonation (`cloud-build-deployer-sa@
  fusioncrm-494201.iam.gserviceaccount.com`) completed without error
  — `print-identity-token --impersonate-service-account` printed only
  the standard impersonation warning, no `Invalid account type` and
  no audience rejection. The pinned audience in the smoke env exactly
  equals `800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess.apps.google
  usercontent.com` (= workflow env `IAP_OAUTH_CLIENT_ID`). The
  request producer side is working as ENG-180 intended.

- **Did the smoke reach /healthz, and if yes, what failure class is
  visible?**
  - Anonymous boot smoke: reached the public URL, got HTTP 302 (IAP
    redirect), accepted as boot OK.
  - Deep authenticated smoke: the request was issued (curl ran, took
    ~225 ms in total), then `check()` saw a non-200 and entered the
    failure branch. The actual HTTP status printed by `check()` was
    swallowed by `BODY=$(check "/healthz")`, so it does not appear in
    the GitHub Actions log. Repo-side reading of `apps/api/routers/
    health.py` and the absence of any matching `fusion-api`
    application log in the same time window are both consistent with
    the deep request never reaching Cloud Run — i.e., IAP rejected it
    at the edge (most plausibly with a 302 to OAuth login, the same
    behaviour as for the anonymous request).
  - **Failure class**: HTTP status mismatch at the first deep-smoke
    `/healthz` (`expected 200`, got non-200). Indistinguishable from
    inside this run between "IAP token rejection → 302" and
    "edge auth misconfiguration → 401/403", but Cloud Run app-log
    silence rules out an application 5xx and rules out a `commit_sha`
    mismatch (commit_sha is only checked once the body parses).

- **Which Cloud Logging filter actually returns relevant logs?**
  - Returns useful entries (app-level):
    `resource.type="cloud_run_revision" AND resource.labels.service_name="fusion-api" AND timestamp>="<iso>" AND timestamp<="<iso>"` (project `fusioncrm-494201`).
  - Returns **empty** in this project today:
    - `resource.type="http_load_balancer" AND timestamp>=...`
    - `resource.type="iap_web" AND timestamp>=...`
    - `protoPayload.serviceName="iap.googleapis.com" AND timestamp>=...`
    - `logName="projects/fusioncrm-494201/logs/cloudaudit.googleapis.com%2Fdata_access" AND protoPayload.serviceName="iap.googleapis.com"`
  - Implication: LB access logging and IAP data-access audit logs
    are off in this project. Enabling either is the cleanest way to
    confirm the IAP edge response.

- **Is ENG-180 blocked only by ENG-178 smoke acceptance, or is there
  a remaining audience/client-id issue?**
  Mixed answer:
  1. **ENG-180 implementation is observably correct on the workflow
     side.** The pinned `IAP_OAUTH_CLIENT_ID` is now visible inside
     the smoke step env (`IAP_AUDIENCE = 800777477533-fv4l6nd3ou3c9
     euvr7re52rfcp680ess.apps.googleusercontent.com`) and the token
     mint did not reject it.
  2. **ENG-180 acceptance ("deep smoke passes through IAP")** cannot
     be claimed yet. The first IAP-fronted `/healthz` is being
     rejected at the edge (or returning a non-200 the smoke does
     not parse). Two plausible remaining-issue branches:
     - **a) IAP backend's `iap.oauth2ClientId` ≠ the pinned ID.**
       The workflow now pins `800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess`,
       but the actual `gcloud compute backend-services describe
       <fusion-api-backend> --global` would need to be read to
       confirm `iap.oauth2ClientId` matches. This is the most likely
       single root cause; `gcloud compute backend-services list` is
       outside the current harness allowlist so I could not verify.
     - **b) Deployer SA missing `roles/iap.httpsResourceAccessor`** on
       the IAP-protected resource. Same audience would mint and still
       be rejected by IAP's IAM gate.
  3. **ENG-178 acceptance is independently blocked** by the
     diagnostic-visibility defect: `BODY=$(check "/healthz")` and
     `BODY=$(check "/integrations")` still swallow the failure
     diagnostics. The captured `cat /tmp/body | head -50`, the
     `HTTP ${status} for ${path}` echo, and the `::error::smoke
     fail:` annotation never reach the GitHub Actions log. Until
     A1's logging patch (or an equivalent route-to-`>&2`) lands,
     every deploy-prod failure on `main` looks identical from CI.

## Ownership Notes

- All edits stayed within the assigned write scope (only
  `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/A2-live.md`).
- No source files, workflow files, or env files were touched.
- No GitHub Actions / Cloud Run / Linear state was mutated.
- No tokens, no secrets, no PHI, no tenant credential payloads, and
  no service-account JSON were logged. The pinned IAP client_id is
  a public OAuth client identifier (documented as such in
  `docs/DEPLOYMENT_RULES.md` §2 / `.github/workflows/deploy-prod.yml`
  comment block) so it is repeated verbatim above.
- Work followed `contract.md`. No contract changes requested.

## Linear Notes

- Recommended Linear status:
  - **ENG-178**: keep In Review / Blocked. Acceptance requires either
    (i) the diagnostic-visibility fix (route `check()` diagnostics
    and `fail()`'s `::error::` to stderr so `BODY=$(check ...)` keeps
    parsing JSON while operators see HTTP status + body) OR (ii) a
    successful deep smoke pass with a fresh deploy. (i) is owned by
    A1 in the parallel mission.
  - **ENG-180**: keep In Review. Workflow-side pinning is verified by
    live evidence (IAP_AUDIENCE in smoke env matches the public
    client ID and token mint succeeded). Acceptance ("audience
    participates end-to-end") is blocked on the IAP edge accepting
    the token — most plausibly a backend-service `iap.oauth2ClientId`
    mismatch or a missing IAM grant on the deployer SA.

- Comment/update for orchestrator to post (English; sanitized):
  > A2-live found run `25982799094` (HEAD `cb4d37e`) failed at the
  > "Hit smoke endpoints" step. The new revision
  > `fusion-api-00053-ssf` was successfully deployed and traffic was
  > on it at smoke time. Anonymous boot smoke got HTTP 302 from
  > `https://fusioncrm.app/api/healthz` (accepted as boot OK). The
  > deep IAP-authenticated `/healthz` then exited 1 ~225 ms after
  > the request started, with **no Cloud Run application log
  > entry** in that window — i.e., the request was rejected at the
  > IAP edge and did not reach `fusion-api`. The `::error::smoke
  > fail:` annotation is not visible in the GitHub log, confirming
  > ENG-178's `BODY=$(check ...)` diagnostic-swallow defect is still
  > present on `main`. The auto-rollback then restored traffic to
  > `fusion-api-00052-xb7`. Workflow-side ENG-180 is verified (env
  > `IAP_AUDIENCE` equals the pinned client ID and token mint via
  > WIF + impersonation succeeded). Remaining root-cause candidates,
  > in priority order: (1) the IAP backend's bound
  > `iap.oauth2ClientId` does not equal the pinned client ID
  > `800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess`; (2) the
  > deployer SA lacks `roles/iap.httpsResourceAccessor` on the
  > IAP-protected backend. Both are observable with one `gcloud
  > compute backend-services describe` call that the current
  > harness allowlist does not permit from A2-live.

- New issues suggested: see Suggested Next Tasks.

## Blockers

- `gcloud compute backend-services list/describe` is outside the
  current harness allowlist, so I cannot read the IAP backend's bound
  `iap.oauth2ClientId` or its IAM policy to confirm/disprove the
  client-id mismatch and IAM-grant hypotheses directly.
- LB access logging and IAP data-access audit logs are not enabled
  for `fusioncrm-494201`, so the exact HTTP status returned by IAP
  for the failing smoke request cannot be read back from Cloud
  Logging. Either enabling those (one-time IAM policy update + one
  `gcloud compute backend-services update --enable-logging
  --logging-sample-rate=1.0`) or A1's diagnostic-routing fix would
  surface the missing status.

## Integration Risks

- Every push to `main` is currently red until either A1's
  diagnostic-routing patch lands (so we can see the real status
  + body) OR the IAP edge accepts the token (so the deep smoke
  passes). The auto-rollback path is robust — traffic always lands
  back on the last-known-good revision — but the green-deploy
  acceptance criterion for ENG-178 and ENG-180 cannot be met until
  this is resolved.
- The dirty tenant credential files on the local working tree are
  unrelated to this failure mode and have no bearing on the smoke
  job (smoke only hits `/healthz`, `/readyz`, `/dashboard/summary`,
  and `/integrations`, and the failure is at the very first
  `/healthz`).

## Process / Lesson Notes

- `BODY=$(check "/healthz")` is the worst kind of CI-only bug: the
  rollback semantics (`$GITHUB_OUTPUT` append, `exit 1`) are
  intact, so production is safe — but operators cannot debug a
  failure from CI alone. ENG-181-style follow-up: emit `BODY` length,
  Content-Type, and the request id on success too, so we never have
  to wait for a failure to learn what the smoke actually saw.
- "Anonymous boot smoke passed (302)" is a confusing log line. The
  notice text reads as if the API is healthy, but actually the 302
  is exclusively IAP behaviour; the underlying Cloud Run app was
  never asked anything. Renaming this notice to `anonymous IAP
  front-door reachable; status 302 (login redirect, expected)`
  would prevent future operators from concluding "but boot smoke
  passed".
- LB access logging is the cheapest single dial that would have
  answered today's question outright (`gcloud compute backend-services
  update fusion-api-backend --enable-logging --logging-sample-rate=1.0
  --global`). It is a candidate for the next deploy hardening pass.

## Suggested Next Tasks

In priority order for Wave 2:

1. **Land A1's diagnostic-routing patch first** (mission
   `20260517-103524-eng-178-eng-180-deploy-smoke-recovery`). Route
   the `check()` and `fail()` diagnostics to stderr so
   `BODY=$(check ...)` keeps parsing JSON while operators see the
   actual HTTP status, body excerpt, and `::error::smoke fail:`
   annotation. This is the single unblocker for ENG-178 acceptance
   and the cheapest path to learning what IAP is actually returning.

2. **Verify IAP backend client-id binding (read-only, off-CI)**. Run
   `gcloud compute backend-services describe <fusion-api-backend>
   --global --project=fusioncrm-494201` and confirm that
   `iap.oauth2ClientId` equals
   `800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess`. If it does not,
   the workflow-side ENG-180 pin is correct but the backend pin is
   wrong; the fix is a single `gcloud compute backend-services
   update --iap=enabled,oauth2-client-id=<id>,oauth2-client-secret=<sec>`
   or the equivalent Cloud Console binding (out of scope for a
   worker task; needs an explicit operator step). This call requires
   `compute` in the harness allowlist.

3. **Verify IAP IAM grant on the deployer SA**. Confirm
   `cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com`
   has `roles/iap.httpsResourceAccessor` either on the IAP-protected
   backend service or at the project level. If missing, IAP would
   reject the bearer token regardless of audience.

4. **Enable LB access logging + IAP data-access audit logs** for
   `fusioncrm-494201`. One-time hardening that converts the current
   "edge rejection looks identical to app silence" mystery into a
   single log query for every future deploy.

5. **Once 1–3 are done, re-trigger deploy-prod from a noop bump
   commit** (or rerun ENG-180's merge commit) and read back the
   smoke step's HTTP status. If `/healthz` returns 200 with
   `commit_sha == github.sha`, ENG-178 and ENG-180 are both
   acceptable.

## Stop-Condition Trigger

None triggered. All requested commands ran read-only. The one
command that would have completed the live picture
(`gcloud compute backend-services list/describe`) is outside the
harness allowlist; that is reported as a Blocker rather than acted
on.
