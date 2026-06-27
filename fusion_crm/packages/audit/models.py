"""Audit models: ``AccessLog``.

This table is append-only by convention. In production, restrict UPDATE/DELETE
on ``audit.access_log`` at the database role level.

The ``tenant_id`` column (ENG-128) is supplied by :class:`TenantScopedMixin`.
``AccessLog`` inherits the mixin even though the table never reads via a
``WHERE tenant_id`` filter today — every audit row MUST carry the tenant of
the principal that produced it, so cross-tenant audit forensics is possible
when M8 lands.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "audit"


class AccessLog(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One row per audited action (PHI read, tool call, login, ...)."""

    __tablename__ = "access_log"
    __table_args__ = (
        Index("ix_access_log_tenant_id", "tenant_id"),
        Index("ix_access_log_principal_id", "principal_id"),
        Index("ix_access_log_person_uid", "person_uid"),
        Index("ix_access_log_action", "action"),
        {"schema": SCHEMA},
    )

    principal_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    principal_email: Mapped[str | None] = mapped_column(String(320))
    person_uid: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(String(256))
    extra: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
