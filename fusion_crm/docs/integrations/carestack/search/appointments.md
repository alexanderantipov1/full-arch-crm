# Appointment Search

**Fusion domain:** `scheduling`
**PHI:** yes — results tie a `patientId` to date/time and may include appointment notes.
**Spec section:** Search Resource 2 (CareStack Developer API v1.0.45)

## Endpoint

### `POST /v1.0/appointments/search` — filtered one-shot appointment lookup

Note: the spec path is `POST /scheduler/api/v1.0/appointments/search` (Appointment Search lives under the `scheduler` service prefix). Kept as `/v1.0/appointments/search` in this header so the grep pattern is uniform.

- **Query params:** none (all filters travel in the body).
- **Body:**
  - `filterQuery` (object, required) — JSON filter. Empty object returns all.
  - `orderBy` (string, optional) — e.g. `"dateTimeUTC desc"`.
  - `pageIndex` (integer, required) — `> 0`.
  - `pageSize` (integer, required) — `> 0`, max `100`.
- **Response envelope (per spec):** `{ Result: [Appointment...], TotalCount: <int> }`.
- **Response envelope (verified live, 2026-05-09):** `{ result: [...], totalRecords: <int> }` — camelCase. The PDF spec is wrong; live API returns lowercase keys. Code should accept both (try `.result` then `.Result`).
- **`dateTime` field:** returned as a naive ISO string with NO timezone suffix (e.g. `"2026-05-11T12:10:00"`). CareStack stores it in UTC; append `Z` before parsing or `Date.parse()` will treat it as local time.

### Supported filter / order fields

- `filterQuery`: `PatientId` (array of ids), `StatusId` (array), `CanReschedule` (bool), `DateTimeUTC` (`{ startDate, endDate }` window — both optional).
- `orderBy`: `DateTimeUTC` only.
- Exclusion semantics are caller-side: build the filter to match what you want included.

### Common filter shapes

- By patient: `{ "PatientId": [...], "statusId": [...] }`
- Upcoming window: `{ "dateTimeUTC": { "startDate": ..., "endDate": ... }, "statusId": [...] }`
- Past only: `{ "dateTimeUTC": { "endDate": "<today>" }, "statusId": [...] }`
- Cancelled: `{ "canReschedule": false, "statusId": [...] }`
- All: `{}`

## Fields returned (summary)

Each `Result` item mirrors the Appointment resource.

| field | type | notes |
|---|---|---|
| id | integer | appointment id |
| bookingMode | integer | 1 Direct, 2 Online |
| dateTime | datetime | appointment time (UTC — TBD — verify in PDF p.38) |
| statusId | integer | FK to Appointment Status |
| duration | integer | minutes |
| locationId | integer | FK |
| appointmentMode | integer | 0 None, 1 In-Office, 2 Tele |
| operatoryId | integer | FK |
| patientId | integer | FK (PHI linkage) |
| notes | string | free text — may be clinical (PHI) |
| productionTypeId | integer | FK |
| providerIds | integer[] | FKs |
| options | integer | option bitmask |
| version | string | opaque concurrency token |

## Fusion mapping

- Target table(s): `scheduling.appointment`; join tables for `providerIds`.
- `ingest.raw_event.event_type`: not emitted automatically — search is on-demand. The sync feed (see `sync/appointments.md`) is the watermarked source.
- Cadence: on-demand only.
- Idempotency key: `(appointmentId, version)` — the opaque version token doubles as a change marker. Fall back to `(appointmentId, dateTime)` when re-processing stale snapshots.
- Open questions:
  - TBD — `DateTimeUTC` filter field name vs the returned `dateTime` property: spec uses both. Assume request-side `DateTimeUTC` is UTC and response `dateTime` matches.
  - Max `pageSize` 100 — for bulk reconciliation prefer sync, not search.
  - Confirm whether `Result` / `TotalCount` envelope keys are case-sensitive on the wire.
