"""Integrations models: provider plumbing only.

The 5 tables here ARE the integrations schema:

- ``IntegrationAccount`` — per-(provider, company_uid) creds + tokens.
- ``ObjectMapping``      — per-account field map per provider object.
- ``SyncRun``            — append-only journal of pull/push/cdc/webhook batches.
- ``CDCCursor``          — last replay_id per CDC channel (Salesforce).
- ``ExternalEntity``     — generic safe for provider objects without canonical home.

Provider-specific tables NEVER live here. Provider records map into the
canonical schemas (``identity``, ``ops``, ``phi``) via the service layer.

Every per-tenant table inherits :class:`TenantScopedMixin` (ENG-128). The
ENG-123 4/4 migration added ``tenant_id`` to all five tables; the mixin
declaration centralises that column.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

from .crypto import EncryptedString

SCHEMA = "integrations"

# Multi-tenancy stub. Replaced with a real Company FK when M10 cuts over.
GLOBAL_COMPANY_UID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class IntegrationAccount(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One row per ``(provider, company_uid)`` pair. Holds OAuth state.

    Provider-specific extras live in ``meta`` JSONB:

    * ``salesforce``: ``instance_url``, ``api_version``, ``login_domain``
    * ``carestack``: ``idp_base_url``, ``api_base_url``, ``api_version``,
      ``vendor_key``, ``account_key``, ``account_id``, encrypted
      ``vendor_username`` / ``account_password``
    * ``hubspot``: ``portal_id``, ``app_id``
    """

    __tablename__ = "integration_account"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "company_uid",
            name="uq_integration_account_tenant_provider_company",
        ),
        CheckConstraint(
            "status IN ('connected', 'disconnected', 'error', 'expired')",
            name="status",
        ),
        Index("ix_integration_account_tenant_id", "tenant_id"),
        Index("ix_integration_account_status", "status"),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    company_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        default=GLOBAL_COMPANY_UID,
        server_default=text(f"'{GLOBAL_COMPANY_UID}'::uuid"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="connected",
        server_default=text("'connected'"),
    )
    access_token: Mapped[str | None] = mapped_column(EncryptedString)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    # `mappings` and `cdc_cursors` cascade-delete because they are pure
    # configuration tied to the account — meaningless without it. `sync_runs`
    # and `external_entities` are operational/historical and use RESTRICT at
    # the FK level (no ORM cascade) so deleting an account that has either
    # raises rather than erases history.
    mappings: Mapped[list[ObjectMapping]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    cdc_cursors: Mapped[list[CDCCursor]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    sync_runs: Mapped[list[SyncRun]] = relationship(
        back_populates="account",
        lazy="noload",
    )
    external_entities: Mapped[list[ExternalEntity]] = relationship(
        back_populates="account",
        lazy="noload",
    )


class ObjectMapping(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Per-account map: provider object name → our canonical target."""

    __tablename__ = "object_mapping"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "sf_object",
            name="uq_object_mapping_account_object",
        ),
        CheckConstraint(
            "direction IN ('pull', 'push', 'both')",
            name="direction",
        ),
        Index("ix_object_mapping_tenant_id", "tenant_id"),
        Index("ix_object_mapping_account_enabled", "account_id", "enabled"),
        {"schema": SCHEMA},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.integration_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Named ``sf_object`` for historical reasons; holds the provider's resource
    # name verbatim (``Lead`` for SF, ``patients`` for CareStack, ...).
    sf_object: Mapped[str] = mapped_column(String(128), nullable=False)
    our_target: Mapped[str] = mapped_column(String(128), nullable=False)
    field_map: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="both",
        server_default=text("'both'"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    account: Mapped[IntegrationAccount] = relationship(back_populates="mappings")


class SyncRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Append-only journal of one pull / push / cdc / webhook batch."""

    __tablename__ = "sync_run"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'pull', 'push', 'cdc', 'webhook')",
            name="direction",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'success', 'failed', 'partial', 'skipped_credential')",
            name="status",
        ),
        Index("ix_sync_run_tenant_id", "tenant_id"),
        Index("ix_sync_run_account_started", "account_id", "started_at"),
        Index("ix_sync_run_status_started", "status", "started_at"),
        {"schema": SCHEMA},
    )

    # RESTRICT: sync_run is operational history; deleting an account that
    # has runs should raise, not erase. ORM relationship has no cascade.
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.integration_account.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sf_object: Mapped[str | None] = mapped_column(String(128))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="running",
        server_default=text("'running'"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    records_succeeded: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    records_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    account: Mapped[IntegrationAccount] = relationship(back_populates="sync_runs")


class CDCCursor(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Last replay_id per CDC channel for a given account (Salesforce)."""

    __tablename__ = "cdc_cursor"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "channel",
            name="uq_cdc_cursor_account_channel",
        ),
        Index("ix_cdc_cursor_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.integration_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(255), nullable=False)
    replay_id: Mapped[int | None] = mapped_column(BigInteger)

    account: Mapped[IntegrationAccount] = relationship(back_populates="cdc_cursors")


class ExternalEntity(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Generic safe for provider objects without a canonical home.

    When an object earns a real domain table (e.g. CareStack Appointment →
    ``phi.appointment`` in M2), migrate the data out and update CATALOG.
    """

    __tablename__ = "external_entity"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "object_type",
            "external_id",
            name="uq_external_entity_account_type_extid",
        ),
        Index("ix_external_entity_tenant_id", "tenant_id"),
        Index("ix_external_entity_person_uid", "person_uid"),
        {"schema": SCHEMA},
    )

    # RESTRICT: external_entity holds historical provider snapshots; deleting
    # an account should not silently erase them. ORM relationship has no
    # cascade.
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.integration_account.id", ondelete="RESTRICT"),
        nullable=False,
    )
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    person_uid: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[IntegrationAccount] = relationship(back_populates="external_entities")


