# Insurance Eligibility Rule Templates

**Fusion domain:** billing (TBD)
**PHI:** no — rule definitions, not patient data
**Spec section:** Insurance Manager — 10.1 – 10.6 (CareStack Developer API v1.0.45)

Eligibility rule templates hold a JSON form definition (`RuleJson`)
that drives the eligibility-check UI for a plan or payor. The inner
`FormContainer` shape is reused from the generic eligibility-rule
resource and is not expanded here.

## Object fields

### TemplateBaseModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |

### EligibilityRuleTemplateDetailModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |
| RuleJson | FormContainer | TBD — `FormContainer` shape in the main Eligibility Rule resource |

## Endpoints

### `GET /insurance/api/v1.0/eligibility-rule/templates` — list eligibility rule templates
- **Body:** none
- **Success:** 200 — array of `TemplateBaseModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `POST /insurance/api/v1.0/eligibility-rule/templates` — create eligibility rule template
- **Body:** `EligibilityRuleTemplateDetailModel`
- **Success:** 201 — `{ templateId: int }`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `GET /insurance/api/v1.0/eligibility-rule/{templateId}` — get eligibility rule template detail
- **Path params:** `templateId` int
- **Body:** none
- **Success:** 200 — `EligibilityRuleTemplateDetailModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`
- **Notes:** spec shows this path without `/templates/` — keep as written.

### `PUT /insurance/api/v1.0/eligibility-rule/{templateId}` — replace eligibility rule template
- **Path params:** `templateId` int
- **Body:** `EligibilityRuleTemplateDetailModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `PATCH /insurance/api/v1.0/eligibility-rule/{templateId}` — patch base fields only
- **Path params:** `templateId` int
- **Body:** `TemplateBaseModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `DELETE /insurance/api/v1.0/amb/eligibility-rule/{templateId}` — delete eligibility rule template
- **Path params:** `templateId` int
- **Permissions:** `PracticeSettings_InsuranceTemplates_Delete`
- **Notes:** spec shows path with `/amb/eligibility-rule/` — likely a
  typo and the correct path is `/eligibility-rule/{templateId}` —
  TBD verify PDF p.150.

## Fusion mapping

- Target table: `billing.eligibility_rule_template` — stores
  `RuleJson` opaquely as jsonb until we have a need to parse it.
- Ingestion: on-demand.
- Open questions:
  - `FormContainer` inner schema — do we ever need to parse it in Fusion?
  - DELETE path inconsistency (see notes on 10.6).
