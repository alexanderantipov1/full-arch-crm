"""raw_event person-page perf indexes (ENG-412)

The person detail page (``GET /persons/{id}``) runs several aggregates over
``ingest.raw_event`` (1.18M rows locally). The table had no index on
``(source, event_type)`` nor on ``payload->>'patientId'``, so every query was
a full Seq Scan. Measured locally: one accounting dedup aggregation 1364ms,
the household candidate scan 2517ms. This revision adds:

- ``ix_raw_event_dedup`` — composite btree
  ``(tenant_id, source, event_type, external_id, received_at)`` turning the
  "latest per external_id" dedup aggregations into Index-Only Scans
  (1364ms → 192ms).
- ``ix_raw_event_patient_id`` — expression btree on
  ``(tenant_id, source, event_type, (payload->>'patientId'))`` for the
  ``patientId IN (...)`` filters (accounting / origin-context).
- ``ix_raw_event_cs_patient_{mobile,phone,workphone}_trgm`` — partial
  pg_trgm GIN indexes on the digits-only phone projection used by the
  household ILIKE-substring pre-filter.
- ``ix_raw_event_cs_patient_email_lower`` — partial btree on
  ``lower(payload->>'email')`` so the household OR-filter's email branch is
  also indexable; without it the OR falls back to a Seq Scan (1270ms → 1.1ms
  with the full BitmapOr).

Indexes are built with ``CREATE INDEX CONCURRENTLY`` inside an autocommit
block: the table is large and live in prod, so we must not hold a write lock.
``CONCURRENTLY`` cannot run inside a transaction, hence the autocommit block.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-13 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The functional expressions here MUST stay byte-identical to the query
# expressions in packages/ingest/repository.py, or the planner will not use
# the index.
_CS_PATIENT_WHERE = (
    "source = 'carestack' AND event_type = 'carestack.patient.upsert'"
)

_TRGM_INDEXES = (
    ("ix_raw_event_cs_patient_mobile_trgm", "mobile"),
    ("ix_raw_event_cs_patient_phone_trgm", "phoneWithExt"),
    ("ix_raw_event_cs_patient_workphone_trgm", "workPhoneWithExt"),
)


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_raw_event_dedup "
            "ON ingest.raw_event "
            "(tenant_id, source, event_type, external_id, received_at)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_raw_event_patient_id "
            "ON ingest.raw_event "
            "(tenant_id, source, event_type, (payload ->> 'patientId'))"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_raw_event_cs_patient_email_lower "
            "ON ingest.raw_event (lower(payload ->> 'email')) "
            f"WHERE {_CS_PATIENT_WHERE}"
        )
        for index_name, field in _TRGM_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                "ON ingest.raw_event USING gin "
                f"(regexp_replace(payload ->> '{field}', '\\D', '', 'g') "
                "gin_trgm_ops) "
                f"WHERE {_CS_PATIENT_WHERE}"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for index_name, _ in _TRGM_INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS ingest.{index_name}")
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS "
            "ingest.ix_raw_event_cs_patient_email_lower"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ingest.ix_raw_event_patient_id")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ingest.ix_raw_event_dedup")
        # pg_trgm extension is left in place — other features may rely on it.
