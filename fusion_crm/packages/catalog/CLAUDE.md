# CLAUDE.md — `packages/catalog`

Workspace-wide reference data sourced from external systems. First
member is the CareStack procedure-code catalog
(`catalog.procedure_code`) — a CDT/CPT lookup table that other
domains join against to resolve an integer `procedureCodeId` into a
`code` string + `description`.

Read the root `CLAUDE.md` and `packages/CLAUDE.md` first.

## Schema (`catalog`)

- **`procedure_code`** — CareStack procedure-code catalog.
  PK = UUID (codebase invariant #8 — UUID primary keys everywhere).
  Business key = `carestack_code_id` (`BIGINT NOT NULL UNIQUE`) — the
  CareStack-assigned procedure-code id (e.g. `117408`) that callers
  pass through the resolver. Columns: `id` (UUID PK),
  `carestack_code_id`, `code`, `description`, `code_type_id`,
  `cdt_category_id`, `payload` (JSONB verbatim entry), `created_at`,
  `updated_at`. Per
  `docs/integrations/carestack/resources/procedure-codes.md`.

## Tenant scoping — workspace-wide, by design

Every other per-tenant domain in this codebase carries a `tenant_id`.
The procedure-code catalog deliberately does not. Reasoning:

1. CDT codes are the ADA-published US dental code standard. They are
   a fixed reference list, not per-tenant data.
2. The CareStack `carestack_code_id` column is a CareStack-internal
   surrogate. Today we operate against a single CareStack account, so
   the id namespace is effectively global. If a future tenant
   produces a colliding id we revisit then — the upsert key is the
   `carestack_code_id` UNIQUE constraint, so a tenant scope can be
   added without a data rewrite.
3. Workspace-wide storage gives every domain a trivial single-column
   join through the resolver service without threading `tenant_id`
   through analytics / timeline queries.

## Primary key vs business key

The local PK is a UUID (per the root codebase invariant); the
CareStack-assigned integer id is stored as `carestack_code_id` and
carries the `UNIQUE` constraint that the idempotent upsert keys on
(`ON CONFLICT (carestack_code_id) DO UPDATE`). Callers everywhere
work in CareStack-id space — `resolve_procedure_codes(ids)` accepts
the integer ids extracted from raw_event payloads and returns
`{carestack_code_id: (code, description)}`.

## Cross-package import rules

The catalog domain imports only `core` (logging, types). It is read
by `interaction`, `ops`, future analytics, and the AI-agent tools
layer — those domains call `CatalogService.resolve_procedure_codes`
and never import the model or repository directly.

## Service responsibilities

`CatalogService` is the public surface:

- `sync_procedure_codes_by_id(client, code_ids, ...)` — **PRIMARY** sync
  (ENG-538). Resolves each id via `GET /v1.0/procedure-codes/{id}` and
  upserts NEW/CHANGED rows. Throttled + backoff on 429/5xx. Detects drift
  (NEW codes, CHANGED code/description), surfaces it in the returned
  `ProcedureCodeByIdSyncOut`, a structured `catalog.procedure_codes.drift`
  log, and a `catalog.procedure_codes.needs_review` log. The work-list (the
  distinct `procedureCodeId`s seen in `ingest.raw_event` treatment-procedure
  payloads) is enumerated by the caller boundary via
  `IngestService.distinct_treatment_procedure_code_ids` — `catalog` may not
  read `ingest`.
- `ensure_procedure_codes(client, ids)` — lazy self-fill: resolve+upsert only
  the ids NOT already cached; returns the newly-inserted ids. Backs the
  treatment-procedure ingest self-fill so a brand-new custom code resolves on
  first sight with no manual backfill.
- `sync_procedure_codes_from_carestack(client, ...)` — DEPRECATED fallback.
  The flat `/v1.0/procedure-codes` LIST endpoint is BROKEN on the real
  account (returns only junk "Other" codes), so this is never relied on; use
  the by-id path. Read-only; no writes.
- `resolve_procedure_codes(ids) -> {carestack_code_id: (code, description)}` —
  batch lookup used by timeline / payments / analytics. Input ids
  are CareStack procedure-code ids.
- `count_procedure_codes()` — total row count (operator + tests).

Drift query (operator): NEW codes since a time → `WHERE created_at > :since`;
CHANGED codes → `WHERE updated_at > :since`. The by-id sync upserts only
NEW/CHANGED rows and bumps `updated_at` on conflict, so both timestamps are
truthful (an unchanged re-sync writes nothing).

## Hard rules

- Read-only CareStack pull. NEVER POST / PUT / DELETE against
  `/procedure-codes`.
- No PHI. Codes are reference data; structured logs may include
  ids, codes, and counts.
- The repository does not commit. The boundary owns the unit of
  work (operator script, scheduled job, test).
- The upsert is idempotent
  (`ON CONFLICT (carestack_code_id) DO UPDATE`). Re-running the sync
  produces no duplicates and no data drift on unchanged catalog rows.
- The Cloud Run scheduler entry is intentionally low-frequency
  (weekly). The CareStack CDT catalog changes rarely (ADA publishes
  annually); a chatty sync would waste CareStack rate-limit budget
  for no gain.
