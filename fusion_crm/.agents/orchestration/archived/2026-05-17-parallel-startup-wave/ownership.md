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
