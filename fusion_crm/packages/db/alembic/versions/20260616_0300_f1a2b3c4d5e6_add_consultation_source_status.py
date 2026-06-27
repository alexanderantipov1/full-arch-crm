"""Add ops.consultation.source_status (verbatim provider status).

Revision ID: f1a2b3c4d5e6
Revises: a8b9c0d1e2f3
Create Date: 2026-06-16 03:00:00.000000+00:00

Additive only (ENG-487). Adds a nullable ``source_status`` column holding the
verbatim provider status string (e.g. CareStack "Confirmed", "Un-Confirmed",
"Ready to Seat"). The existing bucketed ``status`` collapses these (notably
"Confirmed" → SCHEDULED), losing the signal the T-15m reminder (ENG-486) and
other workflows need. Mirrors :class:`packages.ops.models.Consultation`.
Backfill of historical rows is a separate offline script, not this migration.

Idempotent by design: the shared local dev DB (multiple parallel agents) had
this column applied by hand before this migration landed, and that DB also
carries an unrelated multi-branch alembic artifact. Guarding the add/drop on
column presence means ``alembic upgrade head`` / ``downgrade`` is safe to run
against ANY state — fresh, prod, CI, or the drifted dev DB — without ever
failing on a duplicate/absent column. On a clean DB it behaves identically to a
plain add/drop.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "consultation"
_SCHEMA = "ops"
_COLUMN = "source_status"


def _has_column() -> bool:
    cols = inspect(op.get_bind()).get_columns(_TABLE, schema=_SCHEMA)
    return any(c["name"] == _COLUMN for c in cols)


def upgrade() -> None:
    if _has_column():
        return
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.String(length=48), nullable=True),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    if not _has_column():
        return
    op.drop_column(_TABLE, _COLUMN, schema=_SCHEMA)
