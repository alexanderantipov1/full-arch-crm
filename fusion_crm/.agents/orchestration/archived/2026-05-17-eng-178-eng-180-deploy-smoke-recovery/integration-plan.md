# Integration Plan

Base branch: main
Integration branch: integration/deploy-smoke-recovery

## Branches

| Task | Branch | Worktree | Status | Merge Order | Notes |
| --- | --- | --- | --- | --- | --- |
| A1 | agent/deploy-smoke-recovery-A1 | ../Fusion_crm-A1 | planned | 1 | Workflow logging fix. |
| A2 | read-only | primary or separate shell | planned | n/a | Evidence report only. |
| A3 | integration/deploy-smoke-recovery | ../Fusion_crm-integration | blocked | n/a | Integrate only after A1 and A2 reports. |

## Expected Conflicts

- Primary repo has unrelated dirty tenant credential files. Integration must avoid carrying those into deploy-smoke work.
- `.github/workflows/deploy-prod.yml` is single-owner A1 for Wave 1.

## Merge Procedure

1. Update local references.
2. Switch to the integration worktree.
3. Merge branches in the listed order.
4. Run focused checks after each merge.
5. Run full verification after all branches are merged.

## Release Gates

- PR/main merge approved: no
- Staging verification approved: no
- Production deployment explicitly approved: no

## Focused Checks

- Inspect workflow shell block to ensure diagnostics go to stderr and response bodies remain stdout.
- If A1 adds a static regression test, run that test.
- Full repository verify loop before completion:
  - `make lint`
  - `mypy .`
  - `make test`
  - `cd packages/db && alembic check`
