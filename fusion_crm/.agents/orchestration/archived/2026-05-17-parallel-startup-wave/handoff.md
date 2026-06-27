# Agent Orchestration Handoff

Generated: 2026-05-19T05:26:00.898107+00:00
Mission folder: `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave`

## Resume Prompt

```text
Use the orchestrator protocol in .agents/orchestrator/PROTOCOL.md.

Resume mission from /Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave.
Read handoff.md first, then inspect backlog.md, daily-sprint.md, goal.md, acceptance.md, verification.md, linear-sync.md, contract.md, ownership.md, ownership.yaml, board.md, integration-plan.md, decision-log.md, runlog.md, incidents.md, lessons.md, runtime.json, and any reports needed for the next decision. Evaluate goal.md and acceptance.md, summarize current state, identify blockers, sync Linear if needed, apply accepted lessons, and prepare the next wave or integration plan. Do not implement feature work unless explicitly asked.
```

## Git Status

```text
M .github/workflows/deploy-prod.yml
 M .gitignore
 M apps/api/routers/integrations.py
 M apps/api/routers/tenant.py
 M apps/web/app/(staff)/integrations/salesforce/callback/page.tsx
 M apps/web/components/integrations/ProviderCard.tsx
 M apps/web/components/integrations/SfLeadsPanel.tsx
 M apps/web/lib/api/hooks/useCredentials.ts
 M apps/web/lib/api/hooks/useSfLeads.ts
 M apps/web/lib/api/schemas/tenant.ts
 M apps/web/lib/msw/init.tsx
 M apps/web/lib/msw/outreachHandlers.ts
 M apps/web/tests/unit/schemas.test.ts
 M infra/scripts/deploy_cloud_run.sh
 M infra/scripts/preflight_prod.sh
 M packages/actor/models.py
 M packages/audit/models.py
 M packages/auth/models.py
 M packages/identity/CLAUDE.md
 M packages/identity/models.py
 M packages/identity/repository.py
 M packages/identity/schemas.py
 M packages/identity/service.py
 M packages/ingest/CLAUDE.md
 M packages/ingest/models.py
 M packages/ingest/repository.py
 M packages/ingest/schemas.py
 M packages/ingest/service.py
 M packages/ingest/sf_lead_service.py
 M packages/integrations/models.py
 M packages/integrations/salesforce/client.py
 M packages/interaction/models.py
 M packages/ops/models.py
 M packages/outreach/models.py
 M packages/phi/models.py
 M packages/tenant/credential_service.py
 M packages/tenant/schemas.py
 M tests/api/test_integrations_salesforce.py
 M tests/core/test_env_reference_matches_settings.py
 M tests/ingest/test_sf_lead_service.py
 M tests/tenant/test_credential_service.py
?? .agents/
?? .claude/commands/orchestrator.md
?? Agent_Orchestration_Playbook_RU.md
?? apps/web/tests/unit/useCredentials.test.tsx
?? packages/db/alembic/versions/20260518_2010_e1f2a3b4c5d6_add_identity_match_candidate.py
?? packages/db/alembic/versions/20260518_2030_c7d8e9f1a2b3_add_ingest_normalized_person_hint.py
?? tests/api/test_tenant_credential_routes.py
?? tests/core/test_deploy_prod_smoke_logging.py
?? tests/identity/test_match_candidate_model.py
?? tests/identity/test_match_candidate_service.py
?? tests/identity/test_resolve_or_create_from_hint.py
?? tests/ingest/test_normalized_person_hint_model.py
?? tests/ingest/test_normalized_person_hint_service.py
```

## Mission

# Mission: parallel startup wave

## Outcome

- Prove the orchestration model can run independent workstreams in parallel without file ownership conflicts.
- Keep Codex as controller/reviewer while Claude Code handles read-only exploration and scoped implementation/planning work.
- Produce actionable reports for:
  - deploy-prod smoke evidence (`A2-live`);
  - tenant credential diff review (`B1`);
  - next implementation wave planning for ENG-166 / ENG-167 / ENG-168 (`C1`).

## Constraints

- Conversation with the user is in Russian; repository artifacts are English.
- Follow root `CLAUDE.md`, local `CLAUDE.md` files, and `docs/DEPLOYMENT_RULES.md` for deploy-related diagnostics.
- No commits, pushes, merges, deploys, workflow reruns, Cloud Run traffic/config changes, secrets/IAM edits, or destructive git commands.
- Worker reports are mandatory. Codex reviews reports/diffs before accepting work.
- Existing dirty tenant credential files are single-owner review territory. No parallel worker may edit them until Codex review decides the next step.

## Current State

- Branch: `main`, tracking `origin/main`.
- Active dirty files include:
  - deploy-smoke fix: `.github/workflows/deploy-prod.yml`, `tests/core/test_deploy_prod_smoke_logging.py`
  - tenant credential work: `apps/api/routers/tenant.py`, `packages/tenant/credential_service.py`, `packages/tenant/schemas.py`, `tests/tenant/test_credential_service.py`, `tests/api/test_tenant_credential_routes.py`
  - orchestration/policy files under `.agents/` and `.claude/settings.local.json`
- Linear candidates reviewed:
  - ENG-178 / ENG-180: deploy-smoke acceptance still open.
  - ENG-177 / ENG-165: tenant credential UI/API work overlaps current dirty files.
  - ENG-166 / ENG-167 / ENG-168: high-priority next provider/workflow tracks suitable for read-only decomposition.

## Waves

### Wave 1

- Planned:
  - A2-live: Claude Code explorer, read-only deploy-prod / Cloud Run evidence collection.
  - B1: Codex reviewer, read-only review of current tenant credential diff.
  - C1: Claude Code explorer, read-only planning for ENG-166 / ENG-167 / ENG-168.
- Running:
- Complete:
  - A2-live: live deploy-prod evidence collected.
  - B1: tenant credential diff reviewed.
  - C1: ENG-166/167/168 planning completed.
- Blocked:
  - Any production action requires explicit user approval.
  - Tenant credential implementation follow-up waits for B1 review.
  - Deploy-smoke root cause still needs a workflow patch and user-approved rerun.

## Decisions

- 2026-05-17: Use a separate mission folder for broad parallel orchestration rather than overloading the deploy-smoke mission.
- 2026-05-17: A2-live and C1 are safe to run as Claude Code read-only explorers. B1 stays local to Codex to avoid adding another writer over existing dirty tenant files.
- 2026-05-17: Workstreams are parallel because their write scopes are disjoint: A2-live writes only `reports/A2-live.md`, C1 writes only `reports/C1.md`, B1 writes only `reports/B1.md` and mission board updates.
- 2026-05-17: Wave 1 completed. A2-live found the deploy request likely dies at IAP edge; B1 found a medium tenant default/status edge case; C1 recommended ENG-168/Twilio foundations first after credential/runtime gates.
- 2026-05-17: Codex completed read-only IAP backend follow-up. Backend OAuth client ID and deployer `roles/iap.httpsResourceAccessor` are correct. Next deploy-smoke hypothesis is missing `email` claim in the impersonated OIDC token; candidate fix is `--include-email`.

### Wave 2

- Planned:
  - D1: Claude Code worker, local deploy-prod smoke token patch.
  - E1: Claude Code worker, tenant credential default/status edge fix.
- Running:
- Complete:
  - D1: deploy-prod smoke token now uses `--include-email`, with static regression test.
  - E1: tenant credential metadata update clears `is_default` when status becomes non-active.
- Blocked:
  - Any deploy-prod workflow rerun or production mutation requires explicit user approval.

## Wave 2 Decision

- 2026-05-17: Wave 2 completed. Claude Code wrote D1/E1; Codex reviewed the diffs, removed an internal report reference from workflow comments, and re-ran focused tests.

### Wave 3

- Planned:
  - F1: Claude Code verifier, local integration bundle verification.
  - G1: Claude Code explorer, next runtime/Twilio implementation wave brief.
- Running:
- Complete:
  - F1: local integration bundle verification complete; focused checks green.
  - G1: next runtime/Twilio wave brief complete; recommends doc-only ADR wave first.
- Blocked:
  - Commits, pushes, PR creation, Linear mutation, workflow reruns, and production operations require explicit user approval.

## Wave 3 Decision

- 2026-05-17: Wave 3 completed. F1 verified the local bundle and flagged `.claude/scheduled_tasks.lock` as exclude-from-staging. G1 recommended a doc-only ADR wave before any Twilio/SMS implementation.

### Wave 4

- Planned:
  - H1: Claude Code explorer, read-only Salesforce production triage.
- Running:
- Complete:
  - H1: Salesforce production triage complete.
- Blocked:
  - Any production mutation, deploy-prod rerun, commit, push, PR creation, or Linear mutation requires explicit user approval.

## Wave 4 Decision

- 2026-05-17: H1 completed. Production Salesforce runtime endpoints return 409 because no active OAuth credential is resolved. Since 2026-05-16 23:15:06 UTC, `connect/start` succeeds but no callback hits appear, so the next diagnostic signal is the browser/Salesforce page shown immediately after clicking Connect Salesforce.
- 2026-05-17: User supplied the missing signal: Salesforce redirects to `http://localhost:3000/integrations?sf_oauth_error=missing_pkce_cookie`. Codex confirmed production Cloud Run lacks `SALESFORCE_CALLBACK_URL`, while the reference file already documents the correct prod URL. I1 added the env var to the deploy script, preflight public URL gate, and required env-contract test. No production mutation was performed.
- 2026-05-17: User approved production mutation. K1 set `SALESFORCE_CALLBACK_URL` on a new `fusion-api-sfcb-0016` revision and moved `fusion-api` traffic to it. Direct Cloud Run proxy verification shows `POST /integrations/salesforce/connect/start` now returns a Salesforce authorize URL whose `redirect_uri` is `https://fusioncrm.app/api/integrations/salesforce/callback`.

### Wave 5

- Planned:
  - J1: worker implementation for self-service integration credential entry in the app.
- Running:
- Complete:
  - K1: production Salesforce callback hotfix.
  - J1: self-service integration credential API/UI implementation and Codex review.
- Blocked:
  - Full browser visual smoke for the new credentials form remains pending.

## Wave 5 Decision

- 2026-05-17: J1 completed. Worker added tenant-scoped `POST /tenant/credentials`, metadata update/list endpoints, service-layer encrypted bootstrap credential persistence, frontend schemas/hooks, and provider-card credentials form. Codex fixed a test mock and verified 48 backend focused tests, ruff, web vitest/typecheck/lint, and `git diff --check`.

## Backlog

# Mission Backlog

## Intake Queue

| ID | Title | Type | Priority | Risk | Area | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | Live deploy-prod smoke evidence | research | blocker | medium | GitHub Actions, Cloud Run logs | planned | Linear ENG-178/ENG-180. Read-only. |
| I2 | Tenant credential diff review | review | high | medium | `packages/tenant`, `apps/api/routers/tenant.py`, tests | planned | Linear ENG-177/ENG-165 overlap. Codex review only. |
| I3 | Plan next provider workflow wave | research | high | medium | ENG-166, ENG-167, ENG-168 | planned | Read-only decomposition into safe tasks. |

## Backlog Item Template

ID:
Title:
Type: feature | bug | refactor | infra | research
Priority: blocker | high | normal | later
Risk: low | medium | high
Area:
Expected files:
Dependencies:
Acceptance criteria:
Linear issue:

## Daily Sprint

# Daily Sprint Plan

Date: 2026-05-17
Mission: parallel startup wave
Linear project: Fusion CRM — Engineering

## Sprint Goal

- Run three independent workstreams in parallel and use reports to choose the next implementation wave.

## Capacity

| Role | Count | Notes |
| --- | --- | --- |
| Orchestrator | 1 | planning, Linear sync, reviews |
| Workers | 2 | Claude Code read-only explorers: A2-live and C1 |
| Integrator | 1 | merge/conflict owner |
| Verifier | 1 | verification gate |

## Planned Waves

| Wave | Goal | Tasks | Launch Window | Integration Point | Status |
| --- | --- | --- | --- | --- | --- |
| Wave 1 | Parallel read-only evidence and planning plus Codex review | A2-live, B1, C1 | now | after reports | complete |

## Decision Windows

- Planning: freeze ownership and briefs.
- Report review: compare A2-live/C1 outputs and B1 findings.
- Integration: no integration in Wave 1 unless a follow-up is explicitly approved.
- Handoff: summarize next wave candidates and blockers.

## Done Criteria

- Reports exist for A2-live, B1, and C1.
- No worker edited outside assigned write scope.
- Next wave is clearly selected with file ownership and risk notes.

## Goal

# Mission Goal

## Desired Outcome

Stabilize the current Salesforce/CareStack data-foundation path and start
the next additive implementation wave while keeping Codex as orchestrator,
reviewer, and verifier and Claude Code as scoped implementation worker.

## Done State

This mission segment is complete when:

- `ENG-188` Alembic drift is resolved and Linear reflects the result.
- `ENG-182` has a reviewed `identity.match_candidate` foundation patch or a
  documented blocker report.
- Worker changes stay inside assigned ownership.
- No shipped Alembic revision is edited.
- No `.env*`, secrets, deploy scripts, GitHub Actions deploy workflow, Cloud
  Run services/jobs, commits, pushes, merges, or deployments are performed
  without explicit user approval.
- Codex records verification evidence and updates Linear/mission handoff.

## Evidence Required

- `reports/Q0-eng188-alembic-drift.md` exists and documents the Alembic drift
  fix.
- `reports/Q1.md` exists for the `ENG-182` worker result, or the worker
  blocker is recorded.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after integration.
- Focused tests for changed domains pass.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-188`, `ENG-181`, and `ENG-182`.

## Constraints

- Conversation with the user is in Russian.
- Repository artifacts are written in English.
- Follow root and local `CLAUDE.md` files.
- PHI stays out of `ops` and identity matching evidence.
- `identity.person.id` remains the canonical `person_uid`.
- Additive migrations only; existing migrations are immutable.

## Evaluator

Codex orchestrator evaluates the mission goal after every worker report and
returns only:

- `complete`
- `not complete`

If `not complete`, Codex lists the smallest missing evidence or blocker.

## Continuation Budget

Maximum next actions before asking the user again:

1. Review Q1 report and diff.
2. Run focused verification.
3. Apply only minor integration fixes inside Q1 ownership if needed.
4. Update Linear and handoff.

Escalate if Q1 requires broader architecture changes, production/deploy
actions, edits outside ownership, or a second failed worker launch.

## Latest Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/Q0-eng188-alembic-drift.md` documents the ENG-188 Alembic drift
  fix.
- `reports/Q1.md` documents the ENG-182 implementation, Codex review fix, and
  post-review verification.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0.
- `.venv/bin/python -m pytest tests/identity -q` exits 0 with 45 passed.
- `make verify` exits 0.
- `git diff --check` exits 0.
- Linear sync for ENG-182 is updated to In Review with evidence comments;
  ENG-181 receives a parent progress comment. ENG-188 was already synced Done
  after Q0.

## Next Segment: Wave R

Date: 2026-05-19

### Desired Outcome

Start the next additive data-foundation wave with more parallelism while
keeping only one active migration writer.

### Done State

Wave R is complete when:

- `ENG-185` has either a reviewed `ingest.normalized_person_hint` foundation
  patch or a documented blocker report.
- `ENG-185` has a read-only implementation plan that accounts for Q1/R1 and
  the existing Salesforce ingest path.
- The verification scout report identifies the post-R1 review checklist and
  any migration-chain risk.
- Worker changes stay inside assigned ownership.
- No shipped Alembic revision is edited.
- No `.env*`, secrets, deploy scripts, GitHub Actions deploy workflow, Cloud
  Run services/jobs, commits, pushes, merges, or deployments are performed
  without explicit user approval.

### Evidence Required

- `reports/R1.md` exists for the `ENG-185` worker result, or the worker
  blocker is recorded.
- `reports/R2.md` exists for the `ENG-185` read-only plan.
- `reports/R3.md` exists for verification scouting.
- Focused ingest tests pass after R1, unless a blocker is documented.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after R1 review,
  unless a blocker is documented.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-185`; `ENG-183` remains
  untouched because it is the later `ops.inquiry` slice.

### Continuation Budget

Maximum next actions before asking the user again:

1. Launch R1/R2/R3.
2. Review R1/R2/R3 reports.
3. Run focused verification.
4. Apply only minor integration fixes inside R1 ownership if needed.
5. Update Linear and handoff.

Escalate if R1 requires broader architecture changes, a second migration
writer, production/deploy actions, edits outside ownership, or a second failed
worker launch.

### Latest Wave R Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/R1.md` documents the ENG-185 normalized-hint implementation,
  Codex review correction, and post-review verification.
- `reports/R2.md` documents the follow-up ENG-185 pipeline integration plan.
- `reports/R3.md` documents the verification scout checklist.
- `.venv/bin/python -m pytest tests/ingest -q` exits 0 with 31 passed.
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/ops -q` exits
  0 with 95 passed.
- `make verify` exits 0.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after local
  `upgrade head`.
- `cd packages/db && ../../.venv/bin/alembic downgrade -1 && ../../.venv/bin/alembic upgrade head && ../../.venv/bin/alembic check`
  exits 0.
- `git diff --check` exits 0.
- Linear sync: `ENG-185` is ready for In Review with evidence; `ENG-183` was
  corrected back to Backlog.

## Next Segment: Wave S

Date: 2026-05-19

### Desired Outcome

Implement the identity-only ENG-185 follow-up that introduces
`IdentityService.resolve_or_create_from_hint(...)` and its match policy result
contract, while keeping Salesforce/CareStack cutover and `ops.inquiry` out of
scope.

### Done State

Wave S is complete when:

- `ENG-185` has either a reviewed identity match policy entry-point patch or a
  documented blocker report.
- A read-only Salesforce cutover plan identifies the next safe wave after the
  identity service is reviewed.
- A read-only verification scout report identifies import-boundary,
  idempotency, PHI/raw-payload, tenant isolation, and migration-free review
  risks.
- Worker changes stay inside assigned ownership.
- No Alembic revision is added or edited.
- No Salesforce/CareStack behavior, `ops.inquiry`, `.env*`, secrets, deploy
  scripts, GitHub Actions deploy workflow, Cloud Run services/jobs, commits,
  pushes, merges, or deployments are performed without explicit user approval.

### Evidence Required

- `reports/S1.md` exists for the identity match policy worker result, or the
  worker blocker is recorded.
- `reports/S2.md` exists for the Salesforce cutover plan.
- `reports/S3.md` exists for verification scouting.
- Focused identity tests pass after S1, unless a blocker is documented.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after S1 review,
  unless a blocker is documented.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-185`; `ENG-183` remains
  untouched because it is the later `ops.inquiry` slice.

### Continuation Budget

Maximum next actions before asking the user again:

1. Launch S1/S2/S3.
2. Review S1/S2/S3 reports.
3. Run focused verification.
4. Apply only minor integration fixes inside S1 ownership if needed.
5. Update Linear and handoff.

Escalate if S1 requires broader architecture changes, any migration writer,
production/deploy actions, edits outside ownership, PHI-sensitive decisions, or
a second failed worker launch.

### Latest Wave S Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/S1.md` documents the ENG-185 identity match policy entry point,
  Codex review, and post-review verification.
- `reports/S2.md` documents the future Salesforce cutover plan.
- `reports/S3.md` documents the Wave S verification scout checklist.
- `.venv/bin/python -m pytest tests/identity -q` exits 0 with 66 passed.
- `.venv/bin/python -m pytest tests/identity tests/ingest tests/ops -q` exits
  0 with 116 passed.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 with no new upgrade
  operations detected.
- `git diff --check` exits 0.
- `make verify` exits 0 after a small orchestrator-tooling lint fix outside
  product scope.
- Linear sync: `ENG-185` is ready to return to In Review with evidence;
  `ENG-183` remains Backlog.

## Next Segment: Wave T

Date: 2026-05-19

### Desired Outcome

Cut Salesforce Lead pull over to the reviewed ENG-185 hint + identity match
policy path while preserving the current API/UI contract and
`is_reactivation` semantics.

### Done State

Wave T is complete when:

- Salesforce `SfLeadIngestService.pull_recent(...)` captures a raw event,
  captures one normalized person hint from that raw event, calls
  `IdentityService.resolve_or_create_from_hint(...)`, and upserts the lead.
- Hidden SF-specific identity matching is removed from the ingest service.
- The manual pull API shape and frontend contract remain unchanged.
- Worker changes stay inside assigned ownership.
- No Alembic revision is added or edited.
- No `ops.inquiry`, `.env*`, secrets, deploy scripts, GitHub Actions deploy
  workflow, Cloud Run services/jobs, commits, pushes, merges, or deployments
  are performed without explicit user approval.

### Evidence Required

- `reports/T1.md` exists for the Salesforce cutover worker result, or the
  worker blocker is recorded.
- `reports/T2.md` exists for verification scouting.
- Focused ingest/API/identity tests pass after T1, unless a blocker is
  documented.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 after T1 review,
  unless a blocker is documented.
- `git diff --check` exits 0.
- Linear comments/statuses are synced for `ENG-185`; `ENG-183` remains
  untouched because it is the later `ops.inquiry` slice.

### Continuation Budget

Maximum next actions before asking the user again:

1. Launch T1/T2.
2. Review T1/T2 reports.
3. Run focused verification.
4. Apply only minor integration fixes inside T1 ownership if needed.
5. Update Linear and handoff.

Escalate if T1 requires identity edits, schema/migration work, API/UI changes,
production/deploy actions, edits outside ownership, PHI-sensitive decisions, or
a failed worker launch.

### Latest Wave T Evaluation

Date: 2026-05-19
Result: complete

Evidence:

- `reports/T1.md` documents the Salesforce cutover recovery result.
- `reports/T2.md` documents the verification scout recovery result.
- `SfLeadIngestService.pull_recent(...)` now captures raw event, captures a
  normalized person hint using the returned `raw_event.id`, builds `MatchHintIn`,
  calls `IdentityService.resolve_or_create_from_hint(...)`, fetches the person,
  and upserts the lead.
