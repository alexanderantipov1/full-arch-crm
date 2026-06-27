# Overview — CareStack Developer API

- **Protocol:** REST over HTTPS, JSON request/response bodies.
- **Version in URL:** `v1.0` (the `{version}` placeholder in spec
  paths is always `v1.0` for the v1.0.x family).
- **Base URL** for resource endpoints: supplied by CareStack per
  environment/account. Usually of the form `https://<account>.carestack.com`
  (exact host from onboarding email).
- **Auth:** OAuth2 password grant against a separate Identity
  Provider host (default `https://id.carestack.com`). See
  [`01-authentication.md`](./01-authentication.md).
- **Rate limits / pagination:** see [`02-conventions.md`](./02-conventions.md).
- **Errors:** standard HTTP codes; see [`03-errors.md`](./03-errors.md).

## Request envelope (typical)

```
POST /v1.0/patients HTTP/1.1
Host: <account>.carestack.com
Authorization: Bearer <jwt>
Content-Type: application/json
Accept: application/json

{ ...JSON body... }
```

## Response shape

- `2xx` → JSON body of the resource (or 204 No Content on some writes).
- `4xx` / `5xx` → JSON error envelope (see `03-errors.md`).

## Big picture — resource families

| Family | What it covers |
|---|---|
| Clinic config | `Location`, `Facility`, `Operatory`, `Provider`, `User` |
| People | `Patient`, `Referral source` |
| Scheduling | `Appointment`, `Find slot` |
| Clinical | `Periodontal charting`, `Treatment plan`, `Medical alerts`, `Medications`, `Vital monitor`, `Patient notes` |
| Billing | `Payment summary`, `Payment types`, `Adjustment`, `Invoice` (sync), `Accounting procedure/transaction` (sync) |
| Insurance | Whole separate `Insurance Manager` module |
| Operational | `Document upload`, `Referral document` |
| Sync | `Patient sync`, `Appointment sync`, `Treatment procedure sync` (+ existing), `Invoice sync`, `Accounting procedure/transaction sync` |
| Search | `Patient search`, `Appointment search` |
