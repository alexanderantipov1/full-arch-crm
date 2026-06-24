"""Pydantic DTOs for the actor domain (DTOs crossing service boundaries)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ActorType = Literal["human", "ai", "system", "external_service"]
ActorStatus = Literal["active", "inactive", "retired"]
AvailabilityStatus = Literal["available", "busy", "offline", "oncall"]


class ActorIdentifierIn(BaseModel):
    kind: str = Field(..., examples=["salesforce_user_id", "email"])
    value: str = Field(..., min_length=1, max_length=320)


class ActorIdentifierOut(ActorIdentifierIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: UUID
    created_at: datetime


class ActorIn(BaseModel):
    actor_type: ActorType
    name: str = Field(..., min_length=1, max_length=240)
    role: str | None = None
    status: ActorStatus = "active"
    email: str | None = None
    phone: str | None = None
    person_uid: UUID | None = None
    availability_status: AvailabilityStatus = "available"
    meta: dict[str, object] = Field(default_factory=dict)
    identifiers: list[ActorIdentifierIn] = Field(default_factory=list)


class ActorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_type: ActorType
    name: str
    role: str | None
    status: ActorStatus
    email: str | None
    phone: str | None
    person_uid: UUID | None
    availability_status: AvailabilityStatus
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime
    identifiers: list[ActorIdentifierOut] = Field(default_factory=list)


# --- ENG-546: Messenger settings — provider → Mattermost username mapping ----


class ProviderMessengerMappingOut(BaseModel):
    """One CareStack provider (doctor) and its current Mattermost username.

    Powers the staff Messenger-settings card: each ``carestack_provider_id``
    actor with the ``mattermost_username`` it is mapped to (or ``None`` when
    unmapped). The username is what the consult-reminder @mentions (ENG-543).
    """

    actor_id: UUID
    actor_name: str
    carestack_provider_id: str
    mattermost_username: str | None


class ProviderMessengerMappingListOut(BaseModel):
    items: list[ProviderMessengerMappingOut] = Field(default_factory=list)


class SetProviderMessengerUsernameIn(BaseModel):
    mattermost_username: str = Field(..., min_length=1, max_length=320)
