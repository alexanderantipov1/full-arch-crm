# Accounting Procedure Sync

**Fusion domain:** `billing`
**PHI:** mixed — financial rows that reference a `patientId` via the procedure.
**Spec section:** Sync Resource 6 (CareStack Developer API v1.0.45)

## Endpoint

### `GET /v1.0/sync/billing/procedures` — modified-after accounting-procedure feed

Real path: `GET /api/{version}/sync/billing/procedures`.

- **Query params:**
  - `modifiedSince` (datetime, ISO 8601 UTC) — required on the initial call.
  - `continueToken` (string, optional).
  - `pageSize` (number, optional) — default `100`, max `500`.
- **Response:** list of Accounting Procedure objects plus a `continueToken`. Token is `null` when the scan is complete.
- **Scope:** every billable procedure code. Adjustments applied to a code show up here as the corresponding patient-payable or insurance-payable amounts.

## Fields returned (summary)

| field | type | notes |
|---|---|---|
| treatmentProcedureId | integer | FK into Treatment Procedure feed — natural key here |
| insurancePayable | decimal | |
| patientPayable | decimal | |
| isDeleted | bool | tombstone flag |
| providerId | integer | FK |
| locationId | integer | FK |
| patientPaid | decimal | |
| lastUpdatedOn | datetime | watermark source |
| insurancePaid | decimal | |
| patientId | integer | PHI linkage |

No explicit `id`: the row is identified by its `treatmentProcedureId`. Each accounting procedure is the billing twin of one treatment procedure.

## Fusion mapping

- Target table(s): `billing.accounting_procedure` (new). Foreign-keyed to `phi.treatment_procedure.id` via `treatmentProcedureId`.
- `ingest.raw_event.event_type`: `carestack.accounting_procedure.upsert`.
- Cadence: every 15 minutes.
- Idempotency key: `(treatmentProcedureId, lastUpdatedOn)`.
- Open questions:
  - TBD — verify in PDF p.51 whether a single `treatmentProcedureId` can appear twice (e.g. after an adjustment reversal). If yes, we need to keep a history; if no, the natural key is unique.
  - Loading order: the translator should handle rows that arrive before the matching Treatment Procedure row (different cadences). Either queue unresolved rows or tolerate a pending FK — pick one during implementation.
  - `isDeleted=true` should mirror to a soft-deleted flag, not a hard delete.
