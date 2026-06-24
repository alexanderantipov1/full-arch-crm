# ENG-257 — Surface CareStack partial payments (worker report)

- **Task id:** ENG-257
- **Title:** Surface CareStack partial payments — timeline + dashboard
- **Linear issue:** ENG-257
- **Linear URL:** https://linear.app/fusion-dental-implants/issue/ENG-257/task-g-implement-minimum-carestack-treatmentpayment-dashboard-slice
- **Role / agent:** worker / claude-code
- **Branch:** eng-257-eng-257
- **Worktree:** `/Users/eduardkarionov/.fusion-agent-orchestrator/c2db50910d08/carestack-billing-surface-v1/worktrees/ENG-257`
- **Allowed scope:** files listed in `ownership.yaml`, new alembic revision, frontend Zod schema + PM widget. No edits to shipped migrations, no `.env*` changes, no commits on `main`.

## What changed

### Migration (new revision only)

- `packages/db/alembic/versions/20260529_1500_e3f4a5b6c7d8_extend_event_kinds_for_carestack_payments.py`
  - `down_revision = "d2e3f4a5b6c7"` (prior head).
  - Widens `interaction.event` CHECK constraints:
    - `EVENT_KINDS += payment_recorded, payment_refunded, payment_reversed`
    - `SOURCE_KINDS += carestack_accounting_transaction`
    - `data_class="billing"` already allowed via `c1d2e3f4a5b6`.
  - Working `downgrade()` restores the previous tuples (mirrors `c1d2e3f4a5b6` exactly).

### Interaction package — kept in lockstep with the migration

- `packages/interaction/models.py` — `EVENT_KINDS` and `SOURCE_KINDS` tuples extended.
- `packages/interaction/schemas.py` — `EventKind` and `SourceKind` `Literal`s extended; `_SOURCE_KINDS_BY_PROVIDER["carestack"]` adds `carestack_accounting_transaction`.
- `packages/interaction/service.py` — `_KIND_VERB` gets `payment_recorded` / `_refunded` / `_reversed`; `get_treatment_payment_aggregate` returns the new `collected_total` and `payment_event_count` fields.
- `packages/interaction/repository.py` — `get_treatment_payment_aggregate` widens its `source_kind` / `kind` filters to include the new payment events; adds `SUM(amount) FILTER (kind = 'payment_recorded')` as `collected_total` and the matching event count. `payment_total_amount` / `first_payment_at` / `last_payment_at` keep their historical `invoice_created` semantics so the existing widget stays backward-compatible.
- `packages/interaction/CLAUDE.md` — kinds table + opening paragraph updated to include the three new kinds.

### Ingest emission (locked folio → kind map)

- `packages/ingest/carestack_accounting_transaction_service.py` — was capture-only; now also resolves `patientId → person_uid` via the existing `identity.source_link` lookup and emits one `interaction.event` per PAYMENT ledger row.
  - Mapping (locked product decision in `goal.md`):
    | folio / signal | emitted `kind` |
    |---|---|
    | `PATIENTCREDIT`, `COLLECTIONCREDIT`, `INSURANCECREDIT` | `payment_recorded` |
    | `REFUND` folio, or `transactionCode` in `{REFUND, PATIENTREFUND, INSURANCEREFUND}` | `payment_refunded` |
    | any row with `isReversed=true` (overrides folio) | `payment_reversed` |
    | every other folio (`PATIENTPAYABLE`, `INSURANCEPAYABLE`, `ADJUSTMENT*`, `PRACTICE`, `PROVIDER`, `TRANSACTIONCHARGE`, `SubscriptionCredit`, `PATIENTADJUSTOFF`) | _no event — raw-only_ |
  - Event constructed via `EventIn` with `data_class="billing"`, `source_kind="carestack_accounting_transaction"`, `source_external_id=<transaction id>`, `occurred_at=transactionDate`.
  - Summary built by `summary_for_event(...)` — action verb + provider + transaction id only.
  - Safe payload allowlist: `amount` (numeric) and `transaction_type` (lowercased debit/credit). `transactionCode`, procedure codes, provider names, patient identifiers, and clinical text never leave the raw row.
  - Skip-but-capture preserved for missing `patientId` or unlinked patient; raw_event still lands for replay.

### Ingest service / repository — outstanding balances read

- `packages/ingest/repository.py` adds `sum_latest_payment_summary_balances(tenant_id)`. SQL plan: subquery for `MAX(received_at)` per `external_id` over `carestack.payment_summary.snapshot` raw_events, joined back so we aggregate ONLY the latest snapshot per CareStack patient. Sums `balanceDuePatient` and `balanceDueInsurance` as numerics, plus a snapshot `patient_count`. Tenant-scoped via `for_tenant`.
- `packages/ingest/service.py` adds `latest_payment_summary_balances(tenant_id) -> LatestPaymentSummaryBalancesOut` (computes `outstanding_total = patient + insurance`).
- `packages/ingest/schemas.py` adds the `LatestPaymentSummaryBalancesOut` DTO.

### API — PM dashboard

