# Procedure Code

**Fusion domain:** `catalog` (ENG-420 — `catalog.procedure_code`)
**PHI:** no — reference code list (CDT/CPT-style).
**Spec section:** Resource 10 (CareStack Developer API v1.0.45)

## Object fields

| field | type | notes |
|---|---|---|
| id | integer | procedure code id |
| code | string | code name |
| description | string | description of code |
| codeTypeId | integer | 1 Dental, 2 Medical, 3 Other |
| cdtCategoryId | integer | 0 Other, 1 Diagnostic, 2 Preventive, 3 Restorative, 4 Endodontics, 5 Periodontics, 6 Prosthodontics-Removable, 7 Maxillofacial Prosthetics, 8 Implant Services, 9 Prosthodontics-Fixed, 10 Oral and Maxillofacial Surgery, 11 Orthodontics, 12 Adjunctive General Services |

## Endpoints

### `GET /v1.0/procedure-codes/{id}` — one procedure code by id (PRIMARY)
- **Path params:** `id` (integer procedure-code id)
- **Body:** none
- **Success:** 200 — a single Procedure Code object
- **ENG-538:** this is the **primary** catalog source. Verified to resolve
  every real entry (e.g. `6100` → `D6010`, `228501` → custom `D6010.A`).

### `GET /v1.0/procedure-codes` — list all procedure codes (BROKEN — do not use)
- **Path params:** none
- **Query params:** none
- **Body:** none
- **Success:** 200 — array of Procedure Code objects
- **ENG-538 finding:** on the real account this returns only ~20 junk
  "Other" codes (e.g. id `437751`, code "$50 Off Tx", `cdtCategoryId=0`)
  regardless of paging, and NEVER the CDT codes treatment procedures
  reference. Retained only as a harmless fallback; the by-id endpoint is the
  catalog source of truth.

## Fusion mapping

- Target table: `catalog.procedure_code`. PK = UUID (codebase
  invariant #8). Business key = `carestack_code_id`
  (`BIGINT NOT NULL UNIQUE`) — the CareStack-assigned procedure-code
  id. Columns: `id` (UUID PK), `carestack_code_id`, `code`,
  `description`, `code_type_id`, `cdt_category_id`, `payload` (JSONB
  verbatim entry), `created_at`, `updated_at`. Workspace-wide — no
  `tenant_id` (see `packages/catalog/CLAUDE.md` for the rationale).
- Ingestion strategy (ENG-538): read-only **by-id** sync via
  `CatalogService.sync_procedure_codes_by_id` over the distinct
  `procedureCodeId`s observed in `ingest.raw_event` treatment-procedure
  payloads (enumerated through `IngestService`). Idempotent
  (`ON CONFLICT (carestack_code_id) DO UPDATE`, only NEW/CHANGED rows
  written). Self-fill: the treatment-procedure ingest resolves an unseen
  code on first sight via `CatalogService.ensure_procedure_codes`. Drift
  (NEW/CHANGED) surfaced in logs + the sync result. Operator backfill:
  `infra/scripts/backfill_procedure_codes.py`. Scheduled refresh:
  `fusion-job-cs-procedure-codes` (Cloud Run Job, weekly Mon 11:23 UTC).
- Resolution helper: `CatalogService.resolve_procedure_codes(ids)
  -> {carestack_code_id: (code, description)}` for timeline /
  payments / analytics (ENG-419) joins. Inputs are CareStack
  procedure-code ids.
- Open questions: none.
