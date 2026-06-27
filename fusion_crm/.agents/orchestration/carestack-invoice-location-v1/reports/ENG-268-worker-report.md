# ENG-268 Worker Report — Location-scope CareStack invoice events

- **Task id:** ENG-268
- **Linear issue:** ENG-268
- **Linear URL:** https://linear.app/fusion-dental-implants/issue/ENG-268/location-scope-carestack-invoice-events-invoices-payments-dollar-by
- **Linear title:** Location-scope CareStack invoice events
- **Role / agent:** worker / claude-code
- **Session id:** 90af432b7a38
- **Branch:** `eng-268-eng-268`
- **Worktree:** `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/carestack-invoice-location-v1/worktrees/ENG-268`
- **Allowed scope:** invoice ingest service only — mirror the ENG-267
  accounting-transaction location pattern. No new schema, no aggregate
  change, no dashboard change.

## What changed

Mirror-exactly of the accounting-transaction location pattern landed by
ENG-267, applied to the invoice emit. The dashboard aggregate already
filters `invoice_created` by `payload["location_id"]`; this slice fills
in the emit side so the **Invoices** and **Payments** widgets actually
recalculate per location.

### Touched files

- `packages/ingest/carestack_invoice_service.py` — modified.
  - Added `from packages.tenant.service import LocationService` (allowed
    by the `packages/CLAUDE.md` cross-package matrix: `ingest → tenant`
    via service is ✓).
  - Added `NotFoundError` to the `packages.core.exceptions` import.
  - `CareStackInvoiceIngestService.__init__` now instantiates
    `self._locations = LocationService(session)`.
  - `_capture_invoice` resolves the CareStack `locationId` to a
    tenant.location UUID via `_resolve_location_uid(...)` and writes
    `location_id` (str(uuid)) into the safe event payload when mapped.
  - New private method `_resolve_location_uid(tenant_id, cs_id)` —
    identical shape to the accounting-transaction service's helper:
    returns `None` when the row has no `locationId`, when the resolver
    raises `NotFoundError`, when any other exception is logged
    defensively (`except Exception`, English only), or when the
    resolver returns `None` (unmapped). The event still emits in every
    one of these cases — location is enrichment, not gating.
  - New module-level helper `_invoice_location_id(row)` — parses
    `locationId` / `LocationId` as int or numeric string; rejects
    `bool` (which is an int subclass in Python) so `True`/`False` never
    become a location id.
  - Also tightened the existing `invoice_type` write to reject `bool`
    via `not isinstance(invoice_type, bool)` so a stray `True` in the
    payload can never poison the safe field. Matches the
    `_invoice_location_id` defensive style.
- `tests/ingest/test_carestack_invoice_service.py` — new file (mirror of
  the location-focused subset of
  `tests/ingest/test_carestack_accounting_transaction_service.py`):
  - happy-path: raw captured, identity resolved, `invoice_created`
    event emitted with the right shape;
  - mapped CS `locationId` → safe payload gets
    `location_id = str(_LOCATION_UID)`;
  - unmapped (resolver returns `None`) → event still emits, payload
    omits `location_id`;
  - missing `locationId` field → resolver never called, payload omits
    `location_id`;
  - resolver raises `NotFoundError` → event still emits, payload omits
    `location_id`;
  - no-PHI assertion: summary + payload contain no PHI tokens;
    payload key set ⊆ `{amount, invoice_type, location_id}`;
  - helper unit test: `_invoice_location_id` parses int / numeric
    string, rejects `bool`, rejects unparseable strings, returns
    `None` when the field is absent.

## Mapped / unmapped behaviour

| Row state                                                | Raw captured | Event emitted | `payload["location_id"]` |
|----------------------------------------------------------|--------------|---------------|--------------------------|
| `locationId` present & maps to tenant.location           | ✓            | ✓             | `str(uuid)`              |
| `locationId` present, unmapped (resolver returns `None`) | ✓            | ✓             | absent                   |
| `locationId` missing / null / non-numeric                | ✓            | ✓             | absent                   |
| `LocationService.find_by_carestack_id` → `NotFoundError` | ✓            | ✓             | absent                   |
| `LocationService.find_by_carestack_id` → other exception | ✓            | ✓             | absent (logged)          |

Forensic capture is preserved unconditionally — the raw row always lands
in `ingest.raw_event` regardless of the location-resolution outcome.

## Tests run

```text
$ python -m pytest tests/ingest/test_carestack_invoice_service.py -q
....... [100%] 7 passed in 0.19s
```

Followed the TDD red→green cycle: the helper import on line 21 of the
new test module failed with `ImportError: cannot import name
'_invoice_location_id'` before the implementation landed; the full
7-test file passes after.

## Verification status — all four DoD checks GREEN

```text
$ make lint
ruff check .
All checks passed!

$ mypy .
Success: no issues found in 271 source files

$ source .env && make test
python -m pytest -q
... 922 passed in 13.98s

$ cd packages/db && alembic check
No new upgrade operations detected.
```

`make test` requires the parent project's `.env` to be loaded into the
shell (env vars `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`) because the
worktree does not carry its own `.env`. This is the existing local-dev
contract — no `.env*` was added, modified, or committed (per the
do-not-edit-`.env*` rule).

## Risks

- **Low.** This is a single-field, additive change on the emit side of a
  read-only CareStack ingest. The aggregate already consumes the field
  (ENG-267); existing events without `location_id` continue to be
  counted at the tenant level by the same code path.
- **Backfill is intentionally NOT covered.** Historical
  `invoice_created` events emitted before this slice carry no
  `location_id` and stay tenant-scoped. If the dashboard ever needs
  retroactive per-location counts for past invoices, a separate
  one-shot backfill job (re-emit / patch payload) is required.
- **`LocationService.find_by_carestack_id` does no audit write**, so
  this code path adds zero new `audit.access_log` rows per ingested
  invoice. Matches the ENG-267 baseline.

## Blockers / open questions

None.

## Suggested next task

Verify the PM **Invoices** + **Payments** widget actually reads the
`location_id` filter end-to-end against fresh data — the dashboard
aggregate change shipped with ENG-267, but until now no
`invoice_created` event carried the field. A short smoke pass on a
populated local DB (re-run the invoice import scheduler, scope the
widget to one location, confirm count > 0) closes the loop.

## Do-not-merge conditions

- ❌ Do not merge if any of `make lint` / `mypy .` / `make test` /
  `alembic check` regress.
- ❌ Do not merge with `.env*` modifications in the diff.
- ❌ Do not merge if any PHI / clinical token surfaces in the new safe
  event payload — the `test_emitted_event_summary_and_payload_carry_no_phi_tokens`
  test enforces the contract.
- ❌ Do not merge alongside any change that drops or renames
  `payload["location_id"]` filtering in the PM aggregate / Invoices /
  Payments dashboard widget — those consumers ship with ENG-267 and
  must remain wired before this slice is integrated.
