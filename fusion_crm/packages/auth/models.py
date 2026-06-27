"""Auth models: ``Credential``, ``Session``, ``ApiKey``.

Polymorphic auth via ``subject_type`` (`actor | portal_account`). Plaintext
passwords / tokens NEVER persist — only hashes.

`portal_account` and `permission_grant` tables are deferred to M11 and M8
respectively; the `subject_type` CHECK already includes the value so M11
adds the table without an ALTER CHECK.

Every per-tenant table inherits :class:`TenantScopedMixin` (ENG-128). The
ENG-123 4/4 migration added ``tenant_id`` to ``credential``, ``session``,
and ``api_key`` — sessions and api keys are issued in a tenant context and
the credential record is owned by the tenant of its subject.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "auth"


class Credential(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Password / MFA / OAuth / SSO / WebAuthn record for an Actor or PortalAccount.

    Polymorphic by ``subject_type`` — no DB-level FK, since the foreign
    table differs (``actor.actor`` vs ``auth.portal_account``). The CHECK
    accepts both values from day one so M11's portal arrival doesn't
    require a CHECK rewrite.

    The partial unique index ``uq_credential_subject_kind_active`` enforces
    "at most one ACTIVE credential of a given kind per subject" while
    leaving room for revoked / expired history rows.
    """

    __tablename__ = "credential"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('actor', 'portal_account')",
            name="subject_type",
        ),
        CheckConstraint(
            "credential_kind IN "
            "('password', 'mfa_totp', 'oauth_external', 'sso_subject', 'webauthn')",
            name="credential_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="status",
        ),
        Index("ix_credential_tenant_id", "tenant_id"),
        Index("ix_credential_subject", "subject_type", "subject_id"),
        Index("ix_credential_status", "status"),
        Index(
            "uq_credential_subject_kind_active",
            "subject_type",
            "subject_id",
            "credential_kind",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        {"schema": SCHEMA},
    )

    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    credential_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_hash: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Bearer-token web session — staff cookies today, patient portal in M11.

    The raw token NEVER lives in DB; ``token_hash`` is sha256(plaintext).
    Active-session lookups go through the partial indexes
    (``ix_session_subject_active``, ``ix_session_expires``) which only
    consider rows where ``revoked_at IS NULL``.
    """

    __tablename__ = "session"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('actor', 'portal_account')",
            name="subject_type",
        ),
        UniqueConstraint("token_hash", name="uq_session_token_hash"),
        Index("ix_session_tenant_id", "tenant_id"),
        Index(
            "ix_session_subject_active",
            "subject_type",
            "subject_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_session_expires",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        {"schema": SCHEMA},
    )

    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    ip_address: Mapped[Any | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Service-to-service bearer token. Always linked to an Actor.

    Used by MCP server clients (Claude Code, Codex), CI tooling, future
    integrations. Plaintext token shown ONCE on issue; rotation = new key
    + revoke old.

    ``token_prefix`` is the first ~8 chars of the plaintext for display
    (matches the bearer namespace `fcrm_xxx12345…`).
    """

    __tablename__ = "api_key"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_api_key_token_hash"),
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="status",
        ),
        Index("ix_api_key_tenant_id", "tenant_id"),
        Index("ix_api_key_actor_id", "actor_id"),
        Index("ix_api_key_status", "status"),
        {"schema": SCHEMA},
    )

    name: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="RESTRICT"),
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
