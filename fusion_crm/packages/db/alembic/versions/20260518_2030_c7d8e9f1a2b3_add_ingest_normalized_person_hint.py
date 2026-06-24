"""ENG-185: add ingest.normalized_person_hint.

Revision ID: c7d8e9f1a2b3
Revises: e1f2a3b4c5d6
Create Date: 2026-05-18 20:30:00.000000+00:00

Additive only — creates a new ``ingest.normalized_person_hint`` table that
stores the provider-neutral, NON-PHI person evidence extracted from a
``ingest.raw_event`` row. It is the matching-policy input for ENG-185 and
replaces the implicit email/phone reactivation matching currently baked
into ``SfLeadIngestService``; no existing schema is changed.

Constraints/indexes mirror :class:`packages.ingest.models.NormalizedPersonHint`:

* ``UNIQUE (tenant_id, raw_event_id)`` — one hint per raw event for this
  slice. Multi-person extraction would require a follow-up to widen the
  unique key.
* ``ix_normalized_person_hint_source`` on
  ``(tenant_id, source_system, source_kind, source_id)`` — provider-record
  lookup.
* ``ix_normalized_person_hint_email`` / ``..._phone`` /
  ``..._person_uid`` — match-policy lookups.
* ``ix_normalized_person_hint_tenant_id`` — tenant-wide scans.

``person_uid`` and ``source_link_id`` are bare UUID columns with NO FK to
``identity.*``. The ingest layer must not depend on identity row lifecycle
(an identity row could be removed for compliance reasons; the hint stays as
forensic evidence). Identity-side validation enforces tenant scoping when
the match policy writes the pointer.

There is no DB-level CHECK on ``source_system`` / ``source_kind`` here.
Service-layer validation in :class:`packages.ingest.service.IngestService`
imports ``SOURCE_SYSTEMS`` / ``SOURCE_KINDS`` from ``packages.identity``
so the two domains stay aligned without a repeated DB migration when the
identity lists grow.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7d8e9f1a2b3"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "normalized_person_hint",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("raw_event_id", sa.UUID(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=240), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("given_name", sa.String(length=120), nullable=True),
        sa.Column("family_name", sa.String(length=120), nullable=True),
        sa.Column("display_name", sa.String(length=240), nullable=True),
        sa.Column("email_normalized", sa.String(length=320), nullable=True),
        sa.Column("phone_normalized", sa.String(length=32), nullable=True),
        sa.Column("person_uid", sa.UUID(), nullable=True),
        sa.Column("source_link_id", sa.UUID(), nullable=True),
        sa.Column("payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("hint_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "quality_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            name=op.f("fk_normalized_person_hint_tenant_id_tenant"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["raw_event_id"],
            ["ingest.raw_event.id"],
            name=op.f("fk_normalized_person_hint_raw_event_id_raw_event"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_normalized_person_hint")),
        sa.UniqueConstraint(
            "tenant_id",
            "raw_event_id",
            name="uq_normalized_person_hint_tenant_raw_event",
        ),
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_tenant_id",
        "normalized_person_hint",
        ["tenant_id"],
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_source",
        "normalized_person_hint",
        ["tenant_id", "source_system", "source_kind", "source_id"],
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_email",
        "normalized_person_hint",
        ["tenant_id", "email_normalized"],
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_phone",
        "normalized_person_hint",
        ["tenant_id", "phone_normalized"],
        schema="ingest",
    )
    op.create_index(
        "ix_normalized_person_hint_person_uid",
        "normalized_person_hint",
        ["tenant_id", "person_uid"],
        schema="ingest",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_normalized_person_hint_person_uid",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.drop_index(
        "ix_normalized_person_hint_phone",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.drop_index(
        "ix_normalized_person_hint_email",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.drop_index(
        "ix_normalized_person_hint_source",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.drop_index(
        "ix_normalized_person_hint_tenant_id",
        table_name="normalized_person_hint",
        schema="ingest",
    )
    op.drop_table("normalized_person_hint", schema="ingest")
