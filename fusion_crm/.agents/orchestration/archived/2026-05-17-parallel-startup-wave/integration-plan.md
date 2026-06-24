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
