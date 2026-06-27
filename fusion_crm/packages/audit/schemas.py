"""Audit DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccessLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    principal_id: UUID | None
    principal_email: str | None
    person_uid: UUID | None
    action: str
    resource: str | None
    reason: str | None
    extra: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
