"""Pydantic DTOs for the auth domain.

OUT schemas NEVER expose raw tokens, password hashes, or session token
hashes. Only metadata fields cross the service boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SubjectType = Literal["actor", "portal_account"]
CredentialKind = Literal["password", "mfa_totp", "oauth_external", "sso_subject", "webauthn"]
CredentialStatus = Literal["active", "revoked", "expired"]
ApiKeyStatus = Literal["active", "revoked", "expired"]


class CredentialOut(BaseModel):
    """Outbound credential metadata — NEVER includes ``secret_hash``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_type: SubjectType
    subject_id: UUID
    credential_kind: CredentialKind
    status: CredentialStatus
    expires_at: datetime | None
    last_used_at: datetime | None
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime


class SessionOut(BaseModel):
    """Outbound session metadata — NEVER includes ``token_hash``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_type: SubjectType
    subject_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    last_seen_at: datetime
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime


class ApiKeyOut(BaseModel):
    """Outbound API-key metadata — NEVER includes ``token_hash``.

    ``token_prefix`` is safe to display (helps users identify which key is
    in their config).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    actor_id: UUID
    token_prefix: str
    scopes: list[str]
    status: ApiKeyStatus
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_by_actor_id: UUID | None
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime


class IssueSessionResult(BaseModel):
    """One-time issue result for a session.

    The ``raw_token`` is shown ONCE — caller (router) must immediately set
    it as a cookie. The ``session`` payload is metadata only.
    """

    raw_token: str = Field(..., description="Plaintext bearer token, shown once")
    session: SessionOut


class IssueApiKeyResult(BaseModel):
    """One-time issue result for an API key.

    The ``raw_token`` is shown ONCE; rotation requires a new issue + revoke.
    """

    raw_token: str = Field(..., description="Plaintext API key, shown once")
    api_key: ApiKeyOut


class IssueApiKeyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=240)
    actor_id: UUID
    scopes: list[str] = Field(default_factory=list)
    ttl_days: int | None = None
    created_by_actor_id: UUID | None = None
    meta: dict[str, object] = Field(default_factory=dict)
