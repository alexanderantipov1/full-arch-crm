# Existing Treatment Procedure Sync

**Fusion domain:** `phi`
**PHI:** yes — historical procedures performed on a patient (in this or another practice).
**Spec section:** Sync Resource 4 (CareStack Developer API v1.0.45)

## Endpoint

### `GET /v1.0/sync/existing-treatment-procedures` — modified-after feed for "existing" (historical) procedures

Real path: `GET /api/{version}/sync/existing-treatment-procedures`.

- **Query params:**
  - `modifiedSince` (datetime, ISO 8601 UTC) — required on the initial call.
  - `continueToken` (string, optional).
  - `includeDeleted` (bool, optional) — when `true`, returns soft-deleted rows.
  - `pageSize` (number, optional) — default `100`, max `500`.
- **Response envelope:** `{ "results": [...], "continueToken": <string|null> }`.

## Fields returned (summary)

| field | type | notes |
|---|---|---|
| id | integer | existing-procedure id |
| patientId | integer | PHI linkage |
| procedureCodeId | integer | FK |
| tooth | string | comma-separated tooth numbers |
| surfaces | object | bits for `b/l/m/o/f/d/i` |
| materialId | integer | nullable |
| providerId | integer | nullable FK |
| receivedAt | integer | 0 None, 1 This Practice, 2 Other Practice, 3 Referred |
| dateOfService | datetime | nullable |
| quadrantId | integer | 1 Whole, 2 Max, 3 Mand, 4 UR, 5 UL, 6 LL, 7 LR — nullable |
| locationId | integer | FK |
| notes | string | nullable, may be clinical (PHI) |
| isDeleted | bool | tombstone flag |
| lastUpdatedOn | datetime | watermark source |

Unlike the (in-flight) Treatment Procedure feed, this resource has no `treatmentPlanId`, `appointmentId`, `patientEstimate`, `insuranceEstimate`, `proposedDate`, or `statusId` — these rows describe work already done, often outside this practice.

## Fusion mapping

- Target table(s): `phi.treatment_procedure` (new) with a discriminator column (e.g. `kind='existing'`) so in-flight and existing procedures can share a table — or a sibling table `phi.existing_treatment_procedure`. Decide during implementation.
- `ingest.raw_event.event_type`: `carestack.existing_treatment_procedure.upsert`.
- Cadence: every 15 minutes.
- Idempotency key: `(id, lastUpdatedOn)`.
- Open questions:
  - TBD — single table with discriminator vs two tables. Existing rows share most fields with planned rows but not finance fields; a single table keeps queries simpler.
  - TBD — verify in PDF p.47 whether `receivedAt=0 None` is actually emitted or only used as a default.
  - Recommend always running with `includeDeleted=true` to mirror tombstones.
