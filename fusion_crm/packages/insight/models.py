"""Insight domain models — schema ``insight``."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "insight"

CATALOG_PROPOSAL_TYPES = ("mapping", "source_drift", "gap")
CATALOG_PROPOSAL_STATUSES = ("proposed", "approved", "rejected", "unresolved")
CATALOG_REVIEW_STATUSES = ("approved",)


class CatalogProposalType(StrEnum):
    MAPPING = "mapping"
    SOURCE_DRIFT = "source_drift"
    GAP = "gap"


class CatalogProposalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class CatalogReviewStatus(StrEnum):
    APPROVED = "approved"


class SemanticCatalogProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human-review inbox row for a candidate catalog change."""

    __tablename__ = "semantic_catalog_proposal"
    __table_args__ = (
        sa.CheckConstraint(
            "proposal_type IN ('mapping', 'source_drift', 'gap')",
            name="proposal_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'rejected', 'unresolved')",
            name="status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        Index("ix_semantic_catalog_proposal_tenant_status", "tenant_id", "status"),
        Index("ix_semantic_catalog_proposal_tenant_term", "tenant_id", "suggested_term"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposal_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CatalogProposalType.MAPPING.value,
        server_default=text("'mapping'"),
    )
    raw_value: Mapped[str] = mapped_column(String(512), nullable=False)
    source_system: Mapped[str] = mapped_column(String(96), nullable=False)
    source_field: Mapped[str] = mapped_column(String(240), nullable=False)
    suggested_term: Mapped[str] = mapped_column(String(240), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    synonyms: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    confidence: Mapped[float | None] = mapped_column(sa.Float)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    affected_questions: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_read_models: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_reports: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_dashboard_panels: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_chat_answers: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_agent_briefs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=CatalogProposalStatus.PROPOSED.value,
        server_default=text("'proposed'"),
    )
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            f"{SCHEMA}.semantic_catalog_version.id",
            name="fk_semantic_catalog_proposal_approved_version_id_semantic_catalog_version",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )


class SemanticCatalogVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable approved catalog entry for one semantic term version."""

    __tablename__ = "semantic_catalog_version"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "term",
            "version",
            name="uq_semantic_catalog_version_tenant_term_version",
        ),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("review_status IN ('approved')", name="review_status"),
        Index("ix_semantic_catalog_version_tenant_term", "tenant_id", "term"),
        Index("ix_semantic_catalog_version_tenant_status", "tenant_id", "review_status"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    term: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=CatalogReviewStatus.APPROVED.value,
        server_default=text("'approved'"),
    )
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    synonyms: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    allowed_data_sources: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    data_classes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    allowed_outputs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    canonical_fields: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    row_level_fields: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    aggregate_metrics: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    used_by: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.semantic_catalog_version.id", ondelete="RESTRICT"),
        nullable=True,
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.semantic_catalog_proposal.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    affected_questions: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_read_models: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_reports: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_dashboard_panels: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_chat_answers: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_agent_briefs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    approved_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
