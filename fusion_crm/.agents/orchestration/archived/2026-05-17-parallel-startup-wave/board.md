# Agent Orchestration Board

| Task | Linear Issue | Role | Owner | Branch | Worktree | Status | Write Scope | Depends On | Report |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A2-live | ENG-178 / ENG-180 | Claude Code explorer + Codex follow-up | terminal-1 / orchestrator | read-only | primary | complete | reports only | none | reports/A2-live.md, reports/A2-codex-followup.md |
| B1 | ENG-177 / ENG-165 | Codex reviewer | orchestrator | main | primary | complete | reports only | none | reports/B1.md |
| C1 | ENG-166 / ENG-167 / ENG-168 | Claude Code explorer | terminal-2 | read-only | primary | complete | reports only | none | reports/C1.md |
| D1 | ENG-178 / ENG-180 | Claude Code worker + Codex review | terminal-1 / orchestrator | main | primary | complete | `.github/workflows/deploy-prod.yml`, `tests/core/test_deploy_prod_smoke_logging.py`, report | A2-live, A2-codex-followup | reports/D1.md |
| E1 | ENG-177 / ENG-165 | Claude Code worker + Codex review | terminal-2 / orchestrator | main | primary | complete | `packages/tenant/credential_service.py`, `tests/tenant/test_credential_service.py`, report | B1 | reports/E1.md |
| F1 | ENG-178 / ENG-180 / ENG-177 / ENG-165 | Claude Code verifier | terminal-1 | main | primary | complete | report only | D1, E1 | reports/F1.md |
| G1 | ENG-169 / ENG-168 | Claude Code explorer | terminal-2 | read-only | primary | complete | report only | C1 | reports/G1.md |
| H1 | Salesforce prod issue | Claude Code explorer | terminal-1 | read-only | primary | complete | report only | user report | reports/H1.md |
| I1 | Salesforce prod issue | Codex controller | main | main | primary | complete | `infra/scripts/deploy_cloud_run.sh`, `infra/scripts/preflight_prod.sh`, `tests/core/test_env_reference_matches_settings.py`, report | H1 + user localhost redirect evidence | reports/I1.md |
| K1 | Salesforce prod issue | Codex controller | prod hotfix | primary | complete | Cloud Run env + traffic mutation, report | I1 + user approval | reports/K1-prod-hotfix.md |
| J1 | ENG-125 / ENG-19 / ENG-20 / ENG-73 | Codex worker + Codex review | worker-agent / orchestrator | main | primary | complete | tenant credentials API/UI/tests | user approval | reports/J1-review.md |
| L1 | Salesforce local reconnect loop | Codex controller | local hotfix | primary | complete | `apps/api/routers/integrations.py`, `packages/integrations/salesforce/client.py`, `packages/tenant/credential_service.py`, `apps/web/app/(staff)/integrations/salesforce/callback/page.tsx`, `apps/web/lib/api/hooks/useSfLeads.ts`, tests | user localhost pull failure | reports/L1-local-salesforce-reconnect.md |
| M1 | stabilization | Codex verifier/reviewer | orchestrator | main | primary | complete | current diff verification/review, orchestrator script lint cleanup | J1, K1, L1 | reports/M1-stabilization-review.md |
| N1 | data foundation architecture | Tesla read-only explorer + Codex review | subagent / orchestrator | read-only | primary | complete | architecture proposal only | user data model question | reports/N1-data-foundation-architecture.md |
| O1 | ENG-181..ENG-188 Linear sync | Codex orchestrator | orchestrator | main | primary | complete | Linear issues/comments + `linear-sync.md` only | N1, M1 | Linear project audit comment |
| O2 | Linear cleanup | Codex orchestrator | orchestrator | main | primary | complete | Linear statuses/comments + mission records only | O1 + user cleanup approval | Linear project cleanup comment |
| P1 | ENG-165 credentials polish | implementation worker + Codex review | Mill / orchestrator | worker fork | forked workspace | complete | credential UI/API tests only | O2 | reports/P1-eng165-credentials-polish.md |
| P2 | ENG-181..ENG-185 data foundation implementation plan | architecture worker + Codex review | Ohm / orchestrator | read-only | forked workspace | complete | report only | O2 | reports/P2-data-foundation-implementation-plan.md |
| Q0 | ENG-188 Alembic drift | Codex controller | orchestrator | main | primary | complete | model metadata only | P2 | reports/Q0-eng188-alembic-drift.md |
| Q1 | ENG-182 identity match candidate foundation | Claude Code worker + Codex review | Claude / orchestrator | main | primary | complete | `packages/identity/*`, one new Alembic revision, `tests/identity/*`, report | Q0 | reports/Q1.md |
| R1 | ENG-185 normalized person hint foundation | Claude Code worker + Codex review | Claude / orchestrator | main | primary | complete | `packages/ingest/*`, one new Alembic revision, `tests/ingest/*`, report | Q1 | reports/R1.md |
| R2 | ENG-185 follow-up pipeline integration plan | Claude Code explorer | Claude | read-only | primary | complete | report only | Q1, R1 plan | reports/R2.md |
| R3 | Wave R verification scout | Claude Code verifier | Claude | read-only | primary | complete | report only | Q1, R1 plan | reports/R3.md |
| S1 | ENG-185 identity match policy entry point | Claude Code worker + Codex review | Claude / orchestrator | main | primary | complete | `packages/identity/*`, `tests/identity/*`, report; no migration | Q1, R1, R2 | reports/S1.md |
| S2 | ENG-185 Salesforce cutover plan | Claude Code explorer | Claude | read-only | primary | complete | report only | S1 contract | reports/S2.md |
| S3 | Wave S verification scout | Claude Code verifier | Claude | read-only | primary | complete | report only | S1 contract | reports/S3.md |
| T1 | ENG-185 Salesforce cutover | Codex worker + Codex recovery review | Codex worker / orchestrator | main | primary | complete | `packages/ingest/sf_lead_service.py`, `tests/ingest/test_sf_lead_service.py`, `packages/ingest/CLAUDE.md`, recovery report; no migration | S1, S2 | reports/T1.md |
| T2 | Wave T verification scout | Codex verifier + Codex recovery review | Codex worker / orchestrator | read-only | primary | complete | recovery report only | T1 contract | reports/T2.md |

