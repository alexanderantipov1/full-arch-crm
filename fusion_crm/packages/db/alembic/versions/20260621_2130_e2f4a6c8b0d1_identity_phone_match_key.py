"""identity: value_match_key on person_identifier (phone-format dedup)

Adds ``identity.person_identifier.value_match_key`` (NULLABLE ``VARCHAR(320)``)
plus an index on ``(kind, value_match_key)``. This is the canonical comparison
key the resolver/sweep match on, so the same phone stored in different formats
(``2015550123`` vs ``+12015550123``) resolves to ONE person. Before this, all
identity lookups compared the raw ``value`` exactly, so pre-ENG-463 digit-only
phones never matched post-ENG-463 E.164 phones — silently creating duplicates
(~3.5k phantom groups).

Additive only — no data movement here. The column is backfilled for existing
rows by the standalone, idempotent
``infra/scripts/backfill_phone_match_key.py`` (operator-gated, off the deploy
path). The read path keeps a raw-value OR fallback so there is no correctness
gap while the column is NULL. Model parity: the column + index are declared on
``packages/identity/models.py::PersonIdentifier`` so ``alembic check`` stays
clean.

Revision ID: e2f4a6c8b0d1
Revises: 5c46df9990df
Create Date: 2026-06-21 21:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f4a6c8b0d1"
down_revision: str | Sequence[str] | None = "5c46df9990df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "identity"
_TABLE = "person_identifier"
_COLUMN = "value_match_key"
_INDEX = "ix_person_identifier_kind_match_key"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.String(length=320), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(_INDEX, _TABLE, ["kind", _COLUMN], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE, schema=SCHEMA)
    op.drop_column(_TABLE, _COLUMN, schema=SCHEMA)
