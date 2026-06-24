# Verification — full-fidelity-ingestion-v1

Backend verify loop (run from repo root unless noted):

- `make lint`
- `mypy .`
- `make test`
- `cd packages/db && alembic check` (migration drift)

Block-specific:

- A/ENG-426: unit tests for registry upsert + diff; migration applies cleanly.
- B/ENG-427: tests asserting captured field set == source readable set; a
  narrowing regression fails. Real-data smoke: pull one SF object, confirm raw
  payload now carries all queryable fields (incl. previously-missing ones).
  FLS-gap report produced.
- C/ENG-428: test that a simulated new field is detected and absorbed on next
  pull; drift event present in `sync_run.meta`.
- D/ENG-429: per-endpoint audit notes; observed-key snapshot lands in registry.
- E/ENG-430: backfill dry-run + idempotency (re-run produces no duplicate domain
  writes); spot-check `CreatedById` present in 2026-YTD raw rows.
- F/ENG-431: docs-only; no runtime change.

Real-data rule: Salesforce/CareStack-touching changes are verified against real
provider data (local stack against real pull) before merge — mocked tests alone
are insufficient (see feedback_verify_with_real_data_before_merge).
