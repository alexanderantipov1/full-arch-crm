"""Ops models: CRM-safe lead, consultation, and relationship projections.

This domain holds NON-PHI marketing/CRM data only. It references ``Person``
across schemas via ``person_uid`` (a plain UUID column, NOT a cross-schema FK,
because the ops domain may be replicated to systems that have no knowledge of
the identity schema).

``Account`` is the Phase 1 minimal view of an external organisation — SF
``Account`` (or HubSpot Company in the future). The full v0.2 design
(`docs/plans/2026-04-30-full-schema-v0_2.md` §9.1) ships richer demographic
fields (billing_city, owner_person_uid, etc); Phase 1 ships only what the
W1 Salesforce-Lead-pull worker needs, with a deliberate ``(provider,
source_id)`` UNIQUE so re-pulls are idempotent.

Every per-tenant table inherits :class:`TenantScopedMixin` (ENG-128).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "ops"

# Allowed values for Account.provider. Mirrors identity.SOURCE_SYSTEMS but
# narrowed to the providers that actually carry account-level objects.
ACCOUNT_PROVIDERS = ("salesforce", "hubspot", "carestack", "manual", "import")

# Allowed values for Consultation.source_provider. ENG-216 covers Salesforce
# Event and CareStack Appointment; expand here when a third source lands.
CONSULTATION_PROVIDERS = ("salesforce", "carestack")

# Allowed values for Opportunity.source_provider. ENG-414 starts with
# Salesforce as the sole source of truth for funnel ownership; CareStack
# has no opportunity / coordinator concept.
OPPORTUNITY_PROVIDERS = ("salesforce",)

PROFILE_EVIDENCE_PROVIDERS = ("salesforce", "carestack", "manual", "import")


class LeadStatus(StrEnum):
    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    BOOKED = "booked"
    LOST = "lost"


class FollowupStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    SKIPPED = "skipped"


class ConsultationStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"
    # ENG-481: a CareStack appointment that was deleted, or a note/admin
    # "appointment" that never represented a real visit. Excluded entirely
    # from the funnel (not counted in scheduled). ``status`` is a varchar /
    # StrEnum so no migration is needed — new values are just strings.
    DELETED = "deleted"


class ConsultationKind(StrEnum):
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    TREATMENT = "treatment"
    OTHER = "other"


class RelationshipKind(StrEnum):
    PROSPECT = "prospect"
    PATIENT = "patient"


class RelationshipStatus(StrEnum):
    UNKNOWN = "unknown"
    CONSULT_SCHEDULED = "consult_scheduled"
    CONSULT_COMPLETED = "consult_completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A lead is a non-clinical sales/marketing opportunity for a person."""

    __tablename__ = "lead"
    __table_args__ = (
        Index("ix_lead_tenant_id", "tenant_id"),
        Index("ix_lead_person_uid", "person_uid"),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[LeadStatus] = mapped_column(
        String(16), nullable=False, default=LeadStatus.NEW
    )
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Account(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """External organisation tracked alongside a Lead — Phase 1 minimal view.

    The W1 Salesforce worker calls ``OpsService.record_account(...)`` once per
    SF Account it sees and lets multiple Leads link via ``Lead.account_uid``
    (added separately if/when needed). For Phase 1 we just store the row;
    Lead-to-Account linkage joins via the SF Account.Id stored on the Lead's
    raw payload.

    Idempotent on ``(provider, source_id)`` via the UNIQUE constraint —
    re-pulls find the existing row instead of inserting duplicates.

    Phase 1 columns are deliberately minimal: ``provider``, ``source_id``,
    ``name``, ``raw``. Full demographic fields (billing_city, billing_state,
    owner_person_uid) wait for the §9.1 expansion when the slice no longer
    covers our needs.
    """

    __tablename__ = "account"
    __table_args__ = (
        sa.CheckConstraint(
            "provider IN ('salesforce', 'hubspot', 'carestack', "
            "'manual', 'import')",
            name="provider",
        ),
        UniqueConstraint("provider", "source_id", name="uq_account_provider_source"),
        Index("ix_account_tenant_id", "tenant_id"),
        Index("ix_account_provider", "provider"),
        {"schema": SCHEMA},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(240), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    raw: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )


class Opportunity(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Marketing-safe projection of a Salesforce Opportunity (ENG-414).

    Phase-2 funnel owner (Treatment Coordinator) lives on
    ``Opportunity.OwnerId`` in Salesforce. This table mirrors the SF
    Opportunity so the TC is queryable from ops dashboards and AI tools
    without re-reading raw payloads.

    Mirrors :class:`Lead` deliberately: ``owner_id`` / ``owner_name`` are
    kept in ``extra`` JSONB (not typed columns) so the read paths and the
    ENG-408 enrichment pattern keep working without bifurcation.

    Idempotent on ``(tenant_id, source_provider, source_instance,
    external_id)`` so the cron-driven pull and operator backfills both
    converge on the same row. ``stage`` is intentionally a free-form
    string for now; a canonical enum lands after the SF picklist is
    observed in prod (see decision-log).
    """

    __tablename__ = "opportunity"
    __table_args__ = (
        sa.CheckConstraint(
            "source_provider IN ('salesforce')",
            # Bare name; the metadata naming convention prefixes
            # ck_%(table_name)s_ → final name ck_opportunity_source_provider,
            # matching the migration's op.f() literal.
            name="source_provider",
        ),
        UniqueConstraint(
            "tenant_id",
            "source_provider",
            "source_instance",
            "external_id",
            name="uq_opportunity_source",
        ),
        Index("ix_opportunity_tenant_id", "tenant_id"),
        Index("ix_opportunity_person_uid", "person_uid"),
        Index(
            "ix_opportunity_tenant_person_close",
            "tenant_id",
            "person_uid",
            "close_date",
        ),
        Index(
            "ix_opportunity_tenant_provider_created",
            "tenant_id",
            "provider_created_at",
        ),
        # GIN index on extra so the owner-name backfill and the PM dashboard
        # owner-filter can jsonb-path-lookup extra->>'owner_id' without a scan.
        # Mirrors the migration's ix_opportunity_extra_gin (model/migration parity).
        Index("ix_opportunity_extra_gin", "extra", postgresql_using="gin"),
        {"schema": SCHEMA},
    )

    # NULL allowed — opportunities sometimes arrive before the underlying
    # AccountId resolves to a person_uid (converted-lead fallback may miss
    # on first pull and succeed on the next).
    person_uid: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_instance: Mapped[str] = mapped_column(String(96), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    # SF Opportunity Name. Vendor-supplied free text; staff occasionally
    # paste patient names here so dashboards must mask before exposing
    # to AI tools (mirrors the Lead handling pattern).
    name: Mapped[str | None] = mapped_column(String(240))
    # Free-form for Phase 1 — pending picklist discovery, see decision-log.
    stage: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[float | None] = mapped_column(sa.Numeric(14, 2))
    close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Provider-side creation timestamp (SF Opportunity.CreatedDate).
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # ``extra`` mirrors ops.Lead.extra:
    #   - ``owner_id``    — SF OwnerId (005…/00G…)
    #   - ``owner_name``  — display name from Owner.Name SOQL projection
    #     or one-shot backfill (infra/scripts/backfill_opportunity_owner_names.py)
    #   - ``opportunity_stage`` / ``opportunity_type`` / ``lead_source``
    #   - ``is_closed`` / ``is_won`` / ``probability``
    extra: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
    )


class FollowupTask(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """An action a staff member should perform for a person — never PHI content."""

    __tablename__ = "followup_task"
    __table_args__ = (
        Index("ix_followup_task_tenant_id", "tenant_id"),
        Index("ix_followup_task_person_uid", "person_uid"),
        Index("ix_followup_task_due_at", "due_at"),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[FollowupStatus] = mapped_column(
        String(16), nullable=False, default=FollowupStatus.OPEN
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class Consultation(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A scheduled or recorded consultation/appointment for a person.

    Materialises the marketing-safe projection of a CareStack appointment or
    a Salesforce calendar Event. Clinical notes and treatment details stay in
    the provider source (``phi.*`` lands them in M3+); this table only carries
    fields that AI agents and operator dashboards are allowed to see.

    Tenant-scoped (ENG-128) and source-instance scoped (ENG-181). Idempotent
    on ``(tenant_id, source_provider, source_instance, external_id)`` — the
    cron-driven pull (ENG-220) re-upserts on every run.
    """

    __tablename__ = "consultation"
    __table_args__ = (
        sa.CheckConstraint(
            "source_provider IN ('salesforce', 'carestack')",
            name="ck_consultation_source_provider",
        ),
        UniqueConstraint(
            "tenant_id",
            "source_provider",
            "source_instance",
            "external_id",
            name="uq_consultation_source",
        ),
        Index("ix_consultation_tenant_id", "tenant_id"),
        Index("ix_consultation_person_uid", "person_uid"),
        Index(
            "ix_consultation_tenant_person_scheduled",
            "tenant_id",
            "person_uid",
            "scheduled_at",
        ),
        Index(
            "ix_consultation_tenant_provider_created",
            "tenant_id",
            "provider_created_at",
        ),
        # ENG-417: covering Opportunity link. Index name mirrors the
        # migration (``ix_consultation_covering_opportunity_id``) so
        # ``alembic check`` stays clean.
        Index(
            "ix_consultation_covering_opportunity_id",
            "covering_opportunity_id",
        ),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_instance: Mapped[str] = mapped_column(String(96), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int | None] = mapped_column()
    status: Mapped[ConsultationStatus] = mapped_column(
        String(16), nullable=False, default=ConsultationStatus.SCHEDULED
    )
    # ENG-487: verbatim provider status (e.g. CareStack "Confirmed",
    # "Un-Confirmed", "Ready to Seat", "Arrived"). The 5-bucket ``status``
    # above collapses "Confirmed" into SCHEDULED, which loses the signal the
    # T-15m reminder (ENG-486) and other workflows need. Curated mapping per
    # the full-fidelity doctrine — the forensic copy stays in ingest.raw_event.
    # NULL for non-CareStack / legacy rows.
    source_status: Mapped[str | None] = mapped_column(String(48))
    consultation_kind: Mapped[ConsultationKind] = mapped_column(
        String(16), nullable=False, default=ConsultationKind.OTHER
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # Marketing-safe label only — never clinician's role / specialty / notes.
    provider_clinician_name: Mapped[str | None] = mapped_column(String(240))
    # ENG-543: the CareStack provider id (``providerIds[0]``) the appointment was
    # booked under, captured verbatim at ingest. Stable link to the doctor's
    # ``actor.actor`` (kind ``carestack_provider_id``) → its ``mattermost_username``
    # identifier, used to @mention the doctor in the consult-reminder card.
    provider_carestack_id: Mapped[str | None] = mapped_column(String(64))
    # Provider-side creation timestamp. CareStack ``createdOn`` / Salesforce
    # Event ``CreatedDate``. Nullable for legacy rows; the dashboard date
    # filter coalesces to ``created_at`` when this is NULL.
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # ENG-417: covering Opportunity for this consult, used to attribute
    # the operational (TC) owner. NULL for walk-ins / pre-Opportunity
    # consults — those degrade gracefully to clinical-only attribution.
    # FK matches the migration (ondelete SET NULL on opportunity delete);
    # name is generated by the naming convention to
    # ``fk_consultation_covering_opportunity_id_opportunity``.
    covering_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.opportunity.id", ondelete="SET NULL"),
        nullable=True,
    )


class PersonLocationProfile(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Evidence-derived relationship between a person and a clinic location.

    ``identity.person`` is global; patient/customer status is not. This table
    stores the ops-safe per-location projection used by staff UI and agent
    context. Raw provider payloads and clinical notes stay in ``ingest`` /
    ``phi``. Imported row existence alone must not create a ``patient``
    relationship; only completed appointment/consultation evidence can promote
    the relationship kind.
    """

    __tablename__ = "person_location_profile"
    __table_args__ = (
        sa.CheckConstraint(
            "relationship_kind IN ('prospect', 'patient')",
            name="ck_person_location_profile_relationship_kind",
        ),
        sa.CheckConstraint(
            "relationship_status IN ('unknown', 'consult_scheduled', "
            "'consult_completed', 'no_show', 'cancelled')",
            name="ck_person_location_profile_relationship_status",
        ),
        sa.CheckConstraint(
            "last_evidence_provider IS NULL OR last_evidence_provider IN "
            "('salesforce', 'carestack', 'manual', 'import')",
            name="ck_person_location_profile_evidence_provider",
        ),
        UniqueConstraint(
            "tenant_id",
            "person_uid",
            "location_id",
            name="uq_person_location_profile_tenant_person_location",
        ),
        Index("ix_person_location_profile_tenant_id", "tenant_id"),
        Index("ix_person_location_profile_person_uid", "person_uid"),
        Index("ix_person_location_profile_location_id", "location_id"),
        Index(
            "ix_person_location_profile_tenant_location",
            "tenant_id",
            "location_id",
        ),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    relationship_kind: Mapped[RelationshipKind] = mapped_column(
        String(32), nullable=False, default=RelationshipKind.PROSPECT
    )
    relationship_status: Mapped[RelationshipStatus] = mapped_column(
        String(32), nullable=False, default=RelationshipStatus.UNKNOWN
    )
    last_evidence_provider: Mapped[str | None] = mapped_column(String(32))
    last_evidence_source_instance: Mapped[str | None] = mapped_column(String(96))
    last_evidence_external_id: Mapped[str | None] = mapped_column(String(240))
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_consultation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    last_raw_event_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
