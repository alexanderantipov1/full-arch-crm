You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-257
(https://linear.app/fusion-dental-implants/issue/ENG-257). You run in an
isolated git worktree on your own branch — implement, verify, then write a
report. Do NOT touch `main`, do NOT push, do NOT open a PR, do NOT commit
unless verification is green; the Orchestrator integrates.

## Read first
- Root `CLAUDE.md`, `packages/CLAUDE.md`, `packages/ingest/CLAUDE.md`,
  `apps/api/CLAUDE.md`, and the mission spec at
  `.agents/orchestration/carestack-billing-ingest-v1/` (goal/acceptance/verification).
- Docs: `docs/integrations/carestack/sync/accounting-transactions.md`,
  `docs/integrations/carestack/resources/payment-summary.md`.
- Template to mirror EXACTLY: `packages/ingest/carestack_invoice_service.py`
  and its test under `tests/ingest/`. Also `packages/integrations/carestack/client.py`
  (methods `list_invoices_modified_since`, `get_patient`).

## Task — READ-ONLY CareStack ingest (NO write-back, NO new schema)

### A. Accounting transactions (the partial-payment ledger)
1. Add `CareStackClient.list_accounting_transactions_modified_since(modified_since, *, page_size=100, continue_token=None)` →
   `GET /api/{version}/sync/accounting-transactions`. Accept the spec's
   `billing/`-prefixed next-page path as the same endpoint. GET only.
2. Add `packages/ingest/carestack_accounting_transaction_service.py` with
   `CareStackAccountingTransactionIngestService` mirroring the invoice service:
   - capture verbatim row to `ingest.raw_event` as
     `carestack.accounting_transaction.upsert` (capture-then-route: never
     reshape payload);
   - idempotency key `(id, lastUpdatedOn)`;
   - resolve `patientId` → person via
     `IdentityRepository.find_source_link(..., source_instance="carestack-main",
     source_kind="patient", ...)`; rows without `patientId` are captured but
     skipped for linkage;
   - if you emit an `interaction.event`, use `data_class="billing"` and a SAFE
     summary built from amount / `folioType` / `transactionType` / `invoiceId` /
     `isReversed` ONLY — NO clinical codes, NO patient identifiers.
3. Add the matching `*ImportOut` schema in `packages/ingest/schemas.py`.

### B. Payment summary (balances)
1. Add `CareStackClient.get_payment_summary(patient_id)` →
   `GET /api/{version}/billing/payment-summary/{patientId}`. GET only.
2. Capture snapshots to `ingest.raw_event` as
   `carestack.payment_summary.snapshot`. There is NO bulk feed — choose ONE
   trigger and document it in the report: (a) a bounded scheduled sweep over
   already-linked CareStack patients, or (b) an on-demand service method.
   Prefer (a) bounded sweep if simple; keep it page/limit-bounded.

### C. Wiring + tests
1. Wire accounting-transactions into the scheduled fanout in
   `apps/worker/jobs/ingest_scheduled.py` (add to `_CS_OBJECT_SCOPE` and the
   CareStack pull block), bounded like the invoice puller (max_pages small).
2. Add tests under `tests/ingest/` mirroring the invoice/treatment tests:
   row extraction from envelope, patient-link skip path, idempotency key,
   and an assertion that NO PHI / clinical / patient identifier appears in any
   emitted event summary.

## Hard constraints (non-negotiable)
- CareStack is READ-ONLY (5 guard-rails). Add GET calls only; no write path.
- NO new DB schema / migration in this slice. If you think you need a `billing`
  table, STOP and write `Needs decision:` in the report — that is a separate,
  structurally-gated ticket.
- Cross-domain imports per `packages/CLAUDE.md` (ingest may import
  identity/ops/interaction/audit/core only; consume the CareStack client via a
  local Protocol like the invoice service does — do NOT import
  `packages.integrations` from ingest).
- Never log PHI. `except Exception` only (never `except BaseException`).
- English only in the repo.

## Definition of done
1. Run the full verify loop and make it green:
   `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check`.
2. Commit to YOUR worktree branch only (not main) once green.
3. Write `.agents/orchestration/carestack-billing-ingest-v1/reports/ENG-257-worker-report.md`
   with: changed files, what changed, the payment-summary trigger decision,
   tests run + results, verification status, risks, and any blockers. Use the
   worker-report contract in `.agents/orchestration/CLAUDE.md`.
4. Update `runlog.md` markers as you progress; if blocked, write `Blocked:` or
   `Needs decision:` and stop rather than guessing.
