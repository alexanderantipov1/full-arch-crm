"""merge ENG-341 + ENG-560 heads

Revision ID: fd36dd4df2f3
Revises: e9a1c7b4d2f3, e2f4a6c8b0d1
Create Date: 2026-06-22 06:14:29.468585+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = 'fd36dd4df2f3'
down_revision: str | None = ('e9a1c7b4d2f3', 'e2f4a6c8b0d1')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