# --- Notification layer (ENG-436, Interactive Corporate Messenger) ---------
#
# A transactional outbox + notification-rule pair that mirrors the email
# outbox/drain pattern (``outreach.outbound_queue`` + the email dispatcher).
# ``notification_rule`` stores WHICH chat channel a workspace event maps to
# (plus the condition predicates + message template that Block D evaluates /
# renders); ``notification_outbox`` is the durable work queue the arq
# ``drain_notification_outbox`` job drains, sending each row via a
# ``ChatProvider`` (the Mattermost adapter lands in Block B / ENG-435).

NOTIFICATION_PROVIDER_KINDS = ("mattermost", "slack", "telegram")
NOTIFICATION_OUTBOX_STATUSES = ("pending", "locked", "sent", "failed")


class NotificationRule(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Maps a workspace ``event_type`` to a chat channel + message template.

    ``conditions`` is a list of field predicates evaluated by Block D's
    rule engine (here we only store / round-trip them); ``template`` is the
    message blocks/text the renderer fills. Neither is interpreted in this
    package — Block C is the persistence + dispatch plumbing only.
    """

    __tablename__ = "notification_rule"
    __table_args__ = (
        Index("ix_notification_rule_tenant_id", "tenant_id"),
        Index(
            "ix_notification_rule_lookup",
            "tenant_id",
            "event_type",
            "enabled",
        ),
        {"schema": SCHEMA},
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(255), nullable=False)
    conditions: Mapped[list[object]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    template: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    provider_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="mattermost",
        server_default=text("'mattermost'"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    description: Mapped[str | None] = mapped_column(String(255))


class NotificationOutbox(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Transactional outbox row for one chat message to dispatch.

    The dispatcher (``apps.worker.jobs.notification_dispatch``) pulls
    pending rows with ``SELECT ... FOR UPDATE SKIP LOCKED`` (mirrors the
    email outbound queue), resolves a ``ChatProvider`` for
    ``provider_kind``, posts ``payload``, and records the terminal
    outcome. ``rule_id`` is nullable because a row may be enqueued
    directly (not via a rule). Terminal states: pending → locked →
    sent | failed.
    """

    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'locked', 'sent', 'failed')",
            name="status",
        ),
        Index("ix_notification_outbox_tenant_id", "tenant_id"),
        Index(
            "ix_notification_outbox_pending",
            "status",
            "scheduled_for",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_notification_outbox_rule_id", "rule_id"),
        {"schema": SCHEMA},
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.notification_rule.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="mattermost",
        server_default=text("'mattermost'"),
    )
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    locked_by: Mapped[str | None] = mapped_column(String(255))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


