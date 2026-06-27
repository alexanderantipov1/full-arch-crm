# Insurance Plan

**Fusion domain:** billing (TBD)
**PHI:** no — plan configuration, not patient-scoped
**Spec section:** Insurance Manager — 6.1 – 6.11 (CareStack Developer API v1.0.45)

The central insurance-plan object. Carries identity, employer/payor
linkage, reset/waiting rules, linked template ids (coverage, AMB,
pre-auth, eligibility), fee-schedule behaviour, and nested
benefit/payor detail objects.

## Object fields

### InsurancePlanModel (GET / PUT / POST body)

| field | type | notes |
|---|---|---|
| InsurancePlanId | int | plan id |
| PlanName | string | |
| InsuranceType | string | |
| PlanType | string | |
| EmployerID | int? | |
| EmployerName | string | |
| GroupNumber | string | |
| PayorTypeId | int? | |
| CapitationFee | decimal | |
| PlanResetMonth | int? | month of annual reset (1-12) |
| PlanResetDay | int? | day of month of reset |
| RaiseClaim | string | TBD — verify enum in PDF p.80 |
| VerifiedDate | DateTime? | |
| ClaimFormType | string | |
| LastModifiedBy | int | |
| LastModifiedOn | DateTime? | |
| Status | string | |
| InsurancePlanBenefitID | int? | foreign id of benefits row |
| IsAutoCloseEnabled | bool | |
| LinkedFeeInsurancePlanID | int? | |
| MergedPlanID | int? | plan that replaced this one after merge |
| TableOfAllowanceID | int? | |
| TableOfAllowanceFor | string | |
| UseFeeRegister | bool | |
| FeeRegisterNote | string | |
| AlterTotalFees | bool | |
| BenefitCoordinationMethod | int | |
| VerifiedBy | int? | |
| VerifiedOn | DateTime? | |
| IsActive | bool | |
| InsuranceCoverageTable1TemplateId | int | |
| InsuranceCoverageTable2TemplateId | int? | |
| InsurancePreAuthorizationTemplateId | int? | |
| InsuranceAmbTemplateId | int? | |
| InsuranceEligibilityRuleTemplateId | int? | |
| LinkedFeePlanID | int? | |
| WaitingPeriod | short | |
| WaitingPeriodUnit | enum WaitingPeriodUnit | Day=1, Week, Month, Year |
| WaitingPeriodFeeType | enum FeeScheduleType | None=0, UCR, MaxAllowable, HMO, MEDI |
| NonCoveredCodesFeeType | enum FeeScheduleType | same enum |
| BenefitsExceededFeeType | enum FeeScheduleType | same enum |
| CoverageTable1ProviderIds | IEnumerable<int> | |
| CoverageTable2ProviderIds | IEnumerable<int> | |
| AbpSettingMode | enum AbpSettingMode | Included=1, Excluded=2 |
| Benefits | InsurancePlanBenefitModel | nested |
| PayorDetails | PayorModel | nested |

### InsurancePlanBenefitModel

| field | type | notes |
|---|---|---|
| InsurancePlanID | int | |
| InsurancePlanBenefitID | int | |
| FamilyMax | string(15) | |
| FamilyMaxLimit | decimal? | range 0..9999999999.99 |
| IndividualMax | string(15) | |
| IndividualMaxLimit | decimal | range 0..9999999999.99 |
| FamilyDeductible | string(15) | |
| FamilyDeductibleLimit | decimal? | |
| IndividualDeductible | string(15) | |
| IndividualDeductibleLimit | decimal? | |
| IndividualOrthoMax | string(15) | |
| IndividualOrthoAgeLimitApplicable | string(15) | |
| IndividualOrthoAgeLimitInYears | int? | |
| Copay | decimal? | |
| Coinsurance | decimal? | 0..100 |
| Notes | string | |
| CoversTreatmentInProgress | bool | |
| PercentPaidAtBanding | decimal? | |
| PaymentCycle | int? | |
| BenefitsLastUpdatedBy | int? | |
| BenefitsLastUpdatedOn | DateTime? | |
| AbpSetting | AbpSettingModel | |
| IsPeriodicClaimsRequired | bool | |

### AbpSettingModel

| field | type | notes |
|---|---|---|
| SettingMode | enum AbpSettingsMode | Included=1, Excluded=2 |
| ProviderIds | IEnumerable<int> | |
| LocationIds | IEnumerable<int> | |

### Nested PayorModel / PayorAddressModel / PayorContactModel

See `payors.md` — same models are embedded here as `PayorDetails`.

