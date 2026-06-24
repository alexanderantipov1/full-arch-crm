# Insurance Plan AMB Codes

**Fusion domain:** billing (TBD)
**PHI:** no — plan-level alternate-benefit rules
**Spec section:** Insurance Manager — 3.1, 3.2 (CareStack Developer API v1.0.45)

Alternate Benefit (AMB) rules let a payor substitute one procedure
for another (e.g. down-coding a composite filling to an amalgam)
scoped to specific teeth or tooth groups.

## Object fields

### InsurancePlanAmbCodesModel

| field | type | notes |
|---|---|---|
| InsurancePlanId | int | plan id |
| AmbCodes | IEnumerable<AmbCodeModel> | AMB rules for this plan |

### AmbCodeModel

| field | type | notes |
|---|---|---|
| ProcedureCodeId | int | original procedure code |
| AlternateBenefits | IEnumerable<AlternateBenefit> | list of substitutions |

### AlternateBenefit

| field | type | notes |
|---|---|---|
| AmbCodeId | int | id of this AMB rule |
| AlternateProcedureCodeId | int | procedure substituted in place of original |
| AmbToothGroup | AmbToothGroup | tooth scope |

### AmbToothGroup

| field | type | notes |
|---|---|---|
| ToothGroupId | int | |
| ToothCategory | enum (ToothCategory) | see below |
| AmbTeeth | IEnumerable<AmbTooth> | explicit tooth list (used when ToothCategory = Custom) |

### AmbTooth

| field | type | notes |
|---|---|---|
| ToothGroupId | int | |
| Tooth | string | tooth number |

### Enum ToothCategory

`None=0, AllPosteriorPermanentAndPrimary=1, AllPosteriorPermanentOnly,
AllPosteriorPrimaryOnly, AllAnteriorPermanentAndPrimary,
AllAnteriorPermanentOnly, AllAnteriorPrimaryOnly, PermanentMolarsOnly,
PermanentAndPrimaryMolars, UpperSecondMolarsOnly, Custom`

## Endpoints

### `GET /insurance/api/v1.0/plans/{insurancePlanId}/amb-codes` — list plan AMB codes
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** none
- **Success:** 200 — `InsurancePlanAmbCodesModel`

### `POST /insurance/api/v1.0/plans/{insurancePlanId}/amb-codes` — replace plan AMB codes
- **Path params:** `insurancePlanId` int
- **Query params:** none
- **Body:** `InsurancePlanAmbCodesModel`
- **Success:** 200 — TBD — verify in PDF p.76
- **Notes:** POST here acts as an upsert/replace for the plan's AMB set.

## Fusion mapping

- Target:
  - `billing.insurance_plan_amb_code` (by plan_id + procedure_code_id)
  - `billing.insurance_plan_amb_alternate` (child rows, one per `AlternateBenefit`)
  - `billing.amb_tooth_group` referenced from alternate rows
- Ingestion: on-demand; bulk pull if we implement fee estimation.
- Open questions:
  - Are AmbCodeIds stable across POSTs or regenerated? TBD.
