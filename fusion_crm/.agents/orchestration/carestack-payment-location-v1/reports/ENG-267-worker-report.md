# Worker Report — ENG-267

- Task: ENG-267 — Location-scope CareStack payment & treatment dashboard metrics
- Linear: https://linear.app/fusion-dental-implants/issue/ENG-267
- Role / agent: worker / claude-code
- Branch / worktree: `eng-267-eng-267` /
  `~/.fusion-agent-orchestrator/c2db50910d08/carestack-payment-location-v1/worktrees/ENG-267`
- Allowed scope: ingest (CS accounting-transaction + treatment-procedure),
  interaction (aggregate filter), apps/api dashboard wiring, apps/web
  Treatment & payments widget hint, tests.

## What changed

### Emit location on events (payload-only, no schema change)
- `packages/ingest/carestack_accounting_transaction_service.py`
  - Imports `LocationService` and `NotFoundError`.
  - Constructor now also owns `self._locations = LocationService(session)`.
  - After the patient is resolved, `_capture_transaction` extracts the
    CareStack `locationId` via the new `_transaction_location_id`
    helper (accepts int, numeric string, rejects `bool`), then resolves
    it through `LocationService.find_by_carestack_id(tenant_id,
    carestack_location_id)` in `_resolve_location_uid(...)`.
  - On a mapped row, the safe payload picks up
    `"location_id": str(uuid)` alongside the existing
    `amount` / `transaction_type`.
  - On a missing/unmapped/NotFoundError row, `location_id` is omitted —
    the event still emits. `except Exception` swallowed only at the
    resolver call site to log + continue.
- `packages/ingest/carestack_treatment_service.py`
  - Imports `LocationService` and `NotFoundError`.
  - Constructor owns `self._locations = LocationService(session)`.
  - `_capture_treatment` now builds a `safe_payload` dict (was
    hard-coded `{}`); the only field that may land is
    `"location_id": str(uuid)` when the CS `locationId` resolves.
  - Adds helper `_procedure_location_id` (same semantics as the
    accounting one).
  - Adds `_resolve_location_uid` (same shape; logs and returns None
    on resolver failures).
- Where location is resolved: at event emit, inside each ingest
  service, via `LocationService.find_by_carestack_id`
  (`packages/tenant/service.py`). Mission prompt said
  `TenantService.find_by_carestack_id`; the real method lives on the
  `LocationService` in the same `packages.tenant` domain — used that.

### Aggregate filters by location
- `packages/interaction/repository.py`
  - `InteractionRepository.get_treatment_payment_aggregate(...)` gains
    `location_id: UUID | None = None` and, when set, adds the predicate
    `Event.payload["location_id"].astext == str(location_id)` to the
    existing window/source-filtered query.
- `packages/interaction/service.py`
  - `InteractionService.get_treatment_payment_aggregate(...)` gains
    `location_id: UUID | None = None` and passes it through to the
    repository.

### Dashboard wiring + tenant-wide widget hint
- `apps/api/routers/dashboard.py`
  - The PM endpoint already had a `location_id: UUID | None` query
    param. It now passes that param into
    `interaction.get_treatment_payment_aggregate(...)`, so Collected,
    Presented, Completed, Payments, Invoices, `payment_event_count`
    recalculate when the operator changes location.
  - `outstanding_total`, `outstanding_patient_count`, and
    `ar_risk_count` continue to read from the tenant-wide
    `latest_payment_summary_balances` — payment_summary has no
    location (verified mission decision).
- `apps/web/app/(staff)/project-manager/page.tsx`
  - The existing `InfoHint` tooltip is reused. The "Outstanding"
    metric hint and the "patients at AR risk" badge tooltip now end
    with the clarification that those numbers are **tenant-wide,
    not scoped by the location filter (CareStack payment summary
    has no location).** No new component, no schema change.

## Unmapped-location behaviour

- `locationId` field absent → resolver never called; `location_id` omitted from
  payload; event still emits.
- `locationId` present but no `tenant.location` mapped → resolver returns
  `None`; `location_id` omitted; event still emits.
- Resolver raises `NotFoundError` (tenant unknown — defensive) → caught,
  `location_id` omitted; event still emits.
