# Linear Sync

## Policy

- The orchestrator creates and moves Linear issues.
- Workers do not create, split, close, or reprioritize Linear issues.
- Workers may reference the assigned Linear issue in reports.
- Mission folder remains the technical source of truth; Linear is the project board.

## Project / Epic

Linear team: Engineering
Linear project: TBD
Parent issue: TBD

## Status Mapping

| Orchestration Status | Linear Status |
| --- | --- |
| intake | Backlog |
| planned | Todo |
| running | In Progress |
| blocked | In Review |
| needs-integration | In Review |
| reviewing | In Review |
| done | Done |

Available Engineering statuses confirmed on 2026-05-17:
Backlog, Todo, In Progress, In Review, Done, Duplicate, Canceled.

## Issue Map

| Task | Linear Issue | Title | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| A1 | ENG-178 | Phase 4.5 smoke logging fix | Todo | terminal-1 | Do not mark ENG-178 Done. This only restores diagnostics. |
| A2 | ENG-178 / ENG-180 | Read-only deploy smoke diagnostics | Todo | terminal-2 | Gather exact failure evidence from GitHub Actions and Cloud Run logs. |
| A3 | ENG-178 / ENG-180 | Integration and verification decision | Blocked | orchestrator/integrator | Wait for A1 and A2 reports. |

## Sync Log

- 2026-05-17: Linear statuses inspected for team `Engineering`.
- 2026-05-17: Per previous session, ENG-178 acceptance is not complete. ENG-180 remains In Review, not Done.
- 2026-05-17: Wave 1 status: A1 logging fix reviewed; A2 live evidence blocked by Claude Code permissions. Do not mark ENG-178 or ENG-180 Done.
- 2026-05-17: Claude Code permissions broadened for read-only diagnostics. Next sync should include live evidence from deploy-prod run `25982799094` after A2-live.
