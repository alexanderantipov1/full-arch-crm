# Patient Sync

**Fusion domain:** `identity` + `phi`
**PHI:** yes — the full Patient record is returned (see `resources/patients.md`).
**Spec section:** Sync Resource 1 (CareStack Developer API v1.0.45)

## Endpoint

### `GET /v1.0/sync/patients` — modified-after patient feed

Real path: `GET /api/{version}/sync/patients` where `{version}` is the CareStack API version segment (e.g. `v1.0`). Kept as `/v1.0/sync/patients` here for grep uniformity.

- **Query params:**
  - `modifiedSince` (datetime, ISO 8601 UTC) — required on the initial call of a scan.
  - `continueToken` (string, optional) — pagination token from the previous response. `null` / absent starts a fresh scan.
  - `pageSize` (number, optional) — default `100`, max `500`.
- **Response:** list of Patient objects plus a `continueToken`. Token is `null` when the scan is complete.

Follow-up pages reuse the same URL with only `continueToken`:

```
GET /v1.0/sync/patients?continueToken=<token>
```

## Fields returned (summary)

Per-patient shape matches the Patient resource (see `resources/patients.md`). Key fields for Fusion mapping:

| field | type | notes |
|---|---|---|
| patientId | integer | natural key (PHI linkage) |
| patientIdentifier | string | external/display id |
| firstName / middleName / lastName / nickName | string | PHI |
| dob | date | PHI |
| mobile / phoneWithExt | string | PHI |
| email | string | PHI |
| addressLine1/2, city, state, zipCode | string | PHI |
| ssn | string | PHI |
| lastUpdatedOn | datetime | watermark source — TBD — verify in PDF p.43 that field name matches |

## Fusion mapping

- Target table(s): `identity.person`, `identity.person_identifier` (`kind="carestack_patient_id"`), `phi.patient_profile`.
- `ingest.raw_event.event_type`: `carestack.patient.upsert`.
- Cadence: every 5 minutes.
- Idempotency key: `(patientId, lastUpdatedOn)`.
- Open questions:
  - TBD — the spec does not list the Patient object attributes in this section; rely on the Patient resource page for the field list. Verify in PDF p.43 that no sync-only fields (e.g. `isDeleted`) are present.
  - How do we pick the initial `modifiedSince` for bootstrap? Proposal: use the epoch (`1970-01-01T00:00:00Z`) for first-time full load and let pagination walk the entire tenant.
