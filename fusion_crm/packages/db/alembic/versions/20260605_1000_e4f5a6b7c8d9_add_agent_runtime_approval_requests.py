"""add agent runtime approval requests

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-05 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "audit"


def upgrade() -> None:
    op.create_table(
        "agent_runtime_approval_request",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_actor_email", sa.String(length=320), nullable=True),
        sa.Column("decided_by_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_actor_email", sa.String(length=320), nullable=True),
        sa.Column("agent_name", sa.String(length=160), nullable=False),
        sa.Column("tool_id", sa.String(length=160), nullable=True),
        sa.Column("target_kind", sa.String(length=80), nullable=False),
        sa.Column("target_ref", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("requested_action", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "data_classes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affected_surfaces",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "risk_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("approval_posture", sa.String(length=120), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=True),
        sa.Column("edit_summary", sa.Text(), nullable=True),
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
            "status IN ('pending', 'approved', 'rejected', 'needs_edit', 'unresolved')",
            name=op.f("ck_agent_runtime_approval_request_status"),
        ),
        sa.CheckConstraint(
            "target_kind IN ("
            "'semantic_catalog_mapping_proposal', "
            "'semantic_catalog_impact_preview', "
            "'large_analysis_run', "
            "'export_request', "
            "'write_tool_execution'"
            ")",
            name=op.f("ck_agent_runtime_approval_request_target_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["audit.agent_runtime_run.id"],
            name=op.f("fk_agent_runtime_approval_request_source_run_id_agent_runtime_run"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_agent_runtime_approval_request_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_agent_runtime_approval_request"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_runtime_approval_tenant_created_at",
        "agent_runtime_approval_request",
        ["tenant_id", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_runtime_approval_tenant_status",
        "agent_runtime_approval_request",
        ["tenant_id", "status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_runtime_approval_tenant_target_kind",
        "agent_runtime_approval_request",
        ["tenant_id", "target_kind"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_runtime_approval_tenant_target_kind",
        table_name="agent_runtime_approval_request",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_agent_runtime_approval_tenant_status",
        table_name="agent_runtime_approval_request",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_agent_runtime_approval_tenant_created_at",
        table_name="agent_runtime_approval_request",
        schema=SCHEMA,
    )
    op.drop_table("agent_runtime_approval_request", schema=SCHEMA)
