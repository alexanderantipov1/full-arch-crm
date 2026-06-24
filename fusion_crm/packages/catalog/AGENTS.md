# AGENTS.md — `packages/catalog`

Follow the root `CLAUDE.md`, `packages/CLAUDE.md`, and the
package-local `packages/catalog/CLAUDE.md`. The catalog domain holds
workspace-wide reference data — first member is the CareStack
procedure-code (CDT/CPT) catalog (ENG-420).

Non-negotiable reminders:

- Workspace-wide scoping is intentional — do not add `tenant_id` to
  catalog tables without an explicit reason and an ADR.
- Read-only against CareStack. NEVER POST / PUT / DELETE against
  `/procedure-codes`.
- The repository and the service do not commit and do not rollback —
  they only flush. The caller boundary owns the unit of work
  (operator backfill script, Cloud Run Job entry point, test).
  Exceptions from the upsert propagate so the caller can rollback the
  partial unit of work atomically.
- The PK is a UUID (codebase invariant #8). Upsert is idempotent on
  the CareStack-assigned business key `carestack_code_id`
  (`BIGINT NOT NULL UNIQUE`, `ON CONFLICT (carestack_code_id) DO
  UPDATE`). Re-running the sync must remain a no-op on unchanged
  data.
- No PHI. Codes are reference data; logging ids + codes is safe.
