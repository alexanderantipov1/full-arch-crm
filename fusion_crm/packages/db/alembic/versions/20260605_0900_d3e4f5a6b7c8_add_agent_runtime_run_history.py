"""add agent runtime run history

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-05 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "audit"


def upgrade() -> None:
    op.create_table(
        "agent_runtime_run",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_actor_email", sa.String(length=320), nullable=True),
        sa.Column("agent_name", sa.String(length=160), nullable=False),
        sa.Column("provider_kind", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("run_kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("result_posture", sa.String(length=80), nullable=False),
        sa.Column(
            "audit_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            "status IN ('success', 'failure', 'blocked', 'approval_required', 'denied')",
            name=op.f("ck_agent_runtime_run_status"),
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name=op.f("ck_agent_runtime_run_duration_ms_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_agent_runtime_run_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runtime_run")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_runtime_run_tenant_created_at",
        "agent_runtime_run",
        ["tenant_id", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_runtime_run_tenant_run_kind",
        "agent_runtime_run",
        ["tenant_id", "run_kind"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_runtime_run_tenant_status",
        "agent_runtime_run",
        ["tenant_id", "status"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_runtime_run_tenant_status",
        table_name="agent_runtime_run",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_agent_runtime_run_tenant_run_kind",
        table_name="agent_runtime_run",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_agent_runtime_run_tenant_created_at",
        table_name="agent_runtime_run",
        schema=SCHEMA,
    )
    op.drop_table("agent_runtime_run", schema=SCHEMA)
