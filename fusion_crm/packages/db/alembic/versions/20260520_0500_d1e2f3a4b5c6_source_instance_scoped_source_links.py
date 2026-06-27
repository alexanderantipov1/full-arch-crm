"""ENG-190: source-instance scoped external source links.

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f1a2b3
Create Date: 2026-05-20 05:00:00.000000+00:00

Adds first-class ``source_instance`` to ``identity.source_link`` so provider
and import record IDs are scoped to a specific CRM/PMS/import instance. The
old partial unique index on ``(source_system, source_kind, source_id)`` is
replaced by a tenant-scoped, source-instance-aware key:

``(tenant_id, source_system, source_instance, source_kind, source_id)``
``WHERE source_id IS NOT NULL``.

``ingest.normalized_person_hint`` gets the same column so ingest-side match
inputs and local source-data projections can use the exact source-link key.
Existing single-instance rows are backfilled to explicit legacy slugs such as
``salesforce-main`` and ``carestack-main``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c7d8e9f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SOURCE_INSTANCE_CASE = """
CASE source_system
    WHEN 'salesforce' THEN 'salesforce-main'
    WHEN 'carestack' THEN 'carestack-main'
    WHEN 'twilio' THEN 'twilio-main'
    WHEN 'vapi' THEN 'vapi-main'
    WHEN 'web_form' THEN 'web-form-main'
    WHEN 'manual' THEN 'manual-main'
    WHEN 'import' THEN 'import-main'
    ELSE source_system || '-main'
END
"""


def upgrade() -> None:
    op.add_column(
        "source_link",
        sa.Column("source_instance", sa.String(length=96), nullable=True),
        schema="identity",
    )
    op.execute(
        sa.text(
            f"""
            UPDATE identity.source_link
            SET source_instance = {SOURCE_INSTANCE_CASE}
            WHERE source_instance IS NULL
            """
        )
    )
    op.alter_column(
        "source_link",
        "source_instance",
        existing_type=sa.String(length=96),
        nullable=False,
        schema="identity",
    )
    op.drop_index("uq_source_link_external", table_name="source_link", schema="identity")
    op.drop_index("ix_source_link_source", table_name="source_link", schema="identity")
    op.create_index(
        "ix_source_link_source",
        "source_link",
        ["source_system", "source_instance", "source_kind"],
        schema="identity",
    )
    op.create_index(
        "uq_source_link_external",
        "source_link",
        ["tenant_id", "source_system", "source_instance", "source_kind", "source_id"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )

    op.add_column(
        "normalized_person_hint",
        sa.Column("source_instance", sa.String(length=96), nullable=True),
        schema="ingest",
    )
    op.execute(
        sa.text(
            f"""
            UPDATE ingest.normalized_person_hint
            SET source_instance = {SOURCE_INSTANCE_CASE}
            WHERE source_instance IS NULL
            """
        )
    )
    op.alter_column(
        "normalized_person_hint",
        "source_instance",
        existing_type=sa.String(length=96),
        nullable=False,
        schema="ingest",
    )
    op.drop_index(
        "ix_normalized_person_hint_source",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_source",
        "normalized_person_hint",
        ["tenant_id", "source_system", "source_instance", "source_kind", "source_id"],
        schema="ingest",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_normalized_person_hint_source",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_source",
        "normalized_person_hint",
        ["tenant_id", "source_system", "source_kind", "source_id"],
        schema="ingest",
    )
    op.drop_column("normalized_person_hint", "source_instance", schema="ingest")

    op.drop_index("uq_source_link_external", table_name="source_link", schema="identity")
    op.drop_index("ix_source_link_source", table_name="source_link", schema="identity")
    op.create_index(
        "ix_source_link_source",
        "source_link",
        ["source_system", "source_kind"],
        schema="identity",
    )
    op.create_index(
        "uq_source_link_external",
        "source_link",
        ["source_system", "source_kind", "source_id"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("source_id IS NOT NULL"),
    )
    op.drop_column("source_link", "source_instance", schema="identity")
