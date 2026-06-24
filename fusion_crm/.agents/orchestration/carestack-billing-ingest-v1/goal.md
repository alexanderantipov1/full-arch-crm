# Goal — CareStack billing ingest (partial payments & balances)

Capture the CareStack data that lets us see **partial payments, reversals,
refunds, and patient balances** — which we do NOT currently ingest.

Two read-only feeds, following the existing capture-then-route pattern, with
NO new schema:

1. **Accounting transactions** (`sync/accounting-transactions`) — the ledger;
   source of truth for partial payments. Capture verbatim to
   `ingest.raw_event` as `carestack.accounting_transaction.upsert`.
2. **Payment summary** (`billing/payment-summary/{patientId}`) — per-patient
   balances. Capture snapshots as `carestack.payment_summary.snapshot`.

Linear anchor: **ENG-257** (reopened; Linear free-issue limit blocked a new
issue). Canonical `billing` projection + dashboard aggregates are explicitly
OUT OF SCOPE here (structural — needs a `billing` schema/ADR + human approval).
