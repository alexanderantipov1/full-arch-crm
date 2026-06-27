"""Pydantic DTOs for the notification layer (ENG-436, Block C).

``*In`` schemas are the service inputs; ``*Out`` schemas are read-only
projections that accept ORM rows via ``model_validate(obj)``. Kept in a
dedicated module so the messenger layer stays separable from the legacy
provider-plumbing DTOs in ``schemas.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NotificationProviderKind = Literal["mattermost", "slack", "telegram"]
NotificationOutboxStatus = Literal["pending", "locked", "sent", "failed"]


# --- NotificationRule ---


class NotificationRuleIn(BaseModel):
    """Operator-supplied notification rule definition."""

    event_type: str = Field(min_length=1, max_length=128)
    channel: str = Field(min_length=1, max_length=255)
    conditions: list[dict[str, object]] = Field(default_factory=list)
    template: dict[str, object] = Field(default_factory=dict)
    provider_kind: NotificationProviderKind = "mattermost"
    enabled: bool = True
    description: str | None = Field(default=None, max_length=255)


class NotificationRulePatch(BaseModel):
    """Partial update for an existing rule (ENG-458, admin API).

    Every field is optional; only the supplied fields are changed. The
    common case is toggling ``enabled``. ``channel`` accepts a channel
    NAME or id — the route resolves a name to an id before storing.
    ``event_type``/``channel`` cannot be cleared (the rule's identity),
    so they are validated non-empty when present.
    """

    event_type: str | None = Field(default=None, min_length=1, max_length=128)
    channel: str | None = Field(default=None, min_length=1, max_length=255)
    conditions: list[dict[str, object]] | None = None
    template: dict[str, object] | None = None
    provider_kind: NotificationProviderKind | None = None
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=255)


class NotificationRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    event_type: str
    channel: str
    conditions: list[dict[str, object]]
    template: dict[str, object]
    provider_kind: str
    enabled: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class NotificationRuleListOut(BaseModel):
    """List projection for the admin rules endpoint."""

    items: list[NotificationRuleOut]


# --- NotificationOutbox ---


class NotificationOutboxIn(BaseModel):
    """A message to enqueue for chat dispatch."""

    event_type: str = Field(min_length=1, max_length=128)
    channel: str = Field(min_length=1, max_length=255)
    payload: dict[str, object] = Field(default_factory=dict)
    provider_kind: NotificationProviderKind = "mattermost"
    rule_id: UUID | None = None
    scheduled_for: datetime | None = None


class NotificationOutboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    event_type: str
    rule_id: UUID | None
    channel: str
    provider_kind: str
    payload: dict[str, object]
    status: str
    scheduled_for: datetime
    locked_by: str | None
    locked_at: datetime | None
    attempts: int
    sent_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "NotificationOutboxIn",
    "NotificationOutboxOut",
    "NotificationOutboxStatus",
    "NotificationProviderKind",
    "NotificationRuleIn",
    "NotificationRuleListOut",
    "NotificationRuleOut",
    "NotificationRulePatch",
]
