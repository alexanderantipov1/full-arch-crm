"""Catalog domain models — schema ``catalog``.

Workspace-wide reference data. The first member is
``catalog.procedure_code`` — the CareStack procedure-code catalog
(CDT/CPT lookup) — added by ENG-420.

## Tenant scoping decision (ENG-420)

Unlike every other per-tenant domain in this codebase, the procedure-
code catalog is intentionally **workspace-wide** (no ``tenant_id``):

* CDT codes are the ADA-published US dental code standard. They are
  a fixed reference list, not per-tenant data.
* The CareStack ``carestack_code_id`` column is a CareStack-internal
  surrogate. Today we operate against a single CareStack account, so
  the id namespace is effectively global; if a future tenant produces
  a colliding id we revisit then.
* Workspace-wide storage gives every domain a trivial join through
  the resolver service without threading ``tenant_id`` through
  analytics / timeline queries.

## Primary key (ENG-420 fix)

The PK is the codebase-standard ``UUID`` (root ``CLAUDE.md`` invariant
#8 — UUID primary keys everywhere). The CareStack procedure-code id
lives on ``carestack_code_id`` (``BIGINT NOT NULL UNIQUE``) — that is
the natural / business key the upstream API returns, the resolver
looks up, and the idempotent upsert keys on.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy import BigInteger, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "catalog"


class ProcedureCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """CareStack procedure-code catalog row.

    Mirrors ``GET /api/v1.0/procedure-codes``. Fields per
    ``docs/integrations/carestack/resources/procedure-codes.md``:

    * ``id`` — UUID primary key (codebase invariant #8).
    * ``carestack_code_id`` — CareStack procedure code id (e.g.
      ``117408``). The natural business key the resolver and the
      idempotent upsert key on. ``BIGINT NOT NULL UNIQUE``.
    * ``code`` — CDT/CPT code string (e.g. ``"D7240"``).
    * ``description`` — human-readable description.
    * ``code_type_id`` — 1 Dental, 2 Medical, 3 Other.
    * ``cdt_category_id`` — 0..12, CDT category enum (see resource doc).
    * ``payload`` — verbatim CareStack entry so a future column
      extension does not require a re-pull.

    No PHI. This is reference data; every column is safe to log.
    """

    __tablename__ = "procedure_code"
    __table_args__ = (
        UniqueConstraint(
            "carestack_code_id",
            name="uq_procedure_code_carestack_code_id",
        ),
        Index(
            "ix_procedure_code_carestack_code_id",
            "carestack_code_id",
        ),
        {"schema": SCHEMA},
    )

    carestack_code_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_type_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cdt_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
