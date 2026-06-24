# Task P2 — Data Foundation Implementation Plan

## Role

Read-only architecture/schema worker.

## Goal

Prepare a concrete implementation plan for Salesforce/CareStack canonical identity, inquiry, consultation, and ingest hint data foundation before migrations are written.

## Linear

- ENG-181
- ENG-182
- ENG-183
- ENG-184
- ENG-185

## Owned Write Scope

- `.agents/orchestration/20260517-113000-parallel-startup-wave/reports/P2-data-foundation-implementation-plan.md`

## Out Of Scope

- Product code changes.
- Alembic migrations.
- Changes to architectural invariants.
- PHI-bearing fields in `ops`.

## Acceptance

- Proposed tables/columns/enums/indexes for `identity.match_candidate`, `ops.inquiry`, `ops.consultation`, and `ingest.normalized_person_hint` or a clearly justified equivalent.
- Match policy supports automatic high-confidence matching by default and leaves `open` only for ambiguous cases.
- Service/repository boundaries preserve domain rules and avoid PHI leakage.
- Additive migration strategy only.
- Suggested split into 2-4 PRs/agent tasks with disjoint write scopes and tests.

