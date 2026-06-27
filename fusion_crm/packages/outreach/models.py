"""Outreach domain models — schema ``outreach``.

Five tables per ADR-0004 and ENG-133:

- ``outreach.template`` — operator-edited Mustache+MJML email templates,
  versioned, with a ``tracking_enabled`` gate keyed off ``category``.
- ``outreach.campaign`` — a scheduled / immediate batch send referencing
  one ``template`` and one mailbox credential (or auto-route).
- ``outreach.send`` — one row per recipient per campaign, the durable
  source of truth for "what we attempted".
- ``outreach.suppression`` — per-tenant unsubscribe / bounce list,
  composite primary key on ``(tenant_id, recipient_email_normalised)``.
- ``outreach.outbound_queue`` — Postgres-backed work queue for the
  ``outreach.dispatcher`` arq worker (ADR-0004 decision #1). Supports
  ``SELECT … FOR UPDATE SKIP LOCKED`` pulls.

Tenant scoping (per ADR-0003 + ENG-128 sweep): every per-tenant table
declares ``tenant_id`` as a NOT NULL UUID column with a cross-schema
FK to ``tenant.tenant.id``. We declare the column directly (instead of
inheriting ``TenantScopedMixin``) so this domain stays decoupled from
the ENG-128 reconciliation work; the ENG-128 sweep can swap us to the
mixin at its convenience without changing semantics.

ENG-132 addendum (2026-05-10): ``send.campaign_id`` is now NULLABLE so
the ``SendService.enqueue_single`` transactional path (appointment
reminders, consult confirmations) can write a send row without a
campaign. See migration ``d7e9f5b3c1a8`` for the DB-level flip.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "outreach"

# Allowed enum-like value tuples (mirrored in CHECK constraints in the
# migration). Keep these in sync with the Pydantic Literals in schemas.py.
TEMPLATE_BODY_FORMATS = ("markdown", "html", "mjml")
TEMPLATE_CATEGORIES = ("marketing", "clinical", "transactional", "operational")
TEMPLATE_STATUSES = ("draft", "active", "archived")

CAMPAIGN_STATUSES = ("draft", "queued", "sending", "sent", "failed", "cancelled")
CAMPAIGN_MAILBOX_STRATEGIES = ("explicit", "auto_route")

SEND_STATUSES = (
    "queued",
    "sent",
    "bounced",
    "failed",
    "unsubscribed",
    "opened",
)

SUPPRESSION_REASONS = (
    "operator",
    "one_click",
    "bounce_hard",
    "complaint",
)

OUTBOUND_QUEUE_STATUSES = ("pending", "locked", "succeeded", "failed")


# Categories for which tracking_enabled defaults to false AND the service
# refuses to flip true. Marketing is the only category permitted to opt in.
TRACKING_FORBIDDEN_CATEGORIES = frozenset({"clinical", "transactional", "operational"})


class TemplateBodyFormat(StrEnum):
    MARKDOWN = "markdown"
    HTML = "html"
    MJML = "mjml"


class TemplateCategory(StrEnum):
    MARKETING = "marketing"
    CLINICAL = "clinical"
    TRANSACTIONAL = "transactional"
    OPERATIONAL = "operational"


class TemplateStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CampaignMailboxStrategy(StrEnum):
    EXPLICIT = "explicit"
    AUTO_ROUTE = "auto_route"


class SendStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    BOUNCED = "bounced"
    FAILED = "failed"
    UNSUBSCRIBED = "unsubscribed"
    OPENED = "opened"


class SuppressionReason(StrEnum):
    OPERATOR = "operator"
    ONE_CLICK = "one_click"
    BOUNCE_HARD = "bounce_hard"
    COMPLAINT = "complaint"


class OutboundQueueStatus(StrEnum):
    PENDING = "pending"
    LOCKED = "locked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# --- outreach.template ----------------------------------------------------


class Template(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned operator-edited email template.

    The ``subject_template`` and ``body_template`` columns are Mustache
    strings; the renderer (``packages.outreach.render``) substitutes
    placeholders from a tightly-scoped ``PersonRenderContext`` and
    produces a final ``RenderedEmail``. ``body_format`` selects the
    pipeline:

    - ``markdown`` — Mustache → Markdown → HTML
    - ``mjml``     — Mustache → MJML envelope (curated block library)
    - ``html``     — REJECTED at the service layer in Stage 1 (operator-
      supplied raw HTML is too risky pre-PHI). Enum value retained so
      future stages can flip the gate without a migration.
    """

    __tablename__ = "template"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_template_tenant_id_name"),
        sa.CheckConstraint(
            "body_format IN ('markdown', 'html', 'mjml')",
            name="body_format",
        ),
        sa.CheckConstraint(
            "category IN ('marketing', 'clinical', 'transactional', 'operational')",
            name="category",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="status",
        ),
        Index("ix_template_tenant_id", "tenant_id"),
        Index("ix_template_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_format: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TemplateBodyFormat.MARKDOWN.value,
        server_default=text("'markdown'"),
    )
    category: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=TemplateCategory.MARKETING.value,
        server_default=text("'marketing'"),
    )
    tracking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    intent_tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TemplateStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )


