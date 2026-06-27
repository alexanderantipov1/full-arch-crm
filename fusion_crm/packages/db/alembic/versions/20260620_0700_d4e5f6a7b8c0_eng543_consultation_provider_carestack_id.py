"""ENG-543: provider_carestack_id on ops.consultation

Adds ``ops.consultation.provider_carestack_id`` (NULLABLE ``VARCHAR(64)``) — the
CareStack provider id (``providerIds[0]``) the appointment was booked under,
captured verbatim at ingest. It is the stable link from a consultation to its
doctor's ``actor.actor`` (keyed by ``actor_identifier.kind='carestack_provider_id'``),
which in turn carries the doctor's ``mattermost_username`` identifier. The T-15m
consult-reminder uses this chain to resolve a Mattermost ``@mention`` for the
assigned doctor instead of only the plain ``provider_clinician_name`` string.

Additive only — no data movement. Nullable for non-CareStack / legacy rows; the
appointment ingest fills it going forward, so existing rows resolve a mention
only after a re-pull. Model parity: the column is declared on
``packages/ops/models.py::Consultation`` so ``alembic check`` stays clean.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b8
Create Date: 2026-06-20 07:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c0"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "ops"
_TABLE = "consultation"
_COLUMN = "provider_carestack_id"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN, schema=SCHEMA)
