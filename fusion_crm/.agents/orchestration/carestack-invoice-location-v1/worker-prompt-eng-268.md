You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-268
(https://linear.app/fusion-dental-implants/issue/ENG-268). You run in an isolated
git worktree on your own branch. Implement → verify → write a report. Do NOT touch
`main`, do NOT push, do NOT open a PR. Commit to YOUR worktree branch only once
verification is green; the Orchestrator integrates.

## Mission (tiny — invoice service only)
Attach `location_id` to `invoice_created` events so dashboard **Invoices** + **Payments**
recalculate per location. The aggregate already filters `invoice_created` by
location (ENG-267) — only the emit side is missing. NO new schema.

## Read first
- `packages/ingest/carestack_invoice_service.py` — the invoice emit
  (`_capture_invoice` builds `safe_payload` with `amount` / `invoice_type`).
- The DONE pattern to MIRROR EXACTLY:
  `packages/ingest/carestack_accounting_transaction_service.py` (how ENG-267 resolves
  the CS `locationId` via `LocationService.find_by_carestack_id` and adds
  `location_id` to the safe payload, omitting it on missing/unmapped/NotFoundError).
- `packages/tenant/service.py` → `LocationService.find_by_carestack_id`.
- The invoice sync doc `docs/integrations/carestack/sync/invoices.md` confirms the
  invoice row carries `locationId` (integer FK).

## Task
1. In `CareStackInvoiceIngestService`, mirror the accounting-transaction service:
   construct/resolve location via `LocationService`, read the invoice row's
   `locationId`, resolve to our tenant.location UUID, and add
   `location_id` (str(uuid)) to the SAFE event payload of the `invoice_created`
   event. Missing `locationId` / unmapped / `NotFoundError` → omit `location_id`;
   the event still emits and the raw row is still captured.
2. Add `location_id` extraction helper (e.g. `_invoice_location_id(row)`) like the
   accounting service's `_transaction_location_id`.
3. NO change to the aggregate, dashboard, or schemas — they already filter
   `invoice_created` by `payload["location_id"]`.

## Hard constraints
- READ-ONLY CareStack. No new DB schema/migration. No PHI in events/logs/response
  (amount, invoice_type, location_id only — never patient identifiers/clinical).
- Cross-domain imports per `packages/CLAUDE.md` (ingest → tenant via service).
  `except Exception` only. English only.

## Definition of done
1. `make lint` ; `mypy .` ; `make test` ; `cd packages/db && alembic check` all green.
2. Commit to your worktree branch only (not main) once green.
3. Write `.agents/orchestration/carestack-invoice-location-v1/reports/ENG-268-worker-report.md`
   per the worker-report contract (changed files, mapped/unmapped behaviour, tests,
   verification status, risks, do-not-merge).
4. If blocked, write `Needs decision:` and stop.

## Tests
Add to `tests/ingest/test_carestack_invoice_service.py` (mirror the accounting
service's location tests): invoice event carries `location_id` when mapped; omits
when unmapped / missing `locationId`; no PHI tokens in the emitted summary/payload.
