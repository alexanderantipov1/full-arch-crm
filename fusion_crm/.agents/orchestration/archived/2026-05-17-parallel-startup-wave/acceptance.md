# Acceptance Criteria

Use this file for concrete pass/fail criteria. Keep it more specific than
`goal.md`.

## Wave S Criteria

| ID | Criterion | Evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| S-AC-1 | S1 implements an identity-owned `MatchHintIn` input DTO and `ResolveFromHintResult` output DTO without importing `ingest` into `identity`. | `reports/S1.md`, Codex diff review | pass | Identity-only boundary. |
| S-AC-2 | S1 implements `IdentityService.resolve_or_create_from_hint(...)` with source-link recapture, auto-accepted match, open ambiguous match, and new-person fallback behavior. | `reports/S1.md`, focused identity tests | pass | No Salesforce/CareStack behavior changes. |
| S-AC-3 | S1 writes no Alembic revision and edits no shipped migration. | `git status --short`, Codex diff review, `alembic check` | pass | Wave S is migration-free. |
| S-AC-4 | Match policy evidence/conflicts remain PHI-free and raw-payload-free. | `reports/S1.md`, tests covering recursive guard | pass | Defense in depth with existing match candidate guard. |
| S-AC-5 | Tenant isolation and idempotency are covered for candidate lookup, source-link recapture, and active hint/candidate reuse. | `reports/S1.md`, focused identity tests | pass | Must not leak cross-tenant candidates. |
| S-AC-6 | S2 produces the next Salesforce cutover plan after S1, with write scope, test rewrite plan, and verification gate. | `reports/S2.md` | pass | Report-only task. |
| S-AC-7 | S3 produces the Wave S verification scout checklist. | `reports/S3.md` | pass | Report-only task. |
| S-AC-8 | Codex focused verification passes after S1 review or blockers are documented. | `pytest tests/identity -q`, `alembic check`, `git diff --check`, `make verify` if applicable | pass | Orchestrator-owned evidence. |

## Wave T Criteria

| ID | Criterion | Evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| T-AC-1 | Salesforce pull captures a raw event before any normalization, then captures a normalized person hint using the returned raw event id. | `reports/T1.md`, tests | pass | Preserve capture-then-route. |
| T-AC-2 | Salesforce pull calls `IdentityService.resolve_or_create_from_hint(...)` and no longer reaches into `IdentityService._repo` or calls email/phone resolver ladder methods. | `reports/T1.md`, Codex diff review | pass | Removes hidden matching path. |
| T-AC-3 | `is_reactivation` is mapped from `ResolveFromHintResult.was_existing_person_match` and old branch semantics are preserved. | `reports/T1.md`, tests | pass | Re-pull/open/new remain false; auto-accept true. |
| T-AC-4 | Manual pull API and `SfLeadOut` DTO shape remain unchanged. | focused API tests | pass | No route/frontend changes. |
| T-AC-5 | T1 writes no Alembic revision and edits no identity/ops/apps files. | `git status`, Codex diff review, `alembic check` | pass | Wave T is migration-free. |
| T-AC-6 | T2 produces the Wave T verification scout checklist. | `reports/T2.md` | pass | Recovery report after worker sandbox write failure. |
| T-AC-7 | Codex focused verification passes after T1 review or blockers are documented. | focused pytest, `alembic check`, `git diff --check`, `make verify` | pass | Orchestrator-owned evidence. |

## Out Of Scope

- `ENG-183 ops.inquiry`.
- Salesforce/CareStack behavior changes.
- API routes, worker jobs, deploy scripts, GitHub Actions, Cloud Run, env vars,
  secrets, commits, pushes, merges, deployments.
- Any Alembic revision.

## Do Not Accept If

- Required reports are missing.
- Worker changes exceed ownership.
- `identity` imports `ingest`.
- Any migration file is added or edited.
- Salesforce/CareStack behavior changes land in Wave S.
- PHI-looking or raw-payload keys are accepted in match evidence/conflicts.
- Verification is not run or failing without a documented pre-existing blocker.
