# Daily Sprint Plan

Date: 2026-05-17
Mission: ENG-178 ENG-180 deploy smoke recovery
Linear project: TBD

## Sprint Goal

- Make the deploy-prod API smoke failure diagnosable, then use preserved logs to identify the real blocker for ENG-178 acceptance without changing production traffic.

## Capacity

| Role | Count | Notes |
| --- | --- | --- |
| Orchestrator | 1 | planning, Linear sync, reviews |
| Workers | 2 | A1 workflow worker, A2 read-only diagnostics explorer |
| Integrator | 1 | held until A1 and A2 reports are available |
| Verifier | 1 | held until a candidate fix exists |

## Planned Waves

| Wave | Goal | Tasks | Launch Window | Integration Point | Status |
| --- | --- | --- | --- | --- | --- |
| Wave 1 | Restore diagnostic signal and gather evidence | A1, A2 | now | after both reports | partial |
| Wave 2 | Fix real smoke cause or verify green path | A3 plus follow-ups | after Wave 1 review | before any status close | blocked |

## Decision Windows

- Planning: create mission files, ownership map, and task briefs.
- Report review: compare A1 changed files against ownership and A2 evidence against ENG acceptance.
- Integration: one integrator only after reports. No automatic merge or push.
- End-of-day handoff: summarize unresolved blockers and next wave.

## Done Criteria

- `deploy-prod.yml` smoke diagnostics are visible when `check()` fails inside command substitution.
- The next failed smoke run reveals the exact `/healthz` failure mode, or the smoke run passes.
- ENG-178 remains open until `/healthz`, `/readyz`, `/dashboard/summary`, and `/integrations` smoke pass through the public IAP path with matching `commit_sha`.
- ENG-180 remains In Review until the pinned IAP audience path is verified in a green deploy-prod run.