- Other resolver exception → caught with `except Exception`, logged via
  `log.warning(...)`, `location_id` omitted; event still emits.
- Result: a missing/unmapped location never fails a row — the timeline
  event always lands; only the dashboard's location-scoped filter
  view loses it.

## Files touched

- `packages/ingest/carestack_accounting_transaction_service.py`
- `packages/ingest/carestack_treatment_service.py`
- `packages/interaction/repository.py`
- `packages/interaction/service.py`
- `apps/api/routers/dashboard.py`
- `apps/web/app/(staff)/project-manager/page.tsx`
- `tests/ingest/test_carestack_accounting_transaction_service.py`
  (extended)
- `tests/ingest/test_carestack_treatment_service.py` (new)
- `tests/interaction/test_service.py` (extended)
- `tests/api/test_dashboard_pm.py` (extended)
- `tests/integration/test_tenant_isolation.py` (kwarg added so the
  Phase B isolation harness covers the new repo signature)

## Tests run

- `tests/ingest/test_carestack_accounting_transaction_service.py` —
  41 tests pass (existing + 4 new location tests + 1 helper test).
- `tests/ingest/test_carestack_treatment_service.py` — 8 tests pass
  (brand-new file: happy path + status mapping + mapped/unmapped/
  missing/NotFoundError location + no-PHI guard + helper tests).
- `tests/interaction/test_service.py` — 95 tests pass (existing
  aggregate tests updated to assert `location_id=None` is forwarded;
  one new test for explicit `location_id` pass-through).
- `tests/api/test_dashboard_pm.py` — 9 tests pass (existing call now
  asserts `location_id=None` is forwarded; new test confirms a
  `?location_id=<uuid>` query reaches `get_treatment_payment_aggregate`).
- Full suite: **915 passed in 15.73s.**

## Verification status

- `ruff check .` → All checks passed.
- `mypy packages apps` → Success: no issues found in 182 source files.
- `python -m pytest` (full suite) → 915 passed.
- `cd packages/db && alembic check` → No new upgrade operations detected
  (no schema drift — payload-only change, as designed).

All four DoD gates green.

## Risks

- **Payload-only filter is a JSONB read.** The SQL adds
  `(payload->>'location_id') = $1` to a query that already filters on
  `payload->>'amount'`. Postgres performs a sequential JSONB extraction
  per row in this slice (no GIN index on
  `interaction.event.payload`). Volumes are tiny in Phase 1 so this is
  fine; if we ever surface this widget on a tenant with 100k+ events
  inside the time window, an expression index on
  `(payload->>'location_id')` (or the migration the mission documented
  as "out of scope" — adding `event.location_id` column) becomes the
  fix. Not introducing today.
- **Backfill gap.** Existing CareStack payment / treatment events
  emitted before this slice carry no `location_id` in their payload
  and will be excluded from a location-filtered view (they still count
  in the tenant-wide view). New events from the next ingest pull will
  populate. No code change handles the historical rows — this is
  intentional: backfilling would mean reading raw_event payloads back
  out, which is a separate slice and would need an audit trail.
- **CS locationId mapping is operator-driven.** If an operator has not
  yet imported CareStack locations into `tenant.location`, every
  resolver call returns `None` and `location_id` is omitted. The widget
  then renders "no location-scoped data" for that filter. The "Import
  CareStack locations" path (`LocationService.import_locations_from_carestack`)
  must run at least once per tenant for this to populate — operations
  unchanged from before.

## Do-not-merge conditions

- None remaining. The branch is verified green, no PHI leakage, no
  schema change, no destructive ops touched. Orchestrator may
  integrate after the standard review.

## Suggested next task

- (Out of scope here, but a sibling slice may want it.) Add a Phase B
  integration repo-level test that boots Postgres, inserts events with
  and without `payload->>'location_id'`, and asserts the aggregate
  filter behaviour at SQL level. Today the service-level mocks cover
  pass-through and the existing repo-level SQL covers the
  `payload->>'amount'` analogue, so the same predicate idiom is being
  reused.

## Blockers

- None. No `Needs decision:` required; the mission prompt's escalation
  path (adding `interaction.event.location_id` column) was never
  triggered — the payload predicate works exactly like the existing
  `payload->>'amount'` filter the repo already runs.
