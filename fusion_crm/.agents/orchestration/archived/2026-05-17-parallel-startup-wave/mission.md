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
