# Integration Plan

Mission:
Base branch:
Integration branch:
Integrator:

## Branches

| Task | Branch | Worktree | Status | Merge Order | Worker Report | Reviewer Report |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | agent/<mission>-A1 | ../Fusion_crm-A1 | ready | 1 | reports/A1.md | reports/A1-review.md |

## Pre-Merge Checks

- `.agents/orchestration/PARALLEL_WORK_POLICY.md` was applied.
- `git status --short` is understood for every worktree.
- Every agent report confirms branch, worktree, changed files, and tests.
- Every agent report includes task class and ownership card status.
- No branch contains unrelated changes.
- Shared paths and contract changes are declared.
- `tiny_fix` / `hotfix` fast paths satisfy policy requirements.
- Large, high-risk, and contract-changing tasks have cross-runtime reviewer
  reports, or an explicit human reviewer exception is recorded.
- Any branch affected by `main` advancing has synced and rerun focused checks.
- High-risk changes have explicit approval.

## Expected Conflicts

- List files or modules likely to conflict.
- Assign one human or agent integrator to resolve each conflict area.

## Merge Order

1. Merge shared contract PRs first.
2. Merge hotfixes ahead of the queue only when affected workers are marked
   `sync_required`.
3. Merge backend/domain changes before frontend consumers when possible.
4. Merge tests near the related implementation.
5. Merge docs/handoffs last unless they unblock implementation.
6. Merge one PR at a time; after each merge, update affected branches from
   `origin/main` and rerun focused verification.

## Commands

```bash
git switch integration/<mission>
git status --short
git merge --no-ff agent/<mission>-A1
# run focused checks
git merge --no-ff agent/<mission>-A2
# run focused checks
git merge --no-ff agent/<mission>-A3
# run full verification
```

## Verification

Focused checks after each merge:
- TBD

Full verification:
- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check`

## Outcome

- Ready for PR/main:
- Blocked by:
- Follow-up branches:
