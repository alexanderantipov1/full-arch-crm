"""Pydantic schemas for the insight domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CatalogProposalTypeValue = Literal["mapping", "source_drift", "gap"]
CatalogProposalStatusValue = Literal["proposed", "approved", "rejected", "unresolved"]
CatalogReviewStatusValue = Literal["approved"]


class SemanticCatalogProposalIn(BaseModel):
    proposal_type: CatalogProposalTypeValue = "mapping"
    raw_value: str = Field(..., min_length=1, max_length=512)
    source_system: str = Field(..., min_length=1, max_length=96)
    source_field: str = Field(..., min_length=1, max_length=240)
    suggested_term: str = Field(..., min_length=1, max_length=240)
    definition: str = Field(..., min_length=1)
    synonyms: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(..., min_length=1)
    reviewer_note: str | None = None
    affected_questions: list[str] = Field(default_factory=list)
    affected_read_models: list[str] = Field(default_factory=list)
    affected_reports: list[str] = Field(default_factory=list)
    affected_dashboard_panels: list[str] = Field(default_factory=list)
    affected_chat_answers: list[str] = Field(default_factory=list)
    affected_agent_briefs: list[str] = Field(default_factory=list)
    source_references: list[dict[str, Any]] = Field(default_factory=list)


class SemanticCatalogProposalUpdate(BaseModel):
    raw_value: str | None = Field(default=None, min_length=1, max_length=512)
    source_system: str | None = Field(default=None, min_length=1, max_length=96)
    source_field: str | None = Field(default=None, min_length=1, max_length=240)
    suggested_term: str | None = Field(default=None, min_length=1, max_length=240)
    definition: str | None = Field(default=None, min_length=1)
    synonyms: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = Field(default=None, min_length=1)
    reviewer_note: str | None = None
    affected_questions: list[str] | None = None
    affected_read_models: list[str] | None = None
    affected_reports: list[str] | None = None
    affected_dashboard_panels: list[str] | None = None
    affected_chat_answers: list[str] | None = None
    affected_agent_briefs: list[str] | None = None
    source_references: list[dict[str, Any]] | None = None


class CatalogProposalReviewIn(BaseModel):
    reviewer_note: str | None = None


class CatalogProposalApprovalIn(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=240)
    definition: str | None = Field(default=None, min_length=1)
    synonyms: list[str] | None = None
    allowed_data_sources: list[str] | None = None
    data_classes: list[str] | None = None
    allowed_outputs: list[str] | None = None
    canonical_fields: list[str] | None = None
    row_level_fields: list[str] | None = None
    aggregate_metrics: list[str] | None = None
    used_by: list[str] | None = None
    source_references: list[dict[str, Any]] | None = None
    reason: str | None = Field(default=None, min_length=1)
    reviewer_note: str | None = None
    affected_questions: list[str] | None = None
    affected_read_models: list[str] | None = None
    affected_reports: list[str] | None = None
    affected_dashboard_panels: list[str] | None = None
    affected_chat_answers: list[str] | None = None
    affected_agent_briefs: list[str] | None = None


class SemanticCatalogProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    proposal_type: CatalogProposalTypeValue
    raw_value: str
    source_system: str
    source_field: str
    suggested_term: str
    definition: str
    synonyms: list[str]
    confidence: float | None
    reason: str
    reviewer_note: str | None
    affected_questions: list[str]
    affected_read_models: list[str]
    affected_reports: list[str]
    affected_dashboard_panels: list[str]
    affected_chat_answers: list[str]
    affected_agent_briefs: list[str]
    source_references: list[dict[str, Any]]
    status: CatalogProposalStatusValue
    created_by_actor_id: UUID | None
    reviewed_by_actor_id: UUID | None
    reviewed_at: datetime | None
    approved_version_id: UUID | None
    created_at: datetime
    updated_at: datetime


class SemanticCatalogVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    term: str
    version: int
    review_status: CatalogReviewStatusValue
    definition: str
    synonyms: list[str]
    allowed_data_sources: list[str]
    data_classes: list[str]
    allowed_outputs: list[str]
    canonical_fields: list[str]
    row_level_fields: list[str]
    aggregate_metrics: list[str]
    used_by: list[str]
    source_references: list[dict[str, Any]]
    previous_version_id: UUID | None
    proposal_id: UUID | None
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any]
    reason: str
    affected_questions: list[str]
    affected_read_models: list[str]
    affected_reports: list[str]
    affected_dashboard_panels: list[str]
    affected_chat_answers: list[str]
    affected_agent_briefs: list[str]
    approved_by_actor_id: UUID | None
    approved_at: datetime
    created_at: datetime
    updated_at: datetime


class CatalogApprovalOut(BaseModel):
    proposal: SemanticCatalogProposalOut
    version: SemanticCatalogVersionOut
