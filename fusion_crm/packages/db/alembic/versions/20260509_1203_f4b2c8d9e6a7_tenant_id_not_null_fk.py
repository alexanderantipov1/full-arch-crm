"""ENG-123 (4/4): promote `tenant_id` to NOT NULL + FK on every domain table.

Revision ID: f4b2c8d9e6a7
Revises: e3a1b6c7d4f5
Create Date: 2026-05-09 12:03:00.000000+00:00

Final step of the tenant_id fan-out. Migration 2/4 added the column
nullable, migration 3/4 backfilled every existing row. This migration:

1. Sets a server-side DEFAULT on `tenant_id` to the bootstrap tenant
   id (Phase 1 transitional safety net — existing INSERTs that have
   not yet been wired to pass `tenant_id` explicitly default into the
   bootstrap tenant rather than failing with a NOT NULL violation).
   When the per-repository signature sweep lands and every INSERT
   passes `tenant_id` explicitly, a follow-up migration removes this
   default.
2. ALTERs `tenant_id` to NOT NULL on every per-tenant table.
3. ADDs `fk_<table>_tenant_id_tenant` FOREIGN KEY → `tenant.tenant.id`
   with `ON DELETE RESTRICT` (destroying a tenant requires explicit
   service-layer cascade, never silent FK delete).

Order matters: SET DEFAULT before NOT NULL avoids a race where a
concurrent INSERT arrives between the two statements and races the
constraint flip.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b2c8d9e6a7"
down_revision: str | None = "e3a1b6c7d4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Bootstrap tenant id duplicated here from migration 3/4 because Alembic
# revision files do not import each other (each must be self-contained
# so a partial-run downgrade can resurrect the constant cleanly).
BOOTSTRAP_TENANT_ID = "11111111-1111-4111-8111-111111111111"


# Same set as migration 2/4. Order is preserved so 4/4 mirrors 2/4 exactly.
TABLES: tuple[tuple[str, str], ...] = (
    ("identity", "person"),
    ("identity", "person_identifier"),
    ("identity", "source_link"),
    ("identity", "merge_event"),
    ("ops", "lead"),
    ("ops", "followup_task"),
    ("ops", "account"),
    ("phi", "patient_profile"),
    ("phi", "consultation"),
    ("audit", "access_log"),
    ("ingest", "raw_event"),
    ("actor", "actor"),
    ("actor", "actor_identifier"),
    ("auth", "credential"),
    ("auth", "session"),
    ("auth", "api_key"),
    ("interaction", "event"),
    ("integrations", "integration_account"),
    ("integrations", "object_mapping"),
    ("integrations", "sync_run"),
    ("integrations", "cdc_cursor"),
    ("integrations", "external_entity"),
)


def upgrade() -> None:
    for schema, table in TABLES:
        op.alter_column(
            table,
            "tenant_id",
            nullable=False,
            server_default=sa.text(f"'{BOOTSTRAP_TENANT_ID}'::uuid"),
            schema=schema,
        )
        op.create_foreign_key(
            f"fk_{table}_tenant_id_tenant",
            table,
            "tenant",
            ["tenant_id"],
            ["id"],
            source_schema=schema,
            referent_schema="tenant",
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for schema, table in reversed(TABLES):
        op.drop_constraint(
            f"fk_{table}_tenant_id_tenant",
            table,
            schema=schema,
            type_="foreignkey",
        )
        op.alter_column(
            table,
            "tenant_id",
            nullable=True,
            server_default=None,
            schema=schema,
        )
