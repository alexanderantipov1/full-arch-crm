# Insurance Settings

**Fusion domain:** billing (TBD)
**PHI:** no — account-wide toggles, not patient-scoped
**Spec section:** Insurance Manager — 1.1, 1.2 (CareStack Developer API v1.0.45)

## Object fields

### InsuranceSettings

| field | type | notes |
|---|---|---|
| IsDualCoverageEnabled | bool | whether dual-coverage billing is on |
| RequireInsuranceVerification | bool | enforce verification step |
| PayorTypeSettings | PayorTypeSettings | nested per-payor-type toggles |

### PayorTypeSettings

| field | type | notes |
|---|---|---|
| IsEnabled | bool | payor-type gating enabled |
| IsRequired | bool | payor-type required on plans |

## Endpoints

### `GET /insurance/api/v1.0/settings` — fetch account insurance settings
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — `InsuranceSettings`
- **Notes:** singleton per account.

### `POST /insurance/api/v1.0/settings` — update account insurance settings
- **Path params:** none
- **Query params:** none
- **Body:** `InsuranceSettings` (same shape as GET response)
- **Success:** 200 — updated settings (TBD — verify in PDF p.70)
- **Notes:** uses POST, not PUT. Replaces the full settings record.

## Fusion mapping

- Target: `billing.insurance_settings` — single row per Fusion instance
  (or key/value rows if we want per-setting audit).
- Ingestion: on-demand (admin UI hits CareStack directly) or one-shot
  bootstrap on first billing enablement.
- Open questions:
  - Do we mirror settings locally at all, or always read-through?
  - Does CareStack expose audit metadata (who changed it, when)?
