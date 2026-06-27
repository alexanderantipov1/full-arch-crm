"""Actor models: ``Actor`` and ``ActorIdentifier``.

An ``Actor`` is the first-class executor of work — human staff, AI agent,
system job, or external service (e.g. an MCP client). The same shape covers
all four so that workflow assignment, audit, and capability routing can
target any executor uniformly.

NOTE: this domain stores NO credentials or PHI. Auth lives in ``auth.*``,
clinical data in ``phi.*``.

Every per-tenant table inherits :class:`TenantScopedMixin` (ENG-128).
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "actor"


class Actor(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One row per executor of work.

    ``actor_type`` discriminates between humans, AI agents, system jobs, and
    external services. M1 actively uses only ``human`` + ``external_service``;
    the other two values are reserved in CHECK from day one (avoid expensive
    ALTER-CHECK in later phases).

    Optional ``person_uid`` links an actor to a Person row when the actor IS
    also a Person (e.g. a coordinator who is also a contact in our CRM).
    """

    __tablename__ = "actor"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('human', 'ai', 'system', 'external_service')",
            name="actor_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'retired')",
            name="status",
        ),
        CheckConstraint(
            "availability_status IN ('available', 'busy', 'offline', 'oncall')",
            name="availability_status",
        ),
        Index("ix_actor_tenant_id", "tenant_id"),
        Index("ix_actor_type", "actor_type"),
        Index("ix_actor_role", "role"),
        Index("ix_actor_status", "status"),
        Index("ix_actor_person_uid", "person_uid"),
        {"schema": SCHEMA},
    )

    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    role: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    person_uid: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    availability_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="available",
        server_default=text("'available'"),
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    identifiers: Mapped[list[ActorIdentifier]] = relationship(
        back_populates="actor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ActorIdentifier(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Maps an Actor to N external system IDs.

    Used kinds: ``salesforce_user_id``, ``carestack_provider_id``,
    ``carestack_coordinator_id``, ``carestack_user_id``, ``vapi_agent_id``,
    ``email``, ``phone``. ``(kind, value)`` is unique workspace-wide.
    """

    __tablename__ = "actor_identifier"
    __table_args__ = (
        UniqueConstraint("kind", "value", name="uq_actor_identifier_kind_value"),
        Index("ix_actor_identifier_tenant_id", "tenant_id"),
        Index("ix_actor_identifier_value", "value"),
        {"schema": SCHEMA},
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.actor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(320), nullable=False)

    actor: Mapped[Actor] = relationship(back_populates="identifiers")
