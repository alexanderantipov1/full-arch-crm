"""Pydantic DTOs for PHI. Anything sent to a caller goes through these."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientProfileIn(BaseModel):
    person_uid: UUID
    date_of_birth: date | None = None
    sex_at_birth: str | None = None
    allergies: dict = Field(default_factory=dict)
    medical_history: str | None = None


class PatientProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    date_of_birth: date | None
    sex_at_birth: str | None
    allergies: dict
    medical_history: str | None
    created_at: datetime
    updated_at: datetime


class ConsultationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    occurred_at: datetime
    clinician_uid: UUID | None
    chief_complaint: str | None
    findings: str | None
    plan: str | None


class PhiPersonSnapshot(BaseModel):
    """Clinically aware view of a person — only emitted to authorised principals."""

    person_uid: UUID
    profile: PatientProfileOut | None
    recent_consultations: list[ConsultationOut] = Field(default_factory=list)
