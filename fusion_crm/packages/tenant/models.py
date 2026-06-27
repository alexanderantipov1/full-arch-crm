"""Tenant domain models — schema ``tenant``.

Four tables per ADR-0003:

- ``tenant.tenant`` — root entity per clinic / customer.
- ``tenant.location`` — physical offices belonging to a tenant.
- ``tenant.integration_credential`` — encrypted-by-convention provider
  credentials per tenant per integration.
- ``tenant.setting`` — typed key/JSON-value config per tenant.

The four tables are the universe of tenant configuration; per-tenant
data in every other domain references ``tenant.tenant.id`` via plain
UUID columns (no cross-schema model imports).

Multi-mailbox addendum (ENG-125, 2026-05-09): ``integration_credential``
gains four columns to support multiple Google / Microsoft mailboxes
per tenant: ``mailbox_email``, ``location_id``, ``is_default``, and
``tags``. Existing ``(tenant_id, provider_kind, credential_kind)``
remains non-unique on purpose — multi-mailbox depends on that.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "tenant"

# --- Allowed enum-like value tuples (kept in sync with CHECK constraints in migrations).
TENANT_STATUSES = ("active", "paused", "archived")

# Provider list expanded in ENG-125 (2026-05-09) to cover the marketing /
# OS / payments stack the operator wires up alongside SF + CareStack.
# Mirrors the Zod ProviderSchema on the frontend (apps/web/lib/api/schemas).
PROVIDER_KINDS = (
    # Existing core integrations
    "salesforce",
    "hubspot",
    "carestack",
    "open_dental",
    # Voice / call / messaging
    "vapi",
    "twilio",
    # Models / inference vendors
    "openai",
    "anthropic",
    "elevenlabs",
    "deepgram",
    # Email / productivity (multi-mailbox uses these heavily)
    "google_workspace",
    "microsoft_365",
    # Reputation / reviews
    "birdeye",
    "podium",
    "google_business",
    # Payments / patient finance
    "stripe",
    "square",
    "carecredit",
    "sunbit",
    "cherry",
    # Analytics / pixels
    "google_analytics",
    "meta_pixel",
    "tiktok_pixel",
    # Corporate chat / messenger (ENG-435)
    "mattermost",
    # Marketing / SEO ad platforms (ENG-489) — per-tenant credential payloads
    # for the ad-spend ingest connectors (packages/ingest/*_campaign_service.py)
    # and the marketing analytics surface (packages/marketing).
    "google_ads",
    "meta_ads",
    "google_search_console",
    # Catch-all
    "other",
)

# Email-OAuth providers — the ones for which ``mailbox_email`` is meaningful.
# Used by ``IntegrationCredentialService.upsert`` to key on
# ``(tenant_id, provider_kind, credential_kind, mailbox_email)`` instead of
# the single-instance triple.
MAILBOX_PROVIDER_KINDS = frozenset({"google_workspace", "microsoft_365"})

CREDENTIAL_KINDS = ("oauth_token", "api_key", "password_grant", "webhook_secret")
CREDENTIAL_STATUSES = ("active", "expired", "revoked")


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Root entity for a tenant (one clinic / customer)."""

    __tablename__ = "tenant"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenant_slug"),
        CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="status",
        ),
        Index("ix_tenant_status", "status"),
        {"schema": SCHEMA},
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    primary_email: Mapped[str | None] = mapped_column(String(320))
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'America/Los_Angeles'"),
    )
    locale: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'en-US'"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )

    locations: Mapped[list[Location]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Physical office belonging to a tenant.

    ``external_ref`` JSONB carries provider linkage, e.g.
    ``{"carestack_location_id": 10029}``. ``timezone_override`` falls
    back to ``Tenant.timezone`` when null.
    """

    __tablename__ = "location"
    __table_args__ = (
        # Identity is the upstream provider id, not the display name —
        # CareStack tenants legitimately ship multiple locations with
        # the same operator-facing "name" (different branches share
        # the brand). The (tenant_id, carestack_location_id) partial
        # unique enforces idempotent sync; manual operator-created
        # rows (no external_ref) are deduplicated at the service
        # layer via ``find_by_name``.
        Index("ix_location_tenant_id", "tenant_id"),
        Index(
            "ix_location_active",
            "tenant_id",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "uq_location_tenant_id_carestack_id",
            "tenant_id",
            text("(external_ref ->> 'carestack_location_id')"),
            unique=True,
            postgresql_where=text("external_ref ? 'carestack_location_id'"),
        ),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_ref: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(64))
    address_line1: Mapped[str | None] = mapped_column(String(240))
    address_line2: Mapped[str | None] = mapped_column(String(240))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(64))
    zip: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    timezone_override: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="locations")


class IntegrationCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-tenant per-provider credential record.

    ``payload`` JSONB holds the actual secret material — values MUST be
    Fernet-encrypted at the application layer (see
    ``packages.integrations.crypto.encrypt_str``) BEFORE handing the
    payload to the service. This column is JSONB only because Postgres
    has no native ciphertext type; encryption is enforced by convention
    and code review, not by a column type.

    Multi-mailbox columns (ENG-125):

    - ``mailbox_email`` — for ``google_workspace`` / ``microsoft_365``
      grants, the resolved ``me@domain`` from the OAuth flow. Null for
      every other provider; the ``IntegrationCredentialService`` uses it
      as part of the upsert key.
    - ``location_id`` — optional FK to ``tenant.location.id`` so a
      credential can be pinned to a specific office. ON DELETE SET NULL
      so deleting a location does not break unrelated routing rules.
    - ``is_default`` — exactly one default per
      ``(tenant_id, provider_kind)`` is enforced by a partial unique
      index. The default credential is what ``read_for`` /
      ``read_default`` returns when the caller has no location/mailbox
      context.
    - ``tags`` — operator-set free-form labels (``["marketing",
      "consult-followup"]``). Indexed by GIN for routing-rule lookup.
    """

    __tablename__ = "integration_credential"
    __table_args__ = (
        CheckConstraint(
            "provider_kind IN ("
            + ", ".join(f"'{p}'" for p in PROVIDER_KINDS)
            + ")",
            name="provider_kind",
        ),
        CheckConstraint(
            "credential_kind IN "
            "('oauth_token', 'api_key', 'password_grant', 'webhook_secret')",
            name="credential_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name="status",
        ),
        Index("ix_integration_credential_tenant_id", "tenant_id"),
        Index(
            "ix_integration_credential_active",
            "tenant_id",
            "provider_kind",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            # Partial unique: at most one default per tenant per provider.
            # This is the routing-rule fallback target.
            "uq_integration_credential_default",
            "tenant_id",
            "provider_kind",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        Index(
            "ix_integration_credential_mailbox",
            "tenant_id",
            "provider_kind",
            "mailbox_email",
            postgresql_where=text("mailbox_email IS NOT NULL"),
        ),
        Index(
            "ix_integration_credential_location_id",
            "location_id",
            postgresql_where=text("location_id IS NOT NULL"),
        ),
        Index(
            "ix_integration_credential_tags",
            "tags",
            postgresql_using="gin",
        ),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    credential_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    display_name: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Multi-mailbox columns (ENG-125, 2026-05-09).
    mailbox_email: Mapped[str | None] = mapped_column(String(320))
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.location.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )


class Setting(Base):
    """Per-tenant key-value configuration; composite PK ``(tenant_id, key)``."""

    __tablename__ = "setting"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "key", name="pk_setting"),
        Index("ix_setting_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
