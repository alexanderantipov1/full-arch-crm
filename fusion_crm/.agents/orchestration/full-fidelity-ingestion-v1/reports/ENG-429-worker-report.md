# Worker Report — ENG-429 (Block D: CareStack/REST audit + observed-key snapshot)

- **Task**: D — CareStack / REST full-fidelity audit + observed-key snapshot
- **Linear**: ENG-429
- **Role / agent**: orchestrator+worker / claude-code (self-execute)
- **Branch**: eng-425-full-fidelity-ingestion-v1
- **Status**: COMPLETE — live end-to-end verified.

## Audit (CareStack / REST)

`packages/integrations/carestack/client.py` `get(path, query)` / `list_*`
build query params with ONLY `continueToken` + `modifiedSince` (pagination /
sync watermark) — **no `fields=` / sparse / select restriction**. CareStack
returns full objects and we capture them verbatim into `raw_event.payload`.
Conclusion: CareStack capture is already full-fidelity at the wire; the gap was
registry visibility, not field loss. No client change needed.

## What changed

- `packages/ingest/repository.py` — `sample_recent_payloads(event_type, limit)`.
- `packages/ingest/service.py` — `snapshot_observed_schema(provider, object_name,
  event_type)`: union of top-level payload keys across a recent sample →
  `ObservedFieldIn` with JSON-inferred type → `sync_object_schema`. Empty sample
  is a no-op (must not deactivate the registry). `_json_value_type` helper.
- `apps/worker/jobs/ingest_scheduled.py` — `refresh_carestack_schemas_for_tenant`
  + `_for_all_tenants`, over `_CARESTACK_SCHEMA_OBJECTS` (patient, appointment,
  treatment_procedure, invoice, accounting_transaction, payment_summary).
  Reads our own raw events — no CareStack HTTP / credential. Drift →
  `sync_run.meta`.
- `apps/worker/main.py` — both jobs registered; daily cron at 04:33.
- Tests: `tests/ingest/test_observed_schema_snapshot.py` (3),
  `tests/worker/test_ingest_scheduled.py` (+1).

## PHI note

The registry stores field NAMES + JSON types only — never values. A field
named `ssn` / `dob` is schema metadata, not PHI. No PHI is written to the
registry, logs, or `sync_run.meta`.

## Tests / verification

- `pytest tests/ingest tests/worker` → **442 passed**.
- `ruff` + `mypy packages apps` → clean.
- **Live end-to-end** against real CareStack raw data: 6 objects snapshotted
  (patient 39 keys, appointment 12, treatment_procedure 21, invoice 15,
  accounting_transaction 17, payment_summary 8); re-run idempotent
  (`drifted=0`).

## Out of scope (noted)

- Nested-key flattening: the snapshot records top-level keys. Nested object
  shapes are captured verbatim in raw; flattening the registry to nested paths
  is a future enhancement if drift visibility needs it.

## Do-not-merge conditions

- Cross-runtime review for the bundle before integration (contract-changing
  mission).