## File Ownership

| Path / Module | Owner | Status | Notes |
| --- | --- | --- | --- |
| GitHub Actions / Cloud Run logs | A2-live + Codex | complete | Request failed before app; backend IAP client and IAM grant are correct; next likely cause is missing email claim in impersonated OIDC token. |
| Tenant credential dirty diff | B1 | complete | One medium finding: expired credential can remain `is_default=True`. |
| ENG-166/167/168 planning | C1 | complete | ENG-168/Twilio starts first after B1/ENG-165 and ENG-169 gates. |
| `.github/workflows/deploy-prod.yml` + smoke test | D1 + Codex | complete | Added `--include-email`; no workflow rerun. |
| Tenant credential service/test | E1 + Codex | complete | Auto-clear default when status becomes non-active. |
| Local integration verification | F1 | complete | Focused bundle checks green; ready for Codex final review. |
| Runtime/Twilio next wave | G1 | complete | Recommends doc-only ADR wave before Twilio implementation. |
| Salesforce prod triage | H1 | complete | Prod runtime endpoints return 409; OAuth connect starts but no callback after 2026-05-16 23:15:06 UTC. |
| Salesforce callback env contract | I1 | complete | Added `SALESFORCE_CALLBACK_URL` to deploy script, preflight public URL gate, and required env-contract test. |
| Salesforce prod hotfix | K1 | complete | `fusion-api-sfcb-0016` has `SALESFORCE_CALLBACK_URL` and serves 100% traffic. `connect/start` now returns a prod callback URL. |
| Self-service integration credentials | J1 | complete | Worker implemented API/UI path for operator-entered provider credentials; Codex reviewed and verified focused tests. |
| Salesforce local reconnect loop | L1 | complete | Expired SF refresh tokens are marked `expired`; local callback page forwards real `code/state` to FastAPI instead of calling the mock callback. |
| Stabilization review | M1 | complete | `make verify`, focused backend tests, web lint/test, and `git diff --check` pass; full `mypy .`, `make test`, and `alembic check` remain blocked by existing repository-wide debt. |
| Data foundation architecture | N1 | complete | Recommended `ops.inquiry`, `ops.consultation`, `identity.match_candidate` as a policy-based match-decision ledger, and raw/hint/idempotent pipeline split into additive PRs. |
| Linear audit and sync | O1 | complete | Created ENG-181..ENG-188, added project audit note, and commented stale/scope-sensitive tasks without moving statuses. |
| Linear cleanup | O2 | complete | Moved implemented legacy slice work to Done, closed stale/duplicate/test issues, detached future milestone issues from canceled ENG-66, and left only intentional Backlog items active. |
| Credentials polish | P1 | complete | Provider credential form now has supported-provider gating, provider-specific labels, saved/error state, strict frontend/MSW schema validation, and backend cross-provider field rejection. |
| Data foundation implementation plan | P2 | complete | Proposed `ingest.normalized_person_hint`, `identity.match_candidate`, `ops.inquiry`, and `ops.consultation`; next gate is ENG-188 Alembic drift before migrations. |
| Alembic drift cleanup | Q0 | complete | Model metadata now matches existing tenant indexes and outreach server defaults; `alembic check` is clean. |
| Identity match candidate foundation | Q1 | complete | First additive implementation slice for `identity.match_candidate`; Codex review fixed tenant-person validation and recursive PHI/raw-payload evidence guard. |
| Normalized person hint foundation | R1 | complete | Sole Wave R writer and migration owner for `ingest.normalized_person_hint`; Codex review and focused verification complete. |
| Pipeline integration plan | R2 | complete | Read-only ENG-185 follow-up plan; no product edits. |
| Wave R verification scout | R3 | complete | Read-only migration-chain and verification checklist scout. |
| Identity match policy entry point | S1 | complete | Sole Wave S writer; identity-only `resolve_or_create_from_hint(...)`; no migration and no ingest cutover. Codex review and verification complete. |
| Salesforce cutover plan | S2 | complete | Read-only plan for the next ENG-185 wave after S1 review. |
| Wave S verification scout | S3 | complete | Read-only import-boundary, PHI, idempotency, and verification checklist scout. |
| Salesforce cutover | T1 | complete | Rewired `SfLeadIngestService` to normalized hints + identity match policy; no migration; Codex recovery review and verification complete. |
| Wave T verification scout | T2 | complete | Recovery report captures cutover checklist after background report-writing failure. |

