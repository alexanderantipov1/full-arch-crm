# Contract — ENG-311 Fleet Un-Merge `--apply`

## In scope
- Running `split_wrong_merged_persons.py --apply` in batches against local `:5434`.
- Read-only `audit_identity_merges.py` between batches.
- Pre-apply local pg_dump backup.
- Mission runtime + report + ENG-311 Linear comment.

## Out of scope (do NOT)
- No edits to `split_wrong_merged_persons.py` or any product code / migration.
- No Cloud SQL connection; Cloud SQL Auth Proxy stays down. Local `:5434` only.
- No touching `apps/web/lib/msw/handlers.ts` (other stream's WIP).
- No commit / push unless an in-repo file legitimately changes.
- No UPDATE/DELETE on `audit.access_log` (append-only).
- No real CareStack API pull (`--apply` reads local DB only).

## Gates
- Explicit operator "go" required before the canary `--apply` (Step 6) and it carries
  through the fleet batches (Step 7).
