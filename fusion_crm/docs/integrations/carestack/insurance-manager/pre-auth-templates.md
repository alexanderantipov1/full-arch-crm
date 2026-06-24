# Insurance Pre-Authorization Templates

**Fusion domain:** billing (TBD)
**PHI:** no — reusable pre-auth code list
**Spec section:** Insurance Manager — 11.1 – 11.6 (CareStack Developer API v1.0.45)

Reusable lists of procedure-code ids that require pre-authorization.
Attach a template to a plan or payor via the PATCH endpoints in
`plans.md` / `payors.md`.

## Object fields

### TemplateBaseModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |

### PreAuthorizationTemplateDetailModel

| field | type | notes |
|---|---|---|
| TemplateId | int | |
| TemplateName | string | |
| IsDefault | bool | |
| PreAuthorizationCodes | IEnumerable<int> | procedure code ids requiring pre-auth |

## Endpoints

### `GET /insurance/api/v1.0/pre-authorization-codes/templates` — list pre-auth templates
- **Body:** none
- **Success:** 200 — array of `TemplateBaseModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `POST /insurance/api/v1.0/pre-authorization-codes/templates` — create pre-auth template
- **Body:** `PreAuthorizationTemplateDetailModel`
- **Success:** 201 — `{ templateId: int }`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `GET /insurance/api/v1.0/pre-authorization-codes/templates/{templateId}` — get pre-auth template
- **Path params:** `templateId` int
- **Body:** none
- **Success:** 200 — `PreAuthorizationTemplateDetailModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_View`

### `PUT /insurance/api/v1.0/pre-authorization-codes/templates/{templateId}` — replace pre-auth template
- **Path params:** `templateId` int
- **Body:** `PreAuthorizationTemplateDetailModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `PATCH /insurance/api/v1.0/pre-authorization-codes/templates/{templateId}` — patch base fields only
- **Path params:** `templateId` int
- **Body:** `TemplateBaseModel`
- **Permissions:** `PracticeSettings_InsuranceTemplates_AddEdit`

### `DELETE /insurance/api/v1.0/pre-authorization-codes/templates/{templateId}` — delete pre-auth template
- **Path params:** `templateId` int
- **Permissions:** `PracticeSettings_InsuranceTemplates_Delete`

## Fusion mapping

- Target table:
  - `billing.pre_auth_template` — base fields
  - `billing.pre_auth_template_code` — 1..N procedure code ids
- Ingestion: bootstrap pull; refresh on-demand.
- Open questions: none material.
