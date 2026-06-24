# Insurance (patient-level)

**Fusion domain:** `billing` (new, TBD)
**PHI:** mixed — ties insurance identifiers to a patient; SSN may appear in `identificationValue` when `identificationType == 1`.
**Spec section:** Resource 12 (CareStack Developer API v1.0.45)

> This doc covers the **patient-insurance** endpoints only. The **Insurance Manager** module (plans, payors, templates) lives in `insurance-manager/` and is handled separately.

## Object fields

### PatientInsurance

| field | type | notes |
|---|---|---|
| id | integer | patient insurance id |
| activeDate | datetime | insurance active date |
| effectiveDate | datetime | insurance effective date |
| hierarchy | integer | 1 Primary Dental, 2 Secondary Dental, 3 Tertiary Dental, 4 Primary Medical, 5 Secondary Medical |
| identificationType | integer | 1 SSN, 2 SubscriberId |
| identificationValue | string | SSN or subscriber id |
| insuranceType | string | "Dental" / "Medical" |
| patientId | integer | |
| planId | integer | |
| planName | string | |
| policyHolderPatientId | integer | policy holder patient id |
| employer | string | |
| carrier | string | payor name |

### PatientInsuranceBenefits

| field | type | notes |
|---|---|---|
| individualMaxRemaining | decimal | nullable |
| individualDeductibleRemaining | decimal | nullable |
| familyMaxRemaining | decimal | nullable |
| familyDeductibleRemaining | decimal | nullable |
| orthoMaxRemaining | decimal | nullable |
| orthoDeductibleRemaining | decimal | nullable |
| copay | decimal | nullable |
| coinsurance | decimal | nullable |
| shareOfCostRemaining | decimal | nullable |

### InsurancePlan

| field | type | notes |
|---|---|---|
| id | integer | unique plan id |
| planName | string | |
| insuranceType | string | |
| planType | string | |
| payorId | integer | |
| verifiedDate | datetime | |
| groupNumber | string | |
| capitationFee | decimal | |
| payorDetails | PayorDetail | embedded |

### PayorDetail

| field | type | notes |
|---|---|---|
| id | integer | |
| payorIdentifier | string | |
| claimChannel | integer | 1 Paper Based, 2 Electronic |
| phone | string | with extension |
| website | string | |
| address | Address | addressLine1/2, city, state, zipCode |

## Endpoints

### `GET /insurance/api/v1.0/insurances?patientId={patientId}` — list patient insurances
- **Path params:** none
- **Query params:** `patientId` (integer, required)
- **Body:** none
- **Success:** 200 — array of PatientInsurance
- **Notes:** base path `/insurance/api/v1.0` (not `/api/v1.0`).

### `GET /insurance/api/v1.0/insurances/{patientInsuranceId}/benefits` — benefits for one insurance
- **Path params:** `patientInsuranceId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — PatientInsuranceBenefits object

### `GET /api/v1.1/insuranceplans/{insurancePlanId}` — insurance plan details
- **Path params:** `insurancePlanId` (integer)
- **Query params:** none
- **Body:** none
- **Success:** 200 — InsurancePlan object
- **Notes:** this endpoint is on `v1.1`, not `v1.0`.

## Fusion mapping

- Target table(s): `billing.patient_insurance`, `billing.insurance_plan`, `billing.payor` (new domain, TBD).
- Ingestion strategy: on-demand + sync for plan/payor reference data.
- Open questions:
  - `identificationValue` can contain SSN — classify as PHI at the column level.
  - The v1.1 insurance-plan endpoint suggests CareStack is migrating this surface; follow up when v1.0.46 ships.
