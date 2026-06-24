# Appointment Sync

**Fusion domain:** `scheduling`
**PHI:** yes — appointments link a `patientId` to a time slot and may include clinical notes.
**Spec section:** Sync Resource 2 (CareStack Developer API v1.0.45)

## Endpoint

### `GET /v1.0/sync/appointments` — modified-after appointment feed

Real path: `GET /api/{version}/sync/appointments`.

- **Query params:**
  - `modifiedSince` (datetime, ISO 8601 UTC) — required on the initial call of a scan.
  - `continueToken` (string, optional).
  - `pageSize` (number, optional) — default `100`, max `500`.
- **Response:** list of Appointment objects plus a `continueToken`.

## Fields returned (summary)

| field | type | notes |
|---|---|---|
| id | integer | appointment id |
| patientId | integer | FK to patient (PHI linkage) |
| startTime / startDateTime | datetime | in Location's timezone — TBD — spec text says `startTime`, example uses `startDateTime` |
| status | string | e.g. `Scheduled`, `Confirmed` — textual, not `statusId` |
| duration | integer | minutes |
| lastUpdatedOn | datetime | watermark source |
| locationId | integer | FK |
| providerIds | integer[] | FKs |
| operatoryId | integer | FK |
| notes | string | free text (PHI) |
| createdOn | datetime | UTC |

Compare with the on-demand `Appointment` resource which returns `statusId` (integer) and `dateTime`; the sync feed instead carries textual `status` plus `startDateTime`. Translators must not assume the two shapes are identical.

## Fusion mapping

- Target table(s): `scheduling.appointment` (plus provider join table).
- `ingest.raw_event.event_type`: `carestack.appointment.upsert`.
- Cadence: every 5 minutes.
- Idempotency key: `(id, lastUpdatedOn)`.
- Open questions:
  - TBD — reconcile `status` (string here) with `statusId` (int elsewhere). Resolve via the Appointment Status resource lookup table at translate time.
  - TBD — verify in PDF p.43 whether the sync feed emits cancellations as an `isDeleted` flag or just a `status` change; no deletion field is documented in this section.
  - Appointment create/modify APIs return a `version` token; the sync feed does not appear to include it. Our `scheduling.appointment` row can keep the last-known `version` from the on-demand API when available, left `null` when only sync fed the row.
