# Payors

**Fusion domain:** billing (TBD)
**PHI:** no — payor/carrier directory, addresses, and rule
configuration; none patient-scoped
**Spec section:** Insurance Manager — 7.1 – 7.28 (CareStack Developer API v1.0.45)

A payor is an insurance carrier. This group covers the payor record,
its addresses (with NEA attachment and claim/authorization channel
flags), AMB codes, eligibility rules, pre-authorization codes,
provider-specific insurance linkage, payor types, and payor coverage.

## Object fields

### PayorModel

| field | type | notes |
|---|---|---|
| PayorId | int | |
| PayorName | string | |
| PayorNameInForm | string | name printed on claim forms |
| Website | string | |
| IsAutoCloseEnabled | bool | |
| MergedPayorId | int? | payor that replaced this one after merge |
| PayorTypeId | int? | |
| IsElectronicEligibilityCheckEnabled | bool | |
| UseTotalFeeInClaims | bool | |
| RequireAttachmentsForHigherOrderClaims | bool | |
| AddressDetails | PayorAddressModel | embedded primary/default address |
| ContactDetails | PayorContactModel | embedded contact |
| PreAuthorizationTemplateId | int? | |
| AmbTemplateId | int? | |
| EligibilityRuleTemplateId | int? | |
| CoverageTemplateId | int? | |

### PayorAddressModel

| field | type | notes |
|---|---|---|
| PayorAddressId | int | |
| PayorId | int | |
| NickName | string | |
| PayorIdentifier | string | carrier identifier (e.g. payor id number) |
| AddressDetail | AddressModel | lines / city / state / zip |
| ClaimChannel | enum | NotApplicable=0, PaperBased=1, Electronic=2 |
| IsDefaultAddress | bool | (spec shows literal "True" — treat as bool) |
| PhoneWithExt | string | |
| AuthorizationChannel | enum | PaperBased=1, Electronic=2 |
| MergedPayorAddressId | int? | |
| NeaMasterId | string | NEA attachment master id |
| NativeAttachmentCarrierId | string | |

### PayorContactModel

| field | type | notes |
|---|---|---|
| PhoneWithExt | string | |
| Mobile | string | |
| Email | string | |
| Fax | string | |
| Prefix | enum | NotSet=1, Dr, Mrs, Ms, Mr, Capt, Col, Gen, Maj, Miss, Mstr, Rev, Rabbi, Rav |
| LastName | string | |
| FirstName | string | |
| MiddleName | string | |
| Suffix | string | |

### PayorTypeDetailsModel

| field | type | notes |
|---|---|---|
| PayorTypeId | int | |
| PayorTypeName | string | |
| PayorTypeDescription | string | |
| IsActive | bool | |

### PayorCoverageModel

| field | type | notes |
|---|---|---|
| PayorId | int | |
| LinkedTemplateId | int | coverage template id |
| CategoryCoverages | IEnumerable<CustomCategoryCoverageModel> | see `plan-coverages.md` |
| AdditionalCoverages | IEnumerable<CustomAdditionalCoverageModel> | see `plan-coverages.md` |

### ProviderInsuranceDetails

| field | type | notes |
|---|---|---|
| PayorProviderId | int | |
| ProviderId | int | |
| InsuranceId | string | |
| MedicareId | string | |
| MedicaidId | string | |
| LocationId | int? | |

## Endpoints

Compact table — one-line summary per endpoint. Follow spec ordering
(7.1 → 7.28). Full body/response shapes for the address, payor,
coverage, and amb models are above; templated PATCH endpoints take no
body.

### `GET /insurance/api/v1.0/payors/{payorId}/addresses` — list addresses of a payor
- **Path:** `payorId` int. **Response:** array of `PayorAddressModel`.
- **Permissions:** `PracticeSettings_Carriers_View`, `PracticeSettings_Plans_View`, `Patient_InsuranceInfo_InsuranceDetailsAndEligibility_View`, `Claims_Claims_View`, `Claims_Authorizations_View`.

