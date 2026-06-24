"""ENG-439 (Block F): add enrichment.record_annotation (manual-enrichment store).

Revision ID: 37f5ec4af909
Revises: 4fe9f2b9f55a
Create Date: 2026-06-15 06:00:00.000000+00:00

Additive only — creates the 9th canonical schema ``enrichment`` (user-approved
with ENG-439) and its single table ``enrichment.record_annotation``: *our own*
fields layered over canonical entities, written from the staff UI now and the
chat / agent action paths later.

The schema is created here with ``CREATE SCHEMA IF NOT EXISTS enrichment`` so
existing databases (which do not re-run ``init-schemas.sql``) get it; fresh
databases also get it from ``infra/docker/init-schemas.sql``.

Constraints/indexes mirror :class:`packages.enrichment.models.RecordAnnotation`:

* ``CHECK source IN ('ui','chat','agent')`` — the write path provenance.
* ``ix_record_annotation_tenant_id`` — tenant-wide scans.
* ``ix_record_annotation_subject`` — per-subject annotation lookups.

``subject_id`` is intentionally NOT a foreign key (the subject can live in any
schema). ``author_actor_id`` is a DB-level FK to ``actor.actor.id``
(``ON DELETE SET NULL``); ``tenant_id`` FKs ``tenant.tenant.id`` via the mixin.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "37f5ec4af909"
down_revision: str | None = "4fe9f2b9f55a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS enrichment")
    op.create_table(
        "record_annotation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("author_actor_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('ui', 'chat', 'agent')",
            name=op.f("ck_record_annotation_source"),
        ),
        sa.ForeignKeyConstraint(
            ["author_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_record_annotation_author_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_record_annotation_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_annotation")),
        schema="enrichment",
    )
    op.create_index(
        "ix_record_annotation_tenant_id",
        "record_annotation",
        ["tenant_id"],
        schema="enrichment",
    )
    op.create_index(
        "ix_record_annotation_subject",
        "record_annotation",
        ["tenant_id", "subject_type", "subject_id"],
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_record_annotation_subject",
        table_name="record_annotation",
        schema="enrichment",
    )
    op.drop_index(
        "ix_record_annotation_tenant_id",
        table_name="record_annotation",
        schema="enrichment",
    )
    op.drop_table("record_annotation", schema="enrichment")
    # The schema holds ONLY record_annotation (dropped above), so a plain
    # DROP SCHEMA without CASCADE is correct and safer — it will refuse rather
    # than silently destroy anything unexpected that crept in.
    op.execute("DROP SCHEMA IF EXISTS enrichment")