## Blockers

- Production mutations require explicit user approval.
- Tenant credential implementation follow-up waits for B1 review.
- A2-live could not read IAP backend service config because Claude harness lacked `gcloud compute backend-services describe` allowlist; Codex completed that read-only check.
- Repository-wide full gates are not green outside this diff: `mypy .` has existing test typing debt and `make test` is blocked by tenant isolation Phase B fixture plus outreach/worker failures. ENG-188 fixed the previous `alembic check` drift.

## Review Notes

- A2-live: deploy-prod run `25982799094` failed in deep smoke at `/healthz`; `fusion-api-00053-ssf` was serving 100% traffic before rollback; no Cloud Run app request log appeared during the deep-smoke window, so failure likely occurred at IAP edge before Cloud Run.
- A2 Codex follow-up: `fusion-lb-backend-api` has the expected pinned IAP OAuth client ID, and the deployer service account has `roles/iap.httpsResourceAccessor`. Strong next hypothesis: add `--include-email` to the impersonated `gcloud auth print-identity-token` command.
- B1: focused tests passed under `.venv`: `.venv/bin/python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py` => 23 passed.
- C1: read-only plan accepted. It recommends ENG-168 Twilio/SMS as upstream after ENG-165/B1 and ENG-169 runtime ADR gates.
- D1: worker added `--include-email`; Codex removed an internal report reference from production comments and re-ran `python -m pytest tests/core/test_deploy_prod_smoke_logging.py` => 5 passed.
- E1: worker fixed default/status edge; Codex re-ran `.venv/bin/python -m pytest tests/tenant/test_credential_service.py` => 21 passed.
- F1: verified `python -m pytest tests/core/test_deploy_prod_smoke_logging.py` => 5 passed; `.venv/bin/python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py` => 24 passed; `git diff --check` clean.
- G1: next safe wave is three doc-only ADR tasks first (ENG-169 runtime, ENG-168a Twilio credential payload, ENG-168c SMS architecture), then Twilio client, then SMS controlled-send service with migration review.
- H1: prod Salesforce issue is runtime `409`/`SfNotConnectedError`; recent `connect/start` calls return 200 but no Salesforce callback appears afterward. Ask operator what Salesforce shows after clicking Connect.
- I1: user supplied redirect to `http://localhost:3000/integrations?sf_oauth_error=missing_pkce_cookie`. Root cause is missing `SALESFORCE_CALLBACK_URL` on prod Cloud Run env, allowing fallback to stale localhost callback data. Local contract patch is verified; prod deploy still requires explicit approval.
- K1: after user approval, Codex applied targeted Cloud Run env hotfix and shifted traffic to `fusion-api-sfcb-0016`. API-level `connect/start` verification confirms Salesforce authorize URL uses `https://fusioncrm.app/api/integrations/salesforce/callback`.
- J1: self-service credentials API/UI accepted after Codex fixed a unit-test mock. Focused backend/frontend checks are green.
- L1: local pull failed with Salesforce `invalid_grant: expired access/refresh token`. Codex fixed the local callback pass-through and added credential expiry on reconnect-required auth failures. Focused backend/frontend checks are green; localhost UI shows Salesforce `Not connected` with `Connect`.
- M1: `make verify` passed; focused backend bundle passed 71 tests; web lint/test passed; `git diff --check` clean. Full repo checks still expose existing unrelated debt and should be separate stabilization issues.
- N1: architecture agent read identity/ops/ingest/integrations/phi/interaction context and recommended the additive data-foundation split before writing migrations. Codex updated the match policy: automated by default, `auto_accepted` for high-confidence cross-provider matches, `open` only for ambiguous cases.
- O1: Linear now has explicit tasks for data foundation and full verify cleanup. Existing issue statuses were intentionally unchanged. ENG-92 and old M1 slice tasks should not be picked up literally without a code-vs-task cleanup pass.
- O2: Linear cleanup performed after user approval. Closed `ENG-144` as duplicate of `ENG-148`; closed archived/test noise `ENG-61`, `ENG-65`, `ENG-95`, `ENG-99`; detached future milestone work `ENG-81..ENG-86` from canceled parent `ENG-66`; current Backlog intentionally contains active near-term work, future domain packages, and pre-PHI/infrastructure gates.
- P1: Worker polished credential UI/schema/MSW tests. Codex added backend Pydantic cross-provider field rejection and re-ran web/backend focused checks, `make lint`, `make verify`, and `git diff --check`; all passed.
- P2: Worker produced the data-foundation implementation plan. Main risk: Salesforce ingest currently has hidden email/phone reactivation matching inside `SfLeadIngestService`; move this into shared `IdentityService` match policy before CareStack integration.
- Q0: Codex resolved ENG-188 without editing shipped migrations. `alembic check`, `make verify`, focused model tests, and `git diff --check` pass.
- Q1: Claude Code completed ENG-182 in the primary working tree with narrow identity/migration ownership. Codex reviewed the diff, fixed cross-tenant person-reference validation and nested evidence/conflict PHI-key rejection, then verified `tests/identity -q` (45 passed), focused ruff, `alembic check`, `make verify`, and `git diff --check`.
- Wave R: Planned with one active writer (R1) plus two read-only parallel tasks (R2/R3). This increases parallelism without allowing concurrent migration writers over the uncommitted Q1 base.
- R2/R3: Read-only parallel tasks completed while R1 continued. R2 proposed the ENG-185 follow-up identity/Salesforce cutover plan; R3 confirmed R1 must use Q1 revision `e1f2a3b4c5d6` as `down_revision` and left a post-R1 verification checklist.
- R1: Completed and Codex-reviewed. Codex corrected stale issue references to ENG-185 and verified ingest focused tests, adjacent-domain tests, `make verify`, `alembic upgrade head`, `alembic check`, downgrade/upgrade round-trip, and `git diff --check`.
- Wave S: Planned with one active writer (S1) plus two read-only parallel tasks (S2/S3). S1 owns the identity-only match policy entry point and must not add a migration or change Salesforce/CareStack ingest behavior.
- S1: Completed and Codex-reviewed. Verification passed: identity tests, adjacent-domain regression, `alembic check`, `git diff --check`, and `make verify`.
- Wave T: Planned with one active writer (T1) plus one read-only verifier (T2). T1 did not edit identity, migrations, API, frontend, or `ops.inquiry`. Background workers could not write reports under `.agents/**`, so Codex recorded incidents, reviewed the actual diff, created recovery reports, and verified focused gates plus `make verify`.
