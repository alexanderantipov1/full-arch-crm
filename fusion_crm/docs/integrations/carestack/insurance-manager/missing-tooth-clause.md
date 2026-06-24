# Insurance Plan Missing Tooth Clause

**Fusion domain:** billing (TBD)
**PHI:** no — plan-level clause configuration
**Spec section:** Insurance Manager — 4.1, 4.2 (CareStack Developer API v1.0.45)

The missing-tooth clause describes how a plan handles procedures
involving a tooth that was lost before coverage started.

## Object fields

### InsurancePlanMissingToothClauseModel

| field | type | notes |
|---|---|---|
| InsurancePlanMissingToothClauseId | int | row id |
| InsurancePlanId | int | plan id |
| MissingToothClauseType | enum (MissingToothClauseType) | see below |
| MonthInput | byte | month input, only meaningful when clause type references a cooling period |

### Enum MissingToothClauseType

`NoClause = 1, NoCoverageUntilCoolingPeriod,
NotCoveredForLifeOfPolicy, NotCoveredForCongenitallyMissingTooth,
ReducedCoverageUntilCoolingPeriod`

## Endpoints

### `GET /insurance/api/v1.0/plans/{insurancePlanId}/missing-tooth-clause` — fetch clause
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** none
- **Success:** 200 — `InsurancePlanMissingToothClauseModel`
- **Permissions:** `Patient_InsuranceInfo_InsuranceDetailsAndEligibility_View`

### `PUT /insurance/api/v1.0/plans/{insurancePlanId}/missing-tooth-clause` — upsert clause
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** `InsurancePlanMissingToothClauseModel`
- **Success:** 200 — TBD — verify in PDF p.78
- **Permissions:** `Patient_InsuranceInfo_InsurancePlan_Edit`

## Fusion mapping

- Target: `billing.insurance_plan_missing_tooth_clause` (one row per plan).
- Ingestion: on-demand alongside plan details.
- Open questions:
  - What values of `MonthInput` are valid when clause type is `NoClause`? TBD.
