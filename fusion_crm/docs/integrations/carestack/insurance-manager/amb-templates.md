# Insurance AMB Code Templates

**Fusion domain:** billing (TBD)
**PHI:** no — reusable alternate-benefit templates
**Spec section:** Insurance Manager — 9.1 – 9.6 (CareStack Developer API v1.0.45)

Reusable AMB-code bundles. Attach the template to a plan or payor to
pre-populate its alternate-benefit rules; the plan/payor can still be
overridden per instance.

## Object fields

### TemplateBaseModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |

### AmbCodeTemplateDetailModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |
| AmbCodes | IEnumerable<AmbCodeModel> | |

### AmbCodeModel

| field | type | notes |
|---|---|---|
| ProcedureCodeId | int | |
| AlternateBenefits | IEnumerable<AlternateBenefit> | |

### AlternateBenefit

| field | type | notes |
|---|---|---|
| AmbCodeId | int | |
| AlternateProcedureCodeId | int | |
| AmbToothGroup | AmbToothGroup | |

### AmbToothGroup

| field | type | notes |
|---|---|---|
| ToothGroupId | int | |
| ToothCategory | byte (enum ToothCategory) | |
| AmbTeeth | IEnumerable<AmbTooth> | |

### AmbTooth

| field | type | notes |
|---|---|---|
| ToothGroupId | int | |
| Tooth | string | |

### Enum ToothCategory

`None=0, AllPosteriorPermanentAndPrimary, AllPosteriorPermanentOnly,
AllPosteriorPrimaryOnly, AllAnteriorPermanentAndPrimary,
AllAnteriorPermanentOnly, AllAnteriorPrimaryOnly,
PermanentMolarsOnly, PermanentAndPrimaryMolars, UpperSecondMolarsOnly,
Custom`

## Endpoints

### `GET /insurance/api/v1.0/amb/templates` — list AMB templates
- **Body:** none
- **Success:** 200 — array of `TemplateBaseModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `POST /insurance/api/v1.0/amb/templates` — create AMB template
- **Body:** `AmbCodeTemplateDetailModel`
- **Success:** 201 — `{ templateId: int }`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `GET /insurance/api/v1.0/amb/templates/{templateId}` — get AMB template detail
- **Path params:** `templateId` int
- **Body:** none
- **Success:** 200 — `AmbCodeTemplateDetailModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `PUT /insurance/api/v1.0/amb/templates/{templateId}` — update AMB template (full)
- **Path params:** `templateId` int
- **Body:** `{ AmbTemplateModel: IEnumerable<AmbCodeModel> }` (spec wraps body in a `AmbTemplateModel` field — TBD verify PDF p.146)
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `PATCH /insurance/api/v1.0/amb/templates/{templateId}` — patch base fields only
- **Path params:** `templateId` int
- **Body:** `TemplateBaseModel` (`TemplateId`, `TemplateName`, `IsDefault`)
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `DELETE /insurance/api/v1.0/amb/templates/{templateId}` — delete AMB template
- **Path params:** `templateId` int
- **Permissions:** `PracticeSettings_InsuranceTemplates_Delete`

## Fusion mapping

- Target tables:
  - `billing.amb_template`
  - `billing.amb_template_code` — 1..N per template
  - `billing.amb_template_alternate` — 1..N per code
  - `billing.amb_tooth_group` + `billing.amb_tooth` (shared with plan AMB)
- Ingestion: bootstrap pull; per-template fetch on admin demand.
- Open questions:
  - PUT body wrapper name `AmbTemplateModel` vs. flat object — verify.
