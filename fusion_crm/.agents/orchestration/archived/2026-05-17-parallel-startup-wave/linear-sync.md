# Linear Sync

## Policy

- The orchestrator creates and moves Linear issues.
- Workers do not create, split, close, or reprioritize Linear issues.
- Workers may reference the assigned Linear issue in reports.
- Mission folder remains the technical source of truth; Linear is the project board.

## Project / Epic

Linear team: Engineering
Linear project: Fusion CRM — Engineering
Parent issue: TBD

## Status Mapping

| Orchestration Status | Linear Status |
| --- | --- |
| intake | Backlog |
| planned | Ready |
| running | In Progress |
| blocked | Blocked |
| needs-integration | Needs Integration |
| reviewing | In Review |
| verified | Verified |
| done | Done |

## Issue Map

| Task | Linear Issue | Title | Status | Owner | Notes |
| --- | --- | --- | --- | --- | --- |
| A2-live | ENG-178 / ENG-180 | Live deploy-prod smoke evidence | complete | Claude Code + Codex | Deep smoke likely rejected at IAP edge before Cloud Run; backend IAP client and deployer IAP accessor are correct; next hypothesis is missing OIDC email claim. |
| B1 | ENG-177 / ENG-165 | Tenant credential diff review | complete | Codex | One medium edge case before acceptance. |
| C1 | ENG-166 / ENG-167 / ENG-168 | Next provider workflow wave planning | complete | Claude Code | ENG-168/Twilio foundations first after gates. |
| D1 | ENG-178 / ENG-180 | Deploy smoke email claim patch | complete | Claude Code + Codex | Local patch only; needs user-approved deploy-prod run before status move. |
| E1 | ENG-177 / ENG-165 | Tenant credential default/status edge fix | complete | Claude Code + Codex | Focused service tests green; broader route/API acceptance still pending. |
| F1 | ENG-178 / ENG-180 / ENG-177 / ENG-165 | Local integration bundle verification | complete | Claude Code | Focused checks green; ready for Codex final review. |
| G1 | ENG-169 / ENG-168 | Runtime/Twilio next wave brief | complete | Claude Code | Recommends ADR-only wave before implementation. |
| H1 | Salesforce prod issue | Production Salesforce read-only triage | complete | Claude Code | Runtime routes return 409; OAuth start succeeds but callback no longer appears. |
| I1 | Salesforce prod issue | Salesforce callback env contract fix | complete | Codex | Local fix adds `SALESFORCE_CALLBACK_URL` to deploy/preflight/env-contract tests; production still needs approved deploy. |
| K1 | Salesforce prod issue | Targeted Salesforce callback prod hotfix | complete | Codex | `fusion-api-sfcb-0016` serves 100% traffic with `SALESFORCE_CALLBACK_URL`; start URL now uses prod callback. |
| J1 | ENG-125 / ENG-19 / ENG-20 / ENG-73 | Self-service integration credentials UI/API | complete | Worker + Codex | API/UI implementation verified with focused backend/frontend checks. |
| N1 | ENG-181 / ENG-182 / ENG-183 / ENG-184 / ENG-185 | Data foundation architecture | synced | Codex + Tesla | Linear parent/children created for identity matching, inquiry, consultation, and normalized ingest hints. |
| V1 | ENG-186 / ENG-187 / ENG-188 | Full verify cleanup | synced | Codex | Backlog issues created for full `mypy .`, full `make test`, and Alembic drift gates. |
| O2 | ENG-1..ENG-20 / ENG-61 / ENG-65 / ENG-72..ENG-77 / ENG-81..ENG-86 / ENG-88..ENG-93 / ENG-95 / ENG-99 / ENG-144 | Linear cleanup | complete | Codex | Closed stale/duplicate/test issues, detached future milestone issues from canceled parent ENG-66, and left only intentional Backlog work active. |
| P1 | ENG-165 | Credentials polish | complete | Mill + Codex | Implementation complete and locally verified; move to In Review. |
| P2 | ENG-181 / ENG-182 / ENG-183 / ENG-184 / ENG-185 | Data foundation implementation plan | complete | Ohm + Codex | Report complete; parent moves to In Review, children stay Backlog until ENG-188 and PR split. |
| Q0 | ENG-188 | Alembic drift cleanup | complete | Codex | Metadata alignment complete; `alembic check` clean; issue moved to Done. |
| Q1 | ENG-182 | Identity match candidate foundation | complete | Claude Code + Codex | Implementation and Codex review complete; ENG-182 synced to In Review with verification evidence. |
| R1 | ENG-185 | Normalized person hint foundation | complete | Claude Code + Codex | Implementation and Codex review complete; ENG-185 synced to In Review with verification evidence. |
| R2 | ENG-185 | Follow-up pipeline integration plan | complete | Claude Code | Read-only planning under the same Linear issue; report complete. |
| R3 | n/a | Wave R verification scout | complete | Claude Code | Mission-local verification scout; report complete. |
| S1 | ENG-185 | Identity match policy entry point | complete | Claude Code + Codex | Implementation and Codex review complete; no migration or Salesforce cutover. |
| S2 | ENG-185 | Salesforce cutover plan | complete | Claude Code | Read-only planner for the next ENG-185 wave; report complete. |
| S3 | n/a | Wave S verification scout | complete | Claude Code | Mission-local verification scout; report complete. |
| T1 | ENG-185 | Salesforce cutover | complete | Codex worker + Codex | Sole Wave T writer; no migration, no API/UI changes; recovery-reviewed and verified. |
| T2 | n/a | Wave T verification scout | complete | Codex worker + Codex | Mission-local recovery report after worker report-write failure. |

