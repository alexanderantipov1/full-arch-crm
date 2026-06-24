"""Enrichment DTOs (input/output).

Inputs end with ``In``, outputs with ``Out`` (per ``packages/CLAUDE.md``).
Outputs use ``from_attributes`` so the service can ``model_validate`` an ORM
``RecordAnnotation`` directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AnnotationSource = Literal["ui", "chat", "agent"]


class AnnotationIn(BaseModel):
    """One annotation to record on a canonical entity.

    ``value`` is a flexible JSON object; free text rides as
    ``{"text": "..."}``. ``author_actor_id`` is optional — the UI write path
    may not resolve an actor yet, and the chat/agent paths (Block G) supply it.
    """

    subject_type: str = Field(min_length=1, max_length=64)
    subject_id: UUID
    key: str = Field(min_length=1, max_length=128)
    value: dict[str, object] = Field(default_factory=dict)
    source: AnnotationSource
    note: str | None = None
    author_actor_id: UUID | None = None


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    subject_type: str
    subject_id: UUID
    key: str
    value: dict[str, object]
    source: AnnotationSource
    note: str | None
    author_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AnnotationListOut(BaseModel):
    """Envelope for a subject's annotation list."""

    items: list[AnnotationOut]
