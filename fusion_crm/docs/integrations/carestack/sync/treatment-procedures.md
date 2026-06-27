# Treatment Procedure Sync

**Fusion domain:** `phi`
**PHI:** yes — row ties a `patientId` to a dental procedure, tooth, surfaces, dates and financial estimates.
**Spec section:** Sync Resource 3 (CareStack Developer API v1.0.45)

## Endpoint

### `GET /v1.0/sync/treatment-procedures` — modified-after treatment-procedure feed

Real path: `GET /api/{version}/sync/treatment-procedures`.

- **Query params:**
  - `modifiedSince` (datetime, ISO 8601 UTC) — required on the initial call.
  - `continueToken` (string, optional).
  - `includeDeleted` (bool, optional) — when `true`, returns soft-deleted rows (`isDeleted=true`).
  - `pageSize` (number, optional) — default `100`, max `500`.
- **Response envelope:** `{ "results": [...], "continueToken": <string|null> }`.

## Fields returned (summary)

| field | type | notes |
|---|---|---|
| id | integer | procedure id |
| patientId | integer | PHI linkage |
| treatmentPlanId | integer | FK |
| treatmentPlanPhaseId | integer | FK |
| procedureCodeId | integer | FK to procedure code |
| appointmentId | integer | FK, may be null |
| quadrantId | integer | 1 Whole, 2 Max, 3 Mand, 4 UR, 5 UL, 6 LL, 7 LR |
| tooth | string | comma-separated tooth numbers |
| surfaces | object | bits for `b/l/m/o/f/d/i` |
| materialId | integer | nullable |
| providerId | integer | FK |
| locationId | integer | FK |
| proposedDate | datetime | |
| dateOfService | datetime | |
| patientEstimate | decimal | financial |
| insuranceEstimate | decimal | financial |
| statusId | integer | 1 Proposed, 2 Scheduled, 3 Accepted, 4 Rejected, 5 Alternative, 6 Hold, 7 Referred Out, 8 Completed |
| lastUpdatedOn | datetime | watermark source |
| isDeleted | bool | tombstone flag |

## Fusion mapping

- Target table(s): `phi.treatment_procedure` (new).
- `ingest.raw_event.event_type`: `carestack.treatment_procedure.upsert` (use `.delete` variant when `isDeleted=true`, or keep a single `upsert` event and honour the flag in the translator — decide once during implementation).
- Cadence: every 15 minutes.
- Idempotency key: `(id, lastUpdatedOn)`.
- Open questions:
  - TBD — the example uses `tooth: 1,7,8` unquoted; spec says `string`. Translator must tolerate both.
  - TBD — `surfaces` bit map in example uses keys `b/l/m/o/f/d/i`; spec text mentions `B,I,M,O,F,D,I` (letter `L` vs `I` inconsistency). Verify in PDF p.45.
  - Should we always run with `includeDeleted=true` so we can mirror tombstones? Recommended: yes.
