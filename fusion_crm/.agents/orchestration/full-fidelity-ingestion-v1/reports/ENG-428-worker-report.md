# Worker Report — ENG-428 (Block C: schema-refresh + drift job)

- **Task**: C — Schema-refresh + drift detection cron job
- **Linear**: ENG-428
- **Role / agent**: orchestrator+worker / claude-code (self-execute)
- **Branch**: eng-425-full-fidelity-ingestion-v1
- **Status**: COMPLETE — live end-to-end verified.

## What changed

- `apps/worker/jobs/ingest_scheduled.py` — `refresh_salesforce_schemas_for_tenant`
  (per-tenant: describe + Tooling → registry for every `SF_FULL_FIDELITY_OBJECTS`,
  records `schema_drift` (real field changes) + `fls_gaps` (persistent) into
  `sync_run.meta`; absorbs new fields into the next pull automatically) and
  `refresh_salesforce_schemas_for_all_tenants` (fanout over `_list_tenant_ids`).
- `packages/ingest/sf_schema_sync.py` — `SF_FULL_FIDELITY_OBJECTS` constant;
  `static_projection` now defaults to `""` (sync-only callers don't need it).
- `apps/worker/main.py` — both jobs registered in `WorkerSettings.functions`;
  daily arq cron at 04:23 for the fanout.
- `tests/worker/test_ingest_scheduled.py` — 2 tests (drift→meta, no-credential).

## Design notes

- Low cadence (daily): one describe + one Tooling query per object. Cheap.
- `schema_drift` (added/removed/type-changed/readability) is the per-run change
  signal; `fls_gaps` is recorded every run because it is persistent operator
  state, not a change — keeping them separate avoids "everything drifts daily".
- New fields need no code change to be captured: the dynamic projection is
  derived from the registry the next pull reads.

## Tests / verification

- `pytest tests/worker/test_ingest_scheduled.py` → **25 passed**.
- `ruff` + `mypy packages apps` → clean (243 files).
- **Live end-to-end** against the connected org (local stack):
  - 1st run: drift recorded, `failed=0`.
  - 2nd run: `drifted=0` (idempotent), `fls_gap_objects=8`, `failed=0` — proves
    no false drift on a steady-state re-run and that FLS gaps persist in meta.

## Risks

- Low. Additive job + cron; reuses the proven SfSchemaSync.sync path.

## Do-not-merge conditions

- Cross-runtime review for the bundle before integration (contract-changing
  mission), same as A/B.
