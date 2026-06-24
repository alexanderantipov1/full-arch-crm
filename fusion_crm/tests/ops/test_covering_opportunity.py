"""Service tests for the consultation ↔ opportunity link (ENG-417).

Covers ``OpsService.find_covering_opportunity``,
``OpsService.attach_consultation_to_opportunity``, and the lead-owner /
opportunity-owner extractors used by the funnel-responsibility resolver.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ops.models import Consultation, ConsultationKind, ConsultationStatus, Lead
from packages.ops.schemas import OpportunityOut
from packages.ops.service import OpsService

_TENANT = TenantId(uuid.uuid4())
_PERSON = uuid.uuid4()
_NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


def _make_service() -> tuple[OpsService, MagicMock]:
    service = OpsService(MagicMock())
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._identity = MagicMock()  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_find_covering_opportunity_returns_dto_when_repo_hits() -> None:
    service, repo = _make_service()
    row = MagicMock()
    row.id = uuid.uuid4()
    row.person_uid = _PERSON
    row.source_provider = "salesforce"
    row.source_instance = "salesforce-main"
    row.external_id = "006-001"
    row.name = None
    row.stage = "Discovery"
    row.amount = 1000.0
    row.close_date = None
    row.provider_created_at = _NOW
    row.raw_event_id = None
    row.extra = {"owner_id": "005ABC"}
    row.created_at = _NOW
    row.updated_at = _NOW
    repo.find_covering_opportunity = AsyncMock(return_value=row)

    out = await service.find_covering_opportunity(_TENANT, _PERSON, _NOW)
    assert out is not None
    assert out.id == row.id
    assert out.extra["owner_id"] == "005ABC"


@pytest.mark.asyncio
async def test_find_covering_opportunity_returns_none_when_no_row() -> None:
    service, repo = _make_service()
    repo.find_covering_opportunity = AsyncMock(return_value=None)
    out = await service.find_covering_opportunity(_TENANT, _PERSON, _NOW)
    assert out is None


@pytest.mark.asyncio
async def test_attach_consultation_to_opportunity_idempotent_no_change() -> None:
    service, repo = _make_service()
    consult_id = uuid.uuid4()
    opp_id = uuid.uuid4()
    existing = MagicMock(spec=Consultation)
    existing.id = consult_id
    existing.tenant_id = _TENANT
    existing.person_uid = _PERSON
    existing.source_provider = "carestack"
    existing.source_instance = "carestack-main"
    existing.external_id = "cs-1"
    existing.scheduled_at = _NOW
    existing.duration_minutes = None
    existing.status = ConsultationStatus.SCHEDULED
    existing.consultation_kind = ConsultationKind.OTHER
    existing.location_id = None
    existing.provider_clinician_name = None
    existing.raw_event_id = None
    existing.provider_created_at = None
    existing.covering_opportunity_id = opp_id
    existing.created_at = _NOW
    existing.updated_at = _NOW
    repo.get_consultation = AsyncMock(return_value=existing)
    service._session.flush = AsyncMock()  # type: ignore[method-assign]
    service._session.refresh = AsyncMock()  # type: ignore[method-assign]

    out = await service.attach_consultation_to_opportunity(
        _TENANT, consult_id, opp_id
    )
    assert out is not None
    # No-op when the link already matches — must not flush.
    service._session.flush.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_attach_consultation_to_opportunity_returns_none_when_missing() -> None:
    service, repo = _make_service()
    repo.get_consultation = AsyncMock(return_value=None)
    out = await service.attach_consultation_to_opportunity(
        _TENANT, uuid.uuid4(), uuid.uuid4()
    )
    assert out is None


@pytest.mark.asyncio
async def test_attach_consultation_to_opportunity_writes_when_link_changes() -> None:
    service, repo = _make_service()
    consult_id = uuid.uuid4()
    new_opp_id = uuid.uuid4()
    existing = MagicMock(spec=Consultation)
    existing.id = consult_id
    existing.tenant_id = _TENANT
    existing.person_uid = _PERSON
    existing.source_provider = "carestack"
    existing.source_instance = "carestack-main"
    existing.external_id = "cs-1"
    existing.scheduled_at = _NOW
    existing.duration_minutes = None
    existing.status = ConsultationStatus.SCHEDULED
    existing.consultation_kind = ConsultationKind.OTHER
    existing.location_id = None
    existing.provider_clinician_name = None
    existing.raw_event_id = None
    existing.provider_created_at = None
    existing.covering_opportunity_id = None
    existing.created_at = _NOW
    existing.updated_at = _NOW
    repo.get_consultation = AsyncMock(return_value=existing)

    async def _refresh(row: Any) -> None:
        return None

    service._session.flush = AsyncMock()  # type: ignore[method-assign]
    service._session.refresh = AsyncMock(side_effect=_refresh)  # type: ignore[method-assign]

    out = await service.attach_consultation_to_opportunity(
        _TENANT, consult_id, new_opp_id
    )

    assert existing.covering_opportunity_id == new_opp_id
    service._session.flush.assert_awaited_once()  # type: ignore[attr-defined]
    service._session.refresh.assert_awaited_once_with(existing)  # type: ignore[attr-defined]
    assert out is not None


@pytest.mark.asyncio
async def test_get_lead_owner_id_reads_from_extra() -> None:
    service, repo = _make_service()
    lead = MagicMock(spec=Lead)
    lead.extra = {"owner_id": "005LEAD001"}
    repo.find_lead_by_person = AsyncMock(return_value=lead)

    out = await service.get_lead_owner_id(_TENANT, _PERSON)
    assert out == "005LEAD001"


@pytest.mark.asyncio
async def test_get_lead_owner_id_returns_none_when_no_lead() -> None:
    service, repo = _make_service()
    repo.find_lead_by_person = AsyncMock(return_value=None)
    assert await service.get_lead_owner_id(_TENANT, _PERSON) is None


@pytest.mark.asyncio
async def test_get_lead_owner_id_returns_none_when_owner_missing() -> None:
    service, repo = _make_service()
    lead = MagicMock(spec=Lead)
    lead.extra = {}
    repo.find_lead_by_person = AsyncMock(return_value=lead)
    assert await service.get_lead_owner_id(_TENANT, _PERSON) is None


@pytest.mark.asyncio
async def test_get_opportunity_owner_id_reads_from_dto_extra() -> None:
    service, _ = _make_service()
    opp = OpportunityOut(
        id=uuid.uuid4(),
        person_uid=_PERSON,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="006-001",
        name=None,
        stage=None,
        amount=None,
        close_date=None,
        provider_created_at=None,
        raw_event_id=None,
        extra={"owner_id": "005OPPOWN"},
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert await service.get_opportunity_owner_id(opp) == "005OPPOWN"
