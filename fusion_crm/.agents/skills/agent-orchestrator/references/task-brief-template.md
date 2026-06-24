# Terminal Agent Task Brief

Task ID:
Linear issue:
Agent role: explorer | worker | verifier | integrator
Task class: normal | tiny_fix | hotfix | contract_change
Mission folder:
Report path:
Branch:
Worktree:

## Objective

State the concrete outcome for this agent.

## Context

Include only the context needed for this task. Mention repository rules that matter for the assigned area.

Required mission files:
- `goal.md`
- `linear-sync.md`
- `contract.md`
- `ownership.md`
- `.agents/orchestration/PARALLEL_WORK_POLICY.md`

Linear:
- Work against the assigned Linear issue only.
- Do not create, move, close, split, or reprioritize Linear issues.
- Put Linear-related questions in the report.

Shared contract:
- Follow the current `contract.md`.
- Do not change the contract unless this brief explicitly assigns contract ownership.
- If the contract is wrong or incomplete, stop and report.

Goal:
- Treat `goal.md` as the mission stop condition and evidence contract.
- If this task cannot contribute to the goal evidence, stop and report.

## Ownership

Ownership card:
```yaml
task_id: TASK-000
linear_issue_id: ENG-000
linear_issue_url: https://linear.app/...
task_class: normal
worker_runtime: codex | claude-code | other
branch: branch/name
workspace: isolated_worktree
owned_paths:
  - path/or/module/**
shared_paths:
  - path/or/shared-contract
forbidden_paths:
  - .env*
  - shipped alembic revisions
integration_mode: pr_only
requires_integrator_review: true
requires_cross_runtime_review: true
reviewer_runtime: codex | claude-code | human
if_shared_path_needed: stop_and_report
if_main_advances: sync_before_pr
verification:
  - focused command
```

Branch/worktree:
- Work only on the assigned branch and in the assigned worktree.
- Do not merge other branches.
- For `tiny_fix` and low-risk `normal` tasks, push the task branch and open a
  draft PR after focused verification passes. Do not ask the user to confirm
  obvious task-owned file lists.

Allowed write scope:
- `path/or/module`

Allowed read scope:
- `path/or/module`

Do not touch:
- `path/or/module`

Concurrent work:
- Other agents may be editing the repository. Do not revert unrelated changes. Work only inside the allowed write scope.
- If `main` advances and this task touches the same paths or shared contracts, sync before PR or merge.
- For large, high-risk, or contract-changing tasks, expect a read-only reviewer
  from a different runtime before integration.
- Preserve unrelated dirty or untracked files. Stage only files changed for
  this task.
- If this task follows a major merge, large PR boundary, mission direction
  change, context compaction, or budget exhaustion, confirm the Context
  Rollover Gate handoff exists before starting substantial work.

## Steps

1. Inspect the assigned area.
2. Make the scoped change or produce read-only findings.
3. Run focused checks that fit the task.
4. Write the report to the assigned report path.

## Stop Conditions

Stop and report instead of guessing if:
- The task requires editing outside the allowed write scope.
- The task requires touching shared paths that were not declared.
- The task requires changing `contract.md` or any shared contract without explicit contract ownership.
- The task requires creating, moving, closing, splitting, or reprioritizing Linear issues.
- The task no longer contributes to `goal.md`.
- The task requires merging to `main`, release integration, deployment, or
  destructive git commands.
- A migration, env/deploy change, secret, or broad refactor becomes necessary.
- Another agent's changes conflict with the assigned files.
- Unrelated changes are in the same files and cannot be separated safely.
- Required tests cannot run or fail for unclear reasons.
- The task is actually a new substantial mission after a rollover trigger and
  no handoff summary or fresh thread/mission run exists.

## Required Report

Use the report template. Include changed files, tests run, failures, blockers, and suggested next tasks.
