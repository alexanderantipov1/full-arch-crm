"""Service + repository tests for the ENG-217 ops.consultation domain.

Focus: validation, idempotency, change detection. No provider plumbing yet —
PR-B' (ENG-218) and PR-C' (ENG-219) will exercise the puller path end-to-end.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Table

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import PersonUID, TenantId
from packages.ops.models import (
    Consultation,
    ConsultationKind,
    ConsultationStatus,
    PersonLocationProfile,
    RelationshipKind,
    RelationshipStatus,
)
from packages.ops.schemas import ConsultationIn
from packages.ops.service import OpsService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID: PersonUID = PersonUID(uuid.uuid4())


def _make_service() -> tuple[OpsService, MagicMock]:
    session = MagicMock()
    # `upsert_consultation_from_hint` calls `await session.refresh(row)` after
    # add_consultation to populate server-default columns; the test never
    # touches a real DB so we stub it as a no-op AsyncMock that also fills the
    # timestamps so ConsultationOut.model_validate succeeds.
    async def _refresh(row: Any) -> None:
        if getattr(row, "created_at", None) is None:
            row.created_at = _NOW
        if getattr(row, "updated_at", None) is None:
            row.updated_at = _NOW
    session.refresh = AsyncMock(side_effect=_refresh)
    service = OpsService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._identity.get_person = AsyncMock()  # default: returns truthy person
    service._identity.get_person.return_value = MagicMock(id=_PERSON_UID)
    service._repo.find_person_location_profile = AsyncMock(return_value=None)  # type: ignore[attr-defined]
    service._repo.add_person_location_profile = AsyncMock()  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


_NOW = datetime(2026, 5, 21, 19, 0, tzinfo=UTC)


def _make_existing(payload: ConsultationIn, **overrides) -> Consultation:
    """Build a Consultation ORM instance with id+timestamps set so that
    ``ConsultationOut.model_validate(existing)`` does not blow up on the
    nullable DB-side defaults that the test never flushes."""
    base = dict(
        id=uuid.uuid4(),
        tenant_id=_TENANT_ID,
        person_uid=_PERSON_UID,
        source_provider=payload.source_provider,
        source_instance=payload.source_instance,
        external_id=payload.external_id,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        status=payload.status,
        consultation_kind=payload.consultation_kind,
        location_id=payload.location_id,
        provider_clinician_name=payload.provider_clinician_name,
        raw_event_id=payload.raw_event_id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    base.update(overrides)
    return Consultation(**base)


def _payload(**overrides) -> ConsultationIn:
    defaults = dict(
        person_uid=_PERSON_UID,
        source_provider="carestack",
        source_instance="carestack-main",
        external_id="cs-appt-123",
        scheduled_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
        duration_minutes=30,
        status=ConsultationStatus.SCHEDULED,
        consultation_kind=ConsultationKind.INITIAL,
    )
    defaults.update(overrides)
    return ConsultationIn(**defaults)


@pytest.mark.asyncio
async def test_upsert_rejects_unknown_provider() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError) as excinfo:
        await service.upsert_consultation_from_hint(
            _TENANT_ID, _payload(source_provider="zendesk")
        )
    assert "unknown consultation provider" in str(excinfo.value)


@pytest.mark.asyncio
async def test_upsert_rejects_missing_person() -> None:
    service, _ = _make_service()
    service._identity.get_person.return_value = None  # type: ignore[attr-defined]
    with pytest.raises(NotFoundError):
        await service.upsert_consultation_from_hint(_TENANT_ID, _payload())


@pytest.mark.asyncio
async def test_upsert_inserts_when_no_existing_row() -> None:
    service, repo = _make_service()
    repo.find_consultation_by_source = AsyncMock(return_value=None)

    # ``add_consultation`` returns the same instance after a flush. Stamp
    # id + timestamps so the Out projection passes Pydantic validation
    # (DB-side server_defaults don't run in this unit-level mock).
    async def _add(consultation: Consultation) -> Consultation:
        consultation.id = uuid.uuid4()
        consultation.created_at = _NOW
        consultation.updated_at = _NOW
        return consultation

    repo.add_consultation = AsyncMock(side_effect=_add)

    result = await service.upsert_consultation_from_hint(_TENANT_ID, _payload())

    assert result.was_created is True
    assert result.was_changed is True
    assert result.was_status_change is False
    assert result.was_scheduled_at_change is False
    assert result.consultation.source_provider == "carestack"
    assert result.consultation.external_id == "cs-appt-123"
    repo.find_consultation_by_source.assert_awaited_once_with(
        tenant_id=_TENANT_ID,
        source_provider="carestack",
        source_instance="carestack-main",
        external_id="cs-appt-123",
    )
    repo.add_consultation.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_idempotent_returns_no_change_when_payload_matches() -> None:
    service, repo = _make_service()
    payload = _payload()
    existing = _make_existing(payload)
    repo.find_consultation_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    assert result.was_created is False
    assert result.was_changed is False
    assert result.was_status_change is False
    assert result.was_scheduled_at_change is False


@pytest.mark.asyncio
async def test_upsert_marks_changed_when_status_drifts() -> None:
    service, repo = _make_service()
    payload = _payload(status=ConsultationStatus.COMPLETED)
    existing = _make_existing(payload, status=ConsultationStatus.SCHEDULED)
    repo.find_consultation_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    assert result.was_created is False
    assert result.was_changed is True
    assert result.was_status_change is True
    assert result.was_scheduled_at_change is False
    assert result.consultation.status == ConsultationStatus.COMPLETED


@pytest.mark.asyncio
async def test_upsert_marks_scheduled_at_change_separately() -> None:
    service, repo = _make_service()
    payload = _payload(scheduled_at=datetime(2026, 6, 2, 14, 0, tzinfo=UTC))
    existing = _make_existing(
        payload,
        scheduled_at=datetime(2026, 6, 1, 14, 0, tzinfo=UTC),
    )
    repo.find_consultation_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    assert result.was_changed is True
    assert result.was_status_change is False
    assert result.was_scheduled_at_change is True
    assert result.consultation.scheduled_at == datetime(2026, 6, 2, 14, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_upsert_marks_changed_when_clinician_name_drifts() -> None:
    service, repo = _make_service()
    payload = _payload(provider_clinician_name="Dr. Smith")
    existing = _make_existing(payload, provider_clinician_name="Dr. Jones")
    repo.find_consultation_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    assert result.was_changed is True
    assert result.was_status_change is False
    assert result.was_scheduled_at_change is False
    assert result.consultation.provider_clinician_name == "Dr. Smith"


def test_consultation_model_has_expected_columns() -> None:
    """Smoke against the ORM declaration to catch column drift."""
    columns = {c.name for c in Consultation.__table__.columns}
    assert {
        "id",
        "tenant_id",
        "person_uid",
        "source_provider",
        "source_instance",
        "external_id",
        "scheduled_at",
        "duration_minutes",
        "status",
        "consultation_kind",
        "location_id",
        "provider_clinician_name",
        "raw_event_id",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_consultation_table_has_natural_key_unique_constraint() -> None:
    table = cast(Table, Consultation.__table__)
    unique_names = {
        c.name for c in table.constraints if getattr(c, "name", None)
    }
    assert "uq_consultation_source" in unique_names


@pytest.mark.asyncio
async def test_scheduled_consultation_creates_prospect_location_profile() -> None:
    service, repo = _make_service()
    location_id = uuid.uuid4()
    payload = _payload(location_id=location_id)
    repo.find_consultation_by_source = AsyncMock(return_value=None)

    async def _add(consultation: Consultation) -> Consultation:
        consultation.id = uuid.uuid4()
        consultation.created_at = _NOW
        consultation.updated_at = _NOW
        return consultation

    repo.add_consultation = AsyncMock(side_effect=_add)
    captured: dict[str, PersonLocationProfile] = {}

    async def _add_profile(
        profile: PersonLocationProfile,
    ) -> PersonLocationProfile:
        captured["profile"] = profile
        return profile

    repo.add_person_location_profile = AsyncMock(side_effect=_add_profile)

    await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    profile = captured["profile"]
    assert profile.person_uid == _PERSON_UID
    assert profile.location_id == location_id
    assert profile.relationship_kind == RelationshipKind.PROSPECT
    assert profile.relationship_status == RelationshipStatus.CONSULT_SCHEDULED
    assert profile.last_evidence_provider == "carestack"
    assert profile.last_evidence_external_id == "cs-appt-123"


@pytest.mark.asyncio
async def test_completed_consultation_promotes_profile_to_patient() -> None:
    service, repo = _make_service()
    location_id = uuid.uuid4()
    payload = _payload(
        location_id=location_id,
        status=ConsultationStatus.COMPLETED,
    )
    existing_consultation = _make_existing(payload)
    existing_profile = PersonLocationProfile(
        id=uuid.uuid4(),
        tenant_id=_TENANT_ID,
        person_uid=_PERSON_UID,
        location_id=location_id,
        relationship_kind=RelationshipKind.PROSPECT,
        relationship_status=RelationshipStatus.CONSULT_SCHEDULED,
        created_at=_NOW,
        updated_at=_NOW,
    )
    repo.find_consultation_by_source = AsyncMock(return_value=existing_consultation)
    repo.find_person_location_profile = AsyncMock(return_value=existing_profile)

    await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    assert existing_profile.relationship_kind == RelationshipKind.PATIENT
    assert existing_profile.relationship_status == RelationshipStatus.CONSULT_COMPLETED
    assert existing_profile.last_consultation_id == existing_consultation.id


@pytest.mark.asyncio
async def test_cancelled_consultation_does_not_downgrade_patient_profile() -> None:
    service, repo = _make_service()
    location_id = uuid.uuid4()
    payload = _payload(
        location_id=location_id,
        status=ConsultationStatus.CANCELLED,
    )
    existing_consultation = _make_existing(payload)
    existing_profile = PersonLocationProfile(
        id=uuid.uuid4(),
        tenant_id=_TENANT_ID,
        person_uid=_PERSON_UID,
        location_id=location_id,
        relationship_kind=RelationshipKind.PATIENT,
        relationship_status=RelationshipStatus.CONSULT_COMPLETED,
        created_at=_NOW,
        updated_at=_NOW,
    )
    repo.find_consultation_by_source = AsyncMock(return_value=existing_consultation)
    repo.find_person_location_profile = AsyncMock(return_value=existing_profile)

    await service.upsert_consultation_from_hint(_TENANT_ID, payload)

    assert existing_profile.relationship_kind == RelationshipKind.PATIENT
    assert existing_profile.relationship_status == RelationshipStatus.CANCELLED


@pytest.mark.asyncio
async def test_same_person_can_have_conflicting_profiles_per_location() -> None:
    service, repo = _make_service()
    location_a = uuid.uuid4()
    location_b = uuid.uuid4()
    scheduled = _payload(
        external_id="cs-appt-location-a",
        location_id=location_a,
        status=ConsultationStatus.SCHEDULED,
    )
    completed = _payload(
        external_id="cs-appt-location-b",
        location_id=location_b,
        status=ConsultationStatus.COMPLETED,
    )
    repo.find_consultation_by_source = AsyncMock(return_value=None)

    async def _add(consultation: Consultation) -> Consultation:
        consultation.id = uuid.uuid4()
        consultation.created_at = _NOW
        consultation.updated_at = _NOW
        return consultation

    repo.add_consultation = AsyncMock(side_effect=_add)
    created_profiles: list[PersonLocationProfile] = []

    async def _add_profile(
        profile: PersonLocationProfile,
    ) -> PersonLocationProfile:
        created_profiles.append(profile)
        return profile

    repo.add_person_location_profile = AsyncMock(side_effect=_add_profile)

    await service.upsert_consultation_from_hint(_TENANT_ID, scheduled)
    await service.upsert_consultation_from_hint(_TENANT_ID, completed)

    by_location = {profile.location_id: profile for profile in created_profiles}
    assert set(by_location) == {location_a, location_b}
    assert by_location[location_a].person_uid == _PERSON_UID
    assert by_location[location_a].relationship_kind == RelationshipKind.PROSPECT
    assert (
        by_location[location_a].relationship_status
        == RelationshipStatus.CONSULT_SCHEDULED
    )
    assert by_location[location_b].person_uid == _PERSON_UID
    assert by_location[location_b].relationship_kind == RelationshipKind.PATIENT
    assert (
        by_location[location_b].relationship_status
        == RelationshipStatus.CONSULT_COMPLETED
    )


@pytest.mark.asyncio
async def test_consultation_without_location_does_not_create_profile() -> None:
    service, repo = _make_service()
    repo.find_consultation_by_source = AsyncMock(return_value=None)

    async def _add(consultation: Consultation) -> Consultation:
        consultation.id = uuid.uuid4()
        consultation.created_at = _NOW
        consultation.updated_at = _NOW
        return consultation

    repo.add_consultation = AsyncMock(side_effect=_add)

    await service.upsert_consultation_from_hint(_TENANT_ID, _payload())

    repo.find_person_location_profile.assert_not_awaited()
    repo.add_person_location_profile.assert_not_awaited()


def test_person_location_profile_model_has_expected_columns() -> None:
    columns = {c.name for c in PersonLocationProfile.__table__.columns}
    assert {
        "id",
        "tenant_id",
        "person_uid",
        "location_id",
        "relationship_kind",
        "relationship_status",
        "last_evidence_provider",
        "last_evidence_source_instance",
        "last_evidence_external_id",
        "last_evidence_at",
        "last_consultation_id",
        "last_raw_event_id",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_person_location_profile_has_location_unique_constraint() -> None:
    table = cast(Table, PersonLocationProfile.__table__)
    unique_names = {
        c.name for c in table.constraints if getattr(c, "name", None)
    }
    assert "uq_person_location_profile_tenant_person_location" in unique_names
