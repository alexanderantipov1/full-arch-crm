"""Interaction models — Phase 1 slim subset (``interaction.event`` only).

The Phase 1 slice timeline (``GET /persons/{uid}/timeline``) needs a place
to land "lead created from SF" / "consultation rescheduled in CareStack"
events. ``Event`` is that place.

Hard contracts on ``summary`` and ``payload``:

- ``summary``: action verb + provider + non-PII source_id only. NEVER name,
  email, phone, DOB, address, MRN, clinical free-text. Rendered by every
  read surface (Inspector, MCP, dashboard); must be safe in all of them.
- ``payload``: structured non-PII fields only. Same forbidden list as
  summary. PII-bearing fields stay in ``ingest.raw_event.payload``.

Idempotency for **single-pipeline-run** replays is enforced by a partial
UNIQUE on ``(source_provider, source_event_id) WHERE source_event_id IS
NOT NULL``. Cross-pull idempotency (a re-pull creates a NEW
``ingest.raw_event``, so a NEW ``source_event_id``) is NOT enforced here;
that lives in worker-level ``was_changed`` change-detection (W1/W2).

The ``tenant_id`` column (ENG-128) is supplied by :class:`TenantScopedMixin`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, PrimaryKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, UUIDPrimaryKeyMixin

SCHEMA = "interaction"

# Allowed values for ``EventResponsibility.role`` — kept in sync with the
# CHECK constraint on the table (migration ``a6b7c8d9e0f1``). The list is
# small and grows slowly; every new role is an allowlist + migration pair.
#
# ``operational`` — the funnel owner at this stage. Pre-consult events get
#   the Lead owner (call-center agent); consult-onward events get the
#   covering Opportunity owner (Treatment Coordinator), with a fallback
#   to the Lead owner if no Opportunity exists yet.
# ``clinical`` — the doctor / clinical provider attached to the event
#   (CareStack appointment provider). Only present on consultation and
#   treatment events that have a clinical actor identified.
RESPONSIBILITY_ROLES = ("operational", "clinical")
_RESPONSIBILITY_ROLE_SQL = ", ".join(f"'{r}'" for r in RESPONSIBILITY_ROLES)

# Allowed values. Kept in sync with the migration's CHECK constraints.
EVENT_KINDS = (
    "lead_created",
    "lead_updated",
    "consultation_scheduled",
    # Legacy Phase 1 literal retained so existing rows and callers remain valid.
    "consultation_created",
    "consultation_rescheduled",
    "consultation_cancelled",
    "consultation_completed",
    "consultation_no_show",
    "task_created",
    "task_completed",
    "call_logged",
    "call_reference_found",
    "treatment_proposed",
    "treatment_completed",
    "invoice_created",
    "case_opened",
    "case_closed",
    "opportunity_created",
    "opportunity_won",
    "opportunity_lost",
    # ENG-382: pipeline movement (OpportunityHistory stage rows) and the
    # post-conversion identity segment.
    "opportunity_stage_changed",
    "contact_created",
    "payment_recorded",
    "payment_refunded",
    "payment_reversed",
    "payment_applied",
    # ENG-511: B1.3 stage capture. treatment_accepted = CareStack TreatmentPlan
    # StatusId=3; surgery_scheduled / surgery_completed = implant-surgery
    # treatment procedure statusId 2 / 8.
    "treatment_accepted",
    "surgery_scheduled",
    "surgery_completed",
)
SOURCE_PROVIDERS = ("salesforce", "carestack")
DATA_CLASSES = (
    "public",
    "operational",
    "clinical_summary",
    "phi_protected",
    "billing",
    "call_recording_ref",
)
SOURCE_KINDS = (
    "salesforce_lead",
    "salesforce_event",
    "salesforce_task",
    "salesforce_opportunity",
    "salesforce_case",
    # ENG-382 funnel segments.
    "salesforce_contact",
    "salesforce_account",
    "salesforce_opportunity_history",
    "carestack_appointment",
    "carestack_patient",
    "carestack_treatment_procedure",
    "carestack_invoice",
    "carestack_accounting_transaction",
    # ENG-511: per-patient TreatmentPlan ingest that emits treatment_accepted.
    "carestack_treatment_plan",
)
PROJECTION_REF_TYPES = (
    "ops_lead",
    "ops_consultation",
    "ops_followup_task",
)
REVIEW_STATUSES = (
    "auto",
    "pending_review",
    "reviewed",
    "rejected",
)

_EVENT_KIND_SQL = ", ".join(f"'{kind}'" for kind in EVENT_KINDS)
_SOURCE_PROVIDER_SQL = ", ".join(f"'{provider}'" for provider in SOURCE_PROVIDERS)
_DATA_CLASS_SQL = ", ".join(f"'{data_class}'" for data_class in DATA_CLASSES)
_SOURCE_KIND_SQL = ", ".join(f"'{source_kind}'" for source_kind in SOURCE_KINDS)
_PROJECTION_REF_TYPE_SQL = ", ".join(f"'{ref_type}'" for ref_type in PROJECTION_REF_TYPES)
_REVIEW_STATUS_SQL = ", ".join(f"'{status}'" for status in REVIEW_STATUSES)


class Event(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    """Append-only semantic event in a Person's timeline."""

    __tablename__ = "event"
    __table_args__ = (
        sa.CheckConstraint(
            f"kind IN ({_EVENT_KIND_SQL})",
            name="kind",
        ),
        sa.CheckConstraint(
            f"source_provider IN ({_SOURCE_PROVIDER_SQL})",
            name="source_provider",
        ),
        sa.CheckConstraint(
            f"data_class IN ({_DATA_CLASS_SQL})",
            name="data_class",
        ),
        sa.CheckConstraint(
            f"source_kind IS NULL OR source_kind IN ({_SOURCE_KIND_SQL})",
            name="source_kind",
        ),
        sa.CheckConstraint(
            f"projection_ref_type IS NULL OR projection_ref_type IN ({_PROJECTION_REF_TYPE_SQL})",
            name="projection_ref_type",
        ),
        sa.CheckConstraint(
            f"review_status IN ({_REVIEW_STATUS_SQL})",
            name="review_status",
        ),
        # Primary timeline query: latest events for a person, newest first.
        Index("ix_event_tenant_id", "tenant_id"),
        Index("ix_event_person_occurred", "person_uid", "occurred_at"),
        # Partial UNIQUE — single-pipeline-run replay safety. NULL
        # source_event_id rows (manual / future system events) are exempt.
        Index(
            "uq_event_source",
            "source_provider",
            "source_event_id",
            unique=True,
            postgresql_where=sa.text("source_event_id IS NOT NULL"),
        ),
        # ENG-269 cross-pull dedup partial UNIQUE. Re-pulls produce a NEW
        # ``ingest.raw_event`` (and therefore a new ``source_event_id``), so
        # the legacy index above does NOT catch them. This index keys on
        # the STABLE provider identity tuple — ``source_external_id`` is
        # the provider's object id (CareStack invoiceId, SF Lead Id, …),
        # ``kind`` distinguishes lifecycle events that legitimately share
        # the same provider object (treatment_proposed vs treatment_completed
        # on the same procedure id). NULL ``source_external_id`` rows are
        # exempt so manual/system events stay unconstrained.
        Index(
            "uq_event_provider_source_kind",
            "tenant_id",
            "source_provider",
            "source_kind",
            "source_external_id",
            "kind",
            unique=True,
            postgresql_where=sa.text("source_external_id IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.person.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ingest.raw_event.id", ondelete="RESTRICT"),
    )
    data_class: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str | None] = mapped_column(String(64))
    source_external_id: Mapped[str | None] = mapped_column(String(240))
    projection_ref_type: Mapped[str | None] = mapped_column(String(64))
    projection_ref_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="RESTRICT"),
    )