# --- outreach.campaign ----------------------------------------------------


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scheduled or immediate outreach batch.

    Holds the recipient query (a JSON DSL evaluated against
    ``IdentityService`` at preview / enqueue time) and either an
    explicit mailbox credential or the ``auto_route`` strategy. The
    full enqueue + send pipeline lives under ENG-132; this row is the
    single durable record of "what the operator asked us to send".
    """

    __tablename__ = "campaign"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ("
            "'draft', 'queued', 'sending', 'sent', 'failed', 'cancelled'"
            ")",
            name="status",
        ),
        sa.CheckConstraint(
            "mailbox_strategy IN ('explicit', 'auto_route')",
            name="mailbox_strategy",
        ),
        Index("ix_campaign_tenant_id", "tenant_id"),
        Index("ix_campaign_status", "tenant_id", "status"),
        Index("ix_campaign_template_id", "template_id"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.template.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    recipient_query: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    mailbox_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.integration_credential.id", ondelete="SET NULL"),
        nullable=True,
    )
    mailbox_strategy: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CampaignMailboxStrategy.EXPLICIT.value,
        server_default=text("'explicit'"),
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    opened_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    bounced_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    unsubscribed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CampaignStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )


# --- outreach.send --------------------------------------------------------


class Send(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per recipient per campaign — the source of truth for sends.

    ``tenant_id`` is denormalised here (rather than always JOIN-ing
    through campaign) so per-tenant queries / RLS hit a single index
    on this table.

    ``person_uid`` is nullable because not every recipient is a known
    person (operator may seed an external email list). When known we
    keep the link so the timeline can stitch the send back onto the
    person's interaction history.

    ``campaign_id`` is NULLABLE as of ENG-132 (migration
    ``d7e9f5b3c1a8``) so that ``SendService.enqueue_single`` can
    materialise transactional sends (appointment reminders, consult
    confirmations) without a campaign row. Campaign sends still set
    the column and inherit the ``ON DELETE CASCADE`` behaviour.
    """

    __tablename__ = "send"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ("
            "'queued', 'sent', 'bounced', 'failed', 'unsubscribed', 'opened'"
            ")",
            name="status",
        ),
        Index("ix_send_campaign_id_status", "campaign_id", "status"),
        Index("ix_send_tenant_id_recipient_email", "tenant_id", "recipient_email"),
        Index(
            "ix_send_tenant_id_person_uid",
            "tenant_id",
            "person_uid",
            postgresql_where=text("person_uid IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.campaign.id", ondelete="CASCADE"),
        nullable=True,
    )
    person_uid: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.person.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(320))
    mailbox_credential_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.integration_credential.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=SendStatus.QUEUED.value,
        server_default=text("'queued'"),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(Text)


# --- outreach.suppression -------------------------------------------------


class Suppression(Base):
    """Per-tenant unsubscribe / bounce / complaint list.

    Composite primary key on ``(tenant_id, recipient_email_normalised)``
    so a recipient suppressed for tenant A is NOT suppressed for tenant
    B (per ADR-0004 §"Unsubscribe — per-tenant suppression list").
    """

    __tablename__ = "suppression"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "recipient_email_normalised",
            name="pk_suppression",
        ),
        sa.CheckConstraint(
            "reason IN ('operator', 'one_click', 'bounce_hard', 'complaint')",
            name="reason",
        ),
        Index("ix_suppression_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recipient_email_normalised: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    source_send_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.send.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


# --- outreach.outbound_queue ---------------------------------------------


class OutboundQueue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Work queue for the ``outreach.dispatcher`` arq worker.

    The dispatcher pulls rows with::

        SELECT * FROM outreach.outbound_queue
        WHERE status = 'pending'
          AND scheduled_for <= now()
        ORDER BY priority ASC, scheduled_for ASC
        FOR UPDATE SKIP LOCKED
        LIMIT N

    `locked_by` / `locked_at` are stamped by the dispatcher when it
    takes a row. On success the row is set to ``succeeded``; on failure
    the dispatcher increments ``attempts`` and either reschedules
    (``status='pending'``, ``scheduled_for`` advanced) or marks
    ``failed`` after a per-policy attempt cap.
    """

    __tablename__ = "outbound_queue"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending', 'locked', 'succeeded', 'failed')",
            name="status",
        ),
        Index(
            "ix_outbound_queue_pending",
            "status",
            "scheduled_for",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_outbound_queue_tenant_id", "tenant_id"),
        Index("ix_outbound_queue_send_id", "send_id"),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    send_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.send.id", ondelete="CASCADE"),
        nullable=False,
    )
    credential_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenant.integration_credential.id", ondelete="RESTRICT"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=100,
        server_default=text("100"),
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=OutboundQueueStatus.PENDING.value,
        server_default=text("'pending'"),
    )
