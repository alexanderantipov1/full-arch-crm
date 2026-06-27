"""Agent runtime persistence models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "audit"


class AgentRuntimeRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Safe summary of one agent runtime execution."""

    __tablename__ = "agent_runtime_run"
    __table_args__ = (
        Index("ix_agent_runtime_run_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_agent_runtime_run_tenant_status", "tenant_id", "status"),
        Index("ix_agent_runtime_run_tenant_run_kind", "tenant_id", "run_kind"),
        {"schema": SCHEMA},
    )

    trigger_actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    trigger_actor_email: Mapped[str | None] = mapped_column(String(320))
    agent_name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    run_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    tool_calls: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    result_posture: Mapped[str] = mapped_column(String(80), nullable=False)
    audit_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)


class AgentRuntimeApprovalRequest(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    TenantScopedMixin,
    Base,
):
    """Safe human approval boundary for agent-proposed actions."""

    __tablename__ = "agent_runtime_approval_request"
    __table_args__ = (
        Index(
            "ix_agent_runtime_approval_tenant_created_at",
            "tenant_id",
            "created_at",
        ),
        Index("ix_agent_runtime_approval_tenant_status", "tenant_id", "status"),
        Index(
            "ix_agent_runtime_approval_tenant_target_kind",
            "tenant_id",
            "target_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'needs_edit', 'unresolved')",
            name="status",
        ),
        CheckConstraint(
            "target_kind IN ("
            "'semantic_catalog_mapping_proposal', "
            "'semantic_catalog_impact_preview', "
            "'large_analysis_run', "
            "'export_request', "
            "'write_tool_execution'"
            ")",
            name="target_kind",
        ),
        {"schema": SCHEMA},
    )

    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audit.agent_runtime_run.id", ondelete="SET NULL"),
    )
    requested_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    requested_by_actor_email: Mapped[str | None] = mapped_column(String(320))
    decided_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    decided_by_actor_email: Mapped[str | None] = mapped_column(String(320))
    agent_name: Mapped[str] = mapped_column(String(160), nullable=False)
    tool_id: Mapped[str | None] = mapped_column(String(160))
    target_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    target_ref: Mapped[str | None] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    requested_action: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_classes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    affected_surfaces: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    risk_flags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    approval_posture: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_summary: Mapped[str | None] = mapped_column(Text)
    edit_summary: Mapped[str | None] = mapped_column(Text)
