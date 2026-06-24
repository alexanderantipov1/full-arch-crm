# Terminal Agent Task Brief

Task ID:
Linear issue:
Agent role: explorer | worker | verifier | integrator
Mission folder:
Report path:
Branch:
Worktree:

## Objective

State the concrete outcome for this agent.

## Context

Required mission files:
- `linear-sync.md`
- `contract.md`
- `ownership.md`

Linear:
- Work against the assigned Linear issue only.
- Do not create, move, close, split, or reprioritize Linear issues.
- Put Linear-related questions in the report.

Shared contract:
- Follow the current `contract.md`.
- Do not change the contract unless this brief explicitly assigns contract ownership.
- If the contract is wrong or incomplete, stop and report.

## Ownership

Branch/worktree:
- Work only on the assigned branch and in the assigned worktree.
- Do not merge other branches.
- Do not push unless explicitly approved.

Allowed write scope:
- `path/or/module`

Allowed read scope:
- `path/or/module`

Do not touch:
- `path/or/module`

Concurrent work:
- Other agents may be editing the repository. Do not revert unrelated changes. Work only inside the allowed write scope.

## Steps

1. Inspect the assigned area.
2. Make the scoped change or produce read-only findings.
3. Run focused checks that fit the task.
4. Write the report to the assigned report path.

## Stop Conditions

Stop and report instead of guessing if:
- The task requires editing outside the allowed write scope.
- The task requires changing `contract.md` without explicit contract ownership.
- The task requires creating, moving, closing, splitting, or reprioritizing Linear issues.
- The task requires switching branches, merging, rebasing, pushing, or deployment.
- A migration, env/deploy change, secret, or broad refactor becomes necessary.
- Another agent's changes conflict with the assigned files.
- Required tests cannot run or fail for unclear reasons.

## Required Report

Use the report template. Include changed files, tests run, failures, blockers, Linear notes, and suggested next tasks.
