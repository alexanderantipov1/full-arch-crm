"""ENG-455: add integrations.notification_emitted (dedupe ledger).

Revision ID: e7d6c5b4a3f2
Revises: b69bce1e2195
Create Date: 2026-06-15 08:00:00.000000+00:00

Additive only — creates the durable idempotency ledger that guarantees a
domain entity emits AT MOST ONE notification per event type, EVER
(``NotificationEventService.emit`` claims a row here before enqueuing the
outbox row, in the same unit of work). Separate from
``integrations.notification_outbox`` so it survives outbox cleanup/retention:
the outbox is a transient work queue, a claim here is a permanent fact.

* ``integrations.notification_emitted`` — one row per emitted
  ``(tenant_id, event_type, dedupe_key)``. The UNIQUE constraint is the
  enforcement point; the repo claims via ``INSERT ... ON CONFLICT DO NOTHING
  RETURNING id`` so the first caller wins and every later caller is a no-op.

Constraints/indexes mirror :class:`packages.integrations.models`. The UNIQUE
constraint already indexes the claim/lookup key, so the only extra index is a
plain ``tenant_id`` index for tenant-scoped scans.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7d6c5b4a3f2"
down_revision: str | None = "b69bce1e2195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_emitted",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            name=op.f("fk_notification_emitted_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_emitted")),
        sa.UniqueConstraint(
            "tenant_id",
            "event_type",
            "dedupe_key",
            name="uq_notification_emitted_tenant_event_key",
        ),
        schema="integrations",
    )
    op.create_index(
        "ix_notification_emitted_tenant_id",
        "notification_emitted",
        ["tenant_id"],
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_emitted_tenant_id",
        table_name="notification_emitted",
        schema="integrations",
    )
    op.drop_table("notification_emitted", schema="integrations")
