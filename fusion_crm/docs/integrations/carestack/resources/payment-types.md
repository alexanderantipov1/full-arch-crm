# Payment Types

**Fusion domain:** `catalog` (new, TBD)
**PHI:** no — reference list of payment methods and their posting rules.
**Spec section:** Resource 23 (CareStack Developer API v1.0.45)

## Object fields

### PaymentType

| field | type | notes |
|---|---|---|
| PaymentTypeId | int | unique identifier |
| Name | string | display name |
| PaymentCategory | string | category of payment type |
| TransactionCharge | decimal | transaction fee |
| IsUpdatable | bool | whether the entity can be edited |
| IncludePatientPayments | bool | |
| IncludePatientRefunds | bool | |
| IncludeInsurancePayments | bool | |
| IncludeInsuranceRefunds | bool | |
| IncludeCapitation | bool | |
| IncludeCollectionPayments | bool | |
| IsUnsettled | bool | whether the payment is unsettled |
| IsUnsettledByDefault | bool | default unsettled flag |
| AdditionalFields | AdditionalFieldsModel[] | extra fields attached to the payment type |
| IsAutoPostEnabled | bool | auto-posting flag |

### AdditionalFieldsModel

| field | type | notes |
|---|---|---|
| Name | string | field name |
| PaymentTypeId | int | parent payment type id |
| AdditionalFieldId | int | field identifier |
| IsPatientPayment | bool | |
| IsInsurancePayment | bool | |
| IsCollectionAgencyPayment | bool | |

## Endpoints

### `GET /v1.0/payment-types` — list all payment types
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of PaymentType objects

## Fusion mapping

- Target table(s): `catalog.payment_type`, `catalog.payment_type_additional_field` (new domain, TBD).
- Ingestion strategy: sync (low-frequency reference data).
- Open questions: none.