### `POST /insurance/api/v1.0/payors/{payorId}/addresses` — create address for a payor
- **Body:** `PayorAddressModel`. **Response:** `{ PayorAddressId: int }`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `POST /insurance/api/v1.0/payors/{payorId}/addresses/merge/validate` — validate an address merge
- **Body:** `{ MergedPayorAddressId: int, PayorAddressIds: List<int> }`.
- **Response:** `{ InvalidPayorClaims: Dict<int, List<int>>, InvalidPayorAuthorizations: Dict<int, List<int>> }` — ids of claims/authorizations blocking the merge, keyed by payor address id.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `POST /insurance/api/v1.0/payors/{payorId}/addresses/merge` — execute address merge
- **Body:** `{ MergedPayorAddressId: int, PayorAddressIds: List<int> }`. Merges the listed addresses into the target.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `PUT /insurance/api/v1.0/payors/{payorId}/addresses/{payorAddressId}` — update address
- **Body:** `PayorAddressModel`. **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `DELETE /insurance/api/v1.0/payors/{payorId}/addresses/{payorAddressId}` — delete address
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `GET /insurance/api/v1.0/payors/{payorId}/amb-codes` — list payor AMB codes
- **Response:** `{ PayorId: int, AmbCodes: AmbCodeModel[] }` — same `AmbCodeModel` as in `amb-codes.md`.
- **Permissions:** `PracticeSettings_Carriers_View`.

### `PUT /insurance/api/v1.0/payors/{payorId}/amb-codes` — replace payor AMB codes
- **Body:** `{ InsurancePlanId: int, AmbCodes: AmbCodeModel[] }` — note spec uses `InsurancePlanId` field name in payor body (likely TBD — verify in PDF p.119 whether it should be `PayorId`).
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `GET /insurance/api/v1.0/payors/{payorId}` — get payor details
- **Response:** `PayorModel` (with embedded `AddressDetails`, `ContactDetails`, and template ids).
- **Permissions:** `PracticeSettings_Carriers_View`.

### `POST /insurance/api/v1.0/payors` — create new payor
- **Body:** `PayorModel`. **Response:** `{ PayorId: int }`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `PUT /insurance/api/v1.0/payors/{payorId}` — update payor
- **Body:** `PayorModel`. **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `GET /insurance/api/v1.0/payors/{payorId}/eligibility-rule` — get payor eligibility rule
- **Response:** `{ PayorId: int, RuleJson: FormContainer }`. `FormContainer` shape defined in the "Insurance Plan Eligibility rule" resource (same as before — see eligibility templates).
- **Permissions:** `PracticeSettings_Carriers_View`.

### `PUT /insurance/api/v1.0/payors/{payorId}/eligibility-rule` — update payor eligibility rule
- **Body:** `{ PayorId: int, RuleJson: FormContainer }`.
- **Permissions:** `PracticeSettings_Carriers_View` (spec says View — likely a typo for AddEdit — TBD verify PDF p.130).

### `POST /insurance/api/v1.0/payors/merge/validate` — validate payor merge
- **Body:** `{ MergedPayorId: int, PayorIds: List<int> }`.
- **Response:** `{ InvalidPayorClaims: Dict<int, List<int>>, InvalidPayorAuthorizations: Dict<int, List<int>> }`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `POST /insurance/api/v1.0/payors/merge` — execute payor merge
- **Body:** `{ MergedPayorId: int, PayorIds: List<int> }`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `GET /insurance/api/v1.0/payors/{payorId}/pre-authorization-codes` — list payor pre-auth codes
- **Response:** `{ PayorId: int, PreAuthorizationCodes: int[] }`.
- **Permissions:** `PracticeSettings_Carriers_View`.

### `PUT /insurance/api/v1.0/payors/{payorId}/pre-authorization-codes` — replace payor pre-auth codes
- **Body:** `{ PayorId: int, PreAuthorizationCodes: int[] }`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `GET /insurance/api/v1.0/payors/{payorId}/provider-insurance` — list provider-specific insurance ids
- **Response:** `{ PayorId: int, ProviderInsuranceDetails: ProviderInsuranceDetails[] }`.
- **Permissions:** `PracticeSettings_Plans_View`, `PracticeSettings_Carriers_View`.

