"""funnel-responsibility-layer-v1: event_responsibility + covering_opportunity_id (ENG-416 + ENG-417)

Revision ID: c4d5e6f7a8b9
Revises: f5a6b7c8d9e0
Create Date: 2026-06-13 14:00:00.000000

ENG-416 — multi-responsibility on ``interaction.event``:
- New ``interaction.event_responsibility`` table keyed on
  ``(event_id, actor_id, role)`` so one event can carry both the
  operational owner (TC/agent) AND the clinical owner (doctor). See
  ``.agents/orchestration/funnel-responsibility-layer-v1/decision-log.md``
  for why join table over columns.

ENG-417 — covering Opportunity link on ``ops.consultation``:
- New nullable ``covering_opportunity_id`` column with FK to
  ``ops.opportunity.id``. NULL for walk-ins / pre-opportunity consults;
  populated by the resolver for consults whose person has a covering
  Opportunity (nearest preceding ``provider_created_at`` within the
  person's funnel).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b1f2c3d4e5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Initial role allowlist. New roles add a new value here AND in
# packages/interaction/models.py::RESPONSIBILITY_ROLES — both must move
# together (the model docs reference this check).
_RESPONSIBILITY_ROLES = ("operational", "clinical")


def upgrade() -> None:
    op.create_table(
        "event_responsibility",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in _RESPONSIBILITY_ROLES) + ")",
            name=op.f("ck_event_responsibility_role"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_event_responsibility_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["interaction.event.id"],
            name=op.f("fk_event_responsibility_event_id_event"),
            # Cascade on event delete is intentional: the timeline event
            # is append-only in production (interaction has no
            # update/delete service methods), but tests and historic
            # cleanup scripts do issue raw DELETEs. A dangling
            # responsibility row would be orphan garbage; cascade keeps
            # the join table consistent without the operational risk of
            # RESTRICT here (interaction.event itself is RESTRICTed
            # against identity.person, which is the real safety net).
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_event_responsibility_actor_id_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "event_id",
            "actor_id",
            "role",
            name=op.f("pk_event_responsibility"),
        ),
        schema="interaction",
    )
    op.create_index(
        "ix_event_responsibility_tenant_id",
        "event_responsibility",
        ["tenant_id"],
        unique=False,
        schema="interaction",
    )
    # Covers "find every event a given actor owns operationally / clinically".
    op.create_index(
        "ix_event_responsibility_actor_role",
        "event_responsibility",
        ["actor_id", "role"],
        unique=False,
        schema="interaction",
    )
    # Covers "for this event, who owns role X" — the dominant ingest-side
    # read after a write.
    op.create_index(
        "ix_event_responsibility_event_role",
        "event_responsibility",
        ["event_id", "role"],
        unique=False,
        schema="interaction",
    )

    # ENG-417: covering Opportunity link on ops.consultation.
    op.add_column(
        "consultation",
        sa.Column("covering_opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="ops",
    )
    op.create_foreign_key(
        op.f("fk_consultation_covering_opportunity_id_opportunity"),
        "consultation",
        "opportunity",
        ["covering_opportunity_id"],
        ["id"],
        source_schema="ops",
        referent_schema="ops",
        # SET NULL so a deleted opportunity (test fixtures, rare manual
        # cleanups) leaves the consultation visible without the link
        # rather than RESTRICTing the opportunity delete.
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_consultation_covering_opportunity_id",
        "consultation",
        ["covering_opportunity_id"],
        unique=False,
        schema="ops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_consultation_covering_opportunity_id",
        table_name="consultation",
        schema="ops",
    )
    op.drop_constraint(
        op.f("fk_consultation_covering_opportunity_id_opportunity"),
        "consultation",
        type_="foreignkey",
        schema="ops",
    )
    op.drop_column("consultation", "covering_opportunity_id", schema="ops")

    op.drop_index(
        "ix_event_responsibility_event_role",
        table_name="event_responsibility",
        schema="interaction",
    )
    op.drop_index(
        "ix_event_responsibility_actor_role",
        table_name="event_responsibility",
        schema="interaction",
    )
    op.drop_index(
        "ix_event_responsibility_tenant_id",
        table_name="event_responsibility",
        schema="interaction",
    )
    op.drop_table("event_responsibility", schema="interaction")
