"""ENG-509/510: add caller/coordinator/doctor partial indexes on the fact table.

Revision ID: a1b2c3d4e5f6
Revises: e5d4c3b2a190
Create Date: 2026-06-18 06:00:00.000000+00:00

Additive only — the B1 enablement (ENG-509 caller/coordinator, ENG-510 doctor)
fills the ``caller_id`` / ``coordinator_id`` / ``doctor_id`` people dimensions on
``analytics.fact_patient_journey``. The analytics aggregate filters on these
columns (the Caller / Coordinator / Doctor pages, B2.5–B2.7), so each gets a
partial index ``WHERE <col> IS NOT NULL`` — they stay mostly NULL until the
backfill runs, so a partial index is small and skips the unresolved rows.

Model parity: the three indexes are declared in
``packages/analytics/models.py::FactPatientJourney.__table_args__`` so
``alembic check`` stays clean.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "e5d4c3b2a190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "analytics"
_TABLE = "fact_patient_journey"


def upgrade() -> None:
    op.create_index(
        "ix_fact_patient_journey_caller_id",
        _TABLE,
        ["caller_id"],
        schema=SCHEMA,
        postgresql_where=sa.text("caller_id IS NOT NULL"),
    )
    op.create_index(
        "ix_fact_patient_journey_coordinator_id",
        _TABLE,
        ["coordinator_id"],
        schema=SCHEMA,
        postgresql_where=sa.text("coordinator_id IS NOT NULL"),
    )
    op.create_index(
        "ix_fact_patient_journey_doctor_id",
        _TABLE,
        ["doctor_id"],
        schema=SCHEMA,
        postgresql_where=sa.text("doctor_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fact_patient_journey_doctor_id", table_name=_TABLE, schema=SCHEMA
    )
    op.drop_index(
        "ix_fact_patient_journey_coordinator_id", table_name=_TABLE, schema=SCHEMA
    )
    op.drop_index(
        "ix_fact_patient_journey_caller_id", table_name=_TABLE, schema=SCHEMA
    )
