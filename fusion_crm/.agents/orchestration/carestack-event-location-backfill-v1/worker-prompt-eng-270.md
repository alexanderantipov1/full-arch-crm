You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-270
(https://linear.app/fusion-dental-implants/issue/ENG-270). Isolated git worktree
on your own branch. Implement → verify → write a report. Do NOT touch `main`, do
NOT push, do NOT open a PR. Commit to YOUR worktree branch only once green; the
Orchestrator integrates.

## Mission (data-migration backfill — no schema/model change)
ENG-269 dedup kept the earliest row per key; those predate the location feature,
so 0 existing invoice/payment/treatment events carry `payload.location_id` → every
dashboard location filter shows 0. Backfill location onto existing events from
their linked raw_event.

## Read first
- The migration pattern: `packages/db/alembic/versions/20260530_0600_f4a5b6c7d8e9_idempotent_interaction_event_dedupe.py`
  (current head; raw `op.execute(...)` SQL, working downgrade docstring).
- How location maps: `packages/tenant/repository.py` →
  `find_by_carestack_id` resolves `Location.external_ref->>'carestack_location_id'`.
- How events link to raw: `interaction.event.source_event_id` → `ingest.raw_event.id`.
  The raw payload is the verbatim CareStack row and carries `locationId`.

## Task — ONE new Alembic revision (down_revision = current head `f4a5b6c7d8e9`)
`upgrade()` runs a single server-side `op.execute(...)` UPDATE:

```
UPDATE interaction.event e
SET payload = jsonb_set(e.payload, '{location_id}', to_jsonb(l.id::text))
FROM ingest.raw_event r
JOIN tenant.location l
  ON l.tenant_id = e.tenant_id
 AND l.external_ref->>'carestack_location_id' = (r.payload->>'locationId')
WHERE e.source_event_id = r.id
  AND e.kind IN ('invoice_created','payment_recorded','payment_refunded',
                 'payment_reversed','treatment_proposed','treatment_completed')
  AND NOT (e.payload ? 'location_id')
  AND r.payload ? 'locationId'
  AND r.payload->>'locationId' IS NOT NULL;
```
Adjust schema/column names to match the actual models (verify `raw_event` table =
`ingest.raw_event`, column `payload` jsonb, `source_event_id` on the event,
`tenant.location` table + `external_ref` jsonb). Confirm the exact location
mapping column by reading `packages/tenant/models.py` / repository before writing.

- Only rows with a mappable location get updated; others stay as-is.
- The UPDATE is naturally idempotent (the `NOT (payload ? 'location_id')` guard) —
  re-running changes 0 rows.
- `downgrade()` = no-op (cannot tell backfilled from emitted-with-location); say so
  in the docstring. Do NOT strip location_id on downgrade.

## Hard constraints
- DATA-only migration — NO schema/model change, so `alembic check` must stay clean.
- Migrations immutable: NEW revision only.
- No PHI (location id only). `except Exception` only. English only.
- This is a migration-level append-only exception (recorded in decision-log).

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` green.
2. Round-trip: `alembic upgrade head` → `downgrade -1` → `upgrade head`.
3. After upgrade on local DB (currently 0 events with location_id), verify
   `count(*) FILTER (WHERE payload ? 'location_id')` > 0 for the billing kinds and
   that a re-run updates 0 more rows. Record the updated-row counts per kind in the
   report.
4. Commit to your worktree branch only once green.
5. Write `.agents/orchestration/carestack-event-location-backfill-v1/reports/ENG-270-worker-report.md`
   (SQL used, rows updated per kind, round-trip result, risks, do-not-merge).
6. If the location mapping is not what the prompt assumes, STOP and write
   `Needs decision:`.

## Tests
Add a test (DB-backed if the suite has an ingest/interaction integration fixture,
else a SQL-shape/dialect-compile assertion) proving: an event without location_id
whose raw_event has a mappable locationId gets `payload.location_id` after the
migration; an event whose raw has no/Unmappable locationId is left unchanged.
