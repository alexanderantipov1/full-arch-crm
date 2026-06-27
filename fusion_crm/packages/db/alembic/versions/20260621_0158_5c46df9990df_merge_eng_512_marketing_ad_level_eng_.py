"""merge ENG-512 marketing ad-level + ENG-543 provider_carestack_id heads

Revision ID: 5c46df9990df
Revises: c5e7a9b1d3f2, d4e5f6a7b8c0
Create Date: 2026-06-21 01:58:43.446872+00:00

Pure head-merge — no schema operations. ENG-512 (``c5e7a9b1d3f2``, marketing
ad-level tables) and ENG-543 (``d4e5f6a7b8c0``, ops.consultation
provider_carestack_id) were authored independently and both descend from
``c3d4e5f6a7b8`` (ENG-539), so they merged into ``main`` as two concurrent
alembic heads. This revision rejoins them into a single head so
``alembic upgrade head`` is unambiguous again. The two parents touch disjoint
tables, so the merge carries no operations and no ordering dependency.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "5c46df9990df"
down_revision: tuple[str, str] | None = ("c5e7a9b1d3f2", "d4e5f6a7b8c0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