# --- Agent human-in-the-loop layer (ENG-440, Block G) ----------------------
#
# An agent proposes an action in chat with Approve/Reject buttons. The button
# click flows back through the EXISTING signed inbound path (Block E captures
# it to ``ingest.raw_event``), and the worker boundary resolves the decision
# and, on approve, EXECUTES the bound action through a domain service (the
# only executable kind in this MVP is an enrichment annotation). This table is
# the durable proposal store: it records WHAT was proposed, its lifecycle, and
# the human decision. Execution itself happens at the worker boundary (which
# may import both ``integrations`` and ``enrichment``), never here — the
# import matrix forbids ``integrations`` → ``enrichment``.

AGENT_ACTION_PROPOSAL_STATUSES = (
    "pending",
    "approved",
    "rejected",
    "executed",
    "failed",
)
AGENT_ACTION_KINDS = ("annotation",)


class AgentActionProposal(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """One agent-proposed action awaiting a human Approve/Reject in chat.

    ``proposal_ref`` is the opaque id placed in the Mattermost button
    ``context`` so the inbound action click can be matched back to this row;
    it is unique per tenant. ``payload`` holds the bound action parameters
    (for ``kind='annotation'``: ``{subject_type, subject_id, key, value,
    note?}``). The lifecycle is pending → approved | rejected, and on an
    approved annotation execution → executed | failed.
    """

    __tablename__ = "agent_action_proposal"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "proposal_ref",
            name="uq_agent_action_proposal_tenant_ref",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'executed', 'failed')",
            name="status",
        ),
        Index("ix_agent_action_proposal_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    proposal_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(64))
    # DB-level FK to actor.actor.id; we never import the actor model here.
    decided_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)


# --- Notification idempotency ledger (ENG-455, dedupe core) -----------------
#
# A durable "this entity already notified for this event type" ledger that
# guarantees a domain entity emits AT MOST ONE notification per event type,
# EVER — regardless of SF/CareStack pull frequency, retries, overlapping cron
# ticks, or historical backfills. It is SEPARATE from ``notification_outbox``
# so it survives outbox cleanup/retention: the outbox is a transient work
# queue (rows are drained + eventually pruned), whereas a claim here is a
# permanent fact. ``NotificationEventService.emit`` claims a row BEFORE
# enqueuing the outbox row, in the SAME unit of work, so a claimed-but-not-
# enqueued state cannot occur.
#
# The dedupe key is caller-supplied and opaque to this layer (typically the
# stable provider entity id, e.g. an SF Lead Id). The UNIQUE constraint on
# ``(tenant_id, event_type, dedupe_key)`` is the enforcement point; the repo
# claim uses ``INSERT ... ON CONFLICT DO NOTHING RETURNING id`` so the first
# caller wins and every later caller is a no-op.


class NotificationEmitted(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Durable idempotency ledger: one row per emitted (entity, event type).

    A successful ``claim`` records that ``dedupe_key`` has ALREADY produced a
    notification for ``event_type`` in this tenant. Re-claims for the same
    triple are rejected by the UNIQUE constraint, making emit idempotent
    across retries, overlapping cron ticks, and re-pulls.
    """

    __tablename__ = "notification_emitted"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "event_type",
            "dedupe_key",
            name="uq_notification_emitted_tenant_event_key",
        ),
        # The UNIQUE constraint above already indexes
        # (tenant_id, event_type, dedupe_key) — the exact claim/lookup key —
        # so no extra composite index is needed. Keep a plain tenant_id
        # index for tenant-scoped scans/cleanup.
        Index("ix_notification_emitted_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
