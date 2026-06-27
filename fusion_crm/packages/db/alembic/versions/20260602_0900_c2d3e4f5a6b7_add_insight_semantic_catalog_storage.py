"""add insight semantic catalog storage

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-02 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "insight"


def upgrade() -> None:
    # Existing dev/test databases can predate the init-schemas.sql insight entry.
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "semantic_catalog_proposal",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "proposal_type",
            sa.String(length=32),
            server_default=sa.text("'mapping'"),
            nullable=False,
        ),
        sa.Column("raw_value", sa.String(length=512), nullable=False),
        sa.Column("source_system", sa.String(length=96), nullable=False),
        sa.Column("source_field", sa.String(length=240), nullable=False),
        sa.Column("suggested_term", sa.String(length=240), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "synonyms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column(
            "affected_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_read_models",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_reports",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_dashboard_panels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_chat_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_agent_briefs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_references",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'proposed'"),
            nullable=False,
        ),
        sa.Column("created_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_semantic_catalog_proposal_confidence_range"),
        ),
        sa.CheckConstraint(
            "proposal_type IN ('mapping', 'source_drift', 'gap')",
            name=op.f("ck_semantic_catalog_proposal_proposal_type"),
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'unresolved')",
            name=op.f("ck_semantic_catalog_proposal_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_semantic_catalog_proposal_created_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_semantic_catalog_proposal_reviewed_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_semantic_catalog_proposal_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semantic_catalog_proposal")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_catalog_proposal_tenant_status",
        "semantic_catalog_proposal",
        ["tenant_id", "status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_catalog_proposal_tenant_term",
        "semantic_catalog_proposal",
        ["tenant_id", "suggested_term"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "semantic_catalog_version",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("term", sa.String(length=240), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "review_status",
            sa.String(length=24),
            server_default=sa.text("'approved'"),
            nullable=False,
        ),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "synonyms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "allowed_data_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "data_classes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "allowed_outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "canonical_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "row_level_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "aggregate_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "used_by",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_references",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "affected_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_read_models",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_reports",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_dashboard_panels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_chat_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_agent_briefs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("approved_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            "review_status IN ('approved')",
            name=op.f("ck_semantic_catalog_version_review_status"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_semantic_catalog_version_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_semantic_catalog_version_approved_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["previous_version_id"],
            [f"{SCHEMA}.semantic_catalog_version.id"],
            name=op.f("fk_semantic_catalog_version_previous_version_id_semantic_catalog_version"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            [f"{SCHEMA}.semantic_catalog_proposal.id"],
            name=op.f("fk_semantic_catalog_version_proposal_id_semantic_catalog_proposal"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_semantic_catalog_version_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semantic_catalog_version")),
        sa.UniqueConstraint(
            "tenant_id",
            "term",
            "version",
            name=op.f("uq_semantic_catalog_version_tenant_term_version"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_catalog_version_tenant_status",
        "semantic_catalog_version",
        ["tenant_id", "review_status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_catalog_version_tenant_term",
        "semantic_catalog_version",
        ["tenant_id", "term"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_foreign_key(
        op.f("fk_semantic_catalog_proposal_approved_version_id_semantic_catalog_version"),
        "semantic_catalog_proposal",
        "semantic_catalog_version",
        ["approved_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_semantic_catalog_proposal_approved_version_id_semantic_catalog_version"),
        "semantic_catalog_proposal",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_semantic_catalog_version_tenant_term",
        table_name="semantic_catalog_version",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_semantic_catalog_version_tenant_status",
        table_name="semantic_catalog_version",
        schema=SCHEMA,
    )
    op.drop_table("semantic_catalog_version", schema=SCHEMA)
    op.drop_index(
        "ix_semantic_catalog_proposal_tenant_term",
        table_name="semantic_catalog_proposal",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_semantic_catalog_proposal_tenant_status",
        table_name="semantic_catalog_proposal",
        schema=SCHEMA,
    )
    op.drop_table("semantic_catalog_proposal", schema=SCHEMA)
