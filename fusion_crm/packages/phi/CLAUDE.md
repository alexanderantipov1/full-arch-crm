# CLAUDE.md — `packages/phi`  ⚠️ Protected Health Information

This package is the only place clinical data is allowed to live.
**Treat every change here as compliance-relevant.**

## Tables (schema `phi`)

- **`patient_profile`** — one per person; DOB, sex at birth,
  allergies (JSONB), medical history.
- **`consultation`** — one per encounter; chief complaint, findings,
  plan, clinician_uid, occurred_at.

## The gate

`PhiService` is the **only** public surface. Every method:
1. Calls `_ensure_authorised(...)` (checks
   `Principal.can_read_phi()`, raises `PHIAccessDeniedError` otherwise).
2. Performs the read or write.
3. Writes an `audit.access_log` row with the principal, the
   `person_uid`, and a `reason`.

If you need a new PHI access path — add a method here. Do NOT export
`PhiRepository` or models for direct use.

## Hard rules

- **No imports from `packages.phi.repository` or `packages.phi.models`
  outside `packages/phi/`.** Period. Code review enforces this.
- **No PHI in logs.** Log `person_uid`, action codes, and
  `reason` strings. Never log the body of a clinical field.
- **No PHI in error messages or HTTP responses to non-authorised
  callers.** `PHIAccessDeniedError` carries `person_uid` and the action,
  nothing more.
- **No PHI in `ops` snapshots, ingest payloads, or tool outputs**
  unless the calling principal is PHI-authorised AND the path goes
  through `PhiService`.
- **Auditable denial:** when authorisation fails, the audit row STILL
  needs to land. (Today the row is written by the caller after the
  denial bubbles up; keep that property when refactoring.)
- **Backups of the `phi` schema are PHI.** Treat dump files as
  protected — encrypt at rest, restrict bucket access, enforce
  retention.

## Adding a new clinical field

1. Add to the model + migration.
2. Add to the `Out` schema only if the field is intended for
   authorised callers.
3. Decide whether it should be returned in `PhiPersonSnapshot` or
   only via a dedicated endpoint.
4. Update the audit `action` taxonomy if the access pattern is new.

## Reason strings

Every public `PhiService` method takes a `reason: str` keyword. The
current taxonomy:

- `phi.snapshot` — service default
- `api.phi.snapshot` — API call
- `agent.phi.snapshot` — AI agent call
- `phi.profile.upsert` — profile write

Extend this list when you add a new path; keep the prefix consistent
with the caller.