- `apps/api/routers/dashboard.py` injects `IngestService` via `get_ingest_service`, calls `latest_payment_summary_balances` only when the provider filter is `None` or `carestack`, and surfaces the new fields on `DashboardTreatmentPaymentsOut`:
  - `collected_total: float` (sum of `payment_recorded` event amounts in range)
  - `payment_event_count: int`
  - `outstanding_total: float` (sum of latest payment-summary `balanceDuePatient + balanceDueInsurance` per patient)
  - `outstanding_patient_count: int`
  - `has_partial_payments: bool` (true iff `payment_event_count > 0` AND `outstanding_total > 0`)

### Frontend (apps/web)

- `apps/web/lib/api/schemas/dashboard.ts` — `DashboardTreatmentPaymentsSchema` widened to match the API DTO. Added `DashboardTreatmentPayments` type export.
- `apps/web/app/(staff)/project-manager/page.tsx` — Treatment & payments card adds Collected + Outstanding metrics and a `Partial payments outstanding` badge gated on `has_partial_payments`.
- `apps/web/lib/msw/handlers.ts` — PM mock fixture extended with the new fields so dev-mode Zod parsing keeps passing.
- Person operational timeline already renders any kind that comes back from the API; the new `payment_recorded` / `_refunded` / `_reversed` rows ride through `OperationalTimelineEntry` and pick up safe `summary_for_event` strings (e.g. `Payment recorded in CareStack (id=88001)`).

### Tests

- `tests/ingest/test_carestack_accounting_transaction_service.py` — rewritten to cover the new emission contract: happy path produces a `payment_recorded` `EventIn`; parametrised folio → kind mapping (PATIENTCREDIT/COLLECTIONCREDIT/INSURANCECREDIT/REFUND); `isReversed` override; refund `transactionCode` mapping; non-payment folios emit no event; safe payload contains only `amount` + `transaction_type`; PHI tokens never appear in summary or event payload; raw capture-then-route preserved; idempotency key, pagination, validation, and helper unit tests kept.
- `tests/ingest/test_latest_payment_summary_balances.py` — new unit tests covering the service-level coercion and `outstanding_total` math.
- `tests/interaction/test_service.py` — `test_treatment_payment_aggregate_converts_safe_repo_values` updated to seed and assert the new `collected_total` / `payment_event_count` fields; salesforce-only branch asserts they stay zero.
- `tests/interaction/test_models.py` — `EVENT_KINDS` canonical tuple now includes the three new kinds.
- `tests/api/test_dashboard_pm.py` — overrides `get_ingest_service`, seeds the aggregate `SimpleNamespace` with the new fields, and asserts the full new shape of `body["treatment_payments"]`.

## Verification

All green on this worktree:

- `ruff check .` → `All checks passed!`
- `mypy packages apps` → `Success: no issues found in 182 source files`
- `python -m pytest -q` → `891 passed in 14.50s`
- `cd packages/db && alembic check` → `No new upgrade operations detected.`
- Migration round-trip: `alembic upgrade head` (`d2e3f4a5b6c7 -> e3f4a5b6c7d8`) → `alembic downgrade -1` (`e3f4a5b6c7d8 -> d2e3f4a5b6c7`) → `alembic upgrade head` (`d2e3f4a5b6c7 -> e3f4a5b6c7d8`) — all clean.

Test commands assume env vars from the local `.env` (`SECRET_KEY`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`) are exported in the shell; the canonical Fusion CRM `.env` was used (no `.env*` files were modified). The integration test
`tests/integration/test_workflow_ready_redaction.py::test_seeded_event_kinds_keep_raw_payload_out_of_timeline_and_projections` only passes once the new migration is applied to the test DB (it seeds rows with the new payment kinds); the round-trip above is what makes that test pass.

## Risks

- **DB-level CHECK widening only.** The new kinds are valid the moment the migration runs; if any older worker is still pinned to the previous `EVENT_KINDS` tuple at deploy time, it will silently refuse to emit a `payment_*` event but will still capture the raw row — safe degradation, no data loss.
- **`balanceDuePatient` / `balanceDueInsurance` cast to `Numeric(14,2)`** in `sum_latest_payment_summary_balances`. CareStack returns these as floats; the cast preserves cents but truncates anything beyond two decimals. Matches the precision used for `Event.payload["amount"]` elsewhere.
- **`has_partial_payments` is a derived flag** computed in the router only when the provider filter is `None`/`carestack`. With a Salesforce-only filter, the flag is forced to `false`. Documented in the test.
- **Payment-summary aggregate is global per tenant**, not window-scoped. `outstanding_total` reflects "current balances right now", not "balances in the window" — that matches the locked product decision in `goal.md` (collected from ledger events in range; outstanding from the latest snapshot).

## Blockers / Do-not-merge conditions

- None. All Definition-of-Done items are green.
- Before integration: confirm the production DB has been upgraded through `e3f4a5b6c7d8` BEFORE the new emission code path is shipped — otherwise the first PAYMENT row will fail the old `ck_event_kind` and the worker will retry on every pull.
- The dashboard widget's MSW fixture is kept in sync with the Zod schema; a future contract drift between fixture and API will show up as a silent empty card per `feedback_prod_deploy_traps.md` trap #1 — keep them moving together.

## Suggested next task

- Wire the new outstanding-balance signal into the AR-risk count surface (`DashboardTreatmentPaymentsOut.ar_risk_count` is still `None`). That's a separate slice — the data is now available without extra ingestion work.
