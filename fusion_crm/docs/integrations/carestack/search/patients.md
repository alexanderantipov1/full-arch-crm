# Patient Search

**Fusion domain:** `identity` + `phi`
**PHI:** yes — results include names, DOB, mobile, email, address, SSN.
**Spec section:** Search Resource 1 (CareStack Developer API v1.0.45)

## Endpoint

### `POST /v1.0/patients/search` — filtered one-shot patient lookup

Note: the spec path is `POST /api/v2.0/patients/search` (Search v2 lives under `v2.0`, not `v1.0`). Kept under `v1.0/...` in this header only so the grep pattern is uniform; treat the real path as `v2.0`.

- **Query params:** none (all filters travel in the body).
- **Body:**
  - `searchTerm` (string, optional) — plain free-text search (e.g. "John Doe", "1234567").
  - `filterByFields` (array, optional) — list of `{ field, value, type }` complex filters.
  - `orderByFields` (array, optional) — list of `{ field, isDescending }`.
  - `selectFields` (string, optional) — comma-separated list of attributes to project.
  - `offset` (int, optional) — starts at 0.
  - `limit` (int, optional) — page size.
- **Accepts** `searchTerm`, `filterByFields`, or both.
- **Response:** array of Patient objects by default; when `selectFields` is supplied, an array containing only those fields.

### Supported fields

- `filterByFields`: `PatientIdentifier`, `FirstName`, `NickName`, `MiddleName`, `LastName`, `DOB`, `Mobile`, `PhoneWithExt`, `AddressLine1`, `AddressLine2`, `City`, `State`, `ZipCode`, `Email`.
- `orderByFields`: `PatientIdentifier`, `ResponsiblePartyPatientId`.
- `selectFields`: `PatientID`, `PatientIdentifier`, `FirstName`, `NickName`, `MiddleName`, `LastName`, `Mobile`, `PhoneWithExt`, `AddressLine1`, `AddressLine2`, `City`, `State`, `ZipCode`, `LocationName`, `Email`, `SSN`.

### Format notes

- `DOB` is localised: `MM/DD/YYYY` (US) or `DD/MM/YYYY` (UK, AUS).
- `Mobile` is in E.164 format (e.g. `+14015551234`).

## Fields returned (summary)

| field | type | notes |
|---|---|---|
| patientId | integer | internal CareStack id |
| patientIdentifier | string | external/display id |
| firstName / middleName / lastName / nickName | string | name parts (PHI) |
| dob | string | localised date (PHI) |
| mobile | string | E.164 (PHI) |
| phoneWithExt | string | PHI |
| addressLine1 / addressLine2 / city / state / zipCode | string | PHI |
| email | string | PHI |
| ssn | string | only via `selectFields` — PHI |
| locationName | string | FK-by-name to location |

## Fusion mapping

- Target table(s): `identity.person`, `identity.person_identifier` (`kind="carestack_patient_id"`), `phi.patient_profile` (names, contact, demographics).
- `ingest.raw_event.event_type`: not emitted automatically — search is on-demand, not a polling feed. If we want to cache matches, emit `carestack.patient.search_hit` with the matched `patientId`.
- Cadence: on-demand only; invoke from operator UI or agent tool. Do not schedule periodic searches — use the Patient Sync Resource for that.
- Idempotency key: `(patientId)` for any write that routes back to `identity.person`.
- Open questions:
  - TBD — confirm whether `SSN` is ever returned when not explicitly asked for via `selectFields`. Treat as never-shown to operator UI.
  - TBD — `LocationName` has no id; resolve by name against the Locations resource before persisting.
  - Do we prefer `searchTerm` (fuzzier) or structured `filterByFields` by default for our agent tool?
