"""D2: identity.source_link + identity.merge_event (ENG-3)

Revision ID: a3b1c5d7e9f0
Revises: b4f8c9a2d1e0
Create Date: 2026-05-05 22:32:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3b1c5d7e9f0"
down_revision: str | None = "b4f8c9a2d1e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_link",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("person_uid", sa.UUID(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=240), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_system IN ('salesforce', 'carestack', 'twilio', 'vapi', "
            "'web_form', 'manual', 'import')",
            name=op.f("ck_source_link_source_system"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('lead', 'contact', 'patient', 'caller', "
            "'sms_sender', 'submitter')",
            name=op.f("ck_source_link_source_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["person_uid"],
            ["identity.person.id"],
            name=op.f("fk_source_link_person_uid_person"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_link")),
        schema="identity",
    )
    op.create_index(
        "ix_source_link_person_uid",
        "source_link",
        ["person_uid"],
        schema="identity",
    )
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

    op.create_table(
        "merge_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("surviving_person_uid", sa.UUID(), nullable=False),
        sa.Column("merged_person_uid", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=48), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("performed_by_actor_id", sa.UUID(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason IN ('duplicate_email', 'duplicate_phone', 'manual', "
            "'cross_provider_match')",
            name=op.f("ck_merge_event_reason"),
        ),
        sa.CheckConstraint(
            "surviving_person_uid <> merged_person_uid",
            name=op.f("ck_merge_event_distinct_persons"),
        ),
        sa.ForeignKeyConstraint(
            ["surviving_person_uid"],
            ["identity.person.id"],
            name=op.f("fk_merge_event_surviving_person_uid_person"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_merge_event_performed_by_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_merge_event")),
        schema="identity",
    )
    op.create_index(
        "ix_merge_event_surviving",
        "merge_event",
        ["surviving_person_uid"],
        schema="identity",
    )
    op.create_index(
        "ix_merge_event_merged",
        "merge_event",
        ["merged_person_uid"],
        schema="identity",
    )


def downgrade() -> None:
    op.drop_index("ix_merge_event_merged", table_name="merge_event", schema="identity")
    op.drop_index("ix_merge_event_surviving", table_name="merge_event", schema="identity")
    op.drop_table("merge_event", schema="identity")

    op.drop_index("uq_source_link_external", table_name="source_link", schema="identity")
    op.drop_index("ix_source_link_source", table_name="source_link", schema="identity")
    op.drop_index("ix_source_link_person_uid", table_name="source_link", schema="identity")
    op.drop_table("source_link", schema="identity")
