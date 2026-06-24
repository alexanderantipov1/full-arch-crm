# Insurance Coverage Templates

**Fusion domain:** billing (TBD)
**PHI:** no — reusable coverage templates
**Spec section:** Insurance Manager — 8.1 – 8.6 (CareStack Developer API v1.0.45)

Coverage templates bundle a set of coverage categories (percentages,
deductible / maximum waivers, waiting periods) so they can be reused
across many plans or payors.

## Object fields

### TemplateBaseModel (list/summary)

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |

### CoverageTemplateDetailModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |
| Categories | IEnumerable<CoverageCategoryModel> | |

### CoverageCategoryModel

| field | type | notes |
|---|---|---|
| CoverageCategoryId | int | |
| CoverageTemplateId | int | |
| CategoryName | string | |
| ProcedureCodeIds | IEnumerable<int> | codes belonging to this category |
| CoveragePercent | decimal | |
| DeductibleWaived | bool | |
| MaximumsWaived | bool | |
| WaitingPeriod | int | (PUT shape uses `short` — treat as int16-compatible) |
| WaitingPeriodUnit | byte (enum) | Day=1, Week, Month, Year |
| DisplayOrder | int | |

### Enum WaitingPeriodUnit

`Day=1, Week=2, Month=3, Year=4`

## Endpoints

### `GET /insurance/api/v1.0/coverage/templates` — list coverage templates
- **Body:** none
- **Success:** 200 — array of `TemplateBaseModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `POST /insurance/api/v1.0/coverage/templates` — create coverage template
- **Body:** `CoverageTemplateDetailModel`
- **Success:** 201 — `{ templateId: int }`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `GET /insurance/api/v1.0/coverage/templates/{templateId}` — get coverage template detail
- **Path params:** `templateId` int
- **Body:** none
- **Success:** 200 — `CoverageTemplateDetailModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `PUT /insurance/api/v1.0/coverage/templates/{templateId}` — replace categories of a coverage template
- **Path params:** `templateId` int
- **Body:** `CoverageTemplateDetailModel` (spec labels the field as "Response" but it is the PUT body — TBD verify PDF p.141)
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `PATCH /insurance/api/v1.0/coverage/templates/{templateId}` — patch template base fields
- **Path params:** `templateId` int
- **Body:** `TemplateBaseModel` (`TemplateId`, `TemplateName`, `IsDefault` only)
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `DELETE /insurance/api/v1.0/coverage/templates/{templateId}` — delete coverage template
- **Path params:** `templateId` int
- **Permissions:** `PracticeSettings_InsuranceTemplates_Delete`

## Fusion mapping

- Target tables:
  - `billing.coverage_template` — base fields
  - `billing.coverage_template_category` — child rows (`CoverageCategoryModel`)
  - `billing.coverage_template_category_procedure` — link table for `ProcedureCodeIds`
- Ingestion: pull once on billing bootstrap; refresh on demand when
  operator opens template UI.
- Open questions:
  - Is there a way to list templates assigned to a specific payor/plan
    without walking plan records? TBD.
