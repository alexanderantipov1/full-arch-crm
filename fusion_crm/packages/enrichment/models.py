"""Enrichment models: staff/agent-authored annotations on canonical entities.

The single table here IS the ``enrichment`` schema:

- ``RecordAnnotation`` — one of *our own* fields set on a canonical entity
  (a person, lead, opportunity, …) identified by ``(subject_type,
  subject_id)``. ``key`` is the annotation field name, ``value`` is a
  flexible JSONB value (free text rides as ``{"text": "..."}``).

Cross-domain references are plain UUID columns, never Python imports:

- ``subject_id`` is the entity id (the ``person_uid`` when
  ``subject_type == "person"``). It is intentionally NOT a DB foreign key —
  the subject can be any canonical entity across schemas, so a single FK
  target does not exist.
- ``author_actor_id`` references ``actor.actor.id`` via a DB-level FK string
  only; we never import the actor models here.

The table is append-friendly: it keeps the full history of annotations and
is NOT unique on ``(tenant_id, subject_type, subject_id, key)``. The service
exposes ``latest_per_key`` for callers that want the current value per key.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "enrichment"

# Where an annotation came from. ``ui`` = staff frontend write path (now),
# ``chat`` = messenger action path (Block G), ``agent`` = AI agent tool path.
ANNOTATION_SOURCES = ("ui", "chat", "agent")


class RecordAnnotation(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One staff/agent-authored field on a canonical entity.

    ``value`` is JSONB so the same table holds free text (``{"text": "..."}``),
    structured selections (``{"choice": "morning"}``), or richer payloads
    without a schema migration per annotation kind.
    """

    __tablename__ = "record_annotation"
    __table_args__ = (
        CheckConstraint(
            "source IN ('ui', 'chat', 'agent')",
            name="source",
        ),
        Index("ix_record_annotation_tenant_id", "tenant_id"),
        Index(
            "ix_record_annotation_subject",
            "tenant_id",
            "subject_type",
            "subject_id",
        ),
        {"schema": SCHEMA},
    )

    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    author_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text)
