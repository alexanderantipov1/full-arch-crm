# Insurance Plan Coverages

**Fusion domain:** billing (TBD)
**PHI:** no — plan-level coverage configuration
**Spec section:** Insurance Manager — 2.1, 2.2 (CareStack Developer API v1.0.45)

A plan has up to two coverage tables (`CoverageTable1`,
`CoverageTable2`). Each table carries category-level coverage and
procedure-code-level additional coverage, plus which providers it
applies to and an optional link to a coverage template.

## Object fields

### InsurancePlanCoverageModel

| field | type | notes |
|---|---|---|
| InsurancePlanId | int | plan this coverage belongs to |
| LinkedTemplateId | int | coverage template id (0/null = unlinked) |
| CoverageTableId | byte (enum) | 1 = CoverageTable1, 2 = CoverageTable2 |
| AssignedProviderIds | IEnumerable<int> | providers this table applies to |
| CategoryCoverages | IEnumerable<CustomCategoryCoverageModel> | per category |
| AdditionalCoverages | IEnumerable<CustomAdditionalCoverageModel> | per procedure code |

### CustomCategoryCoverageModel

| field | type | notes |
|---|---|---|
| CoverageCategoryId | int | category id (from coverage template) |
| CoveragePercent | decimal | percent covered |
| DeductibleWaived | bool | |
| MaximumsWaived | bool | |
| WaitingPeriod | short | number of units |
| WaitingPeriodUnit | byte (enum) | 1=Day, 2=Week, 3=Month, 4=Year |

### CustomAdditionalCoverageModel

| field | type | notes |
|---|---|---|
| ProcedureCodeId | int | individual procedure code |
| CoveragePercent | decimal | |
| DeductibleWaived | bool | |
| MaximumsWaived | bool | |
| WaitingPeriod | short | |
| WaitingPeriodUnit | byte (enum) | same enum as above |

### Enums

- `InsurancePlanCoverageTable`: 1=CoverageTable1, 2=CoverageTable2
- `WaitingPeriodUnit`: 1=Day, 2=Week, 3=Month, 4=Year

## Endpoints

### `GET /insurance/api/v1.0/plans/{insurancePlanId}/coverage/{coverageTableId}` — get plan coverage for one table
- **Path params:** `insurancePlanId` int, `coverageTableId` int (1 or 2)
- **Query params:** none
- **Body:** none
- **Success:** 200 — `InsurancePlanCoverageModel`
- **Permissions:** `Patient_InsuranceInfo_InsuranceDetailsAndEligibility_View`

### `PUT /insurance/api/v1.0/plans/{insurancePlanId}/coverage` — upsert plan coverage
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** `InsurancePlanCoverageModel` (CoverageTableId in body picks 1 or 2)
- **Success:** 200 — TBD — verify in PDF p.72
- **Permissions:** `Patient_InsuranceInfo_InsurancePlan_Edit`
- **Notes:** single PUT handles both coverage tables, discriminated by `CoverageTableId`.

## Fusion mapping

- Target: `billing.insurance_plan_coverage`
  (composite key `plan_id` + `coverage_table_id`), with child rows in
  `billing.insurance_plan_coverage_category` and
  `billing.insurance_plan_coverage_additional`.
- Ingestion: on-demand when loading a plan; cache allowed since
  coverage changes infrequently.
- Open questions:
  - Is there a bulk endpoint for all plans? Spec shows only per-plan.
  - Does LinkedTemplateId auto-update category rows or do we store both?
