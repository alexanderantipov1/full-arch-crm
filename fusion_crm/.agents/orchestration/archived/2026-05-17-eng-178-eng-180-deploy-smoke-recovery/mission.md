# Mission: ENG-178 ENG-180 deploy smoke recovery

## Outcome

- Restore a diagnosable and trustworthy production API smoke gate for `deploy-prod.yml`.
- Close ENG-178 only after `/healthz` smoke passes end-to-end through the public LB/IAP path and the returned `commit_sha` matches the deployed `github.sha`.
- Keep ENG-180 in review until deploy-prod is green end-to-end with the pinned `IAP_OAUTH_CLIENT_ID` audience.
- Do not perform production mutations from this mission unless the user explicitly approves them in the current conversation.

## Constraints

- Conversation with the user is in Russian; repository artifacts are written in English.
- Follow `CLAUDE.md`, `.github/CLAUDE.md`, and `docs/DEPLOYMENT_RULES.md`.
- GitHub Actions deployment changes must stay aligned with the canonical deploy path and strict smoke gate in `docs/DEPLOYMENT_RULES.md`.
- Do not edit `.env*`, secrets, shipped Alembic revisions, or deploy scripts outside the assigned workflow scope.
- Do not commit, push, merge, rebase, deploy, roll back, or change Cloud Run traffic without explicit user approval.
- Keep product tenant-credential changes separate from deploy/smoke stabilization.

## Current State

- Branch: `main`, tracking `origin/main`.
- Dirty product files already present before this mission:
  - `.claude/scheduled_tasks.lock`
  - `apps/api/routers/tenant.py`
  - `packages/tenant/credential_service.py`
  - `packages/tenant/schemas.py`
  - `tests/tenant/test_credential_service.py`
  - untracked `tests/api/test_tenant_credential_routes.py`
  - untracked `Agent_Orchestration_Playbook_RU.md`
- `.github/workflows/deploy-prod.yml` is currently clean locally.
- Last reported state from the previous Claude Code session:
  - ENG-178 acceptance is not complete. Smoke failed at `/healthz` with unknown exact cause: possible HTTP status mismatch, `commit_sha` mismatch, or application 5xx.
  - ENG-180 acceptance is partial. Pinned `IAP_OAUTH_CLIENT_ID` audience works far enough for the step to execute, but deploy-prod has not gone green end-to-end.
  - Cloud Run logging query against `fusion-api-00053-ssf` returned no rows, likely due to an overly narrow filter.
  - Workflow logging is self-sabotaging: `BODY=$(check "/healthz")` captures stdout from `check()` and hides diagnostic output from GitHub Actions logs.

## Waves

### Wave 1

- Planned:
  - A1: workflow worker for Phase 4.5 smoke logging fix.
  - A2: read-only diagnostics explorer for GitHub Actions and Cloud Run logs.
- Running:
- Complete:
  - A1: completed and Codex-reviewed. Focused regression test passed.
  - A2: completed as partial repo-side report.
- Blocked:
  - ENG-178 and ENG-180 must not move to Done until deploy-prod smoke is green end-to-end.
  - Live GitHub Actions / Cloud Run evidence still missing because Claude Code harness blocked `gh run`, `gh api`, and `gcloud logging read`.

## Decisions

- 2026-05-17: Split workflow logging fix and log investigation into disjoint tasks. A1 owns the workflow file; A2 is read-only and may run inspection commands only.
- 2026-05-17: Tenant credential changes stay out of Wave 1. They are unrelated product work and have dirty files in the primary worktree.
- 2026-05-17: No production-changing commands are authorized. Read-only `gh`/`gcloud logging read` diagnostics are allowed for explorer tasks.
- 2026-05-17: Adopted role preference: Claude Code writes scoped implementation work; Codex controls orchestration, review, integration, and verification.
- 2026-05-17: Wave 1 launched. Claude Code A1 produced the logging fix and static test; Codex verified the focused test locally. Claude Code A2 could not collect live logs due to harness permissions and reported partial findings.
- 2026-05-17: Broadened Claude Code local permissions for bounded work: targeted pytest/mypy/ruff, read-only GitHub Actions, Cloud Logging, and Cloud Run describe/list commands. Verified `gh run list --workflow deploy-prod.yml --branch main --limit 1` runs in `dontAsk` mode and returns deploy-prod run `25982799094` as failed.
