"""Reusable column mixins.

Every persisted entity in the platform uses UUID primary keys and timestamp
columns. Centralising the definitions keeps domain models focused on
domain-specific fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """UUID4 primary key, generated client-side for traceability across services."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """created_at / updated_at, server-managed."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantScopedMixin:
    """Adds a NOT NULL ``tenant_id`` column referencing ``tenant.tenant.id``.

    Reserved for the follow-up that threads ``tenant_id`` through every
    service / repository (ENG-123 splits the schema work from the
    application-layer signature sweep — see ADR-0003 §"Isolation
    model"). Existing models do NOT yet inherit this mixin; a separate
    ticket lands the per-domain refactor.

    The migration set under ENG-123 (1/4..4/4) creates the DB column on
    every per-tenant table with a server_default to the bootstrap
    tenant id, so existing INSERTs that have not been threaded with
    ``tenant_id`` keep working in Phase 1 single-tenant. The follow-up
    PR drops the server_default once every call site is wired.

    The cross-schema FK string ``"tenant.tenant.id"`` resolves at
    constraint-creation time (Postgres + Alembic), so this mixin
    works regardless of model import order.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