### `PUT /insurance/api/v1.0/payors/{payorId}/provider-insurance` — update provider-specific insurance ids
- **Body:** `{ PayorId: int, ProviderInsuranceDetails: ProviderInsuranceDetails[] }`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `PATCH /insurance/api/v1.0/payors/{payorId}/pre-authorization-codes/templates/{templateId}` — attach pre-auth template
- **Body:** none. **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `PATCH /insurance/api/v1.0/payors/{payorId}/eligibility-rule/templates/{templateId}` — attach eligibility rule template
- **Body:** none. **Permissions:** `PracticeSettings_Carriers_AddEdit`.
- **Notes:** spec shows a stray backtick in the path — treat as `insurance/api/v1.0/payors/{payorId}/eligibility-rule/templates/{templateId}`.

### `PATCH /insurance/api/v1.0/payors/{payorId}/amb-codes/templates/{templateId}` — attach AMB template
- **Body:** none. **Permissions:** `PracticeSettings_Carriers_AddEdit`.

### `POST /insurance/api/v1.0/payor-types` — create payor type
- **Body:** `PayorTypeDetailsModel`.
- **Permissions:** `PracticeSettings_Plans_ManageCarrierTypes_AddEdit`.

### `GET /insurance/api/v1.0/payor-types` — list all payor types
- **Response:** array of `PayorTypeDetailsModel`.
- **Permissions:** `PracticeSettings_Plans_View`, `Billing_Statements_GenerateStatements_Generate`, `PracticeSettings_Plans_ManageCarrierTypes_AddEdit`, `PracticeSettings_Plans_Edit`, `Patient_InsuranceInfo_InsuranceDetailsAndEligibility_View`, `PracticeSettings_PaymentsSettings_StatementDetails_View`, `PracticeSettings_PaymentsSettings_StatementSetup_View`.

### `PATCH /api/v1.0/payor-types/{payorTypeId}` — update single payor type
- **Body:** `PayorTypeDetailsModel`.
- **Permissions:** `PracticeSettings_Plans_ManageCarrierTypes_AddEdit`.
- **Notes:** spec path is `api/v1.0/payor-types/...` (no `insurance/` prefix — TBD verify PDF p.134).

### `PUT /insurance/api/v1.0/payor-types` — bulk update payor types
- **Body:** `{ PayorTypes: PayorTypeDetailsModel[] }`.
- **Permissions:** `PracticeSettings_Plans_ManageCarrierTypes_AddEdit`.

### `GET /insurance/api/v1.0/payors/{payorId}/coverage` — get payor coverage
- **Response:** `PayorCoverageModel`.
- **Permissions:** `PracticeSettings_Carriers_View`.

### `PUT /insurance/api/v1.0/payors/{payorId}/coverage` — update payor coverage
- **Body:** `PayorCoverageModel`.
- **Permissions:** `PracticeSettings_Carriers_AddEdit`.

## Fusion mapping

- Target tables:
  - `billing.payor` — `PayorModel` core fields
  - `billing.payor_address` — `PayorAddressModel`
  - `billing.payor_contact` — `PayorContactModel` (may be collapsed into payor row)
  - `billing.payor_type` — `PayorTypeDetailsModel`
  - `billing.payor_coverage*` — payor-level category / additional coverage
  - `billing.payor_provider_insurance` — per-provider ids
  - `billing.payor_pre_auth_code` — list from 7.16
  - `billing.payor_amb_code` — from 7.7 / 7.8
- Ingestion strategy:
  - Initial bulk pull of payors + payor types on billing bootstrap.
  - Subsequent refresh via sync (TBD — spec does not show a modified-after
    endpoint for payors; may need to pull on demand).
- Open questions:
  - `RequireAttachmentsForHigherOrderClaims` — exact semantics? TBD.
  - `IsDefaultAddress` appears typed as literal `True` in spec — treat
    as bool in Fusion schema.
  - Verify PATCH path for single payor type (7.25) really omits `insurance/`.
  - Verify PUT eligibility-rule (7.13) permission is AddEdit, not View.
  - Verify AMB update body field name on 7.8 (`InsurancePlanId` vs `PayorId`).
