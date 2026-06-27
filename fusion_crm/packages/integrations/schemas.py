"""Pydantic DTOs for the integrations domain.

In-going (``*In``) and out-going (``*Out``) schemas for service boundaries.
Token fields are NEVER included in ``Out`` schemas — the public surface
(``GET /integrations/<provider>/status``) returns connection state, not creds.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["pull", "push", "both"]
SyncDirection = Literal["inbound", "pull", "push", "cdc", "webhook"]
AccountStatus = Literal["connected", "disconnected", "error", "expired"]
SyncStatus = Literal[
    "running",
    "succeeded",
    "success",
    "failed",
    "partial",
    "skipped_credential",
]


# --- IntegrationAccount ---


class IntegrationAccountIn(BaseModel):
    """Inputs accepted by ``IntegrationService.upsert_account``.

    ``access_token`` / ``refresh_token`` are accepted in plaintext and stored
    encrypted by the column type. ``meta`` is provider-specific (see
    ``CLAUDE.md`` for shapes).
    """

    provider: str = Field(..., examples=["salesforce", "carestack", "hubspot"])
    company_uid: UUID | None = None
    status: AccountStatus = "connected"
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    meta: dict[str, object] = Field(default_factory=dict)


class IntegrationAccountOut(BaseModel):
    """Outputs from ``IntegrationService``. Tokens are NEVER returned."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    company_uid: UUID
    status: AccountStatus
    token_expires_at: datetime | None
    scopes: list[str]
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime


# --- ObjectMapping ---


class ObjectMappingIn(BaseModel):
    sf_object: str
    our_target: str
    field_map: dict[str, object] = Field(default_factory=dict)
    direction: Direction = "both"
    enabled: bool = True


class ObjectMappingOut(ObjectMappingIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    created_at: datetime
    updated_at: datetime


# --- SyncRun ---


class SyncRunIn(BaseModel):
    sf_object: str | None = None
    direction: SyncDirection
    meta: dict[str, object] = Field(default_factory=dict)


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    sf_object: str | None
    direction: SyncDirection
    status: SyncStatus
    started_at: datetime
    finished_at: datetime | None
    records_total: int
    records_succeeded: int
    records_failed: int
    error: str | None
    meta: dict[str, object]


class SyncRunUpdate(BaseModel):
    """Patch payload to close out a SyncRun."""

    status: SyncStatus
    records_total: int | None = None
    records_succeeded: int | None = None
    records_failed: int | None = None
    error: str | None = None
    meta: dict[str, object] | None = None


# --- CDCCursor ---


class CDCCursorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    channel: str
    replay_id: int | None
    updated_at: datetime


# --- ExternalEntity ---


class ExternalEntityIn(BaseModel):
    object_type: str
    external_id: str
    person_uid: UUID | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    last_modified: datetime | None = None


class ExternalEntityOut(ExternalEntityIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    created_at: datetime
    updated_at: datetime