## Sync Log

- 2026-05-17: Linear candidates reviewed. Do not move Linear statuses until reports are reviewed.
- 2026-05-17: Parallel Wave 1 reports complete. Linear comments/status updates still pending orchestrator approval.
- 2026-05-17: Codex read-only follow-up completed for A2-live. Do not move ENG-178/ENG-180 until the workflow patch is reviewed and a user-approved deploy-prod run passes.
- 2026-05-17: Wave 2 local patches complete and Codex-reviewed. Do not move ENG-178/ENG-180 until deploy-prod is user-approved and green. ENG-177/ENG-165 can proceed to broader acceptance review.
- 2026-05-17: Wave 3 reports complete. No Linear mutation performed.
- 2026-05-17: H1 triage report complete. No Linear mutation performed.
- 2026-05-17: I1 local env-contract patch complete after user supplied localhost redirect evidence. No Linear or production mutation performed.
- 2026-05-17: K1 production hotfix complete after explicit user approval. No Linear mutation performed.
- 2026-05-17: J1 self-service credentials UI/API complete and Codex-reviewed. No Linear mutation performed.
- 2026-05-18: Linear audit completed without existing status changes. Created ENG-181 through ENG-188 and added audit comments to ENG-3, ENG-5, ENG-7, ENG-92, ENG-165, ENG-177, ENG-178, and ENG-180. Added a project-level audit comment noting stale ENG-1..ENG-17 risk and the additive-migration rule.
- 2026-05-18: Linear cleanup completed. Moved implemented legacy slice tasks to Done, closed obsolete scope as Canceled/Duplicate, closed archived test noise ENG-61/65/95/99, closed ENG-144 as duplicate of ENG-148, detached ENG-81..ENG-86 from canceled ENG-66 while keeping them as future milestone Backlog work, and added project cleanup comments. Current Backlog is intentionally ENG-81..86, ENG-110..112, ENG-165..171, and ENG-181..188.
- 2026-05-18: P-wave completed. ENG-165 credential polish implemented and verified; ENG-181 data-foundation implementation plan written. Move ENG-165 and ENG-181 to In Review; keep ENG-182..ENG-185 Backlog until Alembic drift (ENG-188) is resolved and implementation work is split.
- 2026-05-18: Q0 completed. ENG-188 moved to Done after model metadata was aligned with existing tenant indexes and outreach server defaults. `alembic check`, `make verify`, focused model tests, and `git diff --check` passed. ENG-181 commented as unblocked for additive data-foundation work.
- 2026-05-18: Q1 launched for ENG-182. Claude Code owns the first `identity.match_candidate` implementation slice; Linear status remains unchanged until Codex reviews the report and diff.
- 2026-05-19: Q1 completed and Codex-reviewed. Codex fixed tenant-person validation and recursive PHI/raw-payload guard inside Q1 ownership. Local evidence is green: `tests/identity -q` (45 passed), focused ruff, `alembic check`, `make verify`, and `git diff --check`. ENG-181 and ENG-182 are synced to In Review; ENG-188 remains Done. Comments were added to ENG-181, ENG-182, and ENG-188 with the current evidence.
- 2026-05-19: Wave R launched. R1 owns the ENG-185 normalized-person-hint implementation and the only Wave R migration; R2 plans ENG-185 follow-up pipeline integration read-only; R3 scouts verification risk read-only. ENG-185 is synced to In Progress. An initial mistaken ENG-183 status/comment sync was corrected because ENG-183 is the later `ops.inquiry` slice, not normalized hints.
- 2026-05-19: R2 and R3 completed report-only work. Keep ENG-185 In Progress until R1 lands and Codex reviews the implementation. Do not move ENG-185 to In Review until R1 verification passes.
- 2026-05-19: R1 completed and Codex-reviewed. Codex corrected stale issue references to ENG-185 and verified `tests/ingest -q`, `tests/ingest tests/identity tests/ops -q`, `make verify`, `alembic upgrade head`, `alembic check`, downgrade/upgrade round-trip, and `git diff --check`. ENG-185 is synced to In Review and ENG-181/ENG-185 comments contain the evidence.
- 2026-05-19: Wave S planned for ENG-185 follow-up. S1 is the sole writer for the identity-only match policy entry point; S2/S3 are read-only report tasks. ENG-183 remains untouched because it is the later `ops.inquiry` slice.
- 2026-05-19: Wave S launch synced. ENG-185 moved from In Review to In Progress for the follow-up identity policy wave and received a launch comment. ENG-183 remains Backlog.
- 2026-05-19: Wave S completed and Codex-reviewed. S1 identity policy implementation verified with identity tests, adjacent-domain regression, `alembic check`, `git diff --check`, and `make verify`. Move ENG-185 back to In Review with evidence. S2's report scopes the next Salesforce cutover wave.
- 2026-05-19: Wave T planned for the ENG-185 Salesforce cutover. T1 owns `SfLeadIngestService` and its tests; T2 is read-only verification scouting. ENG-183 remains Backlog.
- 2026-05-19: Wave T launch synced. ENG-185 moved from In Review to In Progress for the Salesforce cutover and received a launch comment. ENG-183 remains Backlog.
- 2026-05-19: Wave T completed after Codex recovery review. Background workers could not write reports under `.agents/**`, so incidents were recorded and Codex reviewed the actual T1 diff. Verification passed: SF ingest test (10 passed), focused ingest/identity/API regression (111 passed), `alembic check`, `git diff --check`, focused ruff/mypy, and `make verify`. Move ENG-185 back to In Review with evidence; ENG-183 remains Backlog.
