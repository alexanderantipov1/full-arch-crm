# Contract — ENG-312

## In scope (worker owns)
- `infra/scripts/backfill_person_dob_ssn.py` (new)
- `tests/infra/test_backfill_person_dob_ssn.py` (new)

## Out of scope (do NOT)
- No edits to `packages/identity/service.py` (resolver/veto = ENG-309, frozen).
- No new Alembic migration / schema change (dob/ssn columns already exist).
- No HTTP route wiring (background-only, mirrors ENG-305/307/311 gating).
- No touching `apps/web/lib/msw/handlers.ts` (other stream's WIP).
- No real CareStack API call (tests + script read local DB only).
- No `--apply` run by the worker; default `--dry-run`. Real apply = separate operator go.
- Reuse `_parse_carestack_dob` / `_normalize_ssn` from
  `packages/ingest/carestack_patient_service.py` — do not re-implement.

## Gate
- Worker launch requires operator approve of the printed launch_worker.py command.
