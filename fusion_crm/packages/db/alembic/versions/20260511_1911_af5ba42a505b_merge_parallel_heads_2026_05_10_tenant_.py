"""merge parallel heads 2026-05-10 (tenant_id default + outreach campaign nullable)

Revision ID: af5ba42a505b
Revises: e8d3a5b1c2f4, d7e9f5b3c1a8
Create Date: 2026-05-11 19:11:22.435792+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = 'af5ba42a505b'
down_revision: str | None = ('e8d3a5b1c2f4', 'd7e9f5b3c1a8')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
