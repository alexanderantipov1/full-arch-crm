# Adjustments

**Fusion domain:** `billing` (new, TBD)
**PHI:** mixed — the code catalog itself is non-PHI; adjustments posted to patient accounts are PHI-adjacent (billing data).
**Spec section:** Resource 20 (CareStack Developer API v1.0.45)

## Object fields

### Adjustment code

| field | type | notes |
|---|---|---|
| AdjustmentCodeID | int | unique identifier |
| Category | int | 1 Production, 2 Collection |
| Action | int | see Adjustment Action table below |
| ApplyAs | int | 1 Amount, 2 Percentage |
| AdjustmentCode | string | code |
| Description | string | |
| Status | bool | active flag |
| IsSystemAdjustmentCode | bool | true if system-defined |

### AdjustmentAction values

| value | description |
|---|---|
| 1 | Add to Patient |
| 2 | Add to Insurance |
| 3 | Deduct from Patient |
| 4 | Deduct from Insurance |
| 5 | Transfer to Patient |
| 6 | Transfer to Insurance |

## Endpoints

### `GET /v1.0/adjustments/codes` — list adjustment codes
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of adjustment code objects

## Fusion mapping

- Target table(s): `billing.adjustment_code` (new domain, TBD).
- Ingestion strategy: sync (low-frequency reference data).
- Open questions:
  - Spec documents only the code catalog — is there a separate endpoint to list applied adjustments per patient? Not in Resource 20; check the Sync APIs (accounting transactions).
