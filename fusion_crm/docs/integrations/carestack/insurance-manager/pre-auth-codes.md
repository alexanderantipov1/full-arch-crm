# Insurance Plan Pre-Authorization Codes

**Fusion domain:** billing (TBD)
**PHI:** no — plan-level pre-auth code list
**Spec section:** Insurance Manager — 5.1, 5.2 (CareStack Developer API v1.0.45)

A simple list of procedure code ids that require pre-authorization
under this plan.

## Object fields

### InsurancePlanPreAuthorizationCodesModel

| field | type | notes |
|---|---|---|
| InsurancePlanId | int | plan id |
| PreAuthorizationCodes | IEnumerable<int> | procedure code ids requiring pre-auth |

## Endpoints

### `GET /insurance/api/v1.0/plans/{insurancePlanId}/pre-authorization-codes` — list plan pre-auth codes
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** none
- **Success:** 200 — `InsurancePlanPreAuthorizationCodesModel`
- **Permissions:** `Patient_InsuranceInfo_InsuranceDetailsAndEligibility_View`

### `PUT /insurance/api/v1.0/plans/{insurancePlanId}/pre-authorization-codes` — replace plan pre-auth codes
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** `InsurancePlanPreAuthorizationCodesModel`
- **Success:** 200 — TBD — verify in PDF p.80
- **Permissions:** `Patient_InsuranceInfo_InsurancePlan_Edit`

## Fusion mapping

- Target: `billing.insurance_plan_pre_auth_code`
  (composite key `plan_id` + `procedure_code_id`).
- Ingestion: on-demand alongside plan details; potentially cached.
- Open questions:
  - Does replacing the list purge any audit trail of removed codes? TBD.
