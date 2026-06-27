You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-257
(https://linear.app/fusion-dental-implants/issue/ENG-257). You run in an
isolated git worktree on your own branch. Implement → verify → write a report.
Do NOT touch `main`, do NOT push, do NOT open a PR. Commit to YOUR worktree
branch only once verification is green; the Orchestrator integrates.

## Mission
Surface CareStack PARTIAL PAYMENTS on the person timeline and the PM dashboard.
Ingest already lands accounting-transactions + payment-summary in
`ingest.raw_event` (merged). This slice makes them VISIBLE. NO new `billing`
schema/domain — reuse the enum-extend + emit pattern.

## Read first
- Root `CLAUDE.md`, `packages/CLAUDE.md`, `packages/interaction/CLAUDE.md`,
  `packages/ingest/CLAUDE.md`, `apps/api/CLAUDE.md`, and the mission spec at
  `.agents/orchestration/carestack-billing-surface-v1/` (goal/acceptance/verification).
- Pattern to mirror for the migration: `packages/db/alembic/versions/20260527_1200_c1d2e3f4a5b6_extend_event_kinds_sources_dataclass.py`.
- Pattern to mirror for emission: how `packages/ingest/carestack_invoice_service.py`
  emits `invoice_created` via `InteractionService.create_event(...)`.
- Existing dashboard aggregate: `interaction.get_treatment_payment_aggregate`
  (used in `apps/api/routers/dashboard.py`, `DashboardTreatmentPaymentsOut`).
- Docs: `docs/integrations/carestack/sync/accounting-transactions.md` (folioType
  enum), `docs/integrations/carestack/resources/payment-summary.md` (balances).

## Locked product decisions
- Timeline = ONE event per PAYMENT ledger entry. Map folioType:
  `PATIENTCREDIT` / `COLLECTIONCREDIT` / `INSURANCECREDIT` → `payment_recorded`;
  `REFUND` (or refund transactionCode) → `payment_refunded`;
  any row with `isReversed=true` → `payment_reversed`.
  Charges (`PATIENTPAYABLE`/`INSURANCEPAYABLE`), adjustments, and other internal
  folios emit NO event (stay raw-only).
- Dashboard = `collected_total` from payment events; `outstanding_total` from
  the LATEST `carestack.payment_summary.snapshot` per patient
  (sum `balanceDuePatient` + `balanceDueInsurance`).

## Tasks

### 1. Migration (new revision — mirror c1d2e3f4a5b6 EXACTLY)
- `cd packages/db && alembic revision -m "extend event kinds for carestack payments"`
  OR hand-author with `down_revision` = current head (`alembic heads`).
- Widen the three `interaction.event` CHECK constraints: EVENT_KINDS +=
  `payment_recorded`, `payment_refunded`, `payment_reversed`; SOURCE_KINDS +=
  `carestack_accounting_transaction`. (`billing` data_class already allowed.)
- Provide a working `downgrade` that restores the prior constraint set.
- Update `packages/interaction/models.py` (EVENT_KINDS, SOURCE_KINDS tuples),
  `packages/interaction/schemas.py` (Literals), the `_KIND_VERB` map, and the
  kinds table in `packages/interaction/CLAUDE.md` to MATCH the migration exactly
  — a mismatch makes `alembic check` drift.

### 2. Timeline emission
- In `CareStackAccountingTransactionIngestService`, after capturing raw, for
  PAYMENT folios resolve `patientId`→person (existing `source_link` lookup) and
  emit `interaction.event` via `InteractionService.create_event(...)`:
  `kind` per the folio map above, `source_provider="carestack"`,
  `source_kind="carestack_accounting_transaction"`, `data_class="billing"`,
  `source_external_id`=transaction id, `occurred_at`=transactionDate, summary
  built from amount + transaction type ONLY. NO patient id / clinical data in
  summary or payload. Skip-but-capture if patient unlinked.

### 3. Dashboard aggregate
- Extend `interaction.get_treatment_payment_aggregate` (or add a sibling method)
  to compute `collected_total` from the new payment events in the filter range.
- Add an `ingest`-service read (e.g. `IngestService.latest_payment_summary_balances(tenant_id)`)
  that sums the LATEST `carestack.payment_summary.snapshot` balance per patient
  → `outstanding_total`. The dashboard router may call the ingest service
  (router→service is allowed). Keep tenant scoping.
- Add `collected_total` + `outstanding_total` to `DashboardTreatmentPaymentsOut`
  and populate them in the PM endpoint.

### 4. Frontend (apps/web)
- Add the new fields to the dashboard Zod schema + the treatment/payments widget
  (`/project-manager`): show Collected, Outstanding, and a partial-payment
  indicator. Follow existing widget patterns.
- Confirm payment events render on the person operational-timeline with a safe
  label (the timeline already renders operational events).

## Hard constraints
- CareStack READ-ONLY — no write path. No new DB schema/domain; the migration
  only WIDENS existing CHECK constraints. Migrations are immutable once shipped:
  new revision only, never edit an existing one.
- Capture-then-route preserved. No PHI in event summaries, logs, or dashboard
  responses (amounts + status only).
- Cross-domain imports per `packages/CLAUDE.md` (ingest consumes the CareStack
  client via a local Protocol; do not import `packages.integrations` from
  ingest). `except Exception` only. English only.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check`
   ALL green. Also verify `alembic upgrade head` → `downgrade -1` → `upgrade head`
   round-trips clean.
2. Commit to your worktree branch only (not main) once green.
3. Write `.agents/orchestration/carestack-billing-surface-v1/reports/ENG-257-surface-worker-report.md`
   per the worker-report contract in `.agents/orchestration/CLAUDE.md`
   (changed files, folio→kind mapping, tests, verification status, migration
   round-trip result, risks, do-not-merge conditions).
4. If you hit a structural wall (e.g. you believe a new table is required),
   STOP and write `Needs decision:` in the report rather than guessing.
