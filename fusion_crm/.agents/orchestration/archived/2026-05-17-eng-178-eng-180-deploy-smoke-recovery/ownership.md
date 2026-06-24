# File Ownership

## Rules

- Each editing task must have one primary owner.
- Workers may edit only their assigned write scope.
- Workers must stop and report if they need a file outside their scope.
- Shared files must be sequenced or assigned to one integrator.

## Ownership Table

| Path / Module | Owner Task | Branch | Worktree | Access | Notes |
| --- | --- | --- | --- | --- | --- |
| `.github/workflows/deploy-prod.yml` | A1 | primary or agent/deploy-smoke-recovery-A1 | primary or ../Fusion_crm-A1 | write | Only smoke diagnostic logging changes in the `api-smoke` job. |
| `tests/core/test_deploy_prod_smoke_logging.py` | A1 | primary or agent/deploy-smoke-recovery-A1 | primary or ../Fusion_crm-A1 | optional write | Static regression test if the worker chooses to add one. |
| GitHub Actions logs | A2 | read-only | primary or separate shell | read | `gh run view`/log inspection only. |
| Cloud Run logs for `fusion-api` | A2 | read-only | primary or separate shell | read | `gcloud logging read` only. No service/job/traffic mutations. |
| `.agents/orchestration/20260517-103524-eng-178-eng-180-deploy-smoke-recovery/**` | Orchestrator | main | primary repo | write | Mission source of truth and launch briefs. |

## Read-Only Areas

- Entire repository for A2.
- Dirty product changes under `apps/api/routers/tenant.py`, `packages/tenant/**`, and tenant tests for all ENG-178/180 tasks.

## Prohibited / High-Risk Areas

- `.env*`
- shipped Alembic revisions
- deploy scripts except the explicitly assigned workflow line changes in A1
- secrets
- broad formatting/refactors
- Cloud Run service/job configuration
- Cloud Run traffic
- GitHub Actions production deploy execution
- tenant credential product files during this mission
