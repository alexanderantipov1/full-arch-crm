"""ENG-309: add identity.person.dob + identity.person.ssn.

Revision ID: b1c2d3e4f5a6
Revises: e9f0a1b2c3d4
Create Date: 2026-06-01 07:00:00.000000+00:00

Additive only -- two nullable columns on ``identity.person`` so the
resolver (``IdentityService.resolve_or_create_from_hint``) can enforce
the ENG-309 hard veto: different DOB or different SSN -> never merge,
regardless of how many soft signals (phone, email, address, last name,
accountId) overlap.

These columns are demographic identity-strength signals, not clinical
data. The identity package owns demographic identity (names, DOB, SSN);
the ``phi.*`` schema owns clinical attributes (allergies, prescriptions,
diagnoses, treatment notes). Both DOB and SSN go through the same
``IdentityService`` surface as ``Person.given_name`` and never leak into
log values or evidence dicts (``_FORBIDDEN_EVIDENCE_KEYS`` continues to
reject ``"dob"`` / ``"ssn"`` keys at the evidence layer).

Nullable on purpose: pre-existing rows (predating ENG-309) have no DOB
or SSN, and the resolver veto only fires when BOTH sides have a value.
A NULL on either side defers to the existing soft tier ladder.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "person",
        sa.Column("dob", sa.Date(), nullable=True),
        schema="identity",
    )
    op.add_column(
        "person",
        sa.Column("ssn", sa.String(length=32), nullable=True),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_column("person", "ssn", schema="identity")
    op.drop_column("person", "dob", schema="identity")
