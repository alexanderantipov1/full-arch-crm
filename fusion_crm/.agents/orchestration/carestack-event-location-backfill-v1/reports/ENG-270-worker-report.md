# Worker Report — ENG-270

- **Task id:** ENG-270
- **Title:** Backfill location_id onto existing CareStack events
- **Linear:** [ENG-270](https://linear.app/fusion-dental-implants/issue/ENG-270/backfill-location-id-onto-existing-carestack-events-regression-from)
- **Role / agent:** worker / claude-code
- **Branch:** `eng-270-eng-270`
- **Worktree:** `~/.fusion-agent-orchestrator/c2db50910d08/carestack-event-location-backfill-v1/worktrees/ENG-270`
- **Scope (per goal/contract):** One new Alembic data-only migration + a
  DB-backed integration test. No schema, model, service, router, or
  worker code touched.

## Summary

ENG-269 dedup kept the earliest row per dedup key for
`interaction.event`. Those earliest rows predate the ENG-267/268
location emit feature, so 0 existing
invoice / payment / treatment events on the dashboard carry
`payload.location_id`. The runtime emission is now idempotent
(ENG-269), so a re-pull cannot regain the location — only a one-time
data-only migration can.

This worker added a single new Alembic revision that runs a
server-side `UPDATE` against `interaction.event`, joining the linked
`ingest.raw_event` (verbatim CareStack row carrying `locationId`) and
resolving it through `tenant.location.external_ref->>'carestack_location_id'`
to the tenant-local `tenant.location.id`. The resolved UUID is written
as a string to `payload.location_id`, matching the runtime emit shape
in `carestack_invoice_service` / `carestack_accounting_transaction_service`
/ `carestack_treatment_service`.

## Changed files

- `packages/db/alembic/versions/20260530_0700_a5b6c7d8e9f0_backfill_event_location_id_from_raw.py`
  — new revision `a5b6c7d8e9f0`, `down_revision = f4a5b6c7d8e9`. Module
  exposes `BACKFILL_SQL` so the integration test can replay the same
  statement without running a full `alembic upgrade`. `downgrade()` is
  a documented no-op (backfilled values are indistinguishable from
  runtime-emitted ones, so stripping them would corrupt newly emitted
  rows; replay path via `ingest.raw_event` is documented).
- `tests/integration/test_event_location_backfill.py` — four DB-backed
  cases (mappable / unmappable / ineligible-kind-or-already-set /
  tenant-scoped). Imports the migration's `BACKFILL_SQL` via
  `importlib.util` because version filenames start with a digit
  (`20260530_0700_…`) and are not valid Python module paths.

## SQL used (from the new revision, verbatim)

```sql
UPDATE interaction.event AS e
SET payload = jsonb_set(e.payload, '{location_id}', to_jsonb(l.id::text))
FROM ingest.raw_event AS r
JOIN tenant.location AS l
  ON l.tenant_id = r.tenant_id
 AND l.external_ref->>'carestack_location_id' = r.payload->>'locationId'
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.kind IN (
        'invoice_created',
        'payment_recorded',
        'payment_refunded',
        'payment_reversed',
        'treatment_proposed',
        'treatment_completed'
      )
  AND NOT (e.payload ? 'location_id')
  AND r.payload ? 'locationId'
  AND r.payload->>'locationId' IS NOT NULL;
```

Notes vs the prompt SQL:

- Added `r.tenant_id = e.tenant_id` (defence-in-depth: source_event_id
  FKs to a UUID-keyed table so cross-tenant collision is theoretically
  impossible, but the predicate also lets PostgreSQL use the per-tenant
  indexes on both sides).
- Switched the location join to `l.tenant_id = r.tenant_id` so the
  three-way `(e, r, l)` are all bound to the same tenant in one
  consistent shape.

## Tests run

- `make lint` — clean (ruff).
- `mypy packages apps` — clean (184 files).
- `python -m pytest -q` — 934 passed in 15.15s (full suite; includes the
  four new ENG-270 cases).
- `cd packages/db && alembic check` — `No new upgrade operations
  detected.` (clean — data-only migration, no model drift).

## Migration round-trip on local DB

- Start: `alembic current` reported `f4a5b6c7d8e9` (the prior head from
  ENG-269).
- `alembic upgrade head` — ran `a5b6c7d8e9f0`.
- `alembic downgrade -1` — ran the no-op downgrade back to
  `f4a5b6c7d8e9` (no rows touched, as documented).
- `alembic upgrade head` again — ran `a5b6c7d8e9f0` a second time;
  zero additional rows touched (idempotent guard).

## Local DB counts

Before any of this branch's migrations (local DB at `f4a5b6c7d8e9`):

| kind                | total | with_location |
|---------------------|-------|---------------|
| invoice_created     | 176   | 0             |
| payment_recorded    | 62    | 0             |
| payment_refunded    | 0     | 0             |
| payment_reversed    | 242   | 0             |
| treatment_completed | 200   | 0             |
| treatment_proposed  | 300   | 0             |
| **total**           | 980   | 0             |

After `alembic upgrade head` (this branch's `a5b6c7d8e9f0`):

| kind                | total | with_location | updated |
|---------------------|-------|---------------|---------|
| invoice_created     | 176   | 176           | 176     |
| payment_recorded    | 62    | 62            | 62      |
| payment_refunded    | 0     | 0             | 0       |
| payment_reversed    | 242   | 242           | 242     |
| treatment_completed | 200   | 200           | 200     |
| treatment_proposed  | 300   | 300           | 300     |
| **total**           | 980   | 980           | **980** |

Every billing/treatment event in the local DB carried a mappable
CareStack `locationId` (operator has imported the matching locations
via the W2 CareStack location sync). On a tenant whose operator has
not imported a given CareStack location, the corresponding events
would intentionally be left without `payload.location_id` until the
location import runs — same contract as the runtime emit path.

Idempotency confirmed two ways:

1. The second `alembic upgrade head` after the downgrade round-trip
   logged the migration but the post-state counts above did not
   change.
2. A manual replay of the UPDATE SQL via `psql` (CTE wrapping the
   UPDATE with `RETURNING`) returned `rerun_affected = 0`.

## New integration test cases

`tests/integration/test_event_location_backfill.py` covers:

1. `test_backfill_sets_location_id_for_mappable_events` — one event
   per backfill-eligible kind (six total). Each is linked to a
   `raw_event` carrying the mappable CareStack `locationId`. Asserts
   every seeded event gains `payload.location_id == str(location.id)`
   and that a second `BACKFILL_SQL` execution leaves the rows at the
   same final state.
2. `test_backfill_leaves_unmappable_events_unchanged` — three failure
   modes (no `locationId` key, unmappable `locationId`, `locationId:
   null`). Asserts none of the seeded events gain `payload.location_id`.
3. `test_backfill_skips_ineligible_kind_and_already_set` — a
   `lead_created` (out-of-scope kind) and an `invoice_created` that
   already carries a `location_id` (idempotent guard). Asserts the
   lead row is untouched and the pre-existing `location_id` value is
   preserved exactly (NOT clobbered by the resolved one).
4. `test_backfill_is_tenant_scoped` — two tenants seed locations with
   the same CareStack id. Asserts each tenant's event resolves to its
   own location uuid; no cross-tenant leak.

The test does not run `alembic upgrade` directly — it imports
`BACKFILL_SQL` from the migration module via `importlib.util` and
executes it against the fixture session. Assertions are per-seeded-row
(not against `CursorResult.rowcount`) so the test stays correct even
when the dev DB already contains pre-existing eligible rows that the
migration will legitimately touch.

## Verification status

- Acceptance items (`.agents/orchestration/carestack-event-location-backfill-v1/acceptance.md`):
    - [x] New Alembic revision (down_revision = `f4a5b6c7d8e9`),
          server-side UPDATE for the six billing/treatment kinds.
    - [x] Only rows with a mappable location are touched; re-run is a
          no-op (verified by counts + manual replay); `downgrade()`
          is a documented no-op.
    - [x] No new schema; `alembic check` clean. No PHI introduced
          (location uuid only).
    - [x] Full verify green (`make lint`, `mypy`, `pytest -q`,
          `alembic check`); upgrade -> downgrade -> upgrade round-trip
          executed.
    - [x] After local upgrade: invoice / payment / treatment events
          with a mappable CS `locationId` now carry
          `payload.location_id` (see counts above; `with_location` went
          from 0 to total).
    - [x] Report at `reports/ENG-270-worker-report.md`.

## Risks

- **Operator-driven location coverage.** Events whose raw_event
  references a CareStack location id that the operator has NOT yet
  imported into `tenant.location` stay without `location_id`. This is
  intentional (matches the runtime contract) — once the location is
  imported, a future re-pull will not retroactively set the value
  because the runtime emission is idempotent. The migration would
  need to be re-run manually in that case. Document in the deploy
  runbook: import locations first, then run the backfill.
- **Single-tenant local DB.** The tenant-scope test runs in a
  two-tenant transaction inside the test session and asserts the
  isolation works, but the production verification only covers a
  single-tenant dataset (all 980 rows resolved to the same
  `tenant.location`). The SQL's `l.tenant_id = r.tenant_id` plus
  `r.tenant_id = e.tenant_id` predicates are unit-covered by the
  integration test.
- **Downgrade lossiness.** The `downgrade()` no-op is the right call
  (preserving backfilled values), but operators who roll back this
  revision and then *forget* to re-upgrade will have `location_id`
  on rows whose `down_revision` did not produce them. The migration
  docstring records the rationale and the replay path through
  `ingest.raw_event`.

## Blockers / open questions

None. Mission moved from `assigned` -> `report-ready`.

## Suggested next task

Orchestrator integration: rebase `eng-270-eng-270` into `main`, run
the prod-side `alembic` Job at deploy time, then re-check the
dashboard location filters for invoice / payment / treatment cards.
The same SQL applied to the prod DB will set `payload.location_id`
on every backfill-eligible event whose raw_event carries a mappable
CareStack `locationId`.

## Do-not-merge conditions

- If prod CI's `alembic check` reports drift (it should not — this is
  a data-only migration), STOP — the registry / model layer has
  drifted independently and needs reconciliation before this
  revision lands.
- If the prod-side count of `interaction.event WHERE payload ?
  'location_id' AND kind IN (...)` stays at 0 after the migration
  runs, STOP — that would imply either (a) no
  `tenant.location.external_ref->>'carestack_location_id'` rows have
  been imported in prod (operator import missing) or (b) raw_events
  do not carry `locationId` in prod, both of which are upstream
  issues to investigate before re-running.
- Do NOT change the `downgrade()` body to strip `location_id` —
  see module docstring; that would corrupt rows the runtime
  correctly enriched.
