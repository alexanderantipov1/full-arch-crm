# Patient

**Fusion domain:** `identity` + `phi` (split: name/contact → `identity`; DOB/SSN/demographics → `phi`)
**PHI:** yes — DOB, SSN, driver license, medical-related status, contact info all qualify.
**Spec section:** Resource 3 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | unique patient identifier |
| prefix | integer | 1 NotSet, 2 Dr, 3 Mrs, 4 Ms, 5 Mr, 6 Capt, 7 Col, 8 Gen, 9 Maj, 10 Miss, 11 Mstr, 12 Rev |
| firstName | string | max 255 |
| lastName | string | max 255 |
| middleName | string | max 255 |
| suffix | string | max 255 |
| dob | date | yyyy-mm-dd |
| gender | integer | 1 Male, 2 Female, 3 Other, 4 NotSet |
| maritalStatus | integer | 1 Single, 2 Married, 3 Divorced, 4 Widowed, 5 N/A, 6 Partnered |
| ssn | string | format `111-11-1111`, max 9 |
| driverLicence | string | max 20 |
| defaultLocationId | integer | patient's default location |
| phoneWithExt | string | format `(111) 111-1111 x2222` |
| mobile | string | format `(111) 111-1111`, max 10 |
| workPhoneWithExt | string | format `(111) 111-1111 x2222` |
| fax | string | format `(111) 111-1111` |
| email | string | RFC-style email |
| addressDetail | Address | addressLine1, addressLine2, city, state, zipCode |
| referralSourceSubCategoryId | integer | FK to referral source subcategory |
| patientOrthoStatus | integer | 1 Yes, 2 No, 3 N/A |
| relationshipToResponsibleParty | integer | 1 Self, 2 Spouse, 3 Dependent Child, 4 Other, 5 NotSet |
| responsiblePartyPatientId | integer | null if patient is self-responsible |
| communicationStatus | integer | bitwise OR: 0 None, 1 Email, 2 Text, 4 Voice, 8 Promotion, 16 Postcard |
| patientIdentifier | integer | patient identifier |
| imagingIntegrationId | string | imaging system link; falls back to `patientIdentifier` if null |
| status | integer | 0 Inactive, 1 Active, 2 Duplicate |
| accountId | integer | CareStack account id |

`communicationStatus` uses bitwise OR. Example: accepts Promotion (8) + Text (2) = 10.

## Endpoints

### `POST /v1.0/patients` — create a new patient
- **Path params:** none
- **Query params:** none
- **Body:** Patient object. Required: `firstName`, `lastName`, `dob`, `gender`, `defaultLocationId`. When `addressDetail` is provided, all its fields except `addressLine2` are required.
- **Success:** 200 — created Patient
- **Notes:** duplicate detection — rejects on match by email, SSN, driver license, or the combo (firstName + lastName + dob).

### `PUT /v1.0/patients/` — update an existing patient
- **Path params:** none (id lives in the body)
- **Query params:** none
- **Body:** full Patient object including `id`
- **Success:** 200 — updated Patient
- **Notes:** same field rules as POST.

### `GET /v1.0/patients/{id}` — retrieve patient by id
- **Path params:** `id` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — Patient object

## Fusion mapping

- Target table(s):
  - `identity.person` — canonical `person_uid`, name, contact (phones, email, address).
  - `phi.patient_demographics` — DOB, SSN, gender, marital status, driver license, ortho status.
  - `identity.external_identifier` — CareStack `id`, `patientIdentifier`, `imagingIntegrationId`.
- Ingestion strategy: sync (Patient Sync Resource) + on-demand GET for single reads.
- Open questions:
  - Where does `communicationStatus` belong? Likely `ops` (consent flags) but needs per-channel split.
  - `responsiblePartyPatientId` — model as self-reference in `phi` or expose via `identity` relationships?
