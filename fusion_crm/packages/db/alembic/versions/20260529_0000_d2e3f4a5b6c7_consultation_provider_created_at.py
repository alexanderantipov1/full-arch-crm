"""Add ops.consultation.provider_created_at + backfill from raw_event.

The PM dashboard filters consultations by date, but ``Consultation.scheduled_at``
is the appointment time (when the visit happens), not when the booking
record was created. Operators asked for "consultations created in the last
30 days" — i.e. by provider-side create event.

Adds a nullable ``provider_created_at`` timestamptz column, indexes it on
``(tenant_id, provider_created_at)`` to keep the dashboard aggregate cheap,
and backfills from ``ingest.raw_event.payload->>'createdOn'`` for CareStack
rows. Salesforce calendar events use ``CreatedDate`` — same payload key
exists in raw_event.payload on the SF side so the same backfill statement
covers them.

Going forward, the CareStack appointment ingest path writes this column at
insert time (see follow-up commit on packages/ingest/carestack_appointment_service.py).

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-29 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consultation",
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        schema="ops",
    )
    op.create_index(
        "ix_consultation_tenant_provider_created",
        "consultation",
        ["tenant_id", "provider_created_at"],
        schema="ops",
    )

    # Backfill from raw_event payload. CareStack appointments expose
    # ``createdOn`` (e.g. ``2024-09-10T14:31:22``); Salesforce Events expose
    # ``CreatedDate`` (ISO with offset). Both cast cleanly via ::timestamptz.
    op.execute(
        """
        UPDATE ops.consultation c
        SET provider_created_at = (re.payload->>'createdOn')::timestamptz
        FROM ingest.raw_event re
        WHERE c.raw_event_id = re.id
          AND c.provider_created_at IS NULL
          AND re.payload->>'createdOn' IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE ops.consultation c
        SET provider_created_at = (re.payload->>'CreatedDate')::timestamptz
        FROM ingest.raw_event re
        WHERE c.raw_event_id = re.id
          AND c.provider_created_at IS NULL
          AND re.payload->>'CreatedDate' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_consultation_tenant_provider_created",
        table_name="consultation",
        schema="ops",
    )
    op.drop_column("consultation", "provider_created_at", schema="ops")
