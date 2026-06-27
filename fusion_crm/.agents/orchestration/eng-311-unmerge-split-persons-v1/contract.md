# Contract — ENG-311

## Script contract

- `infra/scripts/split_wrong_merged_persons.py --tenant-id <uuid>
  [--dry-run] [--apply] [--max-splits N] [--person-uid <uuid>]`
- Background-only; NOT wired to HTTP.
- `--dry-run` is the default; `--apply` is the only path that writes.

## Split semantics

- Partition a wrong-merged person's CS source_links by `(dob, ssn)`.
- Largest bucket → stays on original person.id.
- Each other bucket → new person.id (clone Person + identifiers,
  repoint source_links + any denormalized person_uid FKs).
- One `audit.access_log` row per split.

## Invariants

- Idempotent (clean person → no-op).
- Tenant-scoped (no cross-tenant split).
- Append-only audit; one row per split, NO PHI values (person_uid,
  counts only).
- No PHI in structured log values.
- `except Exception`, never `except BaseException`.
- Legitimate same-person multi-registration (same DOB+SSN, different
  pid) is NOT split — those pids share a bucket and stay together.
- No new migration (uses existing tables: identity.person,
  identity.person_identifier, identity.source_link, audit.access_log,
  + any denormalized person_uid table the pre-flight flags).
- Do NOT touch apps/web/lib/msw/handlers.ts.
