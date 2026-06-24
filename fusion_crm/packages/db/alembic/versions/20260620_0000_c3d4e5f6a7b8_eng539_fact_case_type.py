"""ENG-539: implant case_type dimension on fact_patient_journey

Adds the B1.5 implant ``case_type`` dimension to
``analytics.fact_patient_journey``:

- ``analytics.fact_patient_journey.case_type``: new NULLABLE ``VARCHAR(32)``.
  A coarse, CDT-derived implant-case label (one per person). NULL = not an
  implant patient OR an implant patient whose footprint is non-determinative
  (*unclassified*, needs review). Auto values: ``single_implant`` /
  ``multiple_implants`` / ``all_on_x`` / ``overdenture`` / ``implant_bridge``.
  Manual-only / future values (``all_on_4`` / ``all_on_6`` / ``zygomatic`` /
  ``full_arch_upper`` / ``full_arch_lower`` / ``dual_arch``) are set via ENG-513
  enrichment, never auto-derived. See ``packages/analytics/case_type.py``.
- A partial index ``ix_fact_patient_journey_case_type WHERE case_type IS NOT
  NULL`` powers the case-type filter / review-surface query while staying small
  (the column is NULL for every non-implant person).

Additive only — no data movement. The analytics read-model is a rebuildable
projection; the fact builder fills ``case_type`` (``method='auto'``) on the next
rebuild, and a manual override (``method='manual'``) survives rebuilds. Model
parity: the column + index are declared in
``packages/analytics/models.py::FactPatientJourney`` so ``alembic check`` stays
clean. No allowed-value CHECK constraint by design — the taxonomy is operator-
editable in ``case_type.py``, and a DB CHECK would force a migration for every
taxonomy edit; this mirrors the free-string ``source`` dimension.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "analytics"
_TABLE = "fact_patient_journey"
_INDEX = "ix_fact_patient_journey_case_type"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("case_type", sa.String(length=32), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        _INDEX,
        _TABLE,
        ["case_type"],
        schema=SCHEMA,
        postgresql_where=sa.text("case_type IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE, schema=SCHEMA)
    op.drop_column(_TABLE, "case_type", schema=SCHEMA)
