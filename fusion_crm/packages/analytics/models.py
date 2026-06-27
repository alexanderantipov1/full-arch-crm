"""Analytics read-model: ``analytics.fact_patient_journey``.

The ``analytics`` schema is the operator-approved read-model layer (ENG-504 /
ENG-505). It is a **rebuildable projection**, never a source of truth: every row
is derived from canonical domains (``identity`` / ``ops`` / ``interaction`` /
``attribution`` / ``marketing``) by the fact builder (ENG-506) and can be dropped
and rebuilt at any time. Nothing writes here except the builder service.

``fact_patient_journey`` is one row per ``person_uid`` (the global
``identity.person.id``). It traces a patient from ad spend → collected revenue:
the dimension columns (campaign / source / vendor / caller / coordinator /
doctor / location) and the stage timestamps (lead → first contact → consult →
show → treatment presented/accepted → surgery scheduled/completed → first
payment) plus the money columns (revenue / collected / marketing cost).

Per the operator decision (ENG-505), **every column is nullable except the
``person_uid`` primary key**. Fields not yet derivable from canonical data
(caller/coordinator/doctor, treatment_accepted, surgery_*, marketing_cost) ship
NULL and carry provenance ``method='unresolved'`` until B1.* fills them — they
never block the build. ``field_provenance`` is a JSONB sidecar recording, per
field, ``{source, method, confidence, resolved_at}`` so a later auto-resolver or
manual enrichment can fill a field and the projection still survives a rebuild
(manual > auto > unresolved).

No cross-domain Python FK: ``person_uid`` / ``location_id`` / ``campaign_id`` /
``vendor_id`` / ``*_id`` are plain UUID columns (invariant #2/#3). PHI never
lands here — only dates, money, and reference ids.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TimestampMixin

SCHEMA = "analytics"

# Monetary columns: dental-implant case values stay well inside 14,2.
_MONEY = Numeric(14, 2)


class FactPatientJourney(TimestampMixin, Base):
    """One row per ``person_uid`` projecting the full revenue journey.

    Rebuildable projection — the fact builder (ENG-506) upserts on
    ``person_uid``. ``created_at`` / ``updated_at`` (from ``TimestampMixin``)
    double as build-tracking timestamps: ``updated_at`` is the last refresh of
    this person's row.
    """

    __tablename__ = "fact_patient_journey"
    __table_args__ = (
        Index("ix_fact_patient_journey_location_id", "location_id"),
        Index("ix_fact_patient_journey_lead_date", "lead_date"),
        Index("ix_fact_patient_journey_source", "source"),
        Index("ix_fact_patient_journey_campaign_id", "campaign_id"),
        Index("ix_fact_patient_journey_first_payment_date", "first_payment_date"),
        # B1 people dimensions (ENG-509/510) — partial indexes power the
        # caller / coordinator / doctor filters on the analytics aggregate
        # without scanning the (mostly NULL until backfilled) columns.
        Index(
            "ix_fact_patient_journey_caller_id",
            "caller_id",
            postgresql_where=sa.text("caller_id IS NOT NULL"),
        ),
        Index(
            "ix_fact_patient_journey_coordinator_id",
            "coordinator_id",
            postgresql_where=sa.text("coordinator_id IS NOT NULL"),
        ),
        Index(
            "ix_fact_patient_journey_doctor_id",
            "doctor_id",
            postgresql_where=sa.text("doctor_id IS NOT NULL"),
        ),
        # B1.5 implant case_type (ENG-539) — a partial index powers the
        # case-type filter / review-surface query; the column is NULL for every
        # non-implant person, so the partial index stays small.
        Index(
            "ix_fact_patient_journey_case_type",
            "case_type",
            postgresql_where=sa.text("case_type IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    # --- Identity (PK) -----------------------------------------------------
    # The global person reference. Plain UUID (no cross-domain FK, invariant #3).
    person_uid: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, nullable=False
    )

    # --- Dimensions (all nullable) -----------------------------------------
    # Attribution chain node ids (attribution.source_node.id) when resolved,
    # else NULL. campaign_name is denormalised from the node label for display.
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    campaign_name: Mapped[str | None] = mapped_column(String(240))
    source: Mapped[str | None] = mapped_column(String(128))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # Implant case_type (B1.5, ENG-539). Coarse implant-case label derived from
    # the CDT codes of the person's implant procedures (see
    # ``packages/analytics/case_type.py``). Nullable: NULL = not an implant
    # patient OR an implant patient whose footprint is non-determinative
    # (*unclassified*, needs review). Auto values: ``single_implant`` /
    # ``multiple_implants`` / ``all_on_x`` / ``overdenture`` / ``implant_bridge``.
    # Manual-only / future values (``all_on_4`` / ``all_on_6`` / ``zygomatic`` /
    # ``full_arch_upper`` / ``full_arch_lower`` / ``dual_arch``) are set via the
    # ENG-513 enrichment path, never auto-derived. Non-PHI category code.
    case_type: Mapped[str | None] = mapped_column(String(32))
    # People dimensions — unresolved until B1.* (no canonical signal yet).
    caller_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    coordinator_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # tenant.location.id (plain UUID). Drives the aggregate/per-location filter.
    location_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    # --- Stage timestamps (all nullable, tz-aware) -------------------------
    lead_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_contact_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consult_scheduled_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    show_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    treatment_presented_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    treatment_accepted_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    surgery_scheduled_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    surgery_completed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    first_payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Money (all nullable) ----------------------------------------------
    # revenue_amount = gross case value presented/accepted; collected_amount =
    # Net-Collected (ENG-283, excludes payment_applied). marketing_cost is the
    # spend allocated to this person — unresolved until B1.*.
    revenue_amount: Mapped[float | None] = mapped_column(_MONEY)
    collected_amount: Mapped[float | None] = mapped_column(_MONEY)
    marketing_cost_allocated: Mapped[float | None] = mapped_column(_MONEY)

    # --- Provenance sidecar ------------------------------------------------
    # Per-field {source, method: auto|manual|unresolved, confidence,
    # resolved_at}. NOT NULL, defaults to an empty object so a freshly built row
    # always has a provenance map. See packages/analytics/provenance.py.
    field_provenance: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )
