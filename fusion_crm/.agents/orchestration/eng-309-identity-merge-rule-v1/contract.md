# Contract — ENG-309

## Identity-resolution rule

- New hard-block precondition in the merge-decision path: DOB-mismatch
  OR SSN-mismatch (both fields present on both candidate records and
  differing) → return "no merge" BEFORE soft-signal scoring runs.
- Soft signals unchanged in their existing behaviour.
- Both fields read from the latest CareStack patient payload (same path
  the resolver already uses; identified by pre-flight).

## Audit script contract

- `infra/scripts/audit_identity_merges.py --tenant-id <uuid> [--dry-run]`
- Reads `identity.source_link` + the latest `carestack.patient.upsert`
  raw_event payload per linked pid.
- Outputs: structured log line with counts +
  per-person sample on stdout (first N) for operator review.
- No PHI in log values.

## Un-merge script contract (conditional)

- `infra/scripts/split_wrong_merged_persons.py --tenant-id <uuid>
  [--dry-run] [--max-splits N]`
- Idempotent. Background-only. Writes one
  `audit.access_log` row per split for the audit trail.

## Hard limits inherited from prior tickets

- CareStack mocked in all tests.
- Schema separation: `phi.*` reads through `PhiService` if any path
  crosses into PHI tables.
- No PHI in log values (DOB and SSN are PHI — count only).
- `except Exception`, never `except BaseException`.
- English in repo files.
- Strict mypy on backend.
- Do NOT touch `apps/web/lib/msw/handlers.ts`.
