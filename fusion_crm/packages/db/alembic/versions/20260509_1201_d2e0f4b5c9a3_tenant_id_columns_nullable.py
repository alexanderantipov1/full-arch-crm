"""ENG-123 (2/4): add nullable `tenant_id` to every domain table.

Revision ID: d2e0f4b5c9a3
Revises: c1f9d3a4b8e2
Create Date: 2026-05-09 12:01:00.000000+00:00

Adds `tenant_id UUID NULL` to every per-tenant table across identity,
ops, phi, audit, ingest, actor, auth, interaction, integrations. NO
NOT NULL, NO FK yet — migration 3/4 backfills, migration 4/4 promotes.

Tables that are global by nature (none in M1) skip this column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e0f4b5c9a3"
down_revision: str | None = "c1f9d3a4b8e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (schema, table) pairs — every existing per-tenant table.
TABLES: tuple[tuple[str, str], ...] = (
    # identity
    ("identity", "person"),
    ("identity", "person_identifier"),
    ("identity", "source_link"),
    ("identity", "merge_event"),
    # ops
    ("ops", "lead"),
    ("ops", "followup_task"),
    ("ops", "account"),
    # phi
    ("phi", "patient_profile"),
    ("phi", "consultation"),
    # audit
    ("audit", "access_log"),
    # ingest
    ("ingest", "raw_event"),
    # actor
    ("actor", "actor"),
    ("actor", "actor_identifier"),
    # auth
    ("auth", "credential"),
    ("auth", "session"),
    ("auth", "api_key"),
    # interaction
    ("interaction", "event"),
    # integrations
    ("integrations", "integration_account"),
    ("integrations", "object_mapping"),
    ("integrations", "sync_run"),
    ("integrations", "cdc_cursor"),
    ("integrations", "external_entity"),
)


def upgrade() -> None:
    for schema, table in TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", sa.UUID(), nullable=True),
            schema=schema,
        )
        # Lookups by tenant are common for every per-tenant table; create
        # the index now (cheap on empty/near-empty rows; the seed migration
        # backfills on top).
        op.create_index(
            f"ix_{table}_tenant_id",
            table,
            ["tenant_id"],
            schema=schema,
        )


def downgrade() -> None:
    for schema, table in reversed(TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table, schema=schema)
        op.drop_column(table, "tenant_id", schema=schema)