## Endpoints

### `GET /insurance/api/v1.0/plans/{planId}` — get plan by id
- **Path params:** `planId` int
- **Body:** none
- **Success:** 200 — `InsurancePlanModel` (includes `Benefits` and `PayorDetails`)

### `PUT /insurance/api/v1.0/plans/{planId}` — update plan
- **Path params:** `planId` int
- **Body:** `InsurancePlanModel`
- **Success:** 200 — updated plan (TBD — verify in PDF p.88)

### `POST /insurance/api/v1.0/plans` — create plan
- **Body:** `InsurancePlanModel` (InsurancePlanId ignored / 0)
- **Success:** 201 — new plan id (TBD — verify in PDF p.95)

### `POST /insurance/api/v1.0/plans/source-plan/{planId}` — create plan by cloning an existing one
- **Path params:** `planId` int — source plan id
- **Body:** `InsurancePlanModel` — overrides on top of the cloned source
- **Success:** 201 — new plan id (TBD — verify in PDF p.102)

### `GET /insurance/api/v1.0/plans/{planId}/benefit` — get plan benefits
- **Path params:** `planId` int
- **Body:** none
- **Success:** 200 — `InsurancePlanBenefitModel`
- **Notes:** spec path shown as `plans/planId:int}/benefit` with a
  stray brace — treat as `plans/{planId}/benefit`.

### `PUT /insurance/api/v1.0/plans/{planId}/benefit` — update plan benefits
- **Path params:** `planId` int
- **Body:** `InsurancePlanBenefitModel`
- **Success:** 200 — TBD — verify in PDF p.111
- **Notes:** spec section title says "Retrieves" but the method is PUT — it is the update endpoint.

### `GET /insurance/api/v1.0/plans/{planId}/fee-schedule-assignment` — get fee schedule assignment
- **Path params:** `planId` int
- **Body:** none
- **Success:** 200 — `FeeScheduleAssignmentModel`:
  - `FeeScheduleAssignmentId` int
  - `FeeScheduleId` int
  - `FeeScheduleType` enum `FeeScheduleType` (None=0, UCR, MaxAllowable, HMO, MEDI)
  - `PayorId` int?
  - `ProviderId` int?
  - `InsurancePlanId` int?
  - `LocationId` int?
  - `LocationsGroupId` int?
  - `EstimationHierarchyOrder` byte?
  - `BillingHierarchyOrder` byte?
  - `SpecialtyId` int?

### `POST /insurance/api/v1.0/plans/delete` — bulk delete plans
- **Body:** `{ InsurancePlanID: IEnumerable<int> }` (field name singular in spec)
- **Success:** 200 — TBD — verify in PDF p.113
- **Notes:** POST used for bulk delete because request carries a body.

### `PATCH /insurance/api/v1.0/plans/{planId}/pre-authorization-codes/templates/{templateId}` — attach pre-auth template to plan
- **Path params:** `planId` int, `templateId` int
- **Body:** none (action is implied by template id)
- **Permissions:** `Patient_InsuranceInfo_InsurancePlan_Edit`

### `PATCH /insurance/api/v1.0/plans/{planId}/eligibility-rule/templates/{templateId}` — attach eligibility rule template to plan
- **Path params:** `planId` int, `templateId` int
- **Body:** none
- **Permissions:** `Patient_InsuranceInfo_InsurancePlan_Edit`

### `PATCH /insurance/api/v1.0/plans/{planId}/amb-codes/templates/{templateId}` — attach AMB template to plan
- **Path params:** `planId` int, `templateId` int
- **Body:** none
- **Permissions:** `Patient_InsuranceInfo_InsurancePlan_Edit`

## Fusion mapping

- Target tables:
  - `billing.insurance_plan` — top-level fields
  - `billing.insurance_plan_benefit` — 1:1 with plan
  - `billing.insurance_plan_provider_coverage_link` (or embedded arrays)
    for `CoverageTable1ProviderIds` / `CoverageTable2ProviderIds`
  - `billing.fee_schedule_assignment` — shared with the fee-schedule resource
- Ingestion strategy: on-demand fetch per plan id the first time a
  patient with that plan is touched; then refresh via a slow
  background job (e.g. weekly) since plans change rarely.
- Open questions:
  - What is the exact enum set for `RaiseClaim`, `Status`, `PlanType`,
    `InsuranceType`, `ClaimFormType`, `TableOfAllowanceFor`,
    `BenefitCoordinationMethod`? Values not given in spec — TBD.
  - Does `POST .../plans/delete` soft- or hard-delete? TBD.
