"""PHI models: ``PatientProfile`` and ``Consultation``.

These tables live in the dedicated ``phi`` PostgreSQL schema. In production
this schema is granted to a separate role with stricter access policies (RLS
candidates), and is excluded from the ops snapshots.

Every per-tenant table inherits :class:`TenantScopedMixin` (ENG-128).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

SCHEMA = "phi"


class PatientProfile(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Patient-specific clinical profile fields. PHI."""

    __tablename__ = "patient_profile"
    __table_args__ = (
        Index("ix_patient_profile_tenant_id", "tenant_id"),
        Index("ix_patient_profile_person_uid", "person_uid", unique=True),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex_at_birth: Mapped[str | None] = mapped_column(String(16))
    allergies: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    medical_history: Mapped[str | None] = mapped_column(Text)


class Consultation(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """A single clinical encounter. PHI."""

    __tablename__ = "consultation"
    __table_args__ = (
        Index("ix_consultation_tenant_id", "tenant_id"),
        Index("ix_consultation_person_uid", "person_uid"),
        Index("ix_consultation_occurred_at", "occurred_at"),
        {"schema": SCHEMA},
    )

    person_uid: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clinician_uid: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    findings: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)
