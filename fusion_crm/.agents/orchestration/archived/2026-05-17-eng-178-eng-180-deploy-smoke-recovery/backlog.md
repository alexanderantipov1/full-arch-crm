# Mission Backlog

## Intake Queue

| ID | Title | Type | Priority | Risk | Area | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | Fix deploy-prod smoke diagnostic logging | bug | blocker | medium | `.github/workflows/deploy-prod.yml` | planned | Phase 4.5. Diagnostic `echo` output from `check()` and `fail()` must survive command substitution. |
| I2 | Identify real `/healthz` smoke failure cause | research | blocker | high | GitHub Actions, Cloud Run logs | planned | Read-only diagnostics. Determine whether failure is HTTP status, `commit_sha`, or app/runtime error. |
| I3 | Re-run or review deploy-prod end-to-end result | infra | high | high | GitHub Actions production deploy | blocked | Requires user-approved push/merge or manual workflow action. No prod mutation in Wave 1. |
| I4 | Final Linear status sync for ENG-178 and ENG-180 | infra | high | low | Linear | blocked | ENG-178 not Done; ENG-180 remains In Review until green deploy-prod. |
| I5 | Stabilize existing tenant credential product changes | feature | normal | medium | `apps/api`, `packages/tenant`, `tests` | intake | Existing dirty worktree changes are separate from deploy stabilization. Do not mix with ENG-178/180. |

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