- Old hidden identity matching calls are removed from Salesforce ingest.
- `.venv/bin/python -m pytest tests/ingest/test_sf_lead_service.py -q` exits 0
  with 10 passed.
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q`
  exits 0 with 111 passed.
- `cd packages/db && ../../.venv/bin/alembic check` exits 0 with no new upgrade
  operations detected.
- `git diff --check` exits 0.
- Focused ruff and mypy on T1 files exit 0.
- `make verify` exits 0.
- Process incidents `INC-20260519-004` and `INC-20260519-005` document the
  failed worker report-writing path; no code blocker remains.
- Linear sync: `ENG-185` is ready to return to In Review with evidence;
  `ENG-183` remains Backlog.

## Acceptance

# Acceptance Criteria

Use this file for concrete pass/fail criteria. Keep it more specific than
`goal.md`.

## Wave S Criteria

| ID | Criterion | Evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| S-AC-1 | S1 implements an identity-owned `MatchHintIn` input DTO and `ResolveFromHintResult` output DTO without importing `ingest` into `identity`. | `reports/S1.md`, Codex diff review | pass | Identity-only boundary. |
| S-AC-2 | S1 implements `IdentityService.resolve_or_create_from_hint(...)` with source-link recapture, auto-accepted match, open ambiguous match, and new-person fallback behavior. | `reports/S1.md`, focused identity tests | pass | No Salesforce/CareStack behavior changes. |
| S-AC-3 | S1 writes no Alembic revision and edits no shipped migration. | `git status --short`, Codex diff review, `alembic check` | pass | Wave S is migration-free. |
| S-AC-4 | Match policy evidence/conflicts remain PHI-free and raw-payload-free. | `reports/S1.md`, tests covering recursive guard | pass | Defense in depth with existing match candidate guard. |
| S-AC-5 | Tenant isolation and idempotency are covered for candidate lookup, source-link recapture, and active hint/candidate reuse. | `reports/S1.md`, focused identity tests | pass | Must not leak cross-tenant candidates. |
| S-AC-6 | S2 produces the next Salesforce cutover plan after S1, with write scope, test rewrite plan, and verification gate. | `reports/S2.md` | pass | Report-only task. |
| S-AC-7 | S3 produces the Wave S verification scout checklist. | `reports/S3.md` | pass | Report-only task. |
| S-AC-8 | Codex focused verification passes after S1 review or blockers are documented. | `pytest tests/identity -q`, `alembic check`, `git diff --check`, `make verify` if applicable | pass | Orchestrator-owned evidence. |

## Wave T Criteria

| ID | Criterion | Evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| T-AC-1 | Salesforce pull captures a raw event before any normalization, then captures a normalized person hint using the returned raw event id. | `reports/T1.md`, tests | pass | Preserve capture-then-route. |
| T-AC-2 | Salesforce pull calls `IdentityService.resolve_or_create_from_hint(...)` and no longer reaches into `IdentityService._repo` or calls email/phone resolver ladder methods. | `reports/T1.md`, Codex diff review | pass | Removes hidden matching path. |
| T-AC-3 | `is_reactivation` is mapped from `ResolveFromHintResult.was_existing_person_match` and old branch semantics are preserved. | `reports/T1.md`, tests | pass | Re-pull/open/new remain false; auto-accept true. |
| T-AC-4 | Manual pull API and `SfLeadOut` DTO shape remain unchanged. | focused API tests | pass | No route/frontend changes. |
| T-AC-5 | T1 writes no Alembic revision and edits no identity/ops/apps files. | `git status`, Codex diff review, `alembic check` | pass | Wave T is migration-free. |
| T-AC-6 | T2 produces the Wave T verification scout checklist. | `reports/T2.md` | pass | Recovery report after worker sandbox write failure. |
| T-AC-7 | Codex focused verification passes after T1 review or blockers are documented. | focused pytest, `alembic check`, `git diff --check`, `make verify` | pass | Orchestrator-owned evidence. |

## Out Of Scope

- `ENG-183 ops.inquiry`.
- Salesforce/CareStack behavior changes.
- API routes, worker jobs, deploy scripts, GitHub Actions, Cloud Run, env vars,
  secrets, commits, pushes, merges, deployments.
- Any Alembic revision.

## Do Not Accept If

- Required reports are missing.
- Worker changes exceed ownership.
- `identity` imports `ingest`.
- Any migration file is added or edited.
- Salesforce/CareStack behavior changes land in Wave S.
- PHI-looking or raw-payload keys are accepted in match evidence/conflicts.
- Verification is not run or failing without a documented pre-existing blocker.

## Verification

# Verification Plan

Use this file for commands and review checks that prove acceptance criteria.

## Wave S Local Verifier

Commands after S1 reports:

```bash
.venv/bin/python -m pytest tests/identity -q
set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check
git diff --check
make verify
```

Focused review checks:

- S1 changed only `packages/identity/**`, `tests/identity/**`,
  `packages/identity/CLAUDE.md`, and `reports/S1.md`.
- S2/S3 changed only their report files.
- No file under `packages/db/alembic/versions/**` was added or edited by S1.
- `identity` does not import `packages.ingest`.
- `MatchHintIn` contains only normalized person-hint fields, not raw provider
  payloads.
- `ResolveFromHintResult.was_existing_person_match` can map cleanly to the
  current Salesforce `is_reactivation` behavior in the next wave.
- Source-link recapture does not write a match candidate.
- Auto-accept writes source link before `MatchCandidate(status="auto_accepted")`.
- Open ambiguous matches do not block the caller from receiving a usable person.

## Semantic Verifier

Review:

- `goal.md`
- `acceptance.md`
- `contract.md`
- `ownership.md`
- `ownership.yaml`
- `reports/S1.md`
- `reports/S2.md`
- `reports/S3.md`

Decision:

- accepted
- not accepted

If not accepted, list only missing evidence or blockers.

## Full Verification

For Fusion CRM, use the required verify loop when appropriate:

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

Known mission context: prior focused gates were green, while some full
repository-wide gates have separate tracked debt. Do not hide those blockers;
separate current-diff acceptance from repository-wide health.

## Wave T Local Verifier

Commands after T1 reports:

```bash
.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q
set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check
git diff --check
make verify
```

Focused review checks:

- T1 changed only `packages/ingest/sf_lead_service.py`,
  `tests/ingest/test_sf_lead_service.py`, `packages/ingest/CLAUDE.md`, and
  `reports/T1.md`.
- T2 changed only `reports/T2.md`.
- No file under `packages/db/alembic/versions/**` was added or edited.
- No identity/ops/apps files were edited by T1.
- `SfLeadIngestService` still captures raw event before normalized hint.
- `SfLeadIngestService` no longer calls `self._identity._repo`,
  `resolve_by_email`, `resolve_by_phone`, `add_source_link`, or
  `resolve_or_create_person`.
- Raw SOQL records are not passed into identity.

## Linear Sync

# Linear Sync

## Policy

- The orchestrator creates and moves Linear issues.
- Workers do not create, split, close, or reprioritize Linear issues.
- Workers may reference the assigned Linear issue in reports.
- Mission folder remains the technical source of truth; Linear is the project board.

## Project / Epic

Linear team: Engineering
Linear project: Fusion CRM — Engineering
Parent issue: TBD

## Status Mapping

| Orchestration Status | Linear Status |
| --- | --- |
| intake | Backlog |
| planned | Ready |
| running | In Progress |
| blocked | Blocked |
| needs-integration | Needs Integration |
| reviewing | In Review |
| verified | Verified |
| done | Done |

## Issue Map

| Task | Linear Issue | Title | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| A2-live | ENG-178 / ENG-180 | Live deploy-prod smoke evidence | complete | Claude Code + Codex | Deep smoke likely rejected at IAP edge before Cloud Run; backend IAP client and deployer IAP accessor are correct; next hypothesis is missing OIDC email claim. |
| B1 | ENG-177 / ENG-165 | Tenant credential diff review | complete | Codex | One medium edge case before acceptance. |
| C1 | ENG-166 / ENG-167 / ENG-168 | Next provider workflow wave planning | complete | Claude Code | ENG-168/Twilio foundations first after gates. |
| D1 | ENG-178 / ENG-180 | Deploy smoke email claim patch | complete | Claude Code + Codex | Local patch only; needs user-approved deploy-prod run before status move. |
| E1 | ENG-177 / ENG-165 | Tenant credential default/status edge fix | complete | Claude Code + Codex | Focused service tests green; broader route/API acceptance still pending. |
| F1 | ENG-178 / ENG-180 / ENG-177 / ENG-165 | Local integration bundle verification | complete | Claude Code | Focused checks green; ready for Codex final review. |
| G1 | ENG-169 / ENG-168 | Runtime/Twilio next wave brief | complete | Claude Code | Recommends ADR-only wave before implementation. |
| H1 | Salesforce prod issue | Production Salesforce read-only triage | complete | Claude Code | Runtime routes return 409; OAuth start succeeds but callback no longer appears. |
| I1 | Salesforce prod issue | Salesforce callback env contract fix | complete | Codex | Local fix adds `SALESFORCE_CALLBACK_URL` to deploy/preflight/env-contract tests; production still needs approved deploy. |
| K1 | Salesforce prod issue | Targeted Salesforce callback prod hotfix | complete | Codex | `fusion-api-sfcb-0016` serves 100% traffic with `SALESFORCE_CALLBACK_URL`; start URL now uses prod callback. |
| J1 | ENG-125 / ENG-19 / ENG-20 / ENG-73 | Self-service integration credentials UI/API | complete | Worker + Codex | API/UI implementation verified with focused backend/frontend checks. |
| N1 | ENG-181 / ENG-182 / ENG-183 / ENG-184 / ENG-185 | Data foundation architecture | synced | Codex + Tesla | Linear parent/children created for identity matching, inquiry, consultation, and normalized ingest hints. |
| V1 | ENG-186 / ENG-187 / ENG-188 | Full verify cleanup | synced | Codex | Backlog issues created for full `mypy .`, full `make test`, and Alembic drift gates. |
| O2 | ENG-1..ENG-20 / ENG-61 / ENG-65 / ENG-72..ENG-77 / ENG-81..ENG-86 / ENG-88..ENG-93 / ENG-95 / ENG-99 / ENG-144 | Linear cleanup | complete | Codex | Closed stale/duplicate/test issues, detached future milestone issues from canceled parent ENG-66, and left only intentional Backlog work active. |
| P1 | ENG-165 | Credentials polish | complete | Mill + Codex | Implementation complete and locally verified; move to In Review. |
| P2 | ENG-181 / ENG-182 / ENG-183 / ENG-184 / ENG-185 | Data foundation implementation plan | complete | Ohm + Codex | Report complete; parent moves to In Review, children stay Backlog until ENG-188 and PR split. |
| Q0 | ENG-188 | Alembic drift cleanup | complete | Codex | Metadata alignment complete; `alembic check` clean; issue moved to Done. |
| Q1 | ENG-182 | Identity match candidate foundation | complete | Claude Code + Codex | Implementation and Codex review complete; ENG-182 synced to In Review with verification evidence. |
| R1 | ENG-185 | Normalized person hint foundation | complete | Claude Code + Codex | Implementation and Codex review complete; ENG-185 synced to In Review with verification evidence. |
| R2 | ENG-185 | Follow-up pipeline integration plan | complete | Claude Code | Read-only planning under the same Linear issue; report complete. |
| R3 | n/a | Wave R verification scout | complete | Claude Code | Mission-local verification scout; report complete. |
| S1 | ENG-185 | Identity match policy entry point | complete | Claude Code + Codex | Implementation and Codex review complete; no migration or Salesforce cutover. |
| S2 | ENG-185 | Salesforce cutover plan | complete | Claude Code | Read-only planner for the next ENG-185 wave; report complete. |
| S3 | n/a | Wave S verification scout | complete | Claude Code | Mission-local verification scout; report complete. |
| T1 | ENG-185 | Salesforce cutover | complete | Codex worker + Codex | Sole Wave T writer; no migration, no API/UI changes; recovery-reviewed and verified. |
| T2 | n/a | Wave T verification scout | complete | Codex worker + Codex | Mission-local recovery report after worker report-write failure. |

## Sync Log

- 2026-05-17: Linear candidates reviewed. Do not move Linear statuses until reports are reviewed.
- 2026-05-17: Parallel Wave 1 reports complete. Linear comments/status updates still pending orchestrator approval.
- 2026-05-17: Codex read-only follow-up completed for A2-live. Do not move ENG-178/ENG-180 until the workflow patch is reviewed and a user-approved deploy-prod run passes.
- 2026-05-17: Wave 2 local patches complete and Codex-reviewed. Do not move ENG-178/ENG-180 until deploy-prod is user-approved and green. ENG-177/ENG-165 can proceed to broader acceptance review.
- 2026-05-17: Wave 3 reports complete. No Linear mutation performed.
- 2026-05-17: H1 triage report complete. No Linear mutation performed.
- 2026-05-17: I1 local env-contract patch complete after user supplied localhost redirect evidence. No Linear or production mutation performed.
- 2026-05-17: K1 production hotfix complete after explicit user approval. No Linear mutation performed.
- 2026-05-17: J1 self-service credentials UI/API complete and Codex-reviewed. No Linear mutation performed.
- 2026-05-18: Linear audit completed without existing status changes. Created ENG-181 through ENG-188 and added audit comments to ENG-3, ENG-5, ENG-7, ENG-92, ENG-165, ENG-177, ENG-178, and ENG-180. Added a project-level audit comment noting stale ENG-1..ENG-17 risk and the additive-migration rule.
- 2026-05-18: Linear cleanup completed. Moved implemented legacy slice tasks to Done, closed obsolete scope as Canceled/Duplicate, closed archived test noise ENG-61/65/95/99, closed ENG-144 as duplicate of ENG-148, detached ENG-81..ENG-86 from canceled ENG-66 while keeping them as future milestone Backlog work, and added project cleanup comments. Current Backlog is intentionally ENG-81..86, ENG-110..112, ENG-165..171, and ENG-181..188.
- 2026-05-18: P-wave completed. ENG-165 credential polish implemented and verified; ENG-181 data-foundation implementation plan written. Move ENG-165 and ENG-181 to In Review; keep ENG-182..ENG-185 Backlog until Alembic drift (ENG-188) is resolved and implementation work is split.
- 2026-05-18: Q0 completed. ENG-188 moved to Done after model metadata was aligned with existing tenant indexes and outreach server defaults. `alembic check`, `make verify`, focused model tests, and `git diff --check` passed. ENG-181 commented as unblocked for additive data-foundation work.
- 2026-05-18: Q1 launched for ENG-182. Claude Code owns the first `identity.match_candidate` implementation slice; Linear status remains unchanged until Codex reviews the report and diff.
- 2026-05-19: Q1 completed and Codex-reviewed. Codex fixed tenant-person validation and recursive PHI/raw-payload guard inside Q1 ownership. Local evidence is green: `tests/identity -q` (45 passed), focused ruff, `alembic check`, `make verify`, and `git diff --check`. ENG-181 and ENG-182 are synced to In Review; ENG-188 remains Done. Comments were added to ENG-181, ENG-182, and ENG-188 with the current evidence.
- 2026-05-19: Wave R launched. R1 owns the ENG-185 normalized-person-hint implementation and the only Wave R migration; R2 plans ENG-185 follow-up pipeline integration read-only; R3 scouts verification risk read-only. ENG-185 is synced to In Progress. An initial mistaken ENG-183 status/comment sync was corrected because ENG-183 is the later `ops.inquiry` slice, not normalized hints.
- 2026-05-19: R2 and R3 completed report-only work. Keep ENG-185 In Progress until R1 lands and Codex reviews the implementation. Do not move ENG-185 to In Review until R1 verification passes.
- 2026-05-19: R1 completed and Codex-reviewed. Codex corrected stale issue references to ENG-185 and verified `tests/ingest -q`, `tests/ingest tests/identity tests/ops -q`, `make verify`, `alembic upgrade head`, `alembic check`, downgrade/upgrade round-trip, and `git diff --check`. ENG-185 is synced to In Review and ENG-181/ENG-185 comments contain the evidence.
- 2026-05-19: Wave S planned for ENG-185 follow-up. S1 is the sole writer for the identity-only match policy entry point; S2/S3 are read-only report tasks. ENG-183 remains untouched because it is the later `ops.inquiry` slice.
- 2026-05-19: Wave S launch synced. ENG-185 moved from In Review to In Progress for the follow-up identity policy wave and received a launch comment. ENG-183 remains Backlog.
- 2026-05-19: Wave S completed and Codex-reviewed. S1 identity policy implementation verified with identity tests, adjacent-domain regression, `alembic check`, `git diff --check`, and `make verify`. Move ENG-185 back to In Review with evidence. S2's report scopes the next Salesforce cutover wave.
- 2026-05-19: Wave T planned for the ENG-185 Salesforce cutover. T1 owns `SfLeadIngestService` and its tests; T2 is read-only verification scouting. ENG-183 remains Backlog.
- 2026-05-19: Wave T launch synced. ENG-185 moved from In Review to In Progress for the Salesforce cutover and received a launch comment. ENG-183 remains Backlog.
- 2026-05-19: Wave T completed after Codex recovery review. Background workers could not write reports under `.agents/**`, so incidents were recorded and Codex reviewed the actual T1 diff. Verification passed: SF ingest test (10 passed), focused ingest/identity/API regression (111 passed), `alembic check`, `git diff --check`, focused ruff/mypy, and `make verify`. Move ENG-185 back to In Review with evidence; ENG-183 remains Backlog.

## Shared Contract

# Shared Contract

## Purpose

- Coordinate independent workstreams without allowing them to mutate shared state unexpectedly.

## API Contract

- No API contract changes are assigned in Wave 1.
- B1 may recommend API changes but must not implement them.

## Data / Schema Contract

- No schema or migration changes are assigned in Wave 1.
- No shipped Alembic revisions may be edited.

## UI / UX Contract

- No UI changes are assigned in Wave 1.

## Acceptance Criteria

- A2-live report identifies the latest deploy-prod failure evidence or explains the exact access blocker.
- B1 report identifies correctness risks in the current tenant credential diff and whether it can proceed as ENG-177/ENG-165 work.
- C1 report decomposes ENG-166/ENG-167/ENG-168 into safe next tasks with file ownership and sequencing.

## Non-Negotiable Constraints

- Do not change this contract inside a worker task.
- If the contract is incomplete or wrong, stop and report to the orchestrator.
- Do not commit, push, merge, deploy, rerun workflows, change Cloud Run traffic/config, edit env/secrets, or mutate Linear statuses from worker tasks.

## Wave R Contract

### Purpose

Advance the data-foundation sequence after Q1 with one migration writer and
parallel read-only planning/review work.

### Data / Schema Contract

- R1 is the only Wave R writer allowed to add a migration.
- R1 may add `ingest.normalized_person_hint` only.
- R1 must not edit shipped Alembic revisions.
- R1 must not change Salesforce/CareStack ingest behavior.
- `person_uid` and `source_link_id` in `ingest.normalized_person_hint` are
  plain UUID pointers; no identity model/repository imports.
- Normalized hints must not contain raw provider payloads or clinical text in
  `meta` or `quality_flags`.

### API / Worker Contract

- No API routes or worker jobs are assigned in Wave R.
- R2 may propose future ENG-185 route/job/service changes in its report only.

### Acceptance Criteria

- R1 report documents files changed, migration revision/down_revision,
  verification, and deviations from P2.
- R2 report documents the future ENG-185 implementation sequence and
  ownership.
- R3 report documents migration-chain and verification risks.
- Codex reviews reports before any Linear status is moved beyond In Progress.

## Wave S Contract

### Purpose

Advance ENG-185 with one identity-service writer and parallel read-only
planning/review work, without opening a new migration writer wave.

### Data / Schema Contract

- S1 must not add or edit Alembic revisions.
- S1 may update identity models only for Python constants / service validation,
  not schema shape.
- `identity.match_candidate.hint_id` remains a plain UUID pointer in this wave.
- `identity` must not import `ingest`; use an identity-owned `MatchHintIn` DTO
  or equivalent adapter contract.
- Match policy evidence and conflicts must not contain raw provider payloads or
  clinical text.

### API / Worker Contract

- No API routes, worker jobs, Salesforce/CareStack ingest behavior, or
  `ops.inquiry` work is assigned in Wave S.
- S2 may propose the future Salesforce cutover in its report only.

### Acceptance Criteria

- S1 report documents files changed, DTO/result contract, match policy tier
  behavior, verification, and deviations from R2/P2.
- S2 report documents the future Salesforce cutover sequence and ownership.
- S3 report documents import-boundary, migration-free, PHI, idempotency, and
  verification risks.
- Codex reviews reports before any Linear status is moved beyond In Progress.

## Wave T Contract

### Purpose

Complete the ENG-185 Salesforce cutover after S1 by wiring the existing manual
Lead pull to normalized hints and the identity match policy entry point.

### Data / Schema Contract

- T1 must not add or edit Alembic revisions.
- T1 must not edit identity schemas/models/services/repositories.
- T1 must not edit `ops` schema/service/model files.
- Raw Salesforce records remain captured verbatim before any normalization.
- The normalized hint and identity match DTO carry normalized fields only; raw
  SOQL records must not be passed into identity.

### API / Worker Contract

- No API routes, frontend files, or worker jobs are assigned in Wave T.
- The existing manual pull API and `SfLeadOut` DTO contract must remain stable.
- `ops.lead.extra.is_reactivation` remains a boolean. Map it from
  `ResolveFromHintResult.was_existing_person_match`.

### Acceptance Criteria

- T1 report documents files changed, cutover behavior, verification, and
  deviations from S2.
- T2 report documents cutover risks and post-T1 verification checklist.
- Codex reviews reports before any Linear status is moved beyond In Progress.

## Ownership

# File Ownership

## Rules

- Each editing task must have one primary owner.
- Workers may edit only their assigned write scope.
- Workers must stop and report if they need a file outside their scope.
- Shared files must be sequenced or assigned to one integrator.

## Ownership Table

| Path / Module | Owner Task | Branch | Worktree | Access | Notes |
| --- | --- | --- | --- | --- | --- |
| GitHub Actions run logs | A2-live | read-only | primary | read | `gh run list/view` only. No rerun/cancel/dispatch. |
| Cloud Logging / Cloud Run describe/list | A2-live | read-only | primary | read | `gcloud logging read`, service/revision describe/list only. |
| `apps/api/routers/tenant.py` | B1 | main | primary | read | Existing dirty tenant diff. Review only. |
| `packages/tenant/**` | B1 / E1 | main | primary | read/write sequenced | B1 reviewed; E1 fixed default/status edge. No further parallel edits until Codex final review. |
| `tests/tenant/**` | B1 / E1 | main | primary | read/write sequenced | B1 reviewed; E1 added focused service regression test. No further parallel edits until Codex final review. |
| `tests/api/test_tenant_credential_routes.py` | B1 | main | primary | read | Existing untracked test. Review only. |
| Linear ENG-166 / ENG-167 / ENG-168 descriptions and repo docs | C1 | read-only | primary | read | Planning only. |
| `.github/workflows/deploy-prod.yml` | D1 | main | primary | write complete | Added stderr diagnostics and IAP `--include-email`. No workflow rerun without user approval. |
| `tests/core/test_deploy_prod_smoke_logging.py` | D1 | main | primary | write complete | Static deploy-smoke regression tests. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/A2-live.md` | A2-live | read-only | primary | write | Report only. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/B1.md` | B1 | main | primary | write | Report only. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/C1.md` | C1 | read-only | primary | write | Report only. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/D1.md` | D1 | main | primary | write | Report only. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/E1.md` | E1 | main | primary | write | Report only. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/F1.md` | F1 | main | primary | write | Report-only verifier. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/G1.md` | G1 | read-only | primary | write | Report-only planner. |
| `packages/ingest/models.py` | R1 | main | primary | write | Add `NormalizedPersonHint`; no Salesforce/CareStack behavior changes. |
| `packages/ingest/schemas.py` | R1 | main | primary | write | Add hint DTOs only. |
| `packages/ingest/repository.py` | R1 | main | primary | write | Add data-only hint repository methods. |
| `packages/ingest/service.py` | R1 | main | primary | write | Add hint capture service method; no cross-domain business logic. |
| `packages/db/alembic/versions/` | R1 | main | primary | add-only | Add exactly one new revision after Q1; do not edit existing revisions. |
| `tests/ingest/` | R1 | main | primary | write | Focused model/service tests for normalized person hints. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/R1.md` | R1 | main | primary | write | Required worker report. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/R2.md` | R2 | read-only | primary | write | ENG-185 read-only implementation plan. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/R3.md` | R3 | read-only | primary | write | Wave R verification scout report. |
| `packages/identity/models.py` | S1 | main | primary | write | Match rule constants / service validation only; no schema or migration shape change. |
| `packages/identity/schemas.py` | S1 | main | primary | write | Add `MatchHintIn` and `ResolveFromHintResult`. |
| `packages/identity/repository.py` | S1 | main | primary | write | Add tenant-scoped candidate lookup helpers only. |
| `packages/identity/service.py` | S1 | main | primary | write | Add `resolve_or_create_from_hint(...)` and match policy helpers. |
| `packages/identity/CLAUDE.md` | S1 | main | primary | write | Document the new provider entry point if implemented. |
| `tests/identity/` | S1 | main | primary | write | Focused tests for match policy tier ladder and idempotency. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S1.md` | S1 | main | primary | write | Required worker report. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S2.md` | S2 | read-only | primary | write | Salesforce cutover plan only. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S3.md` | S3 | read-only | primary | write | Wave S verification scout report. |
| `packages/ingest/sf_lead_service.py` | T1 | main | primary | write | Cut Salesforce pull over to normalized hints + identity match policy. |
| `tests/ingest/test_sf_lead_service.py` | T1 | main | primary | write | Rewrite SF pull tests for the new policy entry point. |
| `packages/ingest/CLAUDE.md` | T1 | main | primary | write | Document the per-source handler cutover pattern. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md` | T1 | main | primary | write | Required worker report. |
| `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T2.md` | T2 | read-only | primary | write | Wave T verification scout report. |

## Read-Only Areas

- Entire repository for read-only context.

## Prohibited / High-Risk Areas

- `.env*`
- shipped Alembic revisions
- deploy scripts and workflows
- secrets
- broad formatting/refactors
- GitHub Actions workflow reruns/dispatch/cancel.
- Cloud Run service/job/traffic/env/secret/IAM mutations.
- Tenant credential source files for A2-live and C1.
- `.github/workflows/deploy-prod.yml` for B1 and C1.
- Product files for F1 and G1.
- Product files for R2 and R3.
- `packages/identity/**` for R1, except read-only context.
- `packages/ops/**`, `apps/**`, `apps/worker/**`, `packages/integrations/**` for R1, except read-only context.
- Product files for S2 and S3.
- `packages/ingest/**`, `packages/ops/**`, `apps/**`, `apps/worker/**`,
  `packages/integrations/**`, and `packages/db/alembic/versions/**` for S1,
  except read-only context.
- Product files for T2.
- `packages/identity/**`, `packages/ops/**`, `packages/phi/**`, `apps/**`,
  `apps/worker/**`, `packages/integrations/**`, and
  `packages/db/alembic/versions/**` for T1, except read-only context.

## Ownership YAML

```yaml
# Machine-readable ownership rules for orchestration checks.
# Keep this in sync with ownership.md.

tasks:
  S1:
    allowed_paths:
      - "packages/identity/models.py"
      - "packages/identity/schemas.py"
      - "packages/identity/repository.py"
      - "packages/identity/service.py"
      - "packages/identity/CLAUDE.md"
      - "tests/identity/**"
      - ".agents/orchestration/20260517-113000-parallel-startup-wave/reports/S1.md"
    forbidden_paths:
      - "packages/ingest/**"
      - "packages/ops/**"
      - "packages/phi/**"
      - "apps/**"
      - "apps/worker/**"
      - "packages/integrations/**"
      - "packages/db/alembic/versions/**"
      - ".github/workflows/**"
      - "infra/scripts/**"
    can_create_migration: false
  S2:
    allowed_paths:
      - ".agents/orchestration/20260517-113000-parallel-startup-wave/reports/S2.md"
    forbidden_paths:
      - "packages/**"
      - "apps/**"
      - "infra/**"
      - ".github/**"
    can_create_migration: false
  S3:
    allowed_paths:
      - ".agents/orchestration/20260517-113000-parallel-startup-wave/reports/S3.md"
    forbidden_paths:
      - "packages/**"
      - "apps/**"
      - "infra/**"
      - ".github/**"
    can_create_migration: false
  T1:
    allowed_paths:
      - "packages/ingest/sf_lead_service.py"
      - "tests/ingest/test_sf_lead_service.py"
      - "packages/ingest/CLAUDE.md"
      - ".agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md"
    forbidden_paths:
      - "packages/identity/**"
      - "packages/ops/**"
      - "packages/phi/**"
      - "apps/**"
      - "apps/worker/**"
      - "packages/integrations/**"
      - "packages/db/alembic/versions/**"
      - ".github/workflows/**"
      - "infra/scripts/**"
    can_create_migration: false
  T2:
    allowed_paths:
      - ".agents/orchestration/20260517-113000-parallel-startup-wave/reports/T2.md"
    forbidden_paths:
      - "packages/**"
      - "apps/**"
      - "infra/**"
      - ".github/**"
    can_create_migration: false

global_forbidden_paths:
  - ".env*"
  - "packages/db/alembic/versions/**"
  - ".github/workflows/*deploy*"
  - "infra/scripts/deploy*"
  - "infra/scripts/*prod*"
```

## Board

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

## Integration Plan

# Integration Plan

Base branch: main
Integration branch: local working tree (no branch created yet)

## Branches

| Task | Branch | Worktree | Status | Merge Order | Notes |
| --- | --- | --- | --- | --- | --- |
| A1 / D1 | main working tree | primary | ready for Codex final review | 1 | Deploy-smoke bundle: stderr diagnostics + IAP `--include-email` + static workflow tests. |
| B1 / E1 | main working tree | primary | ready for Codex final review | 2 | Tenant credential bundle: metadata routes/service updates + default/status edge fix + tests. |
| F1 | report-only | primary | running | n/a | Local verification report. |
| G1 | report-only | primary | running | n/a | Next runtime/Twilio wave brief. |
| M1 | main working tree | primary | complete | n/a | Stabilization review and focused verification. |
| N1 | read-only | primary | complete | n/a | Data foundation architecture proposal; no code changes. |
| Q0 | main working tree | primary | complete | n/a | ENG-188 Alembic drift cleanup; `alembic check` clean. |
| Q1 | main working tree | primary | complete | n/a | ENG-182 `identity.match_candidate` foundation; Codex review and focused verification complete. |
| R1 | main working tree | primary | complete | n/a | ENG-185 `ingest.normalized_person_hint`; Codex review and verification complete. |
| R2 | read-only | primary | complete | n/a | ENG-185 follow-up implementation plan report only. |
| R3 | read-only | primary | complete | n/a | Wave R verification scout report only. |
| S1 | main working tree | primary | complete | n/a | ENG-185 identity-only match policy entry point; Codex review and verification complete; no migration. |
| S2 | read-only | primary | complete | n/a | Salesforce cutover plan report only. |
| S3 | read-only | primary | complete | n/a | Wave S verification scout report only. |
| T1 | main working tree | primary | complete | n/a | ENG-185 Salesforce cutover; no migration and no API/UI changes; Codex recovery review complete. |
| T2 | read-only | primary | complete | n/a | Wave T verification scout recovery report only. |

## Expected Conflicts

- No cross-worker product-file conflicts in Wave 2: D1 owned deploy workflow/test; E1 owned tenant service/test.
- Current working tree also includes pre-existing tenant route/schema/API-test changes; Codex final review must treat those as part of the tenant bundle.
- `.claude/scheduled_tasks.lock` is dirty but unrelated to the integration bundle; do not revert without explicit user instruction.

## Merge Procedure

1. Review F1 report.
2. Codex final review of deploy-smoke bundle:
   - `.github/workflows/deploy-prod.yml`
   - `tests/core/test_deploy_prod_smoke_logging.py`
3. Codex final review of tenant bundle:
   - `apps/api/routers/tenant.py`
   - `packages/tenant/credential_service.py`
   - `packages/tenant/schemas.py`
   - `tests/tenant/test_credential_service.py`
   - `tests/api/test_tenant_credential_routes.py`
4. Run focused checks:
   - `python -m pytest tests/core/test_deploy_prod_smoke_logging.py`
   - `.venv/bin/python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py`
   - `git diff --check`
   - Current expanded focused gate also passed: `make verify`, 71 backend focused tests, `apps/web` lint/test.
5. Q1 data-foundation checks completed:
   - `.venv/bin/python -m pytest tests/identity -q` => 45 passed.
   - focused ruff for identity service/tests passed.
   - `cd packages/db && ../../.venv/bin/alembic check` => no new upgrade operations detected.
   - `make verify` passed.
   - `git diff --check` passed.
6. Before commit/PR, ask for explicit user approval.
7. Before any deploy-prod rerun, ask for explicit user approval.

## Wave R Merge / Review Procedure

1. Wait for R1, R2, and R3 reports.
2. Review R1 diff against:
   - `packages/ingest/CLAUDE.md`
   - `packages/db/CLAUDE.md`
   - Wave R contract.
3. Confirm R1 added only one new Alembic revision and did not edit shipped
   revisions.
4. Run focused checks:
   - `.venv/bin/python -m pytest tests/ingest -q`
   - `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
   - `git diff --check`
   - `make verify` if focused checks pass.
5. Use R2/R3 reports to decide whether ENG-185 can launch as the next writer
   wave or needs contract changes first.

Wave R focused checks completed:

- `.venv/bin/python -m pytest tests/ingest -q` => 31 passed.
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/ops -q` => 95 passed.
- `make verify` passed.
- `alembic upgrade head` applied R1 revision.
- `alembic check` => no new upgrade operations detected.
- `alembic downgrade -1 && alembic upgrade head && alembic check` passed.
- `git diff --check` passed.

## Wave S Review Procedure

1. Wait for S1, S2, and S3 reports.
2. Review S1 diff against:
   - `packages/identity/CLAUDE.md`
   - `packages/CLAUDE.md`
   - Wave S contract.
3. Confirm S1 did not add or edit any Alembic revision and did not change
   Salesforce/CareStack ingest behavior.
4. Run focused checks:
   - `.venv/bin/python -m pytest tests/identity -q`
   - `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
   - `git diff --check`
   - `make verify` if focused checks pass.
5. Use S2/S3 reports to decide whether the next wave can cut Salesforce over
   or needs contract changes first.

Wave S focused checks completed:

- `.venv/bin/python -m pytest tests/identity -q` => 66 passed.
- `.venv/bin/python -m pytest tests/identity tests/ingest tests/ops -q` => 116 passed.
- `alembic check` => no new upgrade operations detected.
- `git diff --check` passed.
- `make verify` passed after the orchestrator helper S607 lint fix.

## Wave T Review Procedure

1. Wait for T1 and T2 reports.
2. Review T1 diff against:
   - `packages/ingest/CLAUDE.md`
   - `packages/identity/CLAUDE.md`
   - Wave T contract.
3. Confirm T1 did not edit identity files, ops files, apps, or any Alembic
   revision.
4. Run focused checks:
   - `.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q`
   - `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
   - `git diff --check`
   - `make verify` if focused checks pass.
5. Decide whether the next wave is manual local smoke or `ENG-183 ops.inquiry`.

Wave T focused checks completed:

- `.venv/bin/python -m pytest tests/ingest/test_sf_lead_service.py -q` =>
  10 passed.
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q` =>
  111 passed.
- `alembic check` => no new upgrade operations detected.
- `git diff --check` passed.
- Focused ruff and mypy on T1 files passed.
- `make verify` passed.

## Release Gates

- PR/main merge approved: pending user approval.
- Staging verification approved: not applicable yet.
- Production deployment explicitly approved: pending user approval.
- ENG-178/ENG-180 status move: blocked until user-approved deploy-prod run is green.
- ENG-177/ENG-165 status move: pending Codex final review and broader acceptance decision.
- Full repository gates are not clean yet: `mypy .`, `make test`, and `alembic check` expose existing debt outside this bundle. Do not treat those failures as acceptance blockers for the focused credential/Salesforce fixes, but create separate stabilization tasks before claiming full verify health.

## Decision Log

_Missing._

## Run Log

# Run Log

| Time | Task | Agent | Branch | Worktree | Command/Mode | Result | Report | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-19T04:08:03.858288+00:00 | S1 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S1.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/S1.log` |
| 2026-05-19T04:08:03.858623+00:00 | S2 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S2.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/S2.log` |
| 2026-05-19T04:08:03.858715+00:00 | S3 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S3.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/S3.log` |
| 2026-05-19T04:10:24.229681+00:00 | S1 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S1.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/S1.log` |
| 2026-05-19T04:10:24.237666+00:00 | S2 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S2.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/S2.log` |
| 2026-05-19T04:10:24.244491+00:00 | S3 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/S3.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/S3.log` |
| 2026-05-19T05:13:24.153255+00:00 | T1 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T1.log` |
| 2026-05-19T05:13:24.153449+00:00 | T2 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T2.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T2.log` |
| 2026-05-19T05:14:02.685662+00:00 | T1 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T1.log` |
| 2026-05-19T05:14:02.693349+00:00 | T2 | claude | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T2.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T2.log` |
| 2026-05-19T05:16:24.038074+00:00 | T1 | codex | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T1.log` |
| 2026-05-19T05:16:24.038213+00:00 | T2 | codex | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T2.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T2.log` |
| 2026-05-19T05:16:24.806063+00:00 | T1 | codex | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T1.log` |
| 2026-05-19T05:16:24.814242+00:00 | T2 | codex | TBD | `/Users/eduardkarionov/Desktop/Fusion_crm` | background | started | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T2.md` | `/Users/eduardkarionov/Desktop/Fusion_crm/.agents/orchestration/20260517-113000-parallel-startup-wave/logs/T2.log` |

## Incidents

# Incident Log

Use this file to record failures, surprises, bad assumptions, and workflow friction during the mission.

## Incident Template

## INC-YYYYMMDD-NNN: Short title

Date:
Detected by:
Severity: low | medium | high | blocker
Area: planning | launch | worker | Linear | contract | ownership | integration | verification | release

### What happened

### Impact

### Root cause

### Immediate fix

### Durable lesson candidate

### Follow-up action

## INC-20260518-001: Local Salesforce callback used mock completion

Date: 2026-05-18
Detected by: user localhost pull failure
Severity: medium
Area: verification

### What happened

After the operator attempted local Salesforce reconnect, the manual Lead pull
still failed with `invalid_grant: expired access/refresh token`.

### Impact

The UI could report Salesforce as connected while every real pull/sync kept
using a dead refresh token.

### Root cause

The localhost callback page ignored the real Salesforce `code/state` query and
called the mock callback endpoint. The FastAPI OAuth callback never received
the real authorization code, so it never persisted a fresh `oauth_token`.
Separately, failed refresh did not mark the active OAuth credential as expired.

### Immediate fix

Forward the callback page to `/api/integrations/salesforce/callback` with the
original query string, and mark active Salesforce OAuth credentials `expired`
when Salesforce returns a reconnect-required auth failure.

### Durable lesson candidate

Any real OAuth callback page must pass through provider query parameters and
PKCE cookies to the backend callback. Mock callback helpers must stay isolated
to MSW/mock-only paths.

### Follow-up action

Complete a real Salesforce consent flow and then run the manual Lead pull.

## INC-20260518-002: Full repository gates expose existing debt

Date: 2026-05-18
Detected by: Codex stabilization review
Severity: medium
Area: verification

### What happened

The user-requested full verify loop did not become fully green even after the
current diff passed its focused gates. `mypy .` reports existing test typing
errors, `make test` fails on the tenant isolation Phase B fixture and existing
outreach/worker failures, and `alembic check` reports existing schema drift.

### Impact

The current credential/Salesforce package can be reviewed with focused passing
checks, but the repository cannot honestly be called fully verified. Future
agents could waste time rediscovering unrelated failures unless they are
tracked separately.

### Root cause

The repository's documented full loop includes checks that are broader than
the currently green CI-style `make verify` target. Existing tenant/test/alembic
debt predates this stabilization bundle.

### Immediate fix

Ran and recorded both the failing full checks and passing focused checks.
Fixed only fresh errors introduced by the current diff.

### Durable lesson candidate

Every stabilization report must distinguish current-diff acceptance gates from
repository-wide health gates and name known pre-existing blockers explicitly.

### Follow-up action

Create separate Linear/backlog items for full `mypy .`, full `make test`, and
Alembic drift cleanup before claiming full verify health.

## INC-20260519-001: Claude launch prompt swallowed by add-dir

Date: 2026-05-19T03:07:29.830009+00:00
Detected by: orchestrator
Severity: medium
Area: launch

### What happened

run_wave launched Claude with the prompt as a positional argument after --add-dir. The local Claude CLI treats --add-dir as variadic, swallowed the prompt as another directory, and exited with: Input must be provided either through stdin or as a prompt argument when using --print.

### Impact

Q1 first launch exited immediately with no report.

### Root cause

The launch adapter assumed --add-dir consumed exactly one argument.

### Immediate fix

Updated launch_commands.py so claude_command pipes the prompt through stdin and invokes claude --print.

### Durable lesson candidate

For Claude Code non-interactive workers, pipe prompts via stdin because --add-dir may be variadic.

### Follow-up action

Use status_wave after every launch. The failed Q1 runtime entry pid 10413 is
kept as incident evidence; the relaunched pid 12657 completed successfully and
wrote `reports/Q1.md`.

## INC-20260519-002: Wave R Linear issue mapping drift

Date: 2026-05-19
Detected by: orchestrator during Wave R launch sync
Severity: medium
Area: Linear

### What happened

The Wave R normalized-person-hint implementation was initially mapped to
`ENG-183`, but Linear `ENG-183` is `ops.inquiry`. The actual normalized hint
issue is `ENG-185`.

### Impact

`ENG-183` was briefly moved to In Progress and received a Wave R launch
comment that belonged to normalized hints.

### Root cause

Mission shorthand from the P2 implementation sequence did not match the final
Linear child issue numbering.

### Immediate fix

Updated R1/R2 mission files to map normalized hints and follow-up pipeline
planning to `ENG-185`, corrected board/goal/linear-sync records, and returned
`ENG-183` to Backlog with a correction comment.

### Durable lesson candidate

Before launching a new wave from a planning report, confirm the actual Linear
issue title for every issue identifier being moved.

### Follow-up action

Promote a mission-level lesson if another issue-mapping drift occurs.

## INC-20260519-003: Mission scaffold missing machine-check files

Date: 2026-05-19
Detected by: orchestrator during Wave S preflight
Severity: low
Area: planning

### What happened

`check_ownership.py` failed because the resumed mission folder did not contain
`ownership.yaml`. The current worker prompt generated by `run_wave.py` also
references `acceptance.md` and `verification.md`, which were absent from this
older mission folder.

### Impact

Wave S could have launched workers with broken context references and without
machine-readable ownership checks.

### Root cause

The mission folder was created before the current scaffold expectations were
fully aligned with `run_wave.py` and `check_ownership.py`.

### Immediate fix

Added mission-local `acceptance.md`, `verification.md`, and `ownership.yaml`,
then re-ran ownership checks for S1/S2/S3 with explicit file lists. Also fixed
the orchestrator helper's ruff S607 warning by resolving `git` with
`shutil.which(...)`, allowing `make verify` to pass.

### Durable lesson candidate

On mission resume, confirm scaffold files required by current launch/status
scripts exist before launching a new wave.

### Follow-up action

Consider adding a lightweight scaffold-health command to the orchestrator
scripts if this recurs.

## INC-20260519-004: Wave T workers stalled without report output

Date: 2026-05-19T05:16:14.635517+00:00
Detected by: orchestrator
Severity: medium
Area: launch

### What happened

T1/T2 Claude background workers launched at 2026-05-19T05:14:02Z stayed running with empty logs and no reports after multiple status checks; Codex stopped the hung processes before relaunching.

### Impact

Wave T did not progress during the first launch attempt; no product files or reports were written by T1/T2.

### Root cause

Likely worker CLI startup or non-streaming hang before report creation; exact cause unknown.

### Immediate fix

Stopped the stale T1/T2 worker processes and prepared a relaunch with the same ownership boundaries.

### Durable lesson candidate

If background workers show no log output and no report after repeated status checks, inspect child processes before waiting indefinitely and record the launch anomaly.

### Follow-up action

Consider adding heartbeat or timeout metadata to run_wave/status_wave.

## INC-20260519-005: Wave T Codex workers could not finish reports

Date: 2026-05-19T05:22:01.617387+00:00
Detected by: orchestrator
Severity: high
Area: launch

### What happened

After relaunching T1/T2 with codex workers, T1 edited its owned code files but no T1 report was produced; T2 hit repeated sandbox/patch rejections while writing reports/T2.md and remained running without a report. Codex orchestrator stopped the stuck processes for review and recovery.

### Impact

Wave T implementation changes exist locally but worker reports are missing; orchestrator must review actual diff and create recovery evidence before accepting the wave.

### Root cause

Background codex exec sandbox treated mission report patch writes as outside project for worker sessions; worker fallback shell write did not complete.

### Immediate fix

Stopped stuck T1/T2 codex processes and moved to orchestrator-owned recovery review/verification.

### Durable lesson candidate

For background codex workers in this repo, verify report write capability early or provide a report-writing fallback in run_wave before starting implementation work.

### Follow-up action

Patch run_wave/status protocol to use unique logs and a report heartbeat/write preflight before future codex workers.

## Lessons

# Lessons Learned

Use this file for accepted reusable rules derived from incidents.

## Lesson Template

## LES-YYYYMMDD-NNN: Short rule

Source incident:
Applies to:
Rule:
Protocol/template/script update:
Verification:
Status: proposed | accepted | superseded

## LES-20260519-001: Pipe Claude prompts through stdin

Source incident: INC-20260519-001
Applies to: Claude Code non-interactive worker launches.
Rule: Launch Claude Code workers with the prompt piped through stdin when
using `--print`; do not rely on a trailing positional prompt after
`--add-dir`, because the local CLI can treat `--add-dir` as variadic.
Protocol/template/script update: `launch_commands.py` was updated before the
successful Q1 relaunch to pipe the prompt through stdin.
Verification: Q1 relaunch pid 12657 completed and wrote `reports/Q1.md`.
Status: accepted

## LES-20260519-002: Preflight worker report writes under `.agents`

Source incident: INC-20260519-005
Applies to: Codex background worker launches that must write mission reports.
Rule: Before launching a Codex background worker against a mission folder,
verify the worker mode can create or update its assigned `reports/<task>.md`
path under `.agents/**`. If the preflight fails, do not start product edits
with that worker mode; use a mode with write access or assign the report write
to the orchestrator explicitly.
Protocol/template/script update: pending follow-up to `run_wave.py` /
`status_wave.py`.
Verification: Wave T required orchestrator recovery reports because T1/T2
could not write reports from background Codex worker sessions.
Status: accepted

## Runtime

| Wave | Task | Agent | Mode | Status | Worktree | Report | Log |
| --- | --- | --- | --- | --- | --- | --- | --- |
| wave-20260519-030600 | Q1 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-030657 | Q1 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-033235 | R1 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-033235 | R2 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-033235 | R3 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-040803 | S1 | claude | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-040803 | S2 | claude | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-040803 | S3 | claude | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-041024 | S1 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-041024 | S2 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-041024 | S3 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051324 | T1 | claude | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051324 | T2 | claude | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051402 | T1 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051402 | T2 | claude | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051624 | T1 | codex | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051624 | T2 | codex | background | dry-run | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051624 | T1 | codex | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |
| wave-20260519-051624 | T2 | codex | background | not-running | `/Users/eduardkarionov/Desktop/Fusion_crm` | yes | yes |

## Reports

### A2-codex-followup.md

# A2 Codex Follow-up: IAP Smoke Evidence

## Scope

Codex performed a read-only follow-up after `A2-live` because the Claude harness could not run `gcloud compute backend-services describe`.

No production mutations were performed.

## Commands

- `gcloud compute backend-services list --project=fusioncrm-494201 --format='table(name,protocol,loadBalancingScheme)'`
- `gcloud compute backend-services describe fusion-lb-backend-api --global --project=fusioncrm-494201 --format=json`
- `gcloud iap web get-iam-policy --project=fusioncrm-494201 --resource-type=backend-services --service=fusion-lb-backend-api --format=json`
- `gcloud auth print-identity-token --help | rg -n "include-email|audiences|impersonate" -C 3`

## Findings

- Backend service `fusion-lb-backend-api` has IAP enabled.
- Backend service IAP OAuth client ID is `800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess.apps.googleusercontent.com`.
- That OAuth client ID matches the pinned workflow `IAP_CLIENT_ID`.
- IAP IAM policy grants `roles/iap.httpsResourceAccessor` to `serviceAccount:cloud-build-deployer-sa@fusioncrm-494201.iam.gserviceaccount.com`.
- Therefore the earlier likely causes "wrong IAP client ID" and "deployer service account lacks IAP accessor" are not supported by current evidence.

## Strong Next Hypothesis

The smoke token is generated without an email claim:

```bash
gcloud auth print-identity-token \
  --impersonate-service-account="${DEPLOYER_SA}" \
  --audiences="${IAP_AUDIENCE}"
```

Google Cloud IAP documentation says a generated service-account OIDC token must have an `email` claim for IAP to accept it. Local `gcloud auth print-identity-token --help` says `--include-email` adds `email` and `email_verified` claims and is intended for service-account impersonation.

Next candidate fix:

```bash
gcloud auth print-identity-token \
  --impersonate-service-account="${DEPLOYER_SA}" \
  --audiences="${IAP_AUDIENCE}" \
  --include-email
```

## References

- Google Cloud IAP programmatic authentication: service-account OIDC token must include an `email` claim.
- Google Cloud SDK `gcloud auth print-identity-token`: `--include-email` includes `email` and `email_verified` claims for impersonated service accounts.

## Recommendation

Run a single-owner workflow patch in the deploy track:

1. Keep the A1 stderr diagnostics fix.
2. Add `--include-email` to the deploy-prod deep-smoke token command.
3. Add or update a static workflow test that asserts the token command uses both `--audiences="${IAP_AUDIENCE}"` and `--include-email`.
4. Do not rerun deploy-prod or move ENG-178/ENG-180 statuses without explicit user approval.

### A2-live.md

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
- `protoPayload.authenticationInfo.principalEmail`: 

_Trimmed 20431 chars._

### B1.md

# Terminal Agent Report

Task ID: B1
Linear issue: ENG-177 / ENG-165
Agent role: Codex reviewer
Status: complete
Branch: main
Worktree: primary repo

## Findings

1. Medium — `update_metadata` can leave a non-active credential marked as default.
   File: `packages/tenant/credential_service.py:580`

   The method validates `is_default=True` against `cred.status`, but it does not handle the case where the same update changes an existing default credential from `active` to `expired` without sending `is_default=False`. After this call, the row can have `status='expired'` and `is_default=True`. Runtime reads still filter `status == "active"`, so this does not leak a secret or make the expired credential usable, but the operator/admin metadata becomes contradictory and the UI may still display an expired row as the provider default.

   Recommended fix: when `status` changes to any non-active value, either reject the update while `cred.is_default` is true unless `is_default=False` is included, or automatically clear `cred.is_default = False`. Add a service test for an active default updated to `expired`.

2. Low — route handlers directly construct `IntegrationCredentialService(db)`.
   File: `apps/api/routers/tenant.py:156`

   This follows the existing credential route pattern in the file, but it is not ideal under `apps/api/CLAUDE.md`, which prefers route dependencies over constructing services from `AsyncSession` in handlers. Not a blocker for the current diff because nearby DELETE/set-default routes already use this pattern, but a follow-up cleanup should add a dependency provider if this surface grows further.

## Positive Review Notes

- ENG-177 core behavior is present: default listing paths now hide revoked credentials by default.
- `GET /tenant/current` still goes through `TenantService.list_credentials`, which already defaults `include_revoked=False`.
- New `GET /tenant/credentials` exposes explicit `include_revoked`, defaulting to `False`.
- `set-default` correctly opts into `include_revoked=True` only to resolve ownership/provider kind, then delegates to `set_default`, which rejects non-active rows.
- `update_metadata` intentionally avoids decrypting or re-encrypting `payload`.
- Audit `extra` includes tenant/provider/credential metadata and `updated_fields`, but no payload keys or values.
- `IntegrationCredentialOut` omits `payload`; route tests assert payload does not leak.

## Files Changed

None by B1. This was a review-only task.

Reviewed dirty/untracked files:
- `apps/api/routers/tenant.py`
- `packages/tenant/credential_service.py`
- `packages/tenant/schemas.py`
- `tests/tenant/test_credential_service.py`
- `tests/api/test_tenant_credential_routes.py`

## Git State

- Existing tenant credential source/test files remain dirty from prior work.
- B1 only added this report file.
- No commit, push, merge, rebase, deployment, workflow action, or destructive command was run.

## Tests / Checks

- `python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py`
  - Failed in the system Python 3.11 environment because `structlog` is not installed.
- `.venv/bin/python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py`
  - Passed: 23 tests.

## Ownership Notes

- Review stayed within B1 read scope.
- No tenant source files were edited.
- Work followed `contract.md` and `ownership.md`.
- No contract changes requested.

## Linear Notes

- Recommended Linear status:
  - ENG-177: keep In Review until the non-active default edge case is fixed or explicitly accepted.
  - ENG-165: keep Backlog/Planned. The current diff is a useful backend slice for credential metadata editing, but it should be split from broader provider credential UI/API work.
- Suggested Linear comment:
  > Codex review of the tenant credential diff: core ENG-177 behavior is present and focused tests pass under the project `.venv` (`23 passed`). One medium issue remains before acceptance: `update_metadata` can change an existing default credential to `expired` while leaving `is_default=True`, creating contradictory admin/UI metadata. Recommend fixing that edge case with a focused service test before closing ENG-177.

## Blockers

- None for review.
- Implementation follow-up should be single-owner because the relevant tenant files are already dirty.

## Integration Risks

- The dirty tenant diff mixes two concerns:
  - ENG-177: hide revoked credentials by default.
  - ENG-165: add list/update credential metadata endpoints.
- To keep PRs reviewable, split or clearly label the backend slice. The medium finding is in the ENG-165 metadata update behavior, not the revoked-list filter itself.

## Suggested Next Tasks

1. Launch one Claude Code worker for the tenant files only:
   - Fix non-active default handling in `IntegrationCredentialService.update_metadata`.
   - Add a focused service test.
   - Run `.venv/bin/python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py`.
2. After that, Codex should re-review the tenant diff and decide whether ENG-177 can move toward Done.

### C1.md

# Terminal Agent Report

Task ID: C1
Linear issue: ENG-166 / ENG-167 / ENG-168 (planning only)
Agent role: Claude Code explorer
Status: complete
Branch: read-only (no branch created; primary worktree)
Worktree: primary repo

## Summary

Read-only decomposition of the next provider/workflow wave (Salesforce
speed-to-lead, CareStack consultation watcher, Twilio controlled SMS) into three
implementation waves with disjoint file ownership, explicit dependency on
ENG-165 (tenant credential UI/API) and ENG-169 (live-runtime ADR), and Codex
review/verification gates between waves. Twilio (ENG-168) is the hard upstream
because both ENG-166 and ENG-167 ultimately trigger SMS; live intake runtime
choices for ENG-166 and ENG-167 are gated behind the ENG-169 ADR and must not
be implemented as catch-all worker processes.

## Files Changed

- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/C1.md`: this report.

## Git State

- Current branch: `main`
- Dirty files: pre-existing dirty set from the mission (`.github/workflows/deploy-prod.yml`, `apps/api/routers/tenant.py`, `packages/tenant/credential_service.py`, `packages/tenant/schemas.py`, `tests/tenant/test_credential_service.py`, plus untracked `tests/api/test_tenant_credential_routes.py`, `tests/core/test_deploy_prod_smoke_logging.py`, `.agents/`, `.claude/commands/orchestrator.md`, `Agent_Orchestration_Playbook_RU.md`). C1 did not touch any of these.
- Commits made: none
- Push status: not pushed

## Tests / Checks

- None. This task is read-only planning; no test runs were performed.

## Ownership Notes

- All writes were limited to `reports/C1.md`. No source, migration, env, workflow, deploy script, Linear, or tenant credential file was touched.
- Followed `contract.md` Wave 1 carve-out (no API/schema/UI changes proposed for implementation here; this report only proposes future task scopes).
- No contract changes requested.

## Linear Notes

- Recommended Linear status: leave ENG-166 / ENG-167 / ENG-168 in `Backlog`. Do not unblock without first confirming ENG-165 and ENG-169 are accepted.
- Comment for orchestrator to post (after Codex approves this plan): "Implementation-wave plan landed in `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/C1.md`. Hard prerequisites: ENG-165 (tenant credential UI/API) and ENG-169 (live-runtime ADR). Twilio (ENG-168) is the upstream of both SMS-triggering features."
- New issues suggested (do NOT create yet — orchestrator + Codex should approve and Linear-create in a separate step):
  - "ENG-168a: Twilio credential payload + IntegrationCredentialService extension" (Wave 1 design slice).
  - "ENG-168b: `packages/integrations/twilio/` client + token resolver" (Wave 2).
  - "ENG-168c: `packages/sms/` controlled send service + consent/opt-out store" (Wave 2).
  - "ENG-166a: Salesforce live-intake receiver (route + raw_event capture)" (Wave 2, depends on ENG-169 runtime choice).
  - "ENG-166b: `speed_to_lead_context` builder" (Wave 3).
  - "ENG-166c: Salesforce reconciliation by `SystemModstamp`" (Wave 3).
  - "ENG-167a: CareStack appointment webhook discovery + decision memo" (Wave 1).
  - "ENG-167b: CareStack appointment near-real-time poller + cursor" (Wave 2).
  - "ENG-167c: `consultation_scheduled_context` builder + SMS wiring" (Wave 3).
  - "ENG-169-impl: Runtime ADR draft for live subscribers on Cloud Run" (Wave 1; the ADR itself).

## Blockers

- ENG-165 (Settings / Integrations: tenant-owned provider credential UI and API) is on the blockedBy list of all three issues. B1 (this mission) is reviewing the in-flight credential diff; nothing in Wave 2 of this plan may start before B1 lands.
- ENG-169 (Runtime ADR for live subscribers) blocks ENG-166 and ENG-167 implementation of the actual live subscriber. Polling/scheduled and HTTP-receiver fallback paths can be designed but not deployed before the ADR.
- ENG-170 and ENG-171 are listed as blockers in Linear. The relevant docs already exist in-repo (`docs/PROVIDER_INGESTION_STRATEGY.md`, `docs/architecture/CONTEXT_ARCHITECTURE.md`, `docs/governance/TAXONOMY_GOVERNANCE.md`), so these blockers may already be satisfied — Codex should confirm and close them before unblocking ENG-166/167/168.

## Integration Risks

- All three issues converge on `tenant.integration_credential`; multiple workers writing migrations against the `provider_kind` CHECK constraint at the same time would conflict. Sequence migrations through one owner.
- Twilio is already enumerated in `tenant.models.PROVIDER_KIND_CHOICES` and `tenant.schemas.PROVIDER_KIND_LITERAL` (verified in repo). No CHECK-constraint migration is needed for the provider name itself; only `credential_kind` taxonomy (likely `api_key`) and a new payload contract require schema/governance.
- SMS pipeline shares conceptual surface with `packages/outreach` (suppression, audit-row hashing, rate limiter, tracking-token discipline). Reuse the patterns but DO NOT put SMS inside `packages/outreach` — outreach is email-only by ADR-0004; SMS deserves its own domain (`packages/sms` or `packages/messaging/sms`) to keep tenant isolation, consent/opt-out, and quiet-hours rules domain-local. Final naming should be a small ADR.
- Salesforce live-intake must not reintroduce a generic `fusion-worker` Cloud Run Service. The runtime ADR (ENG-169) is the gate; until it lands, only the inbound HTTP receiver (Option 2 in `PROVIDER_INGESTION_STRATEGY.md`) is a safe Cloud Run Service shape because it is request/response.
- CareStack appointment payload is PHI. Hydration must go through `PhiService.upsert` and never log payload bodies. Polling logs must carry only `appointment_id`, `lastUpdatedOn`, `tenant_id`, `sync_run_id`.

## Process / Lesson Notes

- The C1 brief listed `packages/outreach/CLAUDE.md` as "if present" — it is present and is the closest existing template for the SMS controlled-send pipeline (suppression, rate limit, audit-row hashing, dispatcher worker via outbox). Treat outreach as the refer

_Trimmed 24307 chars._

### D1.md

# Terminal Agent Report

Task ID: D1
Linear issue: ENG-181 (deploy-prod IAP smoke email-claim fix)
Agent role: Claude Code worker (write scope: deploy-prod workflow + regression test + this report)
Status: complete
Branch: `main` (working tree, no commit)
Worktree: primary repo

## Summary

Implemented the Codex follow-up recommendation from
`reports/A2-codex-followup.md`: the impersonated service-account OIDC
token minted by the `api-smoke` step now passes `--include-email`, so
the token carries the `email` / `email_verified` claims that Google
Cloud IAP requires before it will forward a Bearer-token request to
the backend Cloud Run service.

Workflow-side ENG-180 (pinned `IAP_OAUTH_CLIENT_ID`) and ENG-178
(stderr-routed smoke diagnostics) are unchanged: the existing
`--impersonate-service-account` and `--audiences` arguments remain in
place, and the regression test still enforces the stderr/JSON contract
for `fail()` / `check()`.

A new static regression test (`test_smoke_token_includes_email_claim`)
locks the three-flag shape of the token mint so a future YAML edit
cannot quietly drop `--include-email` and silently regress the deep
smoke back to "rejected at IAP edge with no app-log entry".

No production operation was performed. No GitHub Actions rerun. No
Cloud Run / Secret Manager / Linear mutation. No commit, no push.

## Files Changed

- `.github/workflows/deploy-prod.yml` — added `--include-email` to the
  `gcloud auth print-identity-token` invocation inside the `api-smoke`
  job's `Hit smoke endpoints` step (`id: smoke`). Existing
  `--impersonate-service-account="${DEPLOYER_SA}"` and
  `--audiences="${IAP_AUDIENCE}"` arguments preserved. Inline comment
  block extended to record WHY the flag is mandatory (IAP rejects
  impersonated SA OIDC tokens without an `email` claim) and to point
  future readers at `reports/A2-codex-followup.md` for live evidence.
- `tests/core/test_deploy_prod_smoke_logging.py` — added
  `test_smoke_token_includes_email_claim`. It reuses the existing
  `_smoke_step_script()` helper (so the test is scoped to the
  `api-smoke` step only, not the unrelated `iam_preflight`
  `print-identity-token` call earlier in the workflow) and asserts the
  exact three-flag shape:
    1. `--impersonate-service-account="${DEPLOYER_SA}"`,
    2. `--audiences="${IAP_AUDIENCE}"`,
    3. `--include-email`.
  No other tests in the file were modified.
- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/D1.md`
  — this report.

## Git State

- Current branch: `main`, working tree (no checkout).
- Modified (write-scope only): `.github/workflows/deploy-prod.yml`,
  `tests/core/test_deploy_prod_smoke_logging.py`,
  `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/D1.md`.
- Other tracked-dirty files in the working tree (pre-existing, owned by
  other workers per mission ownership map; NOT modified by this task):
  `.claude/scheduled_tasks.lock`, `apps/api/routers/tenant.py`,
  `packages/tenant/credential_service.py`,
  `packages/tenant/schemas.py`,
  `tests/tenant/test_credential_service.py`,
  `tests/api/test_tenant_credential_routes.py`.
- Commits made: none.
- Push status: none.

## Tests / Checks

| Command | Result |
| --- | --- |
| `python -m pytest tests/core/test_deploy_prod_smoke_logging.py` | **5 passed in 0.05s** (4 pre-existing ENG-178 stderr-routing tests + 1 new `test_smoke_token_includes_email_claim`) |

Full pytest output:

```
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-8.4.1, pluggy-1.6.0
rootdir: /Users/eduardkarionov/Desktop/Fusion_crm
configfile: pyproject.toml
plugins: asyncio-0.24.0, anyio-4.9.0
asyncio: mode=Mode.AUTO, default_loop_scope=None
collected 5 items

tests/core/test_deploy_prod_smoke_logging.py .....                       [100%]

============================== 5 passed in 0.05s ===============================
```

System Python (3.11.5) had the required pytest deps already; no
`.venv/bin/python` fallback was necessary.

## Assumptions

- The `iam_preflight` step earlier in the workflow (lines ~170–187)
  also calls `gcloud auth print-identity-token --impersonate-service-account`,
  but with a sentinel audience (`https://example.invalid`) purely to
  prove the IAM grant works. That call does NOT need `--include-email`
  because (a) its only consumer is a `>/dev/null` exit-code check and
  (b) the token is never presented to IAP. Out of scope for this task,
  intentionally left unchanged.
- The new regression test scopes itself to the `api-smoke` step via
  `_smoke_step_script()`, so the assertion will never accidentally
  pass against the preflight call.
- `IAP_AUDIENCE` is fed from the top-level `env.IAP_OAUTH_CLIENT_ID`
  (ENG-180 pin). Per Codex follow-up evidence, that value
  (`800777477533-fv4l6nd3ou3c9euvr7re52rfcp680ess.apps.googleusercontent.com`)
  is the OAuth client ID bound to the IAP-protected backend service
  `fusion-lb-backend-api`, and the deployer SA has
  `roles/iap.httpsResourceAccessor` on it. The only missing piece was
  the email claim, which this patch addresses.

## Blockers

None. The fix is a workflow-only change verified by a static test that
runs against the YAML file in this repo. End-to-end acceptance (deep
smoke against IAP-fronted `/healthz` returning HTTP 200 with
`commit_sha == github.sha`) requires a deploy-prod run, which this task
explicitly does NOT trigger per scope.

## Production Operations Confirmation

- No GitHub Actions workflow was triggered or rerun.
- No Cloud Run service / revision / traffic split was touched.
- No Secret Manager secret was read, created, rotated, or deleted.
- No environment variable was modified on any Cloud Run service.
- No `gcloud` mutate command was issued.
- No Linear issue was moved, no Linear comment was posted, no Linear
  status was changed.
- No git commit was created; no branch was pushed.
- No PHI, no tenant credential payload, no token, no secret value

_Trimmed 1053 chars._

### E1.md

# Terminal Agent Report

Task ID: E1
Linear issue: ENG-177 (follow-up to B1 medium finding)
Agent role: Claude Code worker
Status: complete
Branch: main
Worktree: primary repo

## Summary

Fixed the medium finding from `reports/B1.md`:
`IntegrationCredentialService.update_metadata` now clears
`cred.is_default = False` whenever the resulting credential status is not
`active`. Added a focused service test that drives an active default
credential to `status="expired"` without explicitly sending
`is_default=False` and asserts the row ends with `is_default is False`.

## Files Changed

- `packages/tenant/credential_service.py`: in
  `IntegrationCredentialService.update_metadata`, after the existing
  `is_default` handling, force `cred.is_default = False` when
  `cred.status != "active"`. The pre-existing rejection of
  `is_default=True` for non-active credentials runs before this guard, so
  that behavior is preserved unchanged.
- `tests/tenant/test_credential_service.py`: added
  `test_update_metadata_clears_default_when_status_becomes_inactive`.
  Builds an `active`, `is_default=True` Salesforce credential, runs
  `update_metadata` with `IntegrationCredentialUpdate(status="expired")`,
  and asserts the credential ends with `status="expired"`,
  `is_default is False`, and that the audit `extra` carries
  `is_default=False`.

## Git State

- Current branch: `main`
- Dirty files: pre-existing dirty work plus this task's edits to
  `packages/tenant/credential_service.py`,
  `tests/tenant/test_credential_service.py`, and the new
  `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/E1.md`.
- Commits made: none.
- Push status: not pushed.

## Tests / Checks

- `.venv/bin/python -m pytest tests/tenant/test_credential_service.py`
  - Result: **21 passed** in 0.46s. Includes the new
    `test_update_metadata_clears_default_when_status_becomes_inactive`
    and all previously passing service tests.

## Ownership Notes

- Edits stayed within the assigned write scope:
  `packages/tenant/credential_service.py`,
  `tests/tenant/test_credential_service.py`,
  `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/E1.md`.
- No files were touched outside scope. API routes, schemas, migrations,
  env files, commits, and Linear were not edited.
- Work followed `contract.md` and the task brief.
- No contract changes requested.

## Linear Notes

- Recommended Linear status: ENG-177 ready to move toward Done pending
  Codex re-review now that the B1 medium finding is fixed.
- Comment/update for orchestrator to post:
  > Worker E1: medium finding from B1 fixed —
  > `IntegrationCredentialService.update_metadata` now clears
  > `is_default` automatically when the resulting status is non-active.
  > Added `test_update_metadata_clears_default_when_status_becomes_inactive`.
  > `.venv/bin/python -m pytest tests/tenant/test_credential_service.py`
  > → 21 passed.
- New issues suggested: none.

## Blockers

- None.

## Integration Risks

- None observed. The new guard runs after the existing `is_default=True`
  rejection, so the previously documented validation behavior is
  preserved: an attempt to set `is_default=True` while the resulting
  status is non-active still raises `ValidationError`. The fix only
  affects the previously-buggy path where status changed to a non-active
  value without an explicit `is_default=False` accompanying it.
- Per task brief, B1 flagged a separate low finding about route handlers
  constructing `IntegrationCredentialService(db)` directly. That is out
  of E1 write scope and intentionally not touched here.

## Process / Lesson Notes

- The existing test
  `test_update_metadata_updates_metadata_without_touching_payload`
  already exercised an `active → expired` status update, but it did so
  with `cred.is_default = False`. That meant the bug was invisible to
  the unit suite. The new test fills that gap by starting from
  `is_default=True`.

## Confirmation of no production operation

No production operation was performed. No commits, pushes, deploys,
`gcloud`, GitHub Actions reruns, Linear edits, or destructive commands
were issued.

## Suggested Next Tasks

- Codex (or B1 reviewer) re-reviews the tenant diff and decides whether
  ENG-177 can move to Done.
- Optional follow-up (separate task, out of scope for E1): address the
  low B1 finding by adding a FastAPI dependency provider for
  `IntegrationCredentialService` in `apps/api/dependencies.py` and
  switching the `apps/api/routers/tenant.py` credential routes to it.

### F1.md

# Terminal Agent Report

Task ID: F1
Linear issues: ENG-178 / ENG-180 / ENG-177 / ENG-165
Agent role: Claude Code verifier (read-only except this report)
Status: complete
Branch: `main` (working tree, no commit)
Worktree: primary repo

## Summary

Verified the post-D1/E1 local bundle. All three commanded checks pass.
The D1 and E1 workers stayed strictly within their declared write
scopes; the remaining dirty files in the working tree are pre-existing
in-flight changes that D1's report explicitly disclaims and that E1
left untouched. The bundle is local-only — no GitHub Actions rerun, no
Cloud Run / Secret Manager / Linear mutation occurred during D1/E1 or
during this verification.

Recommendation: **ready for Codex final review**, with one caller-out
below about the broader bundle scope so the orchestrator knows the PR
will be larger than just D1+E1.

## Commands Run and Results

| Command | Result |
| --- | --- |
| `python -m pytest tests/core/test_deploy_prod_smoke_logging.py` | **5 passed in 0.03s** (system Python 3.11.5, pytest 8.4.1) |
| `.venv/bin/python -m pytest tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py` | **24 passed in 0.93s** (21 tenant service + 3 tenant credential routes; venv Python 3.12.12, pytest 9.0.3) |
| `git diff --check` | exit 0, no output — no whitespace errors, no conflict markers |

Full pytest output, smoke logging suite:

```
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-8.4.1, pluggy-1.6.0
rootdir: /Users/eduardkarionov/Desktop/Fusion_crm
configfile: pyproject.toml
plugins: asyncio-0.24.0, anyio-4.9.0
asyncio: mode=Mode.AUTO, default_loop_scope=None
collected 5 items

tests/core/test_deploy_prod_smoke_logging.py .....                       [100%]

============================== 5 passed in 0.03s ===============================
```

Full pytest output, tenant credential suite:

```
============================= test session starts ==============================
platform darwin -- Python 3.12.12, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/eduardkarionov/Desktop/Fusion_crm
configfile: pyproject.toml
plugins: asyncio-1.3.0, respx-0.23.1, anyio-4.13.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 24 items

tests/tenant/test_credential_service.py .....................            [ 87%]
tests/api/test_tenant_credential_routes.py ...                           [100%]

============================== 24 passed in 0.93s ==============================
```

Both totals match the per-worker reports:

- D1 report claimed `5 passed` against `tests/core/test_deploy_prod_smoke_logging.py` → reproduced exactly.
- E1 report claimed `21 passed` against `tests/tenant/test_credential_service.py` → reproduced exactly; the additional `3 passed` come from `tests/api/test_tenant_credential_routes.py`, which B1 referenced as part of the same green run on the sibling pre-existing dirty work.

## File-Scope Observations

`git status --short` in the working tree:

```
 M .claude/scheduled_tasks.lock
 M .github/workflows/deploy-prod.yml
 M apps/api/routers/tenant.py
 M packages/tenant/credential_service.py
 M packages/tenant/schemas.py
 M tests/tenant/test_credential_service.py
?? .agents/
?? .claude/commands/orchestrator.md
?? Agent_Orchestration_Playbook_RU.md
?? tests/api/test_tenant_credential_routes.py
?? tests/core/test_deploy_prod_smoke_logging.py
```

Cross-referenced against the board's declared write scopes:

| Path | In scope for | Owner | Notes |
| --- | --- | --- | --- |
| `.github/workflows/deploy-prod.yml` | D1 | D1 (ENG-181/178/180) | `--include-email` added on impersonated OIDC token mint. `git diff --stat` → 33 lines touched. |
| `tests/core/test_deploy_prod_smoke_logging.py` | D1 | D1 | New `test_smoke_token_includes_email_claim` locks the three-flag shape. Untracked because the file is new in this wave. |
| `packages/tenant/credential_service.py` | E1 | E1 (ENG-177) | `update_metadata` now clears `is_default` when status becomes non-active. `git diff --stat` → 120 lines touched. |
| `tests/tenant/test_credential_service.py` | E1 | E1 | New `test_update_metadata_clears_default_when_status_becomes_inactive` plus prior wave additions. `git diff --stat` → 184 lines touched. |
| `apps/api/routers/tenant.py` | NOT D1/E1 | pre-existing | 58 lines changed; B1 reviewed the matching diff (ENG-165 / ENG-177 sibling work). D1's report disclaims it, E1's report disclaims it. |
| `packages/tenant/schemas.py` | NOT D1/E1 | pre-existing | 1 line changed; same sibling lane as the router. |
| `tests/api/test_tenant_credential_routes.py` | NOT D1/E1 | pre-existing | New file (untracked) covering the router work above. Suite passes (3/3). |
| `.claude/scheduled_tasks.lock` | local artifact | environment | Harness scheduling lock; must not enter any PR. |
| `.agents/` (untracked dir) | orchestration | orchestrator | Wave reports incl. this one. |
| `.claude/commands/orchestrator.md` | tooling | orchestrator | New slash-command. |
| `Agent_Orchestration_Playbook_RU.md` | docs | orchestrator | New Russian-language playbook. |

D1's report already documented every pre-existing dirty file by exact
path (see D1 §"Git State"); E1's report did the same. No worker
reverted another worker's edits and no worker stepped outside its
declared scope. The bundle is coherent: every functional change in the
working tree maps to a known owner, a known Linear issue, and a passing
test run.

`git diff --check` clean across the whole working tree confirms there
are no merge-conflict markers and no trailing-whitespace regressions
introduced by either worker.

## Deploy-Prod Local-Only Confirmation

- D1's edit is YAML-only inside `.github/workflows/deploy-prod.yml`.
- D1 ran no `gcloud` mutate command, no GitHub Actions rerun, no Cloud
  Run / Secret Manager change. The D1 report explicitly states this
  under "Produ

_Trimmed 4093 chars._

### G1.md

# Terminal Agent Report

Task ID: G1
Linear issue: ENG-169 (runtime ADR gate) + ENG-168 (Twilio/SMS foundations) — planning only
Agent role: Claude Code explorer / planner
Status: complete
Branch: `main` (primary worktree, no checkout)
Worktree: primary repo

## Summary

Read-only brief for the next implementation wave that follows the current
deploy/tenant bundle (A2-live, B1, D1, E1, F1). The wave has two tracks:
ENG-169 (live-subscriber runtime ADR) and ENG-168 (Twilio + SMS controlled
send). ENG-169 is doc-only and unblocks live ingestion for ENG-166/ENG-167
later; ENG-168 is the first real implementation track because Twilio is the
upstream of every SMS-triggering feature and its outbound-HTTPS shape does
NOT depend on the ENG-169 runtime decision. The two safest first slices are
therefore:

1. ENG-169 → an ADR file at `docs/decisions/ADR-XXXX-live-subscriber-runtime.md`.
2. ENG-168 → a Twilio-credential payload ADR + the `packages/integrations/twilio/`
   read-only client, bundled per `feedback_pr_granularity` (solo dev: bundle
   related slices). Wave kept doc-only until ADR is accepted.

No product file was modified by this task. The only write was this report.

## Files Changed

- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/G1.md` — this report.

## Git State

- Current branch: `main`, working tree (no checkout).
- Dirty files: pre-existing mission dirty set (deploy-prod workflow, tenant
  credential service/schema/routes/tests, plus orchestration files under
  `.agents/`). G1 did not touch any of them.
- Commits made: none.
- Push status: none.

## Tests / Checks

- None. G1 is read-only planning; no test runs were performed.

## Ownership Notes

- Writes stayed inside the assigned scope (`reports/G1.md` only).
- No product file, migration, env file, workflow file, deploy script, Linear
  ticket, Cloud Run / Secret Manager / IAP surface was touched.
- Followed `contract.md` (Wave 1 carve-out: no API / schema / UI / migration
  changes assigned in this task) and `mission.md` (no commits, pushes,
  deploys, workflow reruns, Linear mutations).
- No contract changes requested.

## Linear Notes

- Recommended Linear status:
  - ENG-169: keep `Backlog` until the orchestrator approves this brief; then
    move to `Ready` for a single Claude Code explorer who will draft the ADR.
  - ENG-168: keep `Backlog` (still gated by ENG-165 / B1 close + ENG-169 +
    ENG-168 credential ADR). Do NOT move to `Ready` before all three gates
    clear.
- Comment for orchestrator to post (after Codex approves this brief):
  > G1 brief landed in `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/G1.md`.
  > Next implementation wave is ENG-169 (runtime ADR — doc only) followed by
  > ENG-168 split into ENG-168a (Twilio credential payload ADR), ENG-168b
  > (`packages/integrations/twilio/` client), and ENG-168c (`packages/sms/`
  > controlled-send service). Hard prerequisites: ENG-165 / B1 close, ENG-169
  > ADR accepted, ENG-168a ADR accepted.
- New issues suggested (do NOT create from this task — orchestrator + Codex
  approve, then someone with Linear write-scope creates):
  - `ENG-168a` — "Twilio credential payload + IntegrationCredentialService
    contract (ADR)" — design only.
  - `ENG-168b` — "`packages/integrations/twilio/` client + `from_credential`
    resolver" — outbound HTTPS client + respx tests.
  - `ENG-168c` — "`packages/sms/` controlled-send service + suppression /
    quiet-hours / allowed-template gate" — schema + service + tests.
  - `ENG-169-impl` — "Live-subscriber runtime ADR for Cloud Run" — single
    ADR file under `docs/decisions/`.

## Blockers

- B1 review tail must close before any Wave 2 worker touches
  `packages/tenant/*` (E1 already landed the medium fix; Codex re-review is
  the residual blocker).
- ENG-165 (tenant credential UI/API) — listed as a `blockedBy` on ENG-168
  in Linear; current in-flight diff is the slice satisfying it. Wait for
  Codex acceptance.
- `INTERNAL_CREDENTIAL_TOKEN` must already be wired in prod Secret Manager
  before the Twilio client's `from_credential` resolver path is used from
  any second process — confirmed in tenant CLAUDE.md, but the Twilio ADR
  should call it out explicitly.

## Integration Risks

- ENG-169 ADR risks proposing a new long-running Cloud Run Service shape.
  That conflicts with the 2026-05-15 ENG-172 decision (apps/worker/CLAUDE.md):
  "the long-running `fusion-worker` Cloud Run Service was decommissioned …
  recurring work runs as one-shot Cloud Run Jobs (`fusion-job-bounce-poll`
  every 15min via Cloud Scheduler)". The ADR MUST either reuse that pattern
  or, if it argues for a new Service shape, escalate to user explicitly.
- `tenant.integration_credential.provider_kind = "twilio"` is already in
  `PROVIDER_KINDS` (`packages/tenant/models.py:69`) and
  `ProviderKind` Literal (`packages/tenant/schemas.py:21`). No CHECK-constraint
  migration required for the provider name. Risk: the Twilio Account-SID +
  Auth-Token + (optionally) Messaging-Service-SID payload may not fit
  cleanly into the existing `credential_kind ∈ {oauth_token, api_key,
  password_grant, webhook_secret}` set. The ENG-168a ADR is the place to
  decide; an enum extension needs a separate user-approved migration.
- `packages/outreach` is the closest reference pattern (suppression,
  rate-limit, audit-row hashing, outbox via `outreach.outbound_queue`) but
  SMS must NOT live inside `packages/outreach` per ADR-0004 and the
  cross-package import matrix in `packages/CLAUDE.md`. New `sms` domain is
  required; cross-package import matrix MUST be amended in the same PR that
  adds the package.
- `drain_outbound_queue` is paused in prod per `apps/worker/CLAUDE.md`
  ("ENG-112 reintroduces a real always-on background runtime + Redis
  (Memorystore)"). SMS dispatcher topology (cron-job poll vs always-on
  drain) is exactly the question ENG-169 answers; the SMS service can be
  built before the dispatcher is wired, 

_Trimmed 26880 chars._

### H1.md

# H1 — Production Salesforce Integration Read-Only Triage

- Author: Claude Code explorer
- Date: 2026-05-17 (UTC)
- Scope: read-only diagnosis; no production mutation; no product-file edits;
  only this report file under `.agents/orchestration/.../reports/` was
  written.

## Required reading consulted

- `CLAUDE.md`
- `apps/api/CLAUDE.md`
- `apps/web/CLAUDE.md`
- `apps/CLAUDE.md`
- `packages/CLAUDE.md`
- `docs/DEPLOYMENT_RULES.md`
- `packages/integrations/CLAUDE.md`
- `packages/integrations/salesforce/CLAUDE.md`
- `apps/api/routers/integrations.py`
- `apps/api/routers/integrations_list.py`
- `apps/api/dependencies.py` (`_build_salesforce_client`, `get_salesforce_client`,
  `get_sf_lead_ingest_service`)
- `packages/integrations/salesforce/oauth.py`
- `packages/integrations/salesforce/client.py`

## Commands run

All read-only — `gcloud ... describe|read|list`, `gh run list|view`, `git`,
`rg`, `Read`/`Glob`/`Grep`.

```text
git status --short
git diff --stat HEAD
git diff HEAD -- apps/api/routers/tenant.py packages/tenant/credential_service.py packages/tenant/schemas.py
git diff HEAD -- .github/workflows/deploy-prod.yml
git log --oneline -30 -- apps/api/routers/integrations.py apps/api/routers/integrations_list.py packages/integrations/salesforce/ packages/ingest/sf_lead_service.py
gcloud run services list --project=fusioncrm-494201
gcloud run services describe fusion-api --region=us-west1 --format="value(status.traffic)"
gcloud run revisions list --service=fusion-api --region=us-west1 --limit=8
gcloud run revisions describe fusion-api-00052-xb7 --region=us-west1 --format="value(spec.containers[0].env[].name,spec.containers[0].env[].value)"
gcloud run revisions describe fusion-api-00052-xb7 --region=us-west1 --format="value(spec.containers[0].image,metadata.labels)"
gcloud run revisions describe fusion-api-00053-ssf --region=us-west1 --format="value(metadata.creationTimestamp,spec.containers[0].image)"
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=fusion-api AND (jsonPayload.event=~"sf\." OR jsonPayload.logger=~"salesforce" OR textPayload=~"salesforce" OR jsonPayload.message=~"salesforce" OR jsonPayload.event=~"salesforce")' --limit=20 --freshness=24h
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=fusion-api AND (jsonPayload.event=~"oauth\.callback" OR jsonPayload.event=~"token_persisted" OR jsonPayload.event=~"callback" OR jsonPayload.event=~"refresh_failed" OR jsonPayload.event=~"cred\.resolver" OR jsonPayload.event=~"disconnected" OR jsonPayload.code=~"sf_" OR jsonPayload.error.code=~"sf_" OR textPayload=~"/integrations/salesforce/callback")' --limit=30 --freshness=24h
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=fusion-api AND (textPayload=~"salesforce/callback" OR textPayload=~"integrations/salesforce" OR textPayload=~"sf_oauth")' --limit=30 --freshness=24h
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=fusion-api AND severity>=WARNING' --limit=15 --freshness=24h
gh run list --workflow=deploy-prod.yml --limit 5 --json databaseId,name,status,conclusion,headBranch,createdAt,updatedAt
gh run view 25982799094 --log-failed
```

## Production state at triage time

- `fusion-api` primary traffic: `fusion-api-00052-xb7` = 100% (active).
  Latest-ready is `fusion-api-00053-ssf` but it is **not serving traffic**
  — the last 5 `deploy-prod.yml` runs all `failure`, smoke aborted at
  `--- /healthz ---` and traffic auto-rolled back to 00052.
- `00052-xb7` image: `fusion-api@sha256:03590a0d…`, commit
  `7e09c0a64bb44a3498922083d4f8185b90e08589` (= `7e09c0a`, "fix(deploy):
  filter traffic verification around preview tags (ENG-179)"). Two
  commits behind HEAD on `main` (`cb4d37e`). Both newer commits are
  deploy-workflow-only changes, no SF product code drift.
- `00052-xb7` env (SF-relevant): contains `APP_ENV=production`,
  `LOG_LEVEL=INFO`, `OAUTH_REDIRECT_BASE_URL=https://fusioncrm.app`,
  `WEB_APP_BASE_URL=https://fusioncrm.app`, `APP_COMMIT_SHA=7e09c0a…`,
  Secret-Manager-backed `SECRET_KEY` / `DB_PASSWORD` / `ENCRYPTION_KEY`
  / `INTERNAL_CREDENTIAL_TOKEN` / `DATABASE_URL` / `DATABASE_URL_SYNC`.
  **No `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`,
  `SALESFORCE_CALLBACK_URL`, or `SALESFORCE_DOMAIN`** — this is per
  design (`packages/integrations/salesforce/CLAUDE.md`: runtime must
  resolve client config from `tenant.integration_credential` row
  `(salesforce, api_key)`).
- `apps/web` (`fusion-web-00029-zdf`) is the serving frontend revision.

## Local-diff intersection check

`git status` shows uncommitted changes on `main`:

- `apps/api/routers/tenant.py` — adds `GET /tenant/credentials` (list,
  with `include_revoked` query) and `PUT /tenant/credentials/{id}`
  (metadata update). Removes the old "not yet wired" comment.
- `packages/tenant/credential_service.py` — adds
  `update_metadata(...)` and adds an `include_revoked` flag to
  `list_for_tenant` (default `False` filters revoked rows out of SQL).
- `packages/tenant/schemas.py` — adds `is_default` to
  `IntegrationCredentialUpdate`.
- `.github/workflows/deploy-prod.yml` — adds `--include-email` to the
  IAP identity-token mint and redirects smoke helper diagnostics to
  stderr (ENG-178 phase 4.5 follow-up).
- Tests added/extended: `tests/tenant/...`, `tests/api/test_tenant_credential_routes.py`,
  `tests/core/test_deploy_prod_smoke_logging.py`.

**This diff does not touch Salesforce code paths.** The Salesforce
runtime resolves credentials via `IntegrationCredentialService.read_for(
tenant_id, "salesforce", "<kind>")` (single-row lookup), not
`list_for_tenant(...)`. The only SF-adjacent use of `list_for_tenant`
is `apps/api/routers/integrations.py::disconnect`, which already
filters its iterator to `status == "active"` so a default
`include_revoked=False` would not regress behaviour there. The diff is
also uncommitted and unshipped — it cannot be the production cause

_Trimmed 11533 chars._

### I1.md

# I1 — Salesforce callback env contract fix

## Scope

- Codex follow-up to the production Salesforce OAuth redirect report.
- Local code/config only.
- No production mutation, deploy, workflow rerun, secret edit, or Linear mutation.

## Finding

Production Cloud Run revision `fusion-api-00053-ssf` does not have
`SALESFORCE_CALLBACK_URL` in its runtime environment.

`packages/integrations/salesforce/oauth.py` resolves the callback URL
from Settings first and falls back to the stored integration credential
payload. Because Cloud Run does not receive the env var, production can
fall back to a stale localhost callback URL captured in tenant
credential data.

User-visible symptom:

```text
http://localhost:3000/integrations?sf_oauth_error=missing_pkce_cookie
```

That shape is consistent with the OAuth flow starting on
`https://fusioncrm.app`, then returning to `localhost:3000`; the PKCE
cookie is host-scoped and cannot be sent to localhost.

## Patch

- `infra/scripts/deploy_cloud_run.sh`
  - Added `SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback`
    to canonical `API_ENV_VARS`.
- `infra/scripts/preflight_prod.sh`
  - Added `SALESFORCE_CALLBACK_URL` to `PUBLIC_URL_KEYS`.
- `tests/core/test_env_reference_matches_settings.py`
  - Added `SALESFORCE_CALLBACK_URL` to `REQUIRED_PRODUCTION_CONTRACT`.

## Verification

```text
.venv/bin/python -m pytest tests/core/test_env_reference_matches_settings.py -q
15 passed in 0.26s

.venv/bin/python -m pytest tests/core/test_deploy_prod_smoke_logging.py tests/core/test_env_reference_matches_settings.py -q
20 passed in 0.18s

git diff --check
pass
```

## Live Production Evidence

- `fusion-api` currently sends 100% traffic to `fusion-api-00052-xb7`.
- `fusion-api-00052-xb7` and `fusion-api-00053-ssf` both lack
  `SALESFORCE_CALLBACK_URL`.
- Cloud Run logs show user clicks at `2026-05-17T19:30:54Z`,
  `2026-05-17T20:00:00Z`, and `2026-05-17T20:00:30Z`:
  `POST https://fusioncrm.app/integrations/salesforce/connect/start`
  returned `200` from `fusion-api-00052-xb7`.
- No matching production callback hit appears after those starts.
- Local dev API logs show the callback landing on localhost and failing
  with `sf.oauth.callback_error message=missing_pkce_cookie`, matching
  the user-visible URL.

## Remaining Gate

The repository fix is local only. Production will keep redirecting to
localhost until a user-approved deploy updates `fusion-api` with the
new environment variable.

### J1-review.md

# J1 — Self-service integration credentials UI/API review

## Scope

- Worker implementation for operator-entered provider bootstrap credentials.
- Codex review and verification.
- No production mutation in this workstream.

## Summary

Accepted after one test-harness correction.

The worker added a tenant-scoped metadata-only credentials API and a UI form
on provider cards for storing Salesforce and CareStack bootstrap credentials.
Secret-bearing inputs are accepted only on the write path and persisted through
`IntegrationCredentialService.upsert`, which encrypts payloads. Response DTOs
continue to omit `payload`.

## Files Changed By J1

- `apps/api/routers/tenant.py`
- `packages/tenant/credential_service.py`
- `packages/tenant/schemas.py`
- `tests/tenant/test_credential_service.py`
- `tests/api/test_tenant_credential_routes.py`
- `apps/web/components/integrations/ProviderCard.tsx`
- `apps/web/lib/api/hooks/useCredentials.ts`
- `apps/web/lib/api/schemas/tenant.ts`
- `apps/web/lib/msw/outreachHandlers.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `apps/web/tests/unit/useCredentials.test.tsx`

## Codex Review Note

Initial backend focused tests failed because the unit-test mock for
`AsyncSession.refresh()` did not simulate database-generated UUIDs for newly
inserted credential rows. Codex fixed the mock in
`tests/tenant/test_credential_service.py`; production code did not need a
change for that failure.

## Verification

```text
.venv/bin/python -m pytest tests/core/test_deploy_prod_smoke_logging.py tests/core/test_env_reference_matches_settings.py tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py -q
48 passed in 1.15s

.venv/bin/ruff check apps/api/routers/tenant.py packages/tenant/credential_service.py packages/tenant/schemas.py tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py
All checks passed!

cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run test
4 files, 17 tests passed

cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run typecheck
passed

cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run lint
passed

git diff --check
passed
```

## Residual Risk

- No browser visual smoke was run for the new form in this review pass.
- Full repository verify loop was not run; focused tests covered the changed
  backend/frontend contracts.

### K1-prod-hotfix.md

# K1 — Production Salesforce callback hotfix

## Scope

- Targeted Cloud Run production mutation approved by the user.
- No code deploy, no image rebuild, no secret change, no database mutation.
- Goal: stop Salesforce OAuth from redirecting back to localhost by setting
  the runtime callback URL env var on `fusion-api`.

## Actions

1. Ran targeted env update:

```text
gcloud run services update fusion-api \
  --project=fusioncrm-494201 \
  --region=us-west1 \
  --update-env-vars=SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback \
  --quiet
```

2. Cloud Run initially kept traffic on the manually pinned old revision
   `fusion-api-00052-xb7`, so the env-only update did not affect live
   traffic.

3. Created a uniquely named revision with the same env update:

```text
gcloud run services update fusion-api \
  --project=fusioncrm-494201 \
  --region=us-west1 \
  --revision-suffix=sfcb-0016 \
  --update-env-vars=SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback \
  --quiet
```

4. Verified `fusion-api-sfcb-0016` contains:

```text
SALESFORCE_CALLBACK_URL=https://fusioncrm.app/api/integrations/salesforce/callback
```

5. Shifted traffic:

```text
gcloud run services update-traffic fusion-api \
  --project=fusioncrm-494201 \
  --region=us-west1 \
  --to-revisions=fusion-api-sfcb-0016=100 \
  --quiet
```

## Verification

- `fusion-api-sfcb-0016` is now latest created + latest ready revision.
- `fusion-api-sfcb-0016` serves 100% traffic.
- Startup logs are clean.
- Direct Cloud Run proxy check:

```text
GET  /integrations -> 200
POST /integrations/salesforce/connect/start -> 200
```

- The returned Salesforce authorize URL now contains:

```text
redirect_uri=https%3A%2F%2Ffusioncrm.app%2Fapi%2Fintegrations%2Fsalesforce%2Fcallback
```

## Notes

- Local CLI IAP smoke with the deployer service account could not run
  because the active user lacks `serviceAccountTokenCreator` on
  `cloud-build-deployer-sa`.
- Full browser OAuth completion still needs an operator click through
  Salesforce consent, but the previously broken start URL no longer
  contains localhost.

### L1-local-salesforce-reconnect.md

# L1 — Local Salesforce reconnect loop

## Scope

- Fix localhost behavior after Salesforce refresh-token expiry.
- No production mutation.
- No secret or `.env*` edits.

## Findings

1. Local pull failed exactly on the Salesforce refresh path:

```text
SOQL -> 401
refresh token -> 400 invalid_grant: expired access/refresh token
```

2. The expired `salesforce / oauth_token` row stayed `active`, so
   `/integrations` kept reporting Salesforce as connected and the UI kept
   offering pull/sync against a dead refresh token.

3. The localhost Salesforce callback page discarded the real Salesforce
   `code/state` query and called the mock callback. That made local reconnect
   look complete while the FastAPI OAuth callback never persisted a fresh
   token.

## Changes

- `apps/web/app/(staff)/integrations/salesforce/callback/page.tsx`
  forwards the browser to `/api/integrations/salesforce/callback` with the
  original query string, preserving PKCE cookies and real `code/state`.
- `packages/tenant/credential_service.py` now has `expire_active_for(...)` to
  mark active provider credentials as `expired` without touching payloads.
- `apps/api/routers/integrations.py` catches reconnect-required
  `SfNotConnectedError` from pull/sync/raw lead paths, expires active
  Salesforce OAuth credentials, and returns the standard error envelope.
- `packages/integrations/salesforce/client.py` tags no-refresh-token and
  post-refresh-401 failures with `details.action = reconnect`.
- `apps/web/lib/api/hooks/useSfLeads.ts` invalidates the integrations query
  on pull errors so the card refreshes after backend expiry.
- `apps/web/components/integrations/SfLeadsPanel.tsx` disables manual pull
  while Salesforce is not connected.
- `apps/web/lib/msw/init.tsx` unregisters the old MSW service worker when
  `NEXT_PUBLIC_API_MOCKING=disabled`, preventing stale browser mocks from
  reporting a fake connected state.

## Verification

- `.venv/bin/ruff check apps/api/routers/integrations.py packages/integrations/salesforce/client.py packages/tenant/credential_service.py tests/api/test_integrations_salesforce.py tests/tenant/test_credential_service.py`
- `.venv/bin/python -m pytest tests/api/test_integrations_salesforce.py tests/tenant/test_credential_service.py tests/integrations/test_sf_client.py -q`
  - `49 passed`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run typecheck`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run lint`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run test`
  - `17 passed`
- `git diff --check`
- Restarted `apps/web` dev server on `http://localhost:3000` so it loads
  current `.env.local` (`NEXT_PUBLIC_API_MOCKING=disabled`,
  `NEXT_PUBLIC_USE_REAL_SF=true`).
- Local API:
  - `POST /integrations/salesforce/pull-recent?limit=5` returns `409 sf_not_connected`.
  - The stale local `salesforce / oauth_token` row is now `expired`.
  - `GET /integrations` returns Salesforce as `disconnected`.
- Local UI screenshot verified the Salesforce card shows `Not connected` with
  a `Connect` button.

## Follow-Up

- Complete the real Salesforce browser consent flow from localhost or prod.
- After consent returns, run `Pull 5 latest Leads` again.

### M1-stabilization-review.md

# M1 Stabilization Review

Date: 2026-05-18
Owner: Codex orchestrator
Status: complete with known repository-wide blockers

## Scope

Stabilized and reviewed the current working-tree bundle before any commit/PR:

- deploy smoke diagnostics and Salesforce callback production env contract;
- tenant self-service integration credentials API/UI;
- local Salesforce OAuth reconnect recovery;
- orchestrator script lint cleanup.

No commit, push, merge, deploy, workflow rerun, or `.env*` edit was performed.

## Verification

Passed:

- `PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make lint`
- `PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make typecheck`
- `bash -lc 'set -a; source .env; set +a; PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make verify'`
- `bash -lc 'set -a; source .env; set +a; PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH python -m pytest tests/api/test_integrations_salesforce.py tests/tenant/test_credential_service.py tests/api/test_tenant_credential_routes.py tests/core/test_env_reference_matches_settings.py tests/core/test_deploy_prod_smoke_logging.py tests/core/test_traffic_primary_filter.py -q'` => 71 passed
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run lint`
- `cd apps/web && PATH=/usr/local/opt/node@22/bin:$PATH npm run test` => 17 passed
- `git diff --check`

Blocked / not green:

- `PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH mypy .` fails with 51 existing test typing errors in 10 test files. The fresh errors in the current diff were fixed.
- `bash -lc 'set -a; source .env; set +a; PATH=.venv/bin:/usr/local/opt/node@22/bin:$PATH make test'` fails with 10 failed / 45 error / 425 passed. Main blocker is the existing `two_tenant_db` Phase B fixture raising at `tests/conftest.py:126`; additional existing outreach/worker test failures remain.
- `cd packages/db && alembic check` without env fails on missing required settings; rerun with `.env` loads successfully but reports existing drift: removed `tenant_id` indexes across domains and outreach default drift. No new migration was added in this bundle.

## Review Findings

No blocking finding in the current diff after focused verification.

Residual risks:

- `apps/api/routers/integrations.py` returns a JSON error response after expiring dead OAuth credentials instead of re-raising `SfNotConnectedError`; this is intentional so `get_db()` commits the credential expiry. Keep this behavior covered by route tests.
- `ProviderCard` currently exposes the bootstrap credentials form from provider cards. It is acceptable for the current two providers (`salesforce`, `carestack`), but future providers should get explicit bootstrap schema support before enabling the button.
- `.claude/scheduled_tasks.lock` is unrelated local harness state and must be excluded from any future staging.
- `.claude/scheduled_tasks.lock` is already tracked in git, so `.gitignore`
  alone cannot hide it. Codex added the ignore rule for new clones/future
  cleanup and marked the local path `skip-worktree` to keep it out of this
  staging package.

## Suggested PR Package

One coherent PR is possible:

1. Deploy smoke + prod Salesforce callback contract.
2. Tenant/company self-service provider credentials API/UI.
3. Salesforce reconnect recovery and local callback pass-through.
4. Focused tests and orchestration reports.

Exclude:

- `.claude/scheduled_tasks.lock`

### N1-data-foundation-architecture.md

# N1 Data Foundation Architecture

Date: 2026-05-18
Owner: Tesla read-only architecture agent, reviewed by Codex orchestrator
Status: complete, no file changes from agent

## Recommendation

Use `ops.inquiry`, not `lead_submission`, as the durable business object.
`lead_submission` can remain a provider/source kind. `inquiry` covers
Salesforce Leads, web forms, phone/SMS, HubSpot, and future non-form intake.

Use a separate `ops.consultation` for CareStack appointment/consultation-like
operational records. Do not reuse `phi.consultation` for the Phase 1 marketing
appointment view.

Use `identity.match_candidate` as a match-decision ledger. Do not blindly
auto-merge Salesforce and CareStack people from shared phone/email, but do
support policy-based auto-acceptance when confidence is high enough.

## Proposed Pipeline

```text
Salesforce Lead / CareStack Patient + Appointment
  -> ingest.raw_event
  -> normalized person hints
  -> identity.person + identity.source_link
  -> identity.match_candidate for cross-provider match decisions
  -> ops.inquiry / ops.consultation
  -> interaction.event only for semantic changes
```

## Tables To Add In Small PRs

- `identity.match_candidate` with statuses
  `open | auto_accepted | accepted | rejected | superseded`
- optional `ingest.normalized_person_hint`
- `ops.inquiry`
- `ops.consultation`

Optional raw event metadata in a later small migration:

- `processing_key`
- `payload_sha256`
- `source_observed_at`
- nullable `sync_run_id`

## Match Policy

The desired operating model is automated by default, with manual review only
for ambiguous or contradictory cases.

### Tier 1: Auto-Link

Always resolve automatically when the same stable source identity is seen
again:

- existing `identity.source_link`;
- same Salesforce Lead / Contact ID;
- same CareStack Patient ID.

This is linking, not a fuzzy merge.

### Tier 2: Auto-Accepted Cross-Provider Merge

Automatically merge Salesforce/CareStack people when the policy evidence is
strong, for example:

- exact normalized phone match;
- exact normalized email match;
- compatible normalized name;
- no conflicting name evidence;
- no other active CareStack Patient or Salesforce identity competing for the
  same phone/email;
- tenant/location context is compatible.

The system must still write:

- `identity.match_candidate` with status `auto_accepted`;
- `identity.merge_event`;
- evidence JSON explaining the decision;
- enough provenance to support future undo/split tooling.

### Tier 3: Open Candidate

Do not merge automatically when evidence is weak or ambiguous:

- only phone matches;
- only email matches;
- name conflicts;
- shared family email/phone pattern;
- multiple possible CareStack Patients or Salesforce records match the same
  identifier.

These rows remain `open` candidates and should not block normal operations.

## Key Rules

- Exact provider IDs resolve automatically through `identity.source_link`.
- Same-provider stable IDs resolve automatically.
- Cross-provider email/phone match creates a match decision:
  `auto_accepted` for high-confidence policy matches, `open` for ambiguous
  evidence, `rejected` / `superseded` for contradicted stale candidates.
- Accepted or auto-accepted match candidates record `identity.merge_event` and
  then call explicit domain merge handlers. `IdentityService` should not
  silently rewrite every domain reference.
- CareStack appointment payload is PHI-sensitive. Store only allowlisted
  operational fields outside PHI.

## Implementation Split

1. Identity PR: `identity.match_candidate` model/schema/repository/service tests.
2. Ingest PR: optional `person_hint` and raw event idempotency metadata.
3. Ops inquiry PR: `ops.inquiry` model/service/upsert/tests.
4. Ops consultation PR: `ops.consultation` model/service/upsert/tests.
5. Salesforce pipeline PR: Lead snapshot -> raw_event -> hint -> source_link or match_candidate -> inquiry -> interaction.
6. CareStack pipeline PR: Patient/Appointment sync -> raw_event -> hint -> source_link -> consultation -> interaction.

## Noted Risks

- `identity.person_identifier` uniqueness currently appears global on `(kind, value)`; multi-tenant duplicates may collide.
- `ops.lead` is currently one row per person; Salesforce can have multiple Lead records. Do not extend that 1:1 assumption for repeat ad/form submissions.
- CareStack appointment data must be allowlisted; no notes, DOB, chief complaint, findings, procedure detail, or clinical content in `ops.consultation`.

### P1-eng165-credentials-polish.md

# P1 ENG-165 Credentials Polish Report

Task ID: P1
Linear issue: ENG-165
Agent role: implementation worker + Codex controller review
Status: complete

## Summary

Self-service provider credentials were polished in the existing
tenant-owned credential surface.

Implemented:

- `App credentials` is only shown for supported bootstrap providers:
  `salesforce` and `carestack`.
- Provider-specific field labels for Salesforce Connected App credentials and
  CareStack password-grant credentials.
- Explicit saved state after successful credential save.
- Error state reset when the operator edits or cancels the form.
- Frontend bootstrap schema is strict and rejects cross-provider fields.
- MSW validates `/api/tenant/credentials` with the same Zod schema and returns
  an API error envelope for invalid payloads.
- Hook tests prove unsupported providers do not issue `fetch`, and secret /
  payload fields from a mocked response do not flow into parsed hook data.
- Codex added the matching backend Pydantic guard so production API also
  rejects cross-provider bootstrap fields instead of silently ignoring them.

## Files Changed

- `apps/web/components/integrations/ProviderCard.tsx`
- `apps/web/lib/api/schemas/tenant.ts`
- `apps/web/lib/msw/outreachHandlers.ts`
- `apps/web/tests/unit/schemas.test.ts`
- `apps/web/tests/unit/useCredentials.test.tsx`
- `packages/tenant/schemas.py`
- `tests/api/test_tenant_credential_routes.py`

## Verification

- `.venv/bin/python -m pytest tests/api/test_tenant_credential_routes.py tests/tenant/test_credential_service.py -q` => 30 passed.
- `npm run --prefix apps/web test -- --run tests/unit/schemas.test.ts tests/unit/useCredentials.test.tsx` => 10 passed.
- `npm run --prefix apps/web typecheck` => passed.
- `npm run --prefix apps/web lint` => passed.
- `make lint` => passed.
- `make verify` => passed.
- `git diff --check` => passed.

## Notes

- Direct system `pytest` may fail without the project virtualenv because the
  system interpreter lacks project dependencies.
- The worker reported older local Node path friction; the main workspace
  `npm run --prefix apps/web lint` passed without extra PATH changes.

### P2-data-foundation-implementation-plan.md

# P2 Data Foundation Implementation Plan

Task ID: P2
Linear issue: ENG-181
Agent role: architecture/schema worker
Status: complete
Branch: current working tree, read-only except this report
Worktree: `/Users/eduardkarionov/Desktop/Fusion_crm`

## Summary

The next data-foundation step should add three canonical surfaces:
`ingest.normalized_person_hint`, `identity.match_candidate`, and two ops
business objects: `ops.inquiry` and `ops.consultation`.

The matching path should be automated by default. Exact source IDs and
high-confidence email/phone/name evidence should link or merge automatically
with an explicit `identity.match_candidate` evidence row. Only ambiguous or
contradictory evidence should stay `open`, and open candidates must not block
normal Salesforce or CareStack processing.

## Current Constraints Observed

- `identity.person.id` is the global `person_uid`.
- `identity.source_link` already dedupes stable provider records by
  `(source_system, source_kind, source_id)`.
- `identity.merge_event` already records accepted person merges, but does not
  rewrite downstream domain references.
- `SfLeadIngestService` currently performs hidden email/phone reactivation
  matching inside the Salesforce pipeline. This should move into an explicit
  identity match policy so Salesforce and CareStack use the same rules.
- `ops.lead` is currently one row per person. Do not extend that shape for
  repeated ad/form submissions; use `ops.inquiry`.
- `ops` must remain PHI-free. CareStack clinical details, DOB, treatment notes,
  findings, plans, allergies, prescriptions, procedure details, and free-text
  clinical fields stay out of `ops`.
- Existing `person_identifier` and `source_link` uniqueness appears global in
  model/migration shape instead of tenant-scoped. New tables should use
  `tenant_id` in unique keys, and the old uniqueness shape should be handled by
  the existing verify/drift cleanup before production multi-tenant use.

## Proposed Tables

### `ingest.normalized_person_hint`

Purpose: store the provider-neutral, normalized person evidence extracted from
a raw provider payload. It is not the canonical person row and must not become
an ops dashboard surface.

Columns:

| Column | Type | Null | Notes |
|---|---:|---:|---|
| `id` | UUID PK | no | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID | no | `TenantScopedMixin` |
| `raw_event_id` | UUID | no | DB FK to `ingest.raw_event.id` is acceptable because it stays within `ingest` |
| `source_system` | String(32) | no | `salesforce`, `carestack`, `web_form`, etc. |
| `source_kind` | String(32) | no | `lead`, `contact`, `patient`, `submitter`, etc. |
| `source_id` | String(240) | yes | provider record id if available |
| `observed_at` | TIMESTAMPTZ | no | provider event/update time or `raw_event.received_at` |
| `given_name` | String(120) | yes | normalized/canonical casing only when safe |
| `family_name` | String(120) | yes | normalized/canonical casing only when safe |
| `display_name` | String(240) | yes | non-clinical |
| `email_normalized` | String(320) | yes | lower-cased; do not store raw email variants |
| `phone_normalized` | String(32) | yes | current project normalizer strips to digits |
| `person_uid` | UUID | yes | set after resolution; plain UUID, no Python import from identity |
| `source_link_id` | UUID | yes | optional provenance pointer after link creation |
| `payload_sha256` | String(64) | yes | hash of canonical raw payload bytes, for replay/idempotency |
| `hint_hash` | String(64) | no | hash of normalized matching features |
| `quality_flags` | JSONB | no | e.g. invalid email, missing name, shared-phone risk |
| `meta` | JSONB | no | non-PHI parser metadata only |
| `created_at` / `updated_at` | TIMESTAMPTZ | no | `TimestampMixin` |

Constraints and indexes:

- `UNIQUE (tenant_id, raw_event_id)` if one hint per event.
- If a raw event can yield multiple people later, use
  `UNIQUE (tenant_id, raw_event_id, source_kind, source_id)` instead.
- `ix_normalized_person_hint_source` on
  `(tenant_id, source_system, source_kind, source_id)`.
- `ix_normalized_person_hint_email` on `(tenant_id, email_normalized)`.
- `ix_normalized_person_hint_phone` on `(tenant_id, phone_normalized)`.
- `ix_normalized_person_hint_person_uid` on `(tenant_id, person_uid)`.
- CHECK `source_system` and `source_kind` should mirror identity source lists,
  or use service validation if we want to avoid repeated DB check migrations.

Optional same-PR `ingest.raw_event` additive columns:

- `processing_key` String(320), nullable.
- `payload_sha256` String(64), nullable.
- `source_observed_at` TIMESTAMPTZ, nullable.
- `sync_run_id` UUID, nullable plain pointer to `integrations.sync_run`.

### `identity.match_candidate`

Purpose: explicit decision ledger for matching incoming provider hints and/or
two existing persons. It records why the system auto-linked, auto-merged, left
an ambiguity open, rejected a stale match, or superseded an earlier candidate.

Columns:

| Column | Type | Null | Notes |
|---|---:|---:|---|
| `id` | UUID PK | no | `UUIDPrimaryKeyMixin` |
| `tenant_id` | UUID | no | `TenantScopedMixin` |
| `hint_id` | UUID | yes | plain UUID pointer to `ingest.normalized_person_hint.id`; avoid identity importing ingest |
| `source_person_uid` | UUID | yes | person created from the incoming source, if already materialized |
| `candidate_person_uid` | UUID | no | existing person proposed as the same human |
| `accepted_person_uid` | UUID | yes | populated for `auto_accepted` / `accepted` |
| `merge_event_id` | UUID | yes | plain UUID pointer to `identity.merge_event.id` after an actual merge |
| `status` | String(24) | no | `open`, `auto_accepted`, `accepted`, `rejected`, `superseded` |
| `match_rule` | String(64) | no | e.g. `email_phone_name`, `phone_name`, `email_name`, `source_link` |
| `confidence` | Numeric(5,4) | no | 0.0000-1.0000 |
| `evidence` | JSONB | no | normalized, non-raw evidence; no clinical text |
| `conflicts` | JSONB | no | co

_Trimmed 16263 chars._

### Q0-eng188-alembic-drift.md

# Q0 — ENG-188 Alembic Drift Fix

## Status

Complete.

## Summary

`alembic check` drift was caused by ORM metadata no longer describing
schema objects that already exist in the database:

- ENG-123 tenant indexes existed in the DB, but `TenantScopedMixin` model
  adopters did not declare the matching index metadata.
- `outreach.template.category` and `outreach.campaign.mailbox_strategy`
  had DB server defaults from the original migration, but model metadata
  omitted those `server_default` values.

No shipped Alembic revision was edited. No new migration was needed.

## Files Changed

- `packages/actor/models.py`
- `packages/audit/models.py`
- `packages/auth/models.py`
- `packages/identity/models.py`
- `packages/ingest/models.py`
- `packages/integrations/models.py`
- `packages/interaction/models.py`
- `packages/ops/models.py`
- `packages/outreach/models.py`
- `packages/phi/models.py`

## Verification

- PASS: `cd packages/db && ../../.venv/bin/alembic check`
  - `No new upgrade operations detected.`
- PASS: `source ./.venv/bin/activate; make verify`
  - `ruff check .`
  - `mypy packages apps`
  - deploy-critical pytest bundle: 24 passed
- PASS: `.venv/bin/python -m pytest tests/actor/test_models.py tests/identity/test_models.py tests/interaction/test_models.py tests/ops/test_models.py -q`
  - 35 passed
- PASS: `git diff --check`

## Known External Debt

- `mypy .` still fails on existing test typing debt.
- Full `make test` still fails on the existing tenant isolation Phase B
  fixture plus unrelated outreach/worker failures.

These are tracked by the separate full-verify cleanup issues and were not
introduced by this fix.

## Linear

- `ENG-188` moved to `Done`.
- `ENG-181` commented as unblocked for the next additive data-foundation
  wave.

### Q1.md

# Q1 — ENG-182 Identity Match Candidate Foundation

## Status

Complete.

## Summary

Added the explicit `identity.match_candidate` decision ledger from the P2
data-foundation plan as the first additive slice of ENG-182. The new table
records every cross-provider identity matching decision (open ambiguity,
auto-accept, accept, reject, supersede) with a tenant-scoped uniqueness shape
that mirrors what the future pipeline (ENG-183 / ENG-185) will require to
replace the hidden email/phone reactivation logic currently inside
`SfLeadIngestService`.

No existing migration was edited. No ingest behavior, route, or worker
changed. The implementation respects every cross-package import rule in
`packages/CLAUDE.md` (identity does not import ingest, so `hint_id` stays a
bare UUID column with no Python-level FK to the not-yet-existing
`ingest.normalized_person_hint`).

## Files Changed

- `packages/identity/models.py` — added `MatchCandidate` ORM, the
  `MATCH_CANDIDATE_STATUSES` / `MATCH_CANDIDATE_ACCEPTED_STATUSES` tuples,
  and the `make_person_pair_key()` helper that the partial-unique
  `(tenant_id, person_pair_key)` guard depends on.
- `packages/identity/schemas.py` — added `MatchCandidateIn` /
  `MatchCandidateOut` DTOs (Decimal `confidence` with `ge=0, le=1`).
- `packages/identity/repository.py` — added `add_match_candidate`,
  `get_match_candidate`, `find_open_match_for_pair`,
  `find_active_hint_candidate`, `list_match_candidates_by_status`.
  All paths route through `for_tenant(...)`.
- `packages/identity/service.py` — added `add_match_candidate(...)` and
  `find_open_match_for_pair(...)`. Service enforces status, confidence,
  self-match, accepted-person, and PHI/raw-payload guards before insert
  (deny-list `_FORBIDDEN_EVIDENCE_KEYS`).
- `packages/db/alembic/versions/20260518_2010_e1f2a3b4c5d6_add_identity_match_candidate.py`
  — new additive Alembic revision (one revision, no edits to shipped
  revisions).
- `tests/identity/test_match_candidate_model.py` — model metadata smoke
  tests (columns, CHECK names, indexes, partial-unique `WHERE` clauses,
  `make_person_pair_key` stability).
- `tests/identity/test_match_candidate_service.py` — service-layer
  validation tests against a mock repo (unknown status, confidence
  out-of-range, self-match, accepted-person invariants, PHI/raw-payload
  rejection, happy-path persistence, `decided_at` set for non-`open`
  status, pair-key sorted across call order).

## Migration

- Revision id: `e1f2a3b4c5d6`
- Down revision: `b4c2e1f9a5d7` (location_uniqueness_by_carestack_id)
- File: `packages/db/alembic/versions/20260518_2010_e1f2a3b4c5d6_add_identity_match_candidate.py`

Creates `identity.match_candidate` with:

- columns per the P2 proposal;
- four CHECK constraints (`status`, `confidence_range`, `distinct_persons`,
  `accepted_status`);
- five `ix_match_candidate_*` indexes (tenant, candidate, source_person,
  hint, status);
- two partial-unique indexes:
  - `uq_match_candidate_open_pair` on `(tenant_id, person_pair_key)`
    `WHERE status = 'open' AND person_pair_key IS NOT NULL`;
  - `uq_match_candidate_hint_candidate_active` on
    `(tenant_id, hint_id, candidate_person_uid)`
    `WHERE status IN ('open', 'auto_accepted', 'accepted')
    AND hint_id IS NOT NULL`;
- cross-schema FKs to `tenant.tenant`, `identity.person`,
  `identity.merge_event`, `actor.actor`, and a self-FK on
  `superseded_by_match_id`.

## Verification

- PASS — `.venv/bin/python -m pytest tests/identity -q`
  - `42 passed in 0.18s` (existing 25 tests plus the 17 new ones —
    7 model + 10 service).
- PASS — `make verify`
  - `ruff check .` clean
  - `mypy packages apps` clean (153 source files)
  - deploy-critical pytest bundle: 24 passed.
- PASS — `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic upgrade head`
  - Applied `b4c2e1f9a5d7 -> e1f2a3b4c5d6` against the local Postgres.
- PASS — `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
  - `No new upgrade operations detected.`
- PASS — `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic downgrade -1`
  - then re-`upgrade head`; the round-trip is clean.
- PASS — `git diff --check` (no output).

## Codex Review Addendum

Date: 2026-05-19

Codex reviewed the worker report and Q1 diff against the mission goal,
`packages/CLAUDE.md`, `packages/db/CLAUDE.md`, and `packages/identity/CLAUDE.md`.
The patch stayed inside Q1 ownership and did not edit shipped migrations.

Review finding fixed in Q1 scope:

- Match candidate inserts validated row `tenant_id` but did not verify that
  `candidate_person_uid`, `source_person_uid`, and `accepted_person_uid`
  belonged to that same tenant. Because `identity.person.id` is globally
  unique and the FK does not include `tenant_id`, a caller could have recorded
  a cross-tenant ledger row. Codex added service-layer tenant existence checks
  through `IdentityRepository.get_person(tenant_id, person_uid)`.
- The PHI/raw-payload guard checked only top-level evidence/conflict keys.
  Codex made the guard recursive so nested JSON payloads such as
  `{"signals": [{"date_of_birth": "..."}]}` are rejected.

Post-review verification:

- PASS — `.venv/bin/python -m pytest tests/identity -q`
  - `45 passed in 0.19s`.
- PASS — `.venv/bin/python -m ruff check packages/identity/service.py tests/identity/test_match_candidate_service.py`.
- PASS — `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
  - `No new upgrade operations detected.`
- PASS — `make verify`
  - `ruff check .` clean.
  - `mypy packages apps` clean across 153 source files.
  - deploy-critical pytest bundle: 24 passed.
- PASS — `git diff --check`.

## Deviations From The P2 Proposal

1. **`hint_id` stays bare UUID (no FK / no relationship).** P2 §
   "identity.match_candidate" notes "plain UUID pointer to
   `ingest.normalized_person_hint.id`; avoid identity importing ingest".
   This implementation honors that: the column is plain, an

_Trimmed 3593 chars._

### R1.md

# R1 — ENG-185 Normalized Person Hint Foundation

## Status

Complete (implementation + focused checks). One verification gate
(`alembic check`) could NOT be invoked from this Claude worker session
because the project's `.claude/settings.local.json` allow-list does not
include the `alembic` CLI, and the session runs with `don't ask` mode.
Details and inspection-based equivalent verification are documented
below; Codex (orchestrator) can run the live `alembic check` from a
session with the broader allow-list.

## Summary

Added the additive `ingest.normalized_person_hint` data-foundation slice
described in the P2 implementation plan (ENG-185). The new table stores
provider-neutral, NON-PHI person evidence extracted from a single
`ingest.raw_event` row so the upcoming identity match policy
(ENG-185) can run uniformly across Salesforce, CareStack, and any
future provider without each pipeline re-implementing email/phone
reactivation logic.

This slice is deliberately data-foundation only. No Salesforce or
CareStack ingest behavior changed; `SfLeadIngestService` and the worker
layer are untouched. No existing migration was edited. No `phi` /
`ops` / `identity` write paths were modified.

`identity.match_candidate.hint_id` already exists as a plain UUID
column (Q1 / ENG-182) and is now pointable at rows in the new table
without any further schema work in that table.

## Files Changed

Within R1's owned write scope (see `tasks/R1.md`):

- `packages/ingest/models.py` — added `NormalizedPersonHint` ORM model
  with the P2 column shape, tenant-scoped indexes, and a
  `(tenant_id, raw_event_id)` unique constraint. `person_uid` and
  `source_link_id` are bare UUID columns; no Python-level relationship
  back to `identity.*`. The only DB-level FK is to `ingest.raw_event.id`
  (same-schema FK is allowed by `packages/CLAUDE.md`). Pre-existing
  uncommitted edits in this file (the `ix_raw_event_tenant_id` index)
  were preserved.
- `packages/ingest/schemas.py` — added `NormalizedPersonHintIn` /
  `NormalizedPersonHintOut` DTOs. Input DTO accepts raw `email` and
  `phone` (service-side normalisation; invalid values become quality
  flags, not exceptions). Output DTO mirrors the ORM row 1:1 with
  `from_attributes=True`.
- `packages/ingest/repository.py` — added
  `add_normalized_person_hint(...)`, `find_hint_by_raw_event(...)`,
  `list_unresolved_hints(...)`. All per-tenant reads route through
  `for_tenant(...)`; no commit/rollback.
- `packages/ingest/service.py` — added
  `capture_normalized_person_hint(...)`, plus
  `find_hint_by_raw_event(...)` /
  `list_unresolved_hints(...)` thin pass-throughs. Service enforces
  `source_system` / `source_kind` against
  `identity.SOURCE_SYSTEMS` / `SOURCE_KINDS` (single source of truth
  for source enums), records `invalid_email` / `invalid_phone` /
  `missing_email` / `missing_phone` / `missing_name` quality flags,
  refuses PHI-looking keys in `meta` / `quality_flags`, and computes
  a deterministic SHA-256 `hint_hash` over the normalised matching
  features. `Identity` imports are limited to `identity.service`
  (the cross-package matrix permits `ingest → identity`).
- `packages/db/alembic/versions/20260518_2030_c7d8e9f1a2b3_add_ingest_normalized_person_hint.py`
  — new additive Alembic revision. Down-revision is Q1's
  `e1f2a3b4c5d6`. Creates the table, the unique constraint, and the
  five indexes; downgrade drops them in reverse order.
- `tests/ingest/test_normalized_person_hint_model.py` — model
  metadata smoke tests (columns, nullability, unique constraint
  shape, index shapes, FK on `raw_event_id` only, no FK on
  `person_uid` / `source_link_id`).
- `tests/ingest/test_normalized_person_hint_service.py` — service
  validation tests against a mock repo (unknown source system /
  kind, email + phone normalisation happy path, invalid email /
  phone recorded as quality flags, missing identifiers recorded as
  quality flags, PHI deny-list including nested paths, hint hash
  determinism + sensitivity, full-row persistence with NULL person /
  source-link pointers, raw `capture(...)` path is unchanged and
  does NOT create a hint).

No files outside ownership were touched. No shipped Alembic
revision was edited.

## Migration

- Revision id: `c7d8e9f1a2b3`
- Down revision: `e1f2a3b4c5d6` (ENG-182 / Q1 — uncommitted but
  present in the working tree, per the task brief)
- File:
  `packages/db/alembic/versions/20260518_2030_c7d8e9f1a2b3_add_ingest_normalized_person_hint.py`

Creates `ingest.normalized_person_hint` with:

- columns per the P2 proposal — `id`, `tenant_id`, `raw_event_id`,
  `source_system`, `source_kind`, `source_id`, `observed_at`,
  `given_name`, `family_name`, `display_name`, `email_normalized`,
  `phone_normalized`, `person_uid`, `source_link_id`,
  `payload_sha256`, `hint_hash`, `quality_flags`, `meta`,
  `created_at`, `updated_at`;
- unique constraint
  `uq_normalized_person_hint_tenant_raw_event` on
  `(tenant_id, raw_event_id)` — one hint per raw event for this
  slice;
- cross-schema FK `tenant_id → tenant.tenant.id`
  (`fk_normalized_person_hint_tenant_id_tenant`, ON DELETE RESTRICT);
- same-schema FK `raw_event_id → ingest.raw_event.id`
  (`fk_normalized_person_hint_raw_event_id_raw_event`,
  ON DELETE RESTRICT);
- indexes: `ix_normalized_person_hint_tenant_id`,
  `ix_normalized_person_hint_source` on
  `(tenant_id, source_system, source_kind, source_id)`,
  `ix_normalized_person_hint_email` on
  `(tenant_id, email_normalized)`,
  `ix_normalized_person_hint_phone` on
  `(tenant_id, phone_normalized)`,
  `ix_normalized_person_hint_person_uid` on
  `(tenant_id, person_uid)`.

No CHECK constraints on `source_system` / `source_kind` at the DB
layer; service-layer validation against
`identity.SOURCE_SYSTEMS` / `SOURCE_KINDS` is the single source of
truth so we do not need a repeated DB CHECK migration when the
identity lists grow. Documented in the migration docstring.

## Verification

### Passing in this session

- PASS — `.venv/bin/pytho

_Trimmed 10469 chars._

### R2.md

# R2 — ENG-185 Pipeline Integration Plan

## Status

Complete — read-only architecture plan.

## Role

Claude Code read-only explorer. Branch: working tree (no edits to product
files). Only this report path was written.

## Summary

Plan the smallest safe ENG-185 patch that replaces the hidden email/phone
reactivation logic currently embedded in
`packages/ingest/sf_lead_service.py::SfLeadIngestService._resolve_person`
with an explicit `IdentityService.resolve_or_create_from_hint(...)` entry
point. The new entry point consumes the
`ingest.normalized_person_hint` row produced by R1 / ENG-185, applies the
P2 §"Match Policy" tier ladder, writes an `identity.match_candidate`
ledger row for every non-trivial decision, and returns a typed result so
the Salesforce pipeline (and the future CareStack pipeline) can populate
`ops.lead` / `ops.inquiry` without owning matching policy.

This plan assumes R1 has not yet landed (R1 report is absent at write
time). Where R1 shape matters, the dependency is called out below.

## Current Flow Summary

### Where the hidden match logic lives today

`packages/ingest/sf_lead_service.py` lines 105–229:

1. `SfLeadIngestService.pull_recent(...)` iterates SOQL records, calls
   `IngestService.capture(...)` (verbatim `raw_event` row) before any
   mapping, then calls `_resolve_person(...)` and `OpsService.upsert_lead(...)`.
2. `_resolve_person(tenant_id, sf_id, record)` runs the dedupe ladder:
   - **(a)** `IdentityService._repo.find_source_link(tenant_id, "salesforce", "lead", sf_id)`
     — re-pull → return existing person, `is_reactivation=False`.
   - **(b)** If `record["Email"]` present, `IdentityService.resolve_by_email(...)` →
     on hit call `IdentityService.add_source_link(...)` and return
     `is_reactivation=True`.
   - **(c)** If `record["Phone"]` present, `IdentityService.resolve_by_phone(...)` →
     on hit call `IdentityService.add_source_link(...)` and return
     `is_reactivation=True`.
   - **(d)** Fallback: `IdentityService.resolve_or_create_person(tenant_id,
     "salesforce", "lead", sf_id, hints=PersonIn(...))` creates a new
     person + source_link with identifiers from the SF record, returns
     `is_reactivation=False`.

Tests for this ladder are in
`tests/ingest/test_sf_lead_service.py` (5 mock-based branch tests + 2
limit/SOQL tests + 1 `list_recent` mapping test) — every one of them
mocks the four `IdentityService` calls above.

### Boundary observations

- Line 180 reaches across the service boundary into
  `self._identity._repo.find_source_link(...)`. The new entry point lets
  ingest stay above the repository.
- `ingest` is allowed to import `identity` (matrix in
  `packages/CLAUDE.md`). `identity` is NOT allowed to import `ingest`.
  The `MatchCandidate.hint_id` column already lives as a plain UUID
  pointer for this reason (Q1 report §"Deviations" item 1).
- `SfLeadIngestService` only consumes
  `IdentityService.{resolve_by_email, resolve_by_phone, add_source_link,
  resolve_or_create_person, get_person}` plus the protected `_repo`
  call. After ENG-185 it should consume one method:
  `IdentityService.resolve_or_create_from_hint(...)`.
- No worker job exists for Salesforce yet (`apps/worker/jobs/` has no
  SF entry). The only invocation path today is the API route
  `apps/api/routers/integrations.py::pull_recent`.

## Proposed ENG-185 Implementation Steps

### Step 1 — Identity-only: new entry point skeleton + DTO

Owned write scope:

- `packages/identity/service.py` — add `resolve_or_create_from_hint(...)`
  with the source-link-only tier wired and the high-confidence /
  open-candidate tiers stubbed.
- `packages/identity/schemas.py` — add `ResolveFromHintResult` DTO (see
  "Contract changes" below).
- `packages/identity/repository.py` — add
  `list_candidate_persons_by_identifiers(tenant_id, email, phone)`.
- `tests/identity/test_resolve_or_create_from_hint.py` — new test
  module.
- `packages/identity/CLAUDE.md` — document the new entry point as the
  provider entry point for ingest workers.

The skeleton should call the existing `resolve_or_create_person(...)`
for the source-link-exact case so behavior is unchanged when the hint
matches an existing `(source_system, source_kind, source_id)` triple.

No ingest, no SF service, no Alembic revision in this step.

### Step 2 — Identity-only: tier-1 auto-accept + tier-2 open candidate

Owned write scope (same as step 1, no migration):

- `packages/identity/service.py` — add private helpers
  `_evaluate_match_policy(hint, candidates)` (pure function) and
  `_apply_auto_accept(hint, person, match_rule, confidence, evidence)`
  that writes the source_link and the `MatchCandidate(status='auto_accepted')`
  row in one unit-of-work.
- A `MatchPolicyConfig` constants block (thresholds 0.99 / 0.95 / 0.92
  from P2 §"Match Policy") that can be tuned without touching call
  sites.
- Tests cover the full tier ladder:
  - exact source link → no match candidate, person reused
    (tier 0);
  - email+phone+compatible name → `auto_accepted` + new source_link
    on existing person (tier 1);
  - exact phone, name compatible → `auto_accepted` (tier 1);
  - exact email + name compatible, no competing phone → `auto_accepted`
    (tier 1);
  - email only with multiple candidates → `open` + a new
    source-linked person so the pull keeps moving (tier 2);
  - cross-tenant candidate must NOT leak into matches;
  - re-call with same `hint_id` is idempotent (uses the
    `uq_match_candidate_hint_candidate_active` partial unique guard);
  - bad evidence keys still blocked by existing PHI deny-list.

### Step 3 — Ingest pipeline cutover

Owned write scope:

- `packages/ingest/sf_lead_service.py` — rewrite `_resolve_person(...)`
  to:
  1. call `IngestService.capture_normalized_person_hint(...)` (from R1)
     with the SF record fields already exposed to identifier
     normalization (`Email`, `Phone`, names, `Id`);
  2. call `IdentityService.resolve_or_create_from_hint(...)` with the
     resulting hint DTO;

_Trimmed 15839 chars._

### R3.md

# R3 — Wave R Verification Scout

## Status

Complete (R1 verification pending — R1 report not yet present).

## Role

Claude Code read-only verifier / reviewer. Owned write scope is this
report only (`reports/R3.md`). No product or migration files were
edited. No destructive git commands were run. No migration
upgrade/downgrade was run.

## R1 Report Availability

- `reports/R1.md` — NOT PRESENT at the time R3 finished.
- `reports/R2.md` — NOT PRESENT at the time R3 finished.

Findings below are based on `tasks/R1.md`, `tasks/R2.md`,
`reports/Q1.md`, `reports/P2-data-foundation-implementation-plan.md`,
`ownership.md`, `contract.md`, current product source, and the
Alembic revision files. Codex must re-run the R1 verification block
once `reports/R1.md` lands.

## Alembic / Migration-Chain Observations

### Current Head

The Alembic revision graph parsed from
`packages/db/alembic/versions/**` is single-headed.

Linear chain (oldest → newest):

```
af6c4e767923 (initial)
b4f8c9a2d1e0 (v0_2 actor_auth_integrations)
a3b1c5d7e9f0 (d2 identity_source_link_merge_event)
390b53c6f4a9 (d1 interaction_event_slim)
4ba791c47185 (d3 ops_account)
c1f9d3a4b8e2 (tenant_domain_create)
d2e0f4b5c9a3 (tenant_id_columns_nullable)
e3a1b6c7d4f5 (tenant_bootstrap_seed)
f4b2c8d9e6a7 (tenant_id_not_null_fk)
b7c3e9f1a2d4 (tenant_integration_credential_multi_mailbox)
a8c5e7d2f4b9 (tenant_credentials_seed)
e8d3a5b1c2f4 (tenant_id_drop_server_default)   ┐
c9d2e4f6a8b3 (outreach_domain_create)          ├ branch
d7e9f5b3c1a8 (outreach_send_campaign_nullable) ┘
af5ba42a505b (merge_parallel_heads_2026_05_10_tenant_) ← merge of e8d3a5b1c2f4 + d7e9f5b3c1a8
b4c2e1f9a5d7 (location_uniqueness_by_carestack_id)
e1f2a3b4c5d6 (add_identity_match_candidate — Q1 / ENG-182)   ← CURRENT HEAD
```

I was unable to confirm with the Alembic CLI (`alembic heads`,
`alembic current`, `alembic check`) — the harness denied all
`alembic`/`cd packages/db && alembic …` invocations in this scout
session under `dontAsk` mode. The chain above was reconstructed by
direct file inspection of every `revision` / `down_revision` field
under `packages/db/alembic/versions/`. Codex must re-confirm with
`alembic heads` and `alembic check` after R1.

### Expected R1 Parent

R1's new revision must set:

```python
down_revision: str | None = "e1f2a3b4c5d6"
```

Any other parent (e.g. `b4c2e1f9a5d7`) would create a parallel head
and require a merge migration. The mission goal explicitly forbids a
second migration writer in Wave R (`contract.md` §"Wave R Contract"),
so the linear-chain assumption must hold.

### R1 Must NOT Touch

- `packages/db/alembic/versions/20260518_2010_e1f2a3b4c5d6_add_identity_match_candidate.py`
  (Q1; shipped). The follow-up FK
  `identity.match_candidate.hint_id` →
  `ingest.normalized_person_hint.id` that Q1 deviation #1 deferred
  must be a NEW additive revision after R1 lands, not an edit of
  `e1f2a3b4c5d6`. R1's brief does not assign that FK — it is a
  follow-up beyond R1.
- Any earlier shipped revision file.

### Pre-existing ENG-188 Model Reconciliation (NOT Drift)

`git status` shows `M packages/ingest/models.py`. The only diff is
the addition of:

```python
Index("ix_raw_event_tenant_id", "tenant_id"),
```

This is the ENG-188 (`Q0`) reconciliation: the index already exists
in Postgres (created by an ENG-123 tenant migration) but had been
missing from ORM metadata. `Q0-eng188-alembic-drift.md` documents
this and verified `alembic check → No new upgrade operations
detected`. R1 must:

- KEEP this line as-is; do not "fix" it by removing the index from
  the model or by adding a fresh migration for it. `alembic check`
  will stay clean.
- Treat the modified-but-uncommitted state of
  `packages/ingest/models.py`, `packages/identity/models.py`, etc.
  as the expected baseline.

### R1 New-Revision Shape Expectations

Cross-checked against `tasks/R1.md` and P2 §"ingest.normalized_person_hint":

- Schema: `ingest`, table `normalized_person_hint`.
- One `op.create_table(...)` followed by `op.create_index(...)`
  calls. Use `op.f(...)` for every constraint name so the project's
  `NAMING_CONVENTION` from `packages/db/base.py` is respected (same
  pattern as Q1's revision).
- FK `raw_event_id → ingest.raw_event.id` (intra-schema; allowed).
- `person_uid` UUID, NO FK (identity rule: ingest may import core
  + tenant + identity at service layer but the column must stay a
  plain UUID per `packages/CLAUDE.md` cross-package matrix and the
  brief's "no identity model/repository import" line).
- `source_link_id` UUID, NO FK (same reason).
- Unique: `(tenant_id, raw_event_id)`.
- Indexes per the brief's bullet list.
- No data backfill in this revision.
- `downgrade()` must drop the indexes then the table (mirror Q1's
  pattern).

### `alembic check` Risk After R1

- If R1 follows the model + migration shape in the brief, autogenerate
  should report "No new upgrade operations detected" after R1
  applies — provided the model includes every index/uniq/CHECK that
  is emitted in the new revision and uses the project mixins
  (`UUIDPrimaryKeyMixin`, `TimestampMixin`, `TenantScopedMixin`).
- Common ways R1 could break `alembic check`:
  - Forgetting to add `Index(...)` lines in `__table_args__` for
    indexes created in the migration.
  - Mixing `op.f(...)` vs literal names so the model's
    `Index("ix_...")` differs from the migration's index name.
  - Forgetting `schema="ingest"` on either the model or the
    migration.
  - Adding a server default on `quality_flags` / `meta` in the
    migration without `server_default=text("'{}'::jsonb")` in the
    model (Q1 hit and avoided this).

## Ownership / Contract Observations

### Write Scopes Are Disjoint (Confirmed)

| Worker | Owned writes (this wave) |
|---|---|
| R1 (writer) | `packages/ingest/{models,schemas,repository,service}.py`, `tests/ingest/`, ONE new `packages/db/alembic/versions/*.py`, `reports/R1.md` |
| R2 (read-only planner) | `reports/R2.md` |
| R3 (this report) | `reports/R3.md`

_Trimmed 8211 chars._

### S1.md

# S1 — ENG-185 Identity Match Policy Entry Point

## Status

Complete (implementation + focused checks). One verification gate
(`cd packages/db && alembic check`) could NOT be invoked from this
Claude worker session because the project's
`.claude/settings.local.json` allow-list does not include the `alembic`
CLI under `dontAsk` mode. Wave S adds no migration and edits no shipped
revision, so structurally `alembic check` should remain green; Codex
must re-confirm from a session with the broader allow-list. Details
below.

## Role

Claude Code implementation worker. Branch: `main` (primary worktree).
Q1 and R1 patches were uncommitted but present in the working tree
when S1 started; S1 left them as-is.

## Summary

Added the identity-only follow-up to ENG-185:
`IdentityService.resolve_or_create_from_hint(...)`, a provider-neutral
entry point that consumes a minimal identity-owned `MatchHintIn` DTO
(built by the ingest-side adapter from a captured
`ingest.normalized_person_hint` row), applies the P2 / R2 match policy
tier ladder, writes `identity.match_candidate` rows for non-trivial
decisions, and returns a typed `ResolveFromHintResult` for future
Salesforce / CareStack cutover.

This wave does NOT change Salesforce or CareStack ingest behavior.
`SfLeadIngestService` is untouched. No worker job changed. No API route
changed. No Alembic revision was added or edited. `packages.identity`
does not import `packages.ingest`; the new DTO is the contract.

## Files Changed

Within S1's owned write scope (see `ownership.md`):

- `packages/identity/models.py` — added the `MATCH_RULES` taxonomy
  tuple (`source_link`, `email_phone_name`, `phone_name`,
  `email_name`, `email_only_ambiguous`, `phone_only_ambiguous`) so
  the service-layer validator has a single source of truth for what
  the ledger may record.
- `packages/identity/schemas.py` — added the identity-owned
  `MatchHintIn` (input DTO) and `ResolveFromHintResult` (output DTO).
  Neither references `packages.ingest`.
- `packages/identity/repository.py` — added
  `list_candidate_persons_by_identifiers(tenant_id, email, phone)`
  with double tenant scope (on `Person.tenant_id` AND
  `PersonIdentifier.tenant_id`) and eager identifier loading. Returns
  empty list if neither identifier is given.
- `packages/identity/service.py` — added:
  - module-private match policy primitives:
    `_AutoAccept` / `_OpenAmbiguous` / `_NewPerson` dataclasses, the
    `_evaluate_match_policy(hint, candidates)` pure function, plus
    `_names_compatible`, `_person_identifier_values`,
    `_hint_to_person_in`, and the `_AUTO_ACCEPT_*` /
    `_OPEN_AMBIGUOUS_FLOOR` thresholds (0.99 / 0.95 / 0.92 / 0.70);
  - `IdentityService.resolve_or_create_from_hint(tenant_id, hint)`
    with the full tier ladder;
  - `IdentityService._apply_auto_accept(...)` (Tier 1) — writes the
    source link FIRST then the `MatchCandidate(status='auto_accepted')`
    row; reuses an existing active candidate row when `hint_id` is
    set and `uq_match_candidate_hint_candidate_active` would match;
  - `IdentityService._apply_open_ambiguous(...)` (Tier 2) — creates a
    new source-linked person via `resolve_or_create_person(...)` and
    writes an `open` candidate against the primary existing candidate;
    same idempotent reuse logic;
  - `add_match_candidate` now validates `match_rule ∈ MATCH_RULES`
    before any DB-touching work.
- `packages/identity/CLAUDE.md` — documented the new entry point and
  the `MatchHintIn` identity-owned-DTO rule.
- `tests/identity/test_match_candidate_service.py` — adjusted the two
  existing confidence-bypass tests to use a valid `match_rule`
  (`email_name`); added
  `test_add_match_candidate_rejects_unknown_match_rule` to cover the
  new validator.
- `tests/identity/test_resolve_or_create_from_hint.py` — new test
  module (21 tests) covering:
  - source_system / source_kind validation;
  - PHI deny-list on `meta` and `quality_flags` (recursive guard
    reused);
  - Tier 0 source-link recapture (returns existing person, NO
    candidate row, calls `touch_source_link`, never calls
    `list_candidate_persons_by_identifiers`);
  - Tier 0 orphan-source-link defensive `NotFoundError`;
  - Tier 1 auto-accept for `email_phone_name` / `phone_name` /
    `email_name`;
  - Tier 1 picks the highest-confidence rule when exactly one
    candidate is eligible (others fail rule eligibility);
  - Tier 2 with multiple eligible candidates (collapse to open);
  - Tier 2 with name conflict on a single email match;
  - Tier 2 `phone_only_ambiguous` rule;
  - Fallback brand-new person (no candidates → no match candidate
    row);
  - Idempotency on auto-accept (reuses the active hint-candidate row,
    skips the second source-link write);
  - Idempotency on open candidate;
  - `hint_id=None` disables the active-candidate lookup;
  - Tenant id is forwarded into the candidate lookup AND the
    source-link lookup (cross-tenant guard);
  - Source-link write order: source link MUST be written BEFORE the
    `auto_accepted` candidate row.

No files outside ownership were touched.

## Implemented DTO / Result Contract

### `MatchHintIn`

Identity-owned, the contract the ingest adapter builds from
`ingest.normalized_person_hint` rows:

```python
class MatchHintIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hint_id: UUID | None = None
    source_system: str    # min 1, max 32; validated against SOURCE_SYSTEMS
    source_kind: str      # min 1, max 32; validated against SOURCE_KINDS
    source_id: str        # min 1, max 240 — required for source-link ops
    given_name: str | None
    family_name: str | None
    display_name: str | None
    email_normalized: str | None
    phone_normalized: str | None
    quality_flags: dict[str, object]
    meta: dict[str, object]
```

`source_id` is required (not nullable). All four tiers of the policy
either look up or write a `source_link`, and the existing
`resolve_or_create_person` already requires `source_id`. Making the


_Trimmed 14512 chars._

### S2.md

# S2 — ENG-185 Salesforce Cutover Planner

## Status

Complete — read-only follow-up plan. No product files were edited; only
this report path was written.

## Role

Claude Code read-only explorer. Branch: working tree shared with the rest
of Wave S. S1 may be editing `packages/identity/**` in parallel; the
`reports/S1.md` file is absent at write time, so this plan is based on
`tasks/S1.md` and the contracts S1 has been instructed to implement.
Final contract verification (DTO field names, match-rule taxonomy strings,
exception types) **is pending S1's report** — see the "Pending S1
verification" section.

## Required Reading

Confirmed read:

- `CLAUDE.md` (root)
- `packages/CLAUDE.md`
- `packages/ingest/CLAUDE.md`
- `packages/identity/CLAUDE.md`
- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/Q1.md`
- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/R1.md`
- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/R2.md`
- `.agents/orchestration/20260517-113000-parallel-startup-wave/tasks/S1.md`

Additional context inspected (read-only):

- `packages/ingest/sf_lead_service.py`
- `packages/ingest/service.py` (R1 `capture_normalized_person_hint`)
- `packages/ingest/schemas.py` (R1 hint DTOs)
- `packages/ingest/repository.py`
- `packages/identity/service.py` (Q1 `add_match_candidate`,
  `find_open_match_for_pair`)
- `packages/identity/repository.py`
- `packages/identity/schemas.py`
- `packages/identity/models.py` (MatchCandidate, source enums)
- `tests/ingest/test_sf_lead_service.py`
- `tests/api/test_integrations_salesforce.py`
- `apps/api/routers/integrations.py` (SF pull route surface)

## Current Salesforce Ingest Flow Summary

### Entry point

`apps/api/routers/integrations.py::pull_recent` (POST
`/integrations/salesforce/pull-recent`) calls
`SfLeadIngestService.pull_recent(tenant_id, limit)` (one and only worker
trigger today; no `apps/worker/jobs/ingest_salesforce.py` yet).

### Per-record loop (`SfLeadIngestService.pull_recent`)

For each SOQL record returned by
`SELECT Id, FirstName, LastName, Email, Phone, Company, LeadSource,
Status, CreatedDate FROM Lead ORDER BY CreatedDate DESC LIMIT {N}`:

1. **Capture raw event** — `IngestService.capture(tenant_id,
   RawEventIn(source="salesforce", event_type="lead.pull",
   external_id=sf_id, received_at=now(), payload=record))`. Verbatim,
   before any mapping. Returns the persisted `RawEvent` row but the
   service does NOT keep the row id today.
2. **Resolve person via `_resolve_person(tenant_id, sf_id, record)`**
   (the hidden ENG-100 dedupe ladder):
   - **(a) Re-pull short-circuit.** Calls the protected
     `self._identity._repo.find_source_link(tenant_id, "salesforce",
     "lead", sf_id)`. If found, returns
     `(IdentityService.get_person(tenant_id, link.person_uid), False)`.
     Note: this is the only direct cross-service-into-repo reach in the
     pipeline.
   - **(b) Email reactivation.** If `record["Email"]` present, calls
     `IdentityService.resolve_by_email(...)`. On hit, calls
     `IdentityService.add_source_link(...)` and returns
     `(matched, True)`. `ValidationError` from `normalise_email` is
     swallowed (becomes a no-match, never a crash).
   - **(c) Phone reactivation.** Same as (b) but for
     `record["Phone"]` via `resolve_by_phone`.
   - **(d) Brand-new person fallback.** Builds `PersonIn(...)` with
     name + email/phone identifiers and calls
     `IdentityService.resolve_or_create_person(tenant_id, "salesforce",
     "lead", sf_id, hints=...)`. Returns `(result.person, False)`.
3. **Upsert ops.lead** —
   `OpsService.upsert_lead(tenant_id, person_uid=person.id, raw=record,
   provider_metadata={"sf_lead_id": sf_id, "is_reactivation":
   is_reactivation, "sf_created_at": ..., "company": ...})`.
4. **Build the DTO** — `_to_dto_from_record(...)`. The function reads
   `email` / `phone` from the verbatim SOQL record (NOT from
   `person.identifiers`) to avoid an async lazy-load.

### Tests covering the ladder today

`tests/ingest/test_sf_lead_service.py` (8 tests, mock-based, no real DB):

1. `test_pull_recent_rejects_limit_zero` — input validation.
2. `test_pull_recent_rejects_limit_too_high` — input validation.
3. `test_pull_recent_brand_new_person_creates_via_resolve_or_create` —
   tier (d). Asserts `find_source_link` is called once, then
   `resolve_by_email`, then `resolve_by_phone`, then
   `resolve_or_create_person`. Also asserts capture happened with the
   tenant id and `provider_metadata.is_reactivation is False`.
4. `test_pull_recent_repull_reuses_person_no_dedupe_lookup` —
   tier (a). Asserts none of the email/phone resolvers run when
   `find_source_link` returns an existing link.
5. `test_pull_recent_email_match_marks_reactivation_and_adds_source_link`
   — tier (b). Asserts `add_source_link` with the SF id and that
   `resolve_by_phone` was NOT called.
6. `test_pull_recent_phone_match_when_no_email_match` — tier (c).
   Asserts `add_source_link` and that `resolve_or_create_person` was
   NOT called.
7. `test_pull_recent_no_email_no_phone_creates_new_person` — tier (d)
   with the email-and-phone-absent branch (skips both reactivation
   resolvers entirely).
8. `test_pull_recent_invokes_soql_with_limit` — SOQL string shape.
9. `test_list_recent_maps_lead_extra_to_dto` — read-side, not the
   pull path.

Every test mocks the protected `service._identity._repo.find_source_link`,
the four `IdentityService` methods, and `OpsService`. None of them
touches the new R1 `IngestService.capture_normalized_person_hint`.

### Boundary observations

- `ingest → identity` import is allowed
  (`packages/CLAUDE.md` matrix). `identity → ingest` is not. The S1
  contract therefore introduces an identity-owned `MatchHintIn` DTO
  rather than letting identity import `NormalizedPersonHintOut`.
- `packages/integrations/salesforce/**` is intentionally fenced off
  from `ingest` (Ports & Adapters via `SfClientProtocol`); nothing in
  this cutover changes t

_Trimmed 22042 chars._

### S3.md

# S3 — Wave S Verification Scout

## Status

Complete (S1 verification pending — `reports/S1.md` not present at write time).

## Role

Claude Code read-only verifier / reviewer. Owned write scope is this report
only (`reports/S3.md`). No product or migration files were edited. No
destructive git commands or migration upgrade/downgrade were run.

## S1 Report Availability

- `reports/S1.md` — NOT PRESENT at the time S3 finished.
- `reports/S2.md` — NOT PRESENT at the time S3 finished.

Findings below are based on `tasks/S1.md`, `tasks/S2.md`, `tasks/S3.md`,
`acceptance.md`, `verification.md`, `contract.md`, `ownership.md`,
`ownership.yaml`, `reports/Q1.md`, `reports/R1.md`, `reports/R2.md`,
`reports/R3.md`, the existing identity / ingest sources, and the Alembic
revision files. Codex must re-run the S1-specific review block once
`reports/S1.md` lands.

## Ownership / Contract Observations

### S1 Write Scope Is Disjoint From R1 and From Future Salesforce Cutover

| Worker | Owned writes (Wave S) | Forbidden / out of scope |
| --- | --- | --- |
| S1 (identity writer) | `packages/identity/{models,schemas,repository,service}.py`, `packages/identity/CLAUDE.md`, `tests/identity/**`, `reports/S1.md` | `packages/ingest/**`, `packages/ops/**`, `packages/phi/**`, `apps/**`, `apps/worker/**`, `packages/integrations/**`, `packages/db/alembic/versions/**`, `.github/workflows/**`, `infra/scripts/**` |
| S2 (read-only planner) | `reports/S2.md` | all `packages/**`, `apps/**`, `infra/**`, `.github/**` |
| S3 (this report) | `reports/S3.md` | all `packages/**`, `apps/**`, `infra/**`, `.github/**` |

Cross-wave comparison:

- **R1** owned writes lived in `packages/ingest/**`, `tests/ingest/**`, and
  one new file under `packages/db/alembic/versions/**`. None of those paths
  appear in S1's allowed list. Disjoint at the path level.
- **Future Salesforce cutover** (the next ENG-185 follow-up scoped by S2)
  will touch `packages/ingest/sf_lead_service.py`,
  `tests/ingest/test_sf_lead_service.py`, and possibly
  `packages/integrations/salesforce/**`. None of those are in S1's allowed
  list. Disjoint at the path level.
- The single overlap point is the **identity-side surface that the future
  cutover wave will call** — `IdentityService.resolve_or_create_from_hint(...)`
  and the new `ResolveFromHintResult` / `MatchHintIn` DTOs S1 ships. That
  overlap is read-only from the cutover wave's perspective: the cutover wave
  consumes S1's contract; it does not re-edit S1's files. The integrator
  must ensure the DTO names/fields match what S2 plans on consuming.

### Identity-Only Boundary (Acceptance S-AC-1)

`identity` must not import `packages.ingest`. Confirmed today via grep:

- No `from packages.ingest` / `import packages.ingest` lines anywhere under
  `packages/identity/{models,schemas,repository,service}.py`. S1 must
  preserve this. The only identity-side imports today are:
  - `packages.core.exceptions`, `packages.core.types` — allowed.
  - `packages.db.base`, `packages.db.mixins`, `packages.db.tenant_scope` —
    allowed.
- S1's brief explicitly forbids importing ingest. The `MatchHintIn` DTO
  must therefore live in `packages/identity/schemas.py` with its own
  field set (NOT derived from `NormalizedPersonHintIn` /
  `NormalizedPersonHintOut`). The Salesforce cutover wave (S2 plan) is the
  layer that adapts an `ingest.NormalizedPersonHint` row into a
  `MatchHintIn` DTO before calling identity — that direction (`ingest →
  identity` at the service layer) is allowed by the cross-package matrix
  in `packages/CLAUDE.md`.

### Migration-Free Posture (Acceptance S-AC-3, Contract §"Wave S Contract")

- S1's `ownership.yaml` entry has `can_create_migration: false` and the
  forbidden list contains `packages/db/alembic/versions/**`. The brief is
  unambiguous: "No Alembic revision is added or edited."
- `contract.md §"Wave S Contract"` reinforces this: "S1 must not add or
  edit Alembic revisions. S1 may update identity models only for Python
  constants / service validation, not schema shape."
- Practical consequences for the model file edits S1 is allowed to make:
  - Adding a Python tuple constant such as
    `MATCH_RULES = ("source_link", "email_phone_name", ...)` to
    `packages/identity/models.py` — **safe**. No DDL. `alembic check`
    stays clean.
  - Adding a CHECK constraint on `match_candidate.match_rule` to enforce
    that tuple at the DB layer — **NOT safe in Wave S**. Would require a
    new migration; S1 is forbidden from adding one. Service-layer
    validation is the only acceptable enforcement this wave.
  - Adding/removing columns, indexes, or unique constraints on any
    identity model — **NOT safe**. Same reason.
  - Editing `identity.match_candidate.hint_id` to become a real
    `ForeignKey("ingest.normalized_person_hint.id")` — **NOT safe**.
    The Q1 deviation explicitly left this as a future additive migration
    (and identity must not import ingest, so a real FK at the Python
    layer would also break the import boundary). Keep `hint_id` a bare
    UUID column.
- `alembic check` after S1 should still return "No new upgrade operations
  detected" provided model files only gain Python-level constants and the
  CHECK / unique / index DDL stays untouched. If the autogenerate diff is
  ever non-empty, that is the diff Codex should reject before integration.

### Match Rule Taxonomy (Acceptance S-AC-2)

The brief lists six taxonomy values:

- `source_link` — tier 0 (reserved; the auto-accept never writes one
  because tier 0 returns without a match candidate);
- `email_phone_name`, `phone_name`, `email_name` — tier 1 auto-accept;
- `email_only_ambiguous`, `phone_only_ambiguous` — tier 2 open.

Required service-layer enforcement:

- `MATCH_RULES` tuple in `packages/identity/models.py`.
- `add_match_candidate(...)` (existing method) must reject any payload whose
  `match_rule` is not in the tuple.
- The new `resolve_or_create_from_hint(...)` must pick rules from this
  tuple by const

_Trimmed 17122 chars._

### T1.md

# T1 Report — ENG-185 Salesforce Cutover Recovery

## Status

Complete after Codex orchestrator recovery review.

The background T1 Codex worker edited the assigned product files but could not
write this report because its sandbox rejected writes under `.agents/**`.
Codex stopped the worker after it exited without a report, reviewed the actual
diff, ran verification, and wrote this recovery report as mission evidence.
See incidents `INC-20260519-004` and `INC-20260519-005`.

## Files Changed

- `packages/ingest/sf_lead_service.py`
- `tests/ingest/test_sf_lead_service.py`
- `packages/ingest/CLAUDE.md`
- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/T1.md`

No identity, ops, apps, deploy, env, workflow, or Alembic files were edited by
Wave T.

## Behavior Summary

- `SfLeadIngestService.pull_recent(...)` now binds the `RawEvent` returned by
  `IngestService.capture(...)`.
- It captures a `NormalizedPersonHintIn` using the returned `raw_event.id`
  before identity resolution.
- It builds the identity-owned `MatchHintIn` from the returned normalized hint
  row.
- It calls `IdentityService.resolve_or_create_from_hint(...)`.
- It fetches the resolved person through `IdentityService.get_person(...)`.
- It maps `ResolveFromHintResult.was_existing_person_match` to
  `provider_metadata["is_reactivation"]`.
- The old hidden Salesforce matching ladder was removed from the ingest
  service: no `_identity._repo` access, no `resolve_by_email`, no
  `resolve_by_phone`, no `add_source_link`, and no `resolve_or_create_person`.

## Tests And Checks

Codex ran:

- `.venv/bin/python -m pytest tests/ingest/test_sf_lead_service.py -q`
  - `10 passed`
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q`
  - `111 passed`
- `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
  - `No new upgrade operations detected.`
- `git diff --check -- packages/ingest/sf_lead_service.py tests/ingest/test_sf_lead_service.py packages/ingest/CLAUDE.md`
  - clean
- `.venv/bin/python -m ruff check packages/ingest/sf_lead_service.py tests/ingest/test_sf_lead_service.py`
  - clean
- `.venv/bin/python -m mypy packages/ingest/sf_lead_service.py tests/ingest/test_sf_lead_service.py`
  - clean
- `make verify`
  - ruff clean, mypy clean, deploy-critical pytest `24 passed`

## Deviations From S2

- None in product behavior.
- The worker report was not produced by the worker because `.agents/**` writes
  were rejected in the background Codex worker sandbox. Codex created this
  recovery report after verification.

## Blockers / Follow-ups

- No code blocker remains for Wave T.
- Follow-up: fix the orchestrator worker launch/report-writing path before the
  next Codex background worker wave.
- Next product choice is either manual local Salesforce smoke evidence for this
  cutover or a separate `ENG-183 ops.inquiry` migration writer wave.

### T2.md

# T2 Report — Wave T Verification Scout Recovery

## Status

Complete after Codex orchestrator recovery review.

The background T2 Codex verifier could read source files but could not create
`reports/T2.md` because its sandbox rejected writes under `.agents/**`.
Codex stopped the worker, reviewed its logged observations, reviewed the final
T1 diff directly, and wrote this recovery report as mission evidence.

## T1 Report Availability

`reports/T1.md` was not available when the T2 worker ran. It is now present as
an orchestrator recovery report.

## Ownership / Contract Observations

- T1 product edits were limited to:
  - `packages/ingest/sf_lead_service.py`
  - `tests/ingest/test_sf_lead_service.py`
  - `packages/ingest/CLAUDE.md`
- No identity files, ops files, apps files, deploy/env/workflow files, or
  Alembic revisions were edited in Wave T.
- `ENG-183 ops.inquiry` remains out of scope.

## Cutover Behavior Observations

- Raw Salesforce records are still captured as `RawEventIn.payload` before any
  normalized hint or identity call.
- The normalized hint is captured with the returned `raw_event.id`.
- The raw SOQL record is not passed into identity; identity receives a
  `MatchHintIn` built from the normalized hint row.
- The ingest service no longer reaches into `IdentityService._repo`.
- The ingest service no longer calls `resolve_by_email`, `resolve_by_phone`,
  `add_source_link`, or `resolve_or_create_person`.
- `is_reactivation` is now derived from
  `ResolveFromHintResult.was_existing_person_match`.
- Tests cover new-person, source-link recapture, existing-person match, open
  ambiguous match, no-identifiers, raw-before-hint-before-identity ordering,
  SOQL limit shape, limit validation, and read-side `list_recent` mapping.

## Recommended Codex Verification

Completed:

- `.venv/bin/python -m pytest tests/ingest/test_sf_lead_service.py -q`
- `.venv/bin/python -m pytest tests/ingest tests/identity tests/api/test_integrations_salesforce.py -q`
- `set -a; source ./.env; set +a; cd packages/db && ../../.venv/bin/alembic check`
- `git diff --check`
- focused ruff and mypy on T1 files
- `make verify`

## Blockers

- No code blocker remains.
- Process blocker recorded: background Codex workers could not write mission
  reports under `.agents/**`; future waves should preflight report-write
  capability or use a different worker mode.

## Next Orchestrator Checklist

- Confirm which workers are still running.
- Read any reports marked blocked or partial.
- Check file ownership before launching more workers.
- Review incidents and apply accepted lessons before planning the next wave.
- Escalate only consolidated user approvals.
- Update this handoff after the next wave or integration step.
