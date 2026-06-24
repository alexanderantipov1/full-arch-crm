# CLAUDE.md — `packages/enrichment`

A small, clean domain for *our own* fields layered over the canonical
entities — the manual-enrichment store (ENG-439, Block F). Annotations
are written from the staff UI now and from the chat action path
(Block G) and the AI-agent tools layer later, all through ONE service.

Read the root `CLAUDE.md` and `packages/CLAUDE.md` first.

## Schema (`enrichment`)

The 9th canonical schema (user-approved with ENG-439). Created by the
migration `add_enrichment_record_annotation` (which runs
`CREATE SCHEMA IF NOT EXISTS enrichment` first) and by
`infra/docker/init-schemas.sql` on a fresh DB.

- **`record_annotation`** — one of our own fields set on a canonical
  entity. PK = UUID (codebase invariant #8). `TenantScopedMixin` adds
  `tenant_id`; `TimestampMixin` adds `created_at` / `updated_at`.
  Columns:
    - `subject_type` `String(64)` — the kind of entity
      (`"person"`, `"lead"`, `"opportunity"`, …).
    - `subject_id` `UUID` — the entity id. When
      `subject_type == "person"` this IS the `person_uid`. NOT a DB
      foreign key: the subject can live in any schema, so a single FK
      target does not exist.
    - `key` `String(128)` — the annotation field name
      (`"consult_notes"`, `"preferred_contact_time"`, …).
    - `value` `JSONB NOT NULL DEFAULT '{}'` — flexible value. Free
      text rides as `{"text": "..."}`.
    - `source` `String(16)` — `CHECK source IN ('ui','chat','agent')`.
    - `author_actor_id` `UUID | None` — who set it. DB-level FK to
      `actor.actor.id` (`ON DELETE SET NULL`); we never import the
      actor models in Python.
    - `note` `Text | None` — optional human note.
  Indexes: `ix_record_annotation_tenant_id (tenant_id)`,
  `ix_record_annotation_subject (tenant_id, subject_type, subject_id)`.

## Append-friendly, NOT unique-by-key

`(tenant_id, subject_type, subject_id, key)` is intentionally **not**
unique. The table keeps the full history of annotations — re-setting a
key inserts a new row rather than overwriting. Callers that want the
current value per key use `EnrichmentService.latest_per_key`, which
collapses the newest row per key on read. If a future feature needs
true upsert-by-key semantics, add the unique index in a new migration
and switch the service to `ON CONFLICT DO UPDATE` — but that is a
deliberate behaviour change, not a default.

## Service surface

`EnrichmentService` is the public surface:

- `add_annotation(tenant_id, AnnotationIn, *, principal)` — writes one
  row and one `audit.access_log` row in the same unit of work. Audit
  `action="enrichment.annotation.add"`,
  `resource="enrichment.record_annotation"`,
  `person_uid = subject_id` when `subject_type == "person"`. The audit
  `extra` carries keys/ids only (`subject_type`, `subject_id`, `key`,
  `source`) — never the annotation `value` (which may hold free
  text / PII).
- `list_for_subject(tenant_id, subject_type, subject_id)` — all
  annotations for a subject, newest first, tenant-scoped.
- `latest_per_key(tenant_id, subject_type, subject_id)` — the newest
  annotation per key.

## Cross-package import rules

- **Allowed in:** `tenant` (UUID column only — no model import),
  `actor` (DB-level FK for `author_actor_id`; no model import),
  `audit` (write-only via `AuditService`), `core`. Everything else ✗.
- **Imported by:** every other package via the SERVICE only. The
  models and the repository are private — no
  `from packages.enrichment.models` / `.repository` outside this
  directory.

## Hard rules

- **No PHI in audit `extra`.** The annotation `value` may contain free
  text or PII; it never enters the audit row. Keep `extra` to
  keys/ids.
- **The repository and the service never commit and never roll back —
  they only flush.** The caller boundary owns the unit of work (the
  API `get_db` dependency, a worker job, a test).
- **`source` is validated twice** — by the Pydantic DTO and by the DB
  CHECK constraint — so callers that bypass the DTO still fail closed.
- **One audit row per write.** The annotation and its audit row share
  the unit of work; they commit or roll back together.
