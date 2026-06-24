# Worker Report — ENG-426 (Block A: schema registry)

- **Task**: A — Full-fidelity capture contract + schema registry (ingest)
- **Linear**: ENG-426 — https://linear.app/fusion-dental-implants/issue/ENG-426/a-full-fidelity-capture-contract-schema-registry-ingest
- **Role / agent**: orchestrator+worker / claude-code (self-execute)
- **Branch / worktree**: eng-425-full-fidelity-ingestion-v1 / canonical checkout
- **Allowed scope**: packages/ingest, packages/db/alembic/versions, tests/ingest

## What changed (touched files)

- `packages/ingest/models.py` — new `SourceObjectField` ORM model
  (`ingest.source_object_field`), tenant-scoped, unique
  `(tenant_id, provider, object_name, field_name)`; `readable` + `active`
  flags; `first_seen_at`/`last_seen_at`; `meta` JSONB. Rows never deleted.
- `packages/ingest/schemas.py` — `ObservedFieldIn`, `SourceObjectFieldOut`,
  `FieldTypeChange`, `SchemaDiffOut` (the drift shape, with `has_changes`).
- `packages/ingest/repository.py` — `list_object_fields`, `add_object_field`.
- `packages/ingest/service.py` — `sync_object_schema` (reconcile observed
  schema → registry, returns `SchemaDiffOut`, structured drift log) and
  `get_object_schema`. New `_schema_log` logger.
- `packages/db/alembic/versions/20260614_2100_e6f7a8b9c0d1_add_ingest_source_object_field.py`
  — additive migration (down_revision `d5e6f7a8b9c0`).
- `tests/ingest/test_schema_registry_service.py` — 10 tests.

## Design notes

- Completeness lives at the raw layer; the registry only **records** the
  schema and **diffs** it. No domain mapping touched.
- `readable=False` reserves the FLS-blocked-field case for Block B's
  Tooling-API gap detector. Drift surface (structured log + `sync_run.meta`)
  is wired here as a log; `sync_run.meta` write lands in Block C's job.
- Tenant-scoped because the readable field set depends on the tenant's
  provider org + integration-user permissions.

## Tests run / results

- `pytest tests/ingest/test_schema_registry_service.py` → **10 passed**.
- `ruff check` (changed files) → clean.
- `mypy packages/ingest/*` → clean.
- Alembic: `upgrade head` → `downgrade -1` → `upgrade head` OK on local DB;
  `alembic check` → "No new upgrade operations detected" (only pre-existing
  raw_event trgm-index warnings, unrelated).

## Verification status

PASS (local). Not yet committed — awaiting owner go-ahead per workflow rule.

## Risks

- Low. Additive table + additive service methods; no existing behavior changed.

## Suggested next task

Block B (ENG-427) — Salesforce dynamic describe-driven projection +
Tooling-API FLS-gap detector. Higher risk: reworks the SF client + 8 ingest
services and **requires real-data SF verification** before merge.

## Do-not-merge conditions

- Do not merge Block A alone before B is at least reviewed if the bundle PR
  is the integration unit (per mission contract: single bundle branch).
- Cross-runtime review required before integration (contract-changing: new
  shared `ingest` table consumed by B/C/D).
