# Accounting Transaction Sync

**Fusion domain:** `billing`
**PHI:** mixed — financial ledger entries, most of which reference a `patientId`.
**Spec section:** Sync Resource 7 (CareStack Developer API v1.0.45)

## Endpoint

### `GET /v1.0/sync/accounting-transactions` — modified-after transaction-ledger feed

Real path: `GET /api/{version}/sync/accounting-transactions`. Next-page URL in the spec is prefixed with `billing/` (`/api/{version}/sync/billing/accounting-transactions?continueToken=...`) — treat both as the same endpoint.

- **Query params:**
  - `modifiedSince` (datetime, ISO 8601 UTC) — required on the initial call.
  - `continueToken` (string, optional).
  - `pageSize` (number, optional) — default `100`, max `500`.
- **Response:** list of AccountingTransaction objects plus a `continueToken`. Token is `null` when the scan is complete.
- **Scope:** every ledger entry since a procedure code was checked out for a patient, including adjustments, reversals, refunds, and advance payments against a provider. Use the Adjustments API to manage adjustments; use the Invoice API for invoice details.

## Fields returned (summary)

| field | type | notes |
|---|---|---|
| id | integer | transaction id |
| accountId | integer | account being synced |
| transactionDate | datetime | UTC ISO |
| providerId | integer, optional | provider the transaction is against |
| procedureCodeId | integer, optional | completed procedure code |
| transactionType | string | debit or credit indicator |
| amount | decimal | |
| folioType | string | folio the entry is on — see enum below |
| transactionCode | string | row-level category identifying the transaction kind |
| invoiceId | integer, optional | FK to Invoice |
| locationId | integer | FK |
| adjustmentCodeId | integer, optional | FK when the row is an adjustment |
| isReversed | bool | true when this row has been reversed |
| entryGroupId | string | pairs a debit with its credit counterpart |
| lastUpdatedOn | datetime | watermark source |
| patientId | integer, optional | PHI linkage when present |
| payorId | integer, optional | payor (insurance) linkage when present |

### `folioType` enum

`ADJUSTMENTCREDIT` — Adj-on adjustments.
`ADJUSTMENTDEBIT` — Adj-off adjustments.
`COLLECTIONCREDIT` — collection invoice/receipt.
`INSURANCECREDIT` — insurance invoice/receipt.
`INSURANCEPAYABLE` — treatment-code insurance payable.
`PATIENTADJUSTOFF` — patient adjust-off.
`PATIENTCREDIT` — patient invoice/receipt.
`PATIENTPAYABLE` — treatment-code patient payable.
`PRACTICE` — capitation invoice/receipt paid against practice.
`PROVIDER` — income reduction and provider adjustment.
`REFUND` — refund-related.
`SubscriptionCredit` — membership credits.
`TRANSACTIONCHARGE` — transaction charge associated with a transaction.

## Fusion mapping

- Target table(s): `billing.accounting_transaction` (new). Optional FKs: `invoiceId` → `billing.invoice`, `adjustmentCodeId` → `billing.adjustment_code` (if modelled), `patientId` → `identity.person`, `procedureCodeId` → procedure-code table.
- `ingest.raw_event.event_type`: `carestack.accounting_transaction.upsert`.
- Cadence: every 15 minutes.
- Idempotency key: `(id, lastUpdatedOn)`.
- Open questions:
  - TBD — spec section heading says "5.1)" but this is the 7th sync resource; appears to be a numbering typo in the PDF. Verify in PDF p.53.
  - TBD — the full `transactionCode` enum is cut off in the source dump. Treat `transactionCode` as an opaque string for now and build the enum from observed traffic. Verify in PDF p.53+.
  - `entryGroupId` pairs debit/credit — preserve verbatim so we can reconcile pairs locally; do not reuse CareStack's id as our PK.
  - Reversal semantics: `isReversed=true` means this entry was reversed, not that it is a reversal entry. The reversing entry is a separate row. Model both.
