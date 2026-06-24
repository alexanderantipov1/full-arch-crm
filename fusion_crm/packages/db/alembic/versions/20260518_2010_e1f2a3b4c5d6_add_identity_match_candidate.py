"""ENG-182: add identity.match_candidate decision ledger.

Revision ID: e1f2a3b4c5d6
Revises: b4c2e1f9a5d7
Create Date: 2026-05-18 20:10:00.000000+00:00

Additive only — creates a new ``identity.match_candidate`` table to record
explicit cross-provider identity matching decisions. Replaces the implicit
email/phone reactivation matching currently inside ``SfLeadIngestService``
without changing any existing schema. Pipeline integration lands in later
ENG-183 / ENG-185 tasks.

Schema constraints mirror :class:`packages.identity.models.MatchCandidate`:

* ``status`` CHECK list.
* ``confidence`` CHECK range.
* self-match CHECK (``source_person_uid <> candidate_person_uid``).
* accepted-person CHECK (``accepted_person_uid`` only with accepted status).
* indexes on candidate, source person, hint, and status.
* partial unique ``(tenant_id, person_pair_key)`` for open candidates.
* partial unique ``(tenant_id, hint_id, candidate_person_uid)`` for active
  hint linkage.

``hint_id`` is intentionally a bare UUID column with no FK to
``ingest.normalized_person_hint`` (that table does not exist yet, and the
identity-domain rules forbid importing ingest in Python). The FK is left to
the follow-up migration that lands the hints table (ENG-183).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "b4c2e1f9a5d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MATCH_CANDIDATE_STATUSES = (
    "'open', 'auto_accepted', 'accepted', 'rejected', 'superseded'"
)
_MATCH_CANDIDATE_ACCEPTED_STATUSES = "'auto_accepted', 'accepted'"
_MATCH_CANDIDATE_ACTIVE_STATUSES = "'open', 'auto_accepted', 'accepted'"


def upgrade() -> None:
    op.create_table(
        "match_candidate",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("hint_id", sa.UUID(), nullable=True),
        sa.Column("source_person_uid", sa.UUID(), nullable=True),
        sa.Column("candidate_person_uid", sa.UUID(), nullable=False),
        sa.Column("accepted_person_uid", sa.UUID(), nullable=True),
        sa.Column("merge_event_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("match_rule", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "conflicts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("person_pair_key", sa.String(length=73), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_actor_id", sa.UUID(), nullable=True),
        sa.Column("superseded_by_match_id", sa.UUID(), nullable=True),
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
            f"status IN ({_MATCH_CANDIDATE_STATUSES})",
            name=op.f("ck_match_candidate_status"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_match_candidate_confidence_range"),
        ),
        sa.CheckConstraint(
            "source_person_uid IS NULL "
            "OR source_person_uid <> candidate_person_uid",
            name=op.f("ck_match_candidate_distinct_persons"),
        ),
        sa.CheckConstraint(
            "accepted_person_uid IS NULL "
            f"OR status IN ({_MATCH_CANDIDATE_ACCEPTED_STATUSES})",
            name=op.f("ck_match_candidate_accepted_status"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.tenant.id"],
            name=op.f("fk_match_candidate_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_person_uid"],
            ["identity.person.id"],
            name=op.f("fk_match_candidate_source_person_uid_person"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_person_uid"],
            ["identity.person.id"],
            name=op.f("fk_match_candidate_candidate_person_uid_person"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_person_uid"],
            ["identity.person.id"],
            name=op.f("fk_match_candidate_accepted_person_uid_person"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["merge_event_id"],
            ["identity.merge_event.id"],
            name=op.f("fk_match_candidate_merge_event_id_merge_event"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_actor_id"],
            ["actor.actor.id"],
            name=op.f("fk_match_candidate_decided_by_actor_id_actor"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_match_id"],
            ["identity.match_candidate.id"],
            name=op.f("fk_match_candidate_superseded_by_match_id_match_candidate"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_candidate")),
        schema="identity",
    )
    op.create_index(
        "ix_match_candidate_tenant_id",
        "match_candidate",
        ["tenant_id"],
        schema="identity",
    )
    op.create_index(
        "ix_match_candidate_candidate",
        "match_candidate",
        ["tenant_id", "candidate_person_uid"],
        schema="identity",
    )
    op.create_index(
        "ix_match_candidate_source_person",
        "match_candidate",
        ["tenant_id", "source_person_uid"],
        schema="identity",
    )
    op.create_index(
        "ix_match_candidate_hint",
        "match_candidate",
        ["tenant_id", "hint_id"],
        schema="identity",
    )
    op.create_index(
        "ix_match_candidate_status",
        "match_candidate",
        ["tenant_id", "status", "created_at"],
        schema="identity",
    )
    op.create_index(
        "uq_match_candidate_open_pair",
        "match_candidate",
        ["tenant_id", "person_pair_key"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text(
            "status = 'open' AND person_pair_key IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_match_candidate_hint_candidate_active",
        "match_candidate",
        ["tenant_id", "hint_id", "candidate_person_uid"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text(
            f"status IN ({_MATCH_CANDIDATE_ACTIVE_STATUSES}) "
            "AND hint_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_match_candidate_hint_candidate_active",
        table_name="match_candidate",
        schema="identity",
        postgresql_where=sa.text(
            f"status IN ({_MATCH_CANDIDATE_ACTIVE_STATUSES}) "
            "AND hint_id IS NOT NULL"
        ),
    )
    op.drop_index(
        "uq_match_candidate_open_pair",
        table_name="match_candidate",
        schema="identity",
        postgresql_where=sa.text(
            "status = 'open' AND person_pair_key IS NOT NULL"
        ),
    )
    op.drop_index(
        "ix_match_candidate_status",
        table_name="match_candidate",
        schema="identity",
    )
    op.drop_index(
        "ix_match_candidate_hint",
        table_name="match_candidate",
        schema="identity",
    )
    op.drop_index(
        "ix_match_candidate_source_person",
        table_name="match_candidate",
        schema="identity",
    )
    op.drop_index(
        "ix_match_candidate_candidate",
        table_name="match_candidate",
        schema="identity",
    )
    op.drop_index(
        "ix_match_candidate_tenant_id",
        table_name="match_candidate",
        schema="identity",
    )
    op.drop_table("match_candidate", schema="identity")
