"""ENG-133: create outreach domain (templates, campaigns, sends, suppression, queue).

Revision ID: c9d2e4f6a8b3
Revises: a8c5e7d2f4b9
Create Date: 2026-05-10 12:00:00.000000+00:00

Per ADR-0004 (operator-account email outreach) and the ENG-133 spec.

Creates the ``outreach`` schema (idempotent — also created by
``infra/docker/init-schemas.sql`` on a fresh dev volume; this migration
is the canonical creation path on existing environments per the
ADR-0001 / ENG-123 pattern).

Then creates five tables:

- ``outreach.template`` — operator-edited Mustache+MJML email templates.
- ``outreach.campaign`` — scheduled or immediate batch sends.
- ``outreach.send``     — one row per recipient per campaign.
- ``outreach.suppression`` — per-tenant unsubscribe / bounce list.
- ``outreach.outbound_queue`` — Postgres-backed work queue for the
  dispatcher worker (ADR-0004 decision #1).

Cross-schema FKs reference ``tenant.tenant.id``,
``tenant.integration_credential.id``, ``identity.person.id``, and
``actor.actor.id`` — those schemas / tables already exist by the time
this migration runs (see chain through tenant_credentials_seed →
b7c3e9f1a2d4 → … → 4ba791c47185).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9d2e4f6a8b3"
down_revision: str | None = "a8c5e7d2f4b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CHECK constraint value sets — kept in lock-step with
# ``packages.outreach.models``. Change here = change there.
_TEMPLATE_BODY_FORMATS = "'markdown', 'html', 'mjml'"
_TEMPLATE_CATEGORIES = "'marketing', 'clinical', 'transactional', 'operational'"
_TEMPLATE_STATUSES = "'draft', 'active', 'archived'"
_CAMPAIGN_STATUSES = (
    "'draft', 'queued', 'sending', 'sent', 'failed', 'cancelled'"
)
_CAMPAIGN_MAILBOX_STRATEGIES = "'explicit', 'auto_route'"
_SEND_STATUSES = (
    "'queued', 'sent', 'bounced', 'failed', 'unsubscribed', 'opened'"
)
_SUPPRESSION_REASONS = "'operator', 'one_click', 'bounce_hard', 'complaint'"
_OUTBOUND_QUEUE_STATUSES = "'pending', 'locked', 'succeeded', 'failed'"


def upgrade() -> None:
    # Schema is also created by init-schemas.sql on a fresh volume; this
    # statement is the canonical path on existing environments and keeps
    # the migration self-contained. Idempotent.
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS outreach"))

    # --- outreach.template ---------------------------------------------------
    op.create_table(
        "template",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column(
            "body_format",
            sa.String(length=16),
            server_default=sa.text("'markdown'"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=24),
            server_default=sa.text("'marketing'"),
            nullable=False,
        ),
        sa.Column(
            "tracking_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "intent_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("created_by_actor_id", sa.UUID(), nullable=True),
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
            f"body_format IN ({_TEMPLATE_BODY_FORMATS})",
            name=op.f("ck_template_body_format"),
        ),
        sa.CheckConstraint(
            f"category IN ({_TEMPLATE_CATEGORIES})",
            name=op.f("ck_template_category"),
        ),
        sa.CheckConstraint(
            f"status IN ({_TEMPLATE_STATUSES})",
            name=op.f("ck_template_status"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_template_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_template_created_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_template")),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_template_tenant_id_name"
        ),
        schema="outreach",
    )
    op.create_index(
        "ix_template_tenant_id",
        "template",
        ["tenant_id"],
        schema="outreach",
    )
    op.create_index(
        "ix_template_status",
        "template",
        ["tenant_id", "status"],
        schema="outreach",
    )

    # --- outreach.campaign ---------------------------------------------------
    op.create_table(
        "campaign",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column(
            "recipient_query",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("mailbox_credential_id", sa.UUID(), nullable=True),
        sa.Column(
            "mailbox_strategy",
            sa.String(length=16),
            server_default=sa.text("'explicit'"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sent_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "opened_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "bounced_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "unsubscribed_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("created_by_actor_id", sa.UUID(), nullable=True),
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
            f"status IN ({_CAMPAIGN_STATUSES})",
            name=op.f("ck_campaign_status"),
        ),
        sa.CheckConstraint(
            f"mailbox_strategy IN ({_CAMPAIGN_MAILBOX_STRATEGIES})",
            name=op.f("ck_campaign_mailbox_strategy"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_campaign_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["outreach.template.id"],
            name=op.f("fk_campaign_template_id_template"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mailbox_credential_id"],
            ["tenant.integration_credential.id"],
            name=op.f("fk_campaign_mailbox_credential_id_integration_credential"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_campaign_created_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign")),
        schema="outreach",
    )
    op.create_index(
        "ix_campaign_tenant_id",
        "campaign",
        ["tenant_id"],
        schema="outreach",
    )
    op.create_index(
        "ix_campaign_status",
        "campaign",
        ["tenant_id", "status"],
        schema="outreach",
    )
    op.create_index(
        "ix_campaign_template_id",
        "campaign",
        ["template_id"],
        schema="outreach",
    )

    # --- outreach.send -------------------------------------------------------
    op.create_table(
        "send",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("person_uid", sa.UUID(), nullable=True),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("message_id", sa.String(length=320), nullable=True),
        sa.Column("mailbox_credential_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
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
            f"status IN ({_SEND_STATUSES})",
            name=op.f("ck_send_status"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_send_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["outreach.campaign.id"],
            name=op.f("fk_send_campaign_id_campaign"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["person_uid"],
            ["identity.person.id"],
            name=op.f("fk_send_person_uid_person"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["mailbox_credential_id"],
            ["tenant.integration_credential.id"],
            name=op.f("fk_send_mailbox_credential_id_integration_credential"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_send")),
        schema="outreach",
    )
    op.create_index(
        "ix_send_campaign_id_status",
        "send",
        ["campaign_id", "status"],
        schema="outreach",
    )
    op.create_index(
        "ix_send_tenant_id_recipient_email",
        "send",
        ["tenant_id", "recipient_email"],
        schema="outreach",
    )
    op.create_index(
        "ix_send_tenant_id_person_uid",
        "send",
        ["tenant_id", "person_uid"],
        schema="outreach",
        postgresql_where=sa.text("person_uid IS NOT NULL"),
    )

    # --- outreach.suppression -----------------------------------------------
    op.create_table(
        "suppression",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "recipient_email_normalised",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=24), nullable=False),
        sa.Column("source_send_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"reason IN ({_SUPPRESSION_REASONS})",
            name=op.f("ck_suppression_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_suppression_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_send_id"],
            ["outreach.send.id"],
            name=op.f("fk_suppression_source_send_id_send"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "recipient_email_normalised",
            name="pk_suppression",
        ),
        schema="outreach",
    )
    op.create_index(
        "ix_suppression_tenant_id",
        "suppression",
        ["tenant_id"],
        schema="outreach",
    )

    # --- outreach.outbound_queue --------------------------------------------
    op.create_table(
        "outbound_queue",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("send_id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column(
            "priority",
            sa.SmallInteger(),
            server_default=sa.text("100"),
            nullable=False,
        ),
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
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
        sa.CheckConstraint(
            f"status IN ({_OUTBOUND_QUEUE_STATUSES})",
            name=op.f("ck_outbound_queue_status"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_outbound_queue_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["send_id"],
            ["outreach.send.id"],
            name=op.f("fk_outbound_queue_send_id_send"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["tenant.integration_credential.id"],
            name=op.f("fk_outbound_queue_credential_id_integration_credential"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbound_queue")),
        schema="outreach",
    )
    op.create_index(
        "ix_outbound_queue_pending",
        "outbound_queue",
        ["status", "scheduled_for"],
        schema="outreach",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_outbound_queue_tenant_id",
        "outbound_queue",
        ["tenant_id"],
        schema="outreach",
    )
    op.create_index(
        "ix_outbound_queue_send_id",
        "outbound_queue",
        ["send_id"],
        schema="outreach",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outbound_queue_send_id",
        table_name="outbound_queue",
        schema="outreach",
    )
    op.drop_index(
        "ix_outbound_queue_tenant_id",
        table_name="outbound_queue",
        schema="outreach",
    )
    op.drop_index(
        "ix_outbound_queue_pending",
        table_name="outbound_queue",
        schema="outreach",
    )
    op.drop_table("outbound_queue", schema="outreach")

    op.drop_index(
        "ix_suppression_tenant_id",
        table_name="suppression",
        schema="outreach",
    )
    op.drop_table("suppression", schema="outreach")

    op.drop_index(
        "ix_send_tenant_id_person_uid",
        table_name="send",
        schema="outreach",
    )
    op.drop_index(
        "ix_send_tenant_id_recipient_email",
        table_name="send",
        schema="outreach",
    )
    op.drop_index(
        "ix_send_campaign_id_status",
        table_name="send",
        schema="outreach",
    )
    op.drop_table("send", schema="outreach")

    op.drop_index(
        "ix_campaign_template_id",
        table_name="campaign",
        schema="outreach",
    )
    op.drop_index(
        "ix_campaign_status",
        table_name="campaign",
        schema="outreach",
    )
    op.drop_index(
        "ix_campaign_tenant_id",
        table_name="campaign",
        schema="outreach",
    )
    op.drop_table("campaign", schema="outreach")

    op.drop_index(
        "ix_template_status",
        table_name="template",
        schema="outreach",
    )
    op.drop_index(
        "ix_template_tenant_id",
        table_name="template",
        schema="outreach",
    )
    op.drop_table("template", schema="outreach")

    # Schema is shared infra; we leave it in place. Dropping it would
    # remove any future tables co-located here. (Mirrors the pattern in
    # the tenant_domain_create migration, which also leaves ``tenant``
    # schema in place on downgrade.)
