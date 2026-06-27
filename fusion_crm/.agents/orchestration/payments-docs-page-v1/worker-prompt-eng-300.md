You are a Claude Code WORKER on the Fusion CRM repo. Linear anchor: ENG-300
(https://linear.app/fusion-dental-implants/issue/ENG-300). Isolated git worktree.
Implement → verify → write a report. Do NOT touch `main`, do NOT push, do NOT open
a PR. Commit to YOUR worktree branch only once green; the Orchestrator integrates.

## Mission (frontend only)
Add a **Docs** button next to the `/project-manager/payments` title that opens a
documentation page explaining the CareStack payment data model, with an
**EN ⇄ Русский** toggle. Plus a doc-sync rule.

## Read first
- `apps/web/app/(staff)/project-manager/payments/page.tsx` (the page + its title/
  buttons) and `…/leads/page.tsx` for button/link patterns.
- `apps/web/components/ui/*` (Button, Card) and `apps/web/lib/utils`.
- `packages/ingest/carestack_accounting_transaction_service.py`
  (`_PAYMENT_CODE_TO_KIND`) and `apps/api/routers/dashboard.py`
  (`get_treatment_payment_aggregate` / Collected) — to add pointer comments and to
  keep the doc accurate to the code.

## Tasks
1. **Content module** `apps/web/lib/docs/paymentsDoc.ts` exporting structured `en`
   and `ru` documentation (same content, two languages). Write clear prose from the
   AUTHORITATIVE FACTS below. Keep EN and RU in lockstep.
2. **Docs page** `apps/web/app/(staff)/project-manager/payments/docs/page.tsx`:
   renders the doc; a language toggle (default English; "Русский" button → RU; back
   to "English"). A back link to `/project-manager/payments`. Use Card/Button; clean
   readable typography (headings, the code table, formulas). No external i18n/markdown
   lib needed — render the structured content directly (you may keep sections as
   arrays of {heading, body, optional table} in the module).
3. **Docs button** on `/project-manager/payments` next to the title → links to
   `…/payments/docs` (mirror the existing "Open leads" button style).
4. **Doc-sync rule**: add to BOTH `apps/web/CLAUDE.md` and `packages/ingest/CLAUDE.md`:
   "If you change CareStack payment classification (`_PAYMENT_CODE_TO_KIND`) or the
   Collected formula (`get_treatment_payment_aggregate`), you MUST update
   `apps/web/lib/docs/paymentsDoc.ts` — BOTH `en` and `ru`." Add a one-line pointer
   comment above `_PAYMENT_CODE_TO_KIND` and above the Collected aggregate:
   `# docs: apps/web/lib/docs/paymentsDoc.ts — keep EN+RU in sync`.
5. **Test**: a vitest that the docs page renders and the toggle switches language
   (assert an EN-only phrase, click Русский, assert a RU-only phrase).

## AUTHORITATIVE CONTENT (write accurate EN + RU prose from this; do not invent)
- **Source feed:** CareStack `GET /sync/accounting-transactions` is a double-entry
  ledger. ONE real $500 payment produces TWO rows: a CREDIT "money received" and a
  DEBIT "money applied to an invoice". Each row is captured verbatim into
  `ingest.raw_event` — that is the "document" you see via **View raw** on the page.
- **Key fields:** `transactionCode` (kind of movement), `folioType`,
  `transactionType` (debit/credit), `amount`, `isReversed`, `locationId`, `patientId`,
  `invoiceId`.
- **Classification (strict allow-list by transactionCode):**
  - PATIENTPAYMENTS, INSURANCEPAYMENTS → `payment_recorded` (real cash received) → counts in Collected.
  - PATPAYMENTAPPLIED, INSPAYMENTAPPLIED → `payment_applied` (allocation/offset leg, NOT new cash) → excluded from Collected.
  - PATIENTPAYMENTSDELETE / refund codes / `isReversed=true` on a payment → `payment_reversed`/`payment_refunded` → subtracted from Collected.
  - PROCEDURECOMPLETED (charges), PATIENTADJUSTMENT, FEEUPDATION, anything else → NO payment event (raw only).
  - `isReversed` flips ONLY a payment code to reversed; it never makes a charge/adjustment a payment event.
- **Derived metrics:**
  - **Collected** = Σ payment_recorded − Σ(payment_refunded + payment_reversed) = real cash, net of refunds/reversals. payment_applied NEVER counted.
  - **Payments (count)** = number of payment_recorded.
  - **Outstanding** = sum of each patient's latest payment-summary `balanceDuePatient` + insurance — point-in-time, tenant-wide (NOT location/window scoped).
  - **AR-risk** = patients whose latest balance > $500.
- **Ingestion:** capture-then-route (raw first, then classify); idempotent (re-pull
  adds no duplicate events); location attached at emit from `locationId`; real-time =
  hourly incremental cron (prod ~30 min, ~500 rows/pull cap) + an operator backfill
  for history. Filters: leads/consultations/payments/treatment honor date window +
  location; Outstanding/AR-risk are tenant-wide.
- **Why:** naive folio-based counting double-counts the two legs and reversed
  charges, inflating Collected ~3.3× (or even negative). Classifying strictly by
  transactionCode and counting only real cash received fixes this.

## Hard constraints
- NO PHI in the doc (codes/concepts/amounts-as-examples only; no patient data).
- Strict TS. Mirror existing page patterns. No backend logic change (only pointer
  comments). English in the repo except the `ru` content strings (those are Russian
  by design). 
## Definition of done
1. `cd apps/web && npm run lint && npx tsc --noEmit && npm run test` green.
2. Commit to your worktree branch only once green.
3. Write `.agents/orchestration/payments-docs-page-v1/reports/ENG-300-worker-report.md`.
