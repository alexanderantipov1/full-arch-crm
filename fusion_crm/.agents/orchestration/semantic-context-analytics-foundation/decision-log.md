# Decision Log — Semantic Context And Analytics Foundation

- 2026-05-30T06:57:30Z | Decision: Accept Strategy handoff for
  Linear-backed mission planning. Rationale: the source plan provides a clear
  mission arc, source doctrine, decomposition, constraints, and first slice.
  Execution readiness remains `needs decision`.
- 2026-05-30T06:57:30Z | Decision: Use Linear project
  `Semantic Context And Analytics Foundation` as the umbrella because the
  Linear initiative create tool is unavailable in this session.
- 2026-05-30T06:57:30Z | Decision: Represent the first recommended execution
  slice as Linear milestone `Slice 1 — Manager Questions + Semantic Catalog`
  with ENG-272 and ENG-273.
- 2026-05-30T06:57:30Z | Decision: Do not launch Workers, create
  implementation branches, or modify product code during this planning pass.

## Human Decisions Needed

1. Confirm whether the first execution slice is questions/catalog only, or
   questions/catalog plus Data Intelligence Agent local tooling.
2. Confirm the owner and review cadence for the first 20 to 30 manager
   analytics questions.
3. Confirm production row-level access rules for billing-sensitive and
   PHI-adjacent analytics results.
4. Confirm whether Manager AI Chat V1 starts aggregate-only.
5. Confirm whether local exploratory samples may include masked PHI-like or
   billing-sensitive fields for authorized builders.
6. Confirm export policy for billing and PHI-adjacent cohorts.
7. Confirm whether a Linear initiative should be created manually or linked
   later above the Linear project.

Needs decision: worker assignment is blocked until the relevant decisions above
are resolved or explicitly waived.

- 2026-05-30T07:11:34Z | Decision: Use an Orchestrator-generated seed list of
  30 manager questions for the first draft. Rationale: the team already knows
  enough doctor/operator and marketing director workflows to start without
  waiting on interviews.
- 2026-05-30T07:11:34Z | Decision: Include Data Intelligence Agent local
  tooling in parallel with the questions/catalog slice. Rationale: local
  profiling and gap briefs can inform catalog and read-model choices.
- 2026-05-30T07:11:34Z | Decision: Allow row-level analytics outputs for
  authorized internal roles during this mission. Rationale: doctor/operator and
  marketing director workflows need cohort drilldown. This does not remove
  service-layer checks, source references, data-class markings, `PhiService`,
  or audit requirements.
- 2026-05-30T07:11:34Z | Decision: Allow masked local exploratory samples for
  authorized builders through approved read-only tooling. Rationale: the Data
  Intelligence Agent needs real local shape visibility, but not direct database
  access or raw dumps.
- 2026-05-30T07:11:34Z | Decision: Defer export policy to a later slice.
  Rationale: exports should wait until result contracts and policy are stable.
- 2026-05-30T07:11:34Z | Decision: Try to create a Linear initiative above the
  project. Result: blocked by Linear connector error `save_initiative not
  found`; project remains the operational umbrella.
- 2026-05-30T07:34:50Z | Decision: Documentation should be attached to the
  frontend from the beginning through a read-only Semantic Analytics Workbench.
  Rationale: staff/builders should be able to read manager questions, semantic
  terms, data classes, policy posture, and implementation readiness directly in
  the app instead of switching to repository files.
- 2026-05-30T07:41:56Z | Decision: Current production users are treated as
  authorized internal users for this mission phase, so row-level analytics data
  can be visible to them. Rationale: the near-term product does not have
  external or limited-access users. This does not remove service-layer checks,
  source references, data-class markings, `PhiService`, audit, or the rule that
  raw provider payloads are not ordinary analytics output.

## Current Decisions

1. First wave includes questions/catalog plus Data Intelligence Agent local
   tooling.
2. Manager questions start from the generated 30-question seed draft.
3. Row-level analytics output is allowed for authorized internal roles.
4. Manager AI Chat may support row-level answers, but only through query spec,
   policy preflight, approved services, result contracts, and audit.
5. Masked local exploratory samples are allowed through approved read-only
   tooling.
6. Export policy is deferred.
7. Documentation should be frontend-readable through a read-only internal
   workbench.
8. The primary mission arc includes `Semantic Catalog Proposal Review V1` as a
   catalog-layer extension. Data Intelligence Agent discoveries may produce
   proposals and gap briefs, but only human-reviewed, versioned catalog changes
   become approved business truth.

## Remaining Decisions

1. Confirm whether the Linear initiative should be created manually outside
   this connector.
2. Confirm when to start workers for `Semantic Catalog Proposal Review V1`.
   Linear issues now exist, but execution remains blocked until the founder
   explicitly says to begin.

## 2026-05-30T07:44:04Z — Scope: docs

Self-execute approved for ENG-272 via `--workspace self`.

- Linear: ENG-272 — https://linear.app/fusion-dental-implants/issue/ENG-272/manager-analytics-questions-v1
- Prompt size: 2223 chars (under 5000-char threshold)
- Reason: User approved starting the Semantic Context And Analytics Foundation mission; ENG-272 is the first dependency.
- Allowed scope marker: docs

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-06-02T05:55:00Z — Linear planning

Created the Linear-backed execution structure for `Semantic Catalog Proposal
Review V1` under the `Semantic Context And Analytics Foundation` project.

- Parent: [ENG-313](https://linear.app/fusion-dental-implants/issue/ENG-313/semantic-catalog-proposal-review-v1)
- Children:
  - [ENG-314](https://linear.app/fusion-dental-implants/issue/ENG-314/scr-01-catalog-proposal-and-version-storage)
  - [ENG-315](https://linear.app/fusion-dental-implants/issue/ENG-315/scr-02-catalog-review-api-contracts)
  - [ENG-316](https://linear.app/fusion-dental-implants/issue/ENG-316/scr-03-catalog-review-ui-persistence)
  - [ENG-317](https://linear.app/fusion-dental-implants/issue/ENG-317/scr-04-review-audit-and-version-history)
  - [ENG-318](https://linear.app/fusion-dental-implants/issue/ENG-318/scr-05-data-intelligence-proposal-ingestion)
  - [ENG-319](https://linear.app/fusion-dental-implants/issue/ENG-319/scr-06-impact-preview-from-registry-and-read-models)
  - [ENG-320](https://linear.app/fusion-dental-implants/issue/ENG-320/scr-07-approved-catalog-consumption-path)
  - [ENG-321](https://linear.app/fusion-dental-implants/issue/ENG-321/scr-08-verification-and-production-review)

Workers were not launched. Execution is blocked until the founder gives an
explicit start command.

## 2026-05-30T07:55:20Z — Scope: docs

Self-execute approved for ENG-273 via `--workspace self`.

- Linear: ENG-273 — https://linear.app/fusion-dental-implants/issue/ENG-273/semantic-analytics-catalog-v1
- Prompt size: 2351 chars (under 5000-char threshold)
- Reason: ENG-272 completed; catalog is the next dependency.
- Allowed scope marker: docs

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.

## 2026-05-30T07:55:27Z — Scope: docs

Self-execute approved for ENG-279 via `--workspace self`.

- Linear: ENG-279 — https://linear.app/fusion-dental-implants/issue/ENG-279/data-intelligence-agent-v1
- Prompt size: 2152 chars (under 5000-char threshold)
- Reason: User approved parallel Data Intelligence Agent local tooling in first wave.
- Allowed scope marker: docs

By accepting this scope, the orchestrator certifies the work is small
enough that worktree isolation is not required.