class EventResponsibility(TenantScopedMixin, Base):
    """Funnel responsibility for an :class:`Event` — multi-role per event.

    DISTINCT from :attr:`Event.created_by_actor_id`, which records "who
    inserted the row" (audit). This table records who is OPERATIONALLY
    responsible for the real-world record at this stage of the funnel
    (Lead owner / Treatment Coordinator) AND who is CLINICALLY
    responsible (the doctor on a consult).

    Composite PK ``(event_id, actor_id, role)`` lets a single event carry
    one row per (actor, role) pair without duplication. Allowed roles are
    enumerated in :data:`RESPONSIBILITY_ROLES`; the DB CHECK constraint
    is the safety net.

    Cross-schema FK strings (``interaction.event.id``, ``actor.actor.id``)
    are DB-level constraints only — this package never Python-imports
    ``actor`` (per ``packages/CLAUDE.md`` matrix).
    """

    __tablename__ = "event_responsibility"
    __table_args__ = (
        sa.CheckConstraint(
            f"role IN ({_RESPONSIBILITY_ROLE_SQL})",
            name="role",
        ),
        PrimaryKeyConstraint(
            "event_id", "actor_id", "role", name="pk_event_responsibility"
        ),
        Index("ix_event_responsibility_tenant_id", "tenant_id"),
        Index(
            "ix_event_responsibility_actor_role",
            "actor_id",
            "role",
        ),
        Index(
            "ix_event_responsibility_event_role",
            "event_id",
            "role",
        ),
        {"schema": SCHEMA},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("interaction.event.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("actor.actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
