"""ENG-436: add integrations.notification_rule + notification_outbox.

Revision ID: a7b8c9d0e1f2
Revises: e6f7a8b9c0d1
Create Date: 2026-06-15 03:00:00.000000+00:00

Additive only — creates the Interactive Corporate Messenger layer's
transactional outbox + notification-rule pair (Block C, ENG-436),
mirroring the email outbox pattern (``outreach.outbound_queue``):

* ``integrations.notification_rule`` — maps a workspace ``event_type`` to
  a chat ``channel`` plus the JSONB ``conditions`` predicates and
  ``template`` blocks (interpreted by Block D). Indexed for per-event
  enabled-rule lookup.
* ``integrations.notification_outbox`` — durable work queue drained by the
  arq ``drain_notification_outbox`` dispatcher. Partial pending index on
  ``(status, scheduled_for) WHERE status = 'pending'`` keeps the
  ``FOR UPDATE SKIP LOCKED`` pull cheap. ``rule_id`` FK SET NULL so a row
  enqueued directly survives rule deletion.

Constraints/indexes mirror :class:`packages.integrations.models`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_rule",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=255), nullable=False),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "template",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "provider_kind",
            sa.String(length=32),
            server_default=sa.text("'mattermost'"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_notification_rule_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_rule")),
        schema="integrations",
    )
    op.create_index(
        "ix_notification_rule_tenant_id",
        "notification_rule",
        ["tenant_id"],
        schema="integrations",
    )
    op.create_index(
        "ix_notification_rule_lookup",
        "notification_rule",
        ["tenant_id", "event_type", "enabled"],
        schema="integrations",
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.String(length=255), nullable=False),
        sa.Column(
            "provider_kind",
            sa.String(length=32),
            server_default=sa.text("'mattermost'"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
            "status IN ('pending', 'locked', 'sent', 'failed')",
            name=op.f("ck_notification_outbox_status"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["integrations.notification_rule.id"],
            name=op.f("fk_notification_outbox_rule_id_notification_rule"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_notification_outbox_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_outbox")),
        schema="integrations",
    )
    op.create_index(
        "ix_notification_outbox_tenant_id",
        "notification_outbox",
        ["tenant_id"],
        schema="integrations",
    )
    op.create_index(
        "ix_notification_outbox_pending",
        "notification_outbox",
        ["status", "scheduled_for"],
        unique=False,
        schema="integrations",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_notification_outbox_rule_id",
        "notification_outbox",
        ["rule_id"],
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_outbox_rule_id",
        table_name="notification_outbox",
        schema="integrations",
    )
    op.drop_index(
        "ix_notification_outbox_pending",
        table_name="notification_outbox",
        schema="integrations",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index(
        "ix_notification_outbox_tenant_id",
        table_name="notification_outbox",
        schema="integrations",
    )
    op.drop_table("notification_outbox", schema="integrations")

    op.drop_index(
        "ix_notification_rule_lookup",
        table_name="notification_rule",
        schema="integrations",
    )
    op.drop_index(
        "ix_notification_rule_tenant_id",
        table_name="notification_rule",
        schema="integrations",
    )
    op.drop_table("notification_rule", schema="integrations")
