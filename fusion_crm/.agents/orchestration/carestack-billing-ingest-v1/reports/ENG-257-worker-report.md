# ENG-257 Worker Report — CareStack billing ingest: accounting-transactions + payment-summary

- **Task id:** ENG-257
- **Title:** CareStack billing ingest — accounting-transactions + payment-summary
- **Linear issue:** [ENG-257](https://linear.app/fusion-dental-implants/issue/ENG-257/task-g-implement-minimum-carestack-treatmentpayment-dashboard-slice)
- **Role / agent:** worker / claude-code (Opus 4.7)
- **Branch / worktree:** `eng-257-eng-257` /
  `~/.fusion-agent-orchestrator/c2db50910d08/carestack-billing-ingest-v1/worktrees/ENG-257`
- **Allowed scope:** owns
  `packages/integrations/carestack/client.py`,
  `packages/ingest/carestack_accounting_transaction_service.py`,
  `packages/ingest/carestack_payment_summary_service.py`,
  `packages/ingest/schemas.py`, `apps/worker/jobs/ingest_scheduled.py`,
  `tests/ingest/`. Touched two supporting CLAUDE.md files (carestack
  integration + ingest doc tables) and two existing tests for new
  surface assertions.

## Touched files

- `packages/integrations/carestack/client.py` — added
  `list_accounting_transactions_modified_since(...)` and
  `get_payment_summary(patient_id)`. Both are GET-only.
- `packages/integrations/carestack/CLAUDE.md` — extended the
  "Endpoints used today" list with the two new endpoints + the existing
  patient/appointment/treatment-procedure/invoice/locations rows that
  were missing.
- `packages/ingest/schemas.py` — added
  `CareStackAccountingTransactionImportOut` and
  `CareStackPaymentSummaryImportOut` DTOs.
- `packages/ingest/carestack_accounting_transaction_service.py` *(new)* —
  `CareStackAccountingTransactionIngestService` mirroring the invoice
  service.
- `packages/ingest/carestack_payment_summary_service.py` *(new)* —
  `CareStackPaymentSummaryIngestService` for the bounded scheduled
  sweep.
- `packages/ingest/CLAUDE.md` — appended two rows to the sources table.
- `apps/worker/jobs/ingest_scheduled.py` — added accounting-transaction
  + payment-summary to `_CS_OBJECT_SCOPE` and the CareStack pull block,
  extended `_carestack_counters` to fold the new counters into the
  `sync_run` journal totals, extended the log + return envelope.
- `tests/ingest/test_carestack_accounting_transaction_service.py`
  *(new)* — 19 tests.
- `tests/ingest/test_carestack_payment_summary_service.py` *(new)* —
  8 tests.
- `tests/integrations/carestack/test_client.py` — 5 new tests covering
  initial `modifiedSince`, `continueToken` forwarding, non-object body
  rejection for accounting-transactions, and happy + non-object body
  cases for `get_payment_summary`.
- `tests/worker/test_ingest_scheduled.py` — extended the existing
  CareStack pull happy-path test to patch the two new services and
  assert their wiring + the expanded result envelope.

## What changed

### A. Accounting transactions (the partial-payment ledger)

`CareStackClient.list_accounting_transactions_modified_since` posts
against the canonical
`GET /api/v1.0/sync/accounting-transactions` path. Per the spec note,
CareStack's next-page URL is `billing/`-prefixed; that is the SAME
endpoint — we always send the canonical path with `continueToken` as a
query parameter and CareStack accepts it identically. GET only.

`CareStackAccountingTransactionIngestService` mirrors the invoice
service shape:

- captures the **verbatim row** to `ingest.raw_event` with
  `source="carestack"` and
  `event_type="carestack.accounting_transaction.upsert"` (capture-then-
  route; no payload reshape);
- encodes the spec's idempotency key `(id, lastUpdatedOn)` as the
  raw-event `external_id` (`f"{id}:{lastUpdatedOn}"`, fall back to
  bare `id` when `lastUpdatedOn` is missing) — re-pulls of an unchanged
  row produce the same `external_id`; a CareStack-side edit produces a
  new one;
- resolves the optional `patientId` → person via
  `IdentityRepository.find_source_link(..., source_instance="carestack-main",
  source_kind="patient", ...)`;
- rows without `patientId` (practice-level advance payments) or
  rows whose patient has not yet been linked are still captured to
  `raw_event` and counted as `skipped` — the row is replayable once
  patient ingest catches up;
- bounded by `days` / `page_size` / `max_pages` with the same
  ValidationError bands as the invoice service.

`CareStackAccountingTransactionImportOut` mirrors the invoice DTO with
`imported_count`, `skipped_count`, `page_count`, `next_continue_token`.

### B. Payment summary (balances) — trigger decision

`CareStackClient.get_payment_summary(patient_id)` calls
`GET /api/v1.0/billing/payment-summary/{patientId}`. GET only.

**Decision: (a) bounded scheduled sweep.** Reasons:

- Spec preference: the worker prompt explicitly says "Prefer (a)
  bounded sweep if simple".
- Operational simplicity: the sweep folds into the existing scheduled
  CareStack fanout — one cron tick produces both ledger captures and
  fresh balance snapshots in the same `sync_run` lifecycle.
- Bounded by design: `max_patients=50` cap in the scheduled call;
  service-level validation rejects values outside `[1, 500]`.
- Failure isolation: a single patient's API failure (4xx/5xx) is
  logged with PHI-safe metadata (CareStack patient id + exception
  class only) and the sweep continues. The error is counted as
  `error_count` and surfaces in the sync_run journal as `failed`.
- On-demand snapshots can land later as a thin wrapper around the
  same capture method if a dashboard needs them — the design does
  not preclude it.

`CareStackPaymentSummaryIngestService.import_payment_summary_snapshots`
walks `identity.source_link` rows scoped to
`source_system="carestack"` + `source_kind="patient"` (ordered by
`first_seen_at` desc — the dashboard ordering), calls CareStack once
per patient, and captures each verbatim PaymentSummary object to
`ingest.raw_event` as `carestack.payment_summary.snapshot` with the
CareStack patient id as `external_id`. Re-runs append additional
snapshots — intentional, because the timeline of snapshots is the
value (balances change over time).

### C. Wiring

`apps/worker/jobs/ingest_scheduled.pull_carestack_for_tenant` now
sequences (in order) locations → patients → appointments →
treatment-procedures → invoices → accounting-transactions →
payment-summary snapshots. `_CS_OBJECT_SCOPE` expanded accordingly so
the `sync_run` journal records the slice. `_carestack_counters` folds
the new counters into `records_total` / `records_succeeded` /
`records_failed`; payment-summary `error_count` surfaces as `failed`
so a partial outage flips the journal status to `partial`.

### Deliberate non-emission of `interaction.event`

The accounting-transaction kind is NOT in `interaction.event.kind`'s
allowed set, and the `source_kind` enum does not include
`carestack_accounting_transaction`. Adding either requires:

1. New enum literals in `packages/interaction/models.py` (EVENT_KINDS,
   SOURCE_KINDS).
2. New Pydantic Literals in `packages/interaction/schemas.py`.
3. A new Alembic migration to update the CHECK constraints.
4. A new verb entry in `_KIND_VERB` and the kinds table in
   `packages/interaction/CLAUDE.md`.

That work is structurally gated by the "NO new DB schema / migration
in this slice" hard constraint. The worker prompt acknowledges this
implicitly with the conditional "if you emit an `interaction.event`"
language. The contract is therefore: capture-to-`raw_event` only, no
timeline emission in this slice. The future canonical `billing`
projection (deferred per `ownership.yaml.deferred_structural`) is the
right place to surface partial payments and balance trends on the
person timeline.

The tests assert this explicitly with a positive "no
`InteractionService` reference exists on the service" check, and the
"PHI fixture set is allowed in the verbatim raw payload but does NOT
appear in any other field we set" check.

## Tests run + results

Local verify loop (env: `SECRET_KEY`, `DATABASE_URL`,
`DATABASE_URL_SYNC`, `REDIS_URL`, `INTERNAL_CREDENTIAL_TOKEN`,
`TENANT_DEFAULT_SLUG` set inline; Postgres + Redis from
`docker compose` running on 5434 / 6380):

| Step | Command | Result |
|---|---|---|
| Lint | `make lint` | `All checks passed!` |
| Type-check | `mypy .` | `Success: no issues found in 266 source files` |
| Tests | `make test` | `864 passed in 14.57s` |
| Migration drift | `cd packages/db && alembic check` | `No new upgrade operations detected.` |

Focused run on the new tests:
`pytest tests/ingest/test_carestack_accounting_transaction_service.py
tests/ingest/test_carestack_payment_summary_service.py
tests/integrations/carestack/test_client.py -q` →
41 passed in 0.42s.

Verification status: **green**.

## Coverage summary

| Path | Tests |
|---|---|
| Accounting-transaction service | 19 tests covering happy path, the spec's `(id, lastUpdatedOn)` external_id encoding, fallback when `lastUpdatedOn` is missing, no-patient-id skip, unlinked-patient skip, no-id skip, no-interaction-event positive assertion, no-PHI-in-our-fields assertion, days/page_size/max_pages validation, pagination + max_pages exhaustion + continueToken following, envelope key variants (`accountingTransactions`, `results`), and helper unit tests. |
| Payment-summary service | 8 tests covering the sweep iterating over linked patients with the correct source_link filter, blank/None source_id skip, failure isolation (one patient API failure does not poison the sweep), empty link list, max_patients validation, and no-PHI-in-our-event-metadata assertion. |
| Client | 5 tests covering initial `modifiedSince` send, `continueToken` forwarding, non-object body rejection on accounting-transactions, happy path on payment-summary, non-object body rejection on payment-summary. |
| Scheduled worker | Existing happy-path test extended to assert the two new services are constructed and called once each, and that the result envelope keys include `accounting_transactions` + `payment_summaries`. |

## Risks

- **No interaction.event emission means no person timeline view of
  partial payments in this slice.** Intentional and gated by the
  no-migration constraint; the canonical `billing` projection ticket
  will surface this. Not a regression — `invoice_created` timeline
  events still fire from the invoice service.
- **Payment-summary sweep is unbounded by tenant patient count above
  `max_patients=50`.** A clinic with thousands of linked CareStack
  patients gets stale snapshots for patients past the most-recently-
  linked 50 per tick. Mitigation today: every 30 minutes
  (`fusion-job-cs-pull` cadence) gives 96 ticks per 48 h. Follow-up:
  rotate through the patient set if the cadence is too low for the
  business question.
- **Re-running the sweep appends additional snapshots** to
  `raw_event`. Intentional — balances change over time. Storage cost
  per tick is bounded by `max_patients` × ~200 bytes of JSON.
- **Idempotency `external_id` includes a CareStack-provided
  `lastUpdatedOn` string verbatim.** If CareStack ever changes the
  string format mid-stream, the encoded key changes too. This is the
  conservative direction (we get an extra forensic capture, not a
  silent drop). The raw payload still carries the original field for
  reconstruction.

## Blockers / questions

None blocking. Two notes inherited from the spec's accounting-
transactions doc:

- `transactionCode` enum is documented as cut off in the source PDF —
  we treat it as an opaque string verbatim until observed traffic
  exhausts the values. Out of scope for this slice (no projection).
- The PDF heading is mis-labelled "5.1)" while the resource is the 7th
  sync feed — recorded in the doc; no code impact.

## Do-not-merge conditions

- Do not enable the CareStack pull on a tenant that has not run the
  patient pull first. The accounting-transaction service relies on
  `source_link` rows from the patient pull to attribute
  `patientId` → person; without them every row goes to `skipped`. The
  scheduled fanout already runs patients before
  accounting-transactions, so this is satisfied automatically there;
  it matters for ad-hoc operator pulls.
- Do not surface the verbatim `raw_event.payload` from these new
  event types to ops dashboards or AI agents — the same PHI-adjacency
  rules in `packages/ingest/CLAUDE.md` apply. The Phase 1 local-dev
  Inspector carve-out remains the only exception.

## Suggested next task

The next structural step is the canonical `billing` projection +
dashboard aggregates. The `ownership.yaml` already marks it as
deferred and requiring an ADR + human approval. When that lands it
should also gain a CHECK-constraint migration to add
`accounting_transaction_*` event kinds and the
`carestack_accounting_transaction` / `carestack_payment_summary`
source kinds to `interaction`, so the partial-payment timeline
becomes visible on a Person.
