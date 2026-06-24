# Worker Report — ENG-430 (Block E: SF 2026-YTD history backfill)

- **Task**: E — Salesforce 2026-YTD history backfill through the dynamic projection
- **Linear**: ENG-430
- **Role / agent**: orchestrator+worker / claude-code (self-execute)
- **Branch**: eng-425-full-fidelity-ingestion-v1
- **Status**: COMPLETE — script + mechanism verified live; the full 2026-YTD run
  is a deliberate operator action (not run here).

## What changed

- `infra/scripts/backfill_sf_full_fidelity.py` — operator-run backfill. Per
  object, builds the dynamic (registry-derived, wide) projection via
  `SfSchemaSync.projection`, pages from `--since` (default 2026-01-01) by
  `CreatedDate ASC`, and **force re-captures** each row via
  `IngestService.capture` directly.

## Key design point

The normal pull path skips unchanged rows (the ENG-381 capture change-guard),
so a naive re-pull would NOT widen history. The backfill deliberately bypasses
the guard by calling `capture` directly, appending a fresh WIDE raw_event per
row. Old narrow rows remain as immutable evidence; the new rows are the fuller
forensic copy. Dry-run is the DEFAULT; `--apply` writes.

## Verification

- `ruff` + `mypy` on the script → clean.
- Live tiny-window proof:
  - dry-run `--object Lead --max-rows 5` → `seen=5 captured=0`.
  - `--apply --object Lead --max-rows 2` → `captured=2`; the newest `lead.pull`
    raw_event now has **240 keys** incl. `CreatedById` and `utm_source__c`
    (vs the old 45-field capture). Force-recapture widens history. ✅

## Not run here (deliberate operator action)

The full 2026-YTD backfill across all 8 objects is large (hundreds of thousands
of rows × 8 objects, each appending a new raw_event) and was intentionally not
executed in this session. Run it deliberately and watch `ingest.raw_event`
growth:

    set -a && . ./.env && set +a
    PYTHONPATH=. .venv/bin/python infra/scripts/backfill_sf_full_fidelity.py --apply

## Risks

- Storage growth: each backfilled row appends a new wide raw_event. Monitor
  `ingest.raw_event` size before/after a full run.
- Boundary re-reads: cursor advances by `CreatedDate` (not unique); a full run
  may re-capture a few boundary rows. Harmless for forensic evidence.

## Do-not-merge conditions

- Cross-runtime review for the bundle before integration.
