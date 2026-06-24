"""ENG-132: relax outreach.send.campaign_id to NULLABLE for transactional sends.

Revision ID: d7e9f5b3c1a8
Revises: c9d2e4f6a8b3
Create Date: 2026-05-10 14:00:00.000000+00:00

ENG-133 created ``outreach.send.campaign_id`` as NOT NULL on the
assumption every send belongs to a campaign. ENG-132 adds the
``enqueue_single`` transactional path (appointment reminders, consult
confirmations) which has no campaign row — the send is created
directly by the operator UI / a workflow step.

Per ADR-0004 §"Mailbox routing" we still want the campaign FK so the
campaign rollup view works for the campaign case; making the column
nullable preserves the FK + cascade behaviour for campaign sends while
allowing campaign-less rows for transactional sends.

The accompanying ``outreach.models.Send`` change makes
``campaign_id`` optional on the model side. The column already has
``ON DELETE CASCADE`` from ENG-133; that cascade only fires when a
non-null campaign id is set, so this migration does not need to
adjust the FK behaviour.

No data migration is required — every existing send row already has a
non-null campaign id (the ENG-133 + ENG-132 release order guarantees
that no transactional send predates this column flip).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7e9f5b3c1a8"
down_revision: str | None = "c9d2e4f6a8b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "send",
        "campaign_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        schema="outreach",
    )


def downgrade() -> None:
    # The downgrade refuses if any campaign-less send row exists. We
    # cannot synthesise a campaign id for transactional sends after
    # the fact, and silently dropping rows is worse than failing the
    # rollback.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM outreach.send WHERE campaign_id IS NULL
            ) THEN
                RAISE EXCEPTION 'cannot downgrade: outreach.send rows '
                    'exist with campaign_id IS NULL';
            END IF;
        END $$;
        """
    )
    op.alter_column(
        "send",
        "campaign_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        schema="outreach",
    )
