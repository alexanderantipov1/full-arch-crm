# Worker Report — ENG-272 Manager Analytics Questions V1

- Task id: ENG-272
- Linear issue: ENG-272
- Linear URL: https://linear.app/fusion-dental-implants/issue/ENG-272/manager-analytics-questions-v1
- Linear title: Manager Analytics Questions V1
- Role: worker
- Agent: claude-code
- Session id: 5df28a5c2071
- Branch: main
- Worktree: . (self-execute approved via `--workspace self`, scope `docs`,
  per decision-log entry 2026-05-30T07:44:04Z)
- Allowed scope: docs only — no product code, no `.env*`, no migrations,
  no commits, no pushes.

## Summary

Refined `manager-analytics-questions-v1.md` from a flat list of 30
seed questions into a structured V1 seed spec. Every question now has
priority, workflow group, default output level (aggregate vs row-level vs
aggregate+drilldown), output shape, filters, candidate semantic terms,
data-class concerns, ambiguity/clarification notes, and review owner.
Added a priority roll-up, a cross-cutting ambiguity index that feeds
ENG-273, and an expanded candidate catalog terms list grouped by concern.
Existing guardrails (PhiService routing, raw-payload exclusion,
service-owned result contracts) are preserved and expanded.

No product code was touched. No commits or pushes were performed.

## Touched Files

- `.agents/orchestration/semantic-context-analytics-foundation/manager-analytics-questions-v1.md`
  — full rewrite into the V1 seed spec described above.

## What Changed

1. Reframed the file from "Seed Draft" to "V1 Seed Spec" while keeping
   the explicit "not yet final product truth" caveat.
2. Audience header now states the two roles (doctor/operator,
   marketing director) and confirms current production users are
   authorized internal users while keeping `PhiService`, audit, source
   reference, and data-class guardrails.
3. Added a Legend section defining priority (P0–P3), default output
   level (aggregate, aggregate+drilldown, row-level), and data classes
   (`ops`, `identity`, `integration_metadata`, `billing`, `phi_adjacent`,
   `phi`).
4. Restructured all 30 questions into per-question blocks with the
   following fields:
   - Priority
   - Workflow group
   - Reviewer
   - Default output level
   - Output shape (concrete row/aggregate fields)
   - Filters
   - Candidate semantic terms (referenced from the candidate term list)
   - Data classes touched
   - Ambiguities / clarification notes
5. Added a refined Workflow Group Index that consolidates similar
   workflows (e.g. "Treatment and revenue" + "Payment and balance"
   remain split because they have different reviewer audiences and
   different data-class profiles).
6. Added a Priority Roll-Up table for quick triage.
7. Added an Output Expectations And Guardrails section that explicitly
   keeps row-level outputs subject to service-owned result contracts,
   source references, data-class markings, audit, and the no-raw-payload
   rule.
8. Added a Cross-Cutting Ambiguities And Clarification Notes section
   that lists ten recurring decisions (attribution model, attribution
   windows, stale thresholds, source normalization, balance
   source-of-truth, payment evidence definition, CareStack link
   definition, owner definition, cancelled-vs-no-show, business unit /
   location). These are explicitly tagged as inputs to ENG-273, not
   blockers for ENG-272 review.
9. Expanded the candidate first catalog terms into three labelled
   groups: cohort/outcome, source/attribution, operational/provenance,
   and derived metrics/thresholds.
10. Added a Next Steps list pointing to ENG-273, ENG-274, ENG-282.

## Tests / Checks Run

This task touches only mission documentation under
`.agents/orchestration/semantic-context-analytics-foundation/`. No
product code, no migrations, no schema changes, no dependencies, no
runtime behavior. The repo-level verify loop is not applicable and was
not run.

Local checks performed:

- File written successfully via the Write tool (single file, ~440 lines).
- Internal cross-references verified by inspection:
  - Workflow Group Index rows cover Q1–Q30 with no orphans or duplicates.
  - Priority Roll-Up rows cover Q1–Q30 with no orphans or duplicates.
  - Every candidate term referenced inside a question block also appears
    in the Candidate First Catalog Terms list.
  - Every cross-cutting ambiguity item references at least one question.

## Verification Status

Verification against acceptance.md and verification.md for ENG-272:

- acceptance.md item A requires 20–30 questions grouped by workflow and
  priority, each with output shape, filters, row-level vs aggregate
  need, data-class concern, and review owner. **Met.** 30 questions,
  workflow + priority groups, all required per-question fields present.
- verification.md First Slice Verification items for
  "Manager Analytics Questions and Semantic Catalog V1" relevant to the
  questions side:
  - "Questions cover lead source, consultation, follow-up, treatment,
    payment, owner, location, and risk workflows." **Met conceptually**
    via the six workflow groups. Risk and exception is implicit in
    Q8, Q12, Q24, Q13, Q15, Q28 (stale, missing, breach worklists).
    No verification.md change needed; the seed spec covers all listed
    workflow concepts.
  - "Each question has priority, expected output, filters,
    row-level/aggregate need, data-class concern, and reviewer." **Met.**
  - "Seed draft is reviewed before it becomes product truth." Pending
    human review. The file header preserves the "not yet final product
    truth" caveat. The Next Steps section lists human review of P0 as
    item 1.
- contract.md architecture constraints are preserved verbatim:
  no DB access from agents, no raw SQL, services own logic, repositories
  data-only, PhiService gates PHI, raw payloads are not ordinary
  analytics output, row-level allowed for authorized internal users with
  service-layer checks intact.

No acceptance.md, contract.md, or verification.md edits were required.
Their language is already broad enough to cover the refined spec, and
none of them needed contract drift to align.

## Risks

1. **Priority assignments are an orchestrator-and-worker judgment call,
   not a human decision yet.** The P0 set (Q1, Q2, Q5, Q6, Q16, Q17,
   Q19) reflects the best read of doctor/operator daily worklists and
   marketing director funnel needs. Human reviewer may reassign.
2. **Output shapes are concrete but not yet locked to source fields.**
   The shapes assume canonical fields (`person_uid`, `lead_source`,
   `location`, etc.) that ENG-273 will define precisely. The shapes here
   are directional for ENG-273/ENG-274/ENG-277 sizing, not yet
   implementation contracts.
3. **Some questions touch `billing` and `phi_adjacent` data classes.**
   Q3, Q4, Q5, Q6, Q9, Q12, Q14, Q16–Q19, Q21, Q25, Q26, Q28 all touch
   billing in some form. ENG-273 must classify each candidate term
   before ENG-277 services expose results. ENG-275 (Policy Preflight)
   then enforces gating.
4. **Source attribution model is unresolved.** First-touch vs last-touch
   vs multi-touch attribution affects almost every marketing director
   question. This is the largest cross-cutting decision waiting on
   ENG-273.
5. **No question in this V1 list is expected to require clinical-note
   PHI.** This claim is asserted in the Output Expectations section; if
   ENG-273 finds that any candidate term implicitly requires clinical
   content, that term must be re-scoped or removed.

## Blockers / Questions

- None blocking ENG-272 completion. The seed spec is ready for human
  review.
- The decisions listed under Cross-Cutting Ambiguities are inputs to
  ENG-273 (Semantic Analytics Catalog V1) and do not block ENG-272.

## Runtime Telemetry Note

The mission runtime directory lives outside the project working
directory at
`~/.fusion-agent-orchestrator/<repo-hash>/semantic-context-analytics-foundation/`.
The Claude Code sandbox for this session denied directory access outside
`/Users/eduardkarionov/Desktop/Fusion_crm`, so this worker session did
not write `runtime.json` or `runlog.md` directly. Per the decision-log
entry 2026-05-30T07:44:04Z, the orchestrator approved self-execute and
is responsible for runtime telemetry updates for this session. The
orchestrator should append the worker completion handoff to
`runtime.json` and `runlog.md` after reading this report.

## Suggested Next Task

ENG-273 (Semantic Analytics Catalog V1). The seed spec now provides
concrete inputs:

- the candidate first catalog terms list (grouped by concern);
- the ten cross-cutting ambiguities that the catalog must resolve;
- per-question data-class hints that the catalog must confirm.

ENG-279 (Data Intelligence Agent V1) can proceed in parallel as planned,
per the first wave decision. The seed spec gives the Data Intelligence
Agent specific gap-finding targets in Q13, Q15, Q23, Q28.

ENG-282 (Semantic Analytics Workbench V1) is not yet ready to render
this file as in-app docs because ENG-273 catalog entries are required
for cross-linking question terms to definitions. ENG-282 may begin its
read-only UI shell after ENG-273 first-draft entries exist.

## Do-Not-Merge Conditions

- Do not treat the seed spec as approved product truth until a human
  reviewer signs off on priorities, workflow grouping, and the candidate
  term list. The file header preserves this caveat.
- Do not start ENG-277 (Analytics Services V1) directly from this file.
  ENG-273 catalog entries and ENG-274 query specs must exist first so
  services bind to typed query contracts, not to question prose.
- Do not expose any question's drilldown row shape as a public API
  contract from this file. Row shapes here are directional only.
- Do not edit `acceptance.md`, `contract.md`, or `verification.md` from
  this report. No drift was identified; their existing language already
  covers the refined spec.
