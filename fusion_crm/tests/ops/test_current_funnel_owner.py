"""Tests for ENG-418 ``OpsService.get_current_funnel_owner``.

The current-owner rule (managers-confirmed): Lead owner until at least
one Opportunity exists that is not closed-lost; once one exists, the
newest non-lost Opportunity's owner takes over.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ops.service import OpsService

_TENANT = TenantId(uuid.uuid4())
_PERSON = uuid.uuid4()
_NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


def _make_service() -> tuple[OpsService, MagicMock]:
    service = OpsService(MagicMock())
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._identity = MagicMock()  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


def _opp(
    *,
    stage: str | None = "Discovery",
    owner_id: str | None = "005ABC",
    owner_name: str | None = "Olivia TC",
    opp_id: uuid.UUID | None = None,
):
    row = MagicMock()
    row.id = opp_id or uuid.uuid4()
    row.stage = stage
    extra = {}
    if owner_id is not None:
        extra["owner_id"] = owner_id
    if owner_name is not None:
        extra["owner_name"] = owner_name
    row.extra = extra
    return row


@pytest.mark.asyncio
async def test_falls_back_to_lead_owner_when_no_opportunities() -> None:
    service, repo = _make_service()
    repo.list_opportunities_for_person = AsyncMock(return_value=[])
    lead = MagicMock()
    lead.extra = {"owner_id": "005LEAD", "owner_name": "Alice Agent"}
    repo.find_lead_by_person = AsyncMock(return_value=lead)

    owner = await service.get_current_funnel_owner(_TENANT, _PERSON)

    assert owner is not None
    assert owner.stage == "lead"
    assert owner.external_id == "005LEAD"
    assert owner.owner_name == "Alice Agent"


@pytest.mark.asyncio
async def test_picks_first_non_lost_opportunity_owner() -> None:
    service, repo = _make_service()
    # list_opportunities returns newest-first; the resolver should pick
    # the first non-closed-lost one.
    opps = [
        _opp(stage="Closed Lost", owner_id="005LOST"),
        _opp(stage="Discovery", owner_id="005WIN", owner_name="Tom TC"),
    ]
    repo.list_opportunities_for_person = AsyncMock(return_value=opps)
    repo.find_lead_by_person = AsyncMock(return_value=None)

    owner = await service.get_current_funnel_owner(_TENANT, _PERSON)

    assert owner is not None
    assert owner.stage == "opportunity"
    assert owner.external_id == "005WIN"
    assert owner.owner_name == "Tom TC"
    assert owner.opportunity_id == opps[1].id


@pytest.mark.asyncio
async def test_falls_back_to_lead_when_only_lost_opportunity_exists() -> None:
    service, repo = _make_service()
    opps = [_opp(stage="Closed Lost", owner_id="005LOST")]
    repo.list_opportunities_for_person = AsyncMock(return_value=opps)
    lead = MagicMock()
    lead.extra = {"owner_id": "005LEAD"}
    repo.find_lead_by_person = AsyncMock(return_value=lead)

    owner = await service.get_current_funnel_owner(_TENANT, _PERSON)

    assert owner is not None
    assert owner.stage == "lead"
    assert owner.external_id == "005LEAD"


@pytest.mark.asyncio
async def test_returns_none_when_no_lead_and_no_opportunity_owner() -> None:
    service, repo = _make_service()
    repo.list_opportunities_for_person = AsyncMock(return_value=[])
    repo.find_lead_by_person = AsyncMock(return_value=None)

    owner = await service.get_current_funnel_owner(_TENANT, _PERSON)

    assert owner is None


@pytest.mark.asyncio
async def test_returns_none_when_lead_has_no_owner_id() -> None:
    service, repo = _make_service()
    repo.list_opportunities_for_person = AsyncMock(return_value=[])
    lead = MagicMock()
    lead.extra = {"owner_name": "no owner_id stored"}
    repo.find_lead_by_person = AsyncMock(return_value=lead)

    owner = await service.get_current_funnel_owner(_TENANT, _PERSON)

    assert owner is None


@pytest.mark.asyncio
async def test_sum_opportunity_amount_forwards_to_repo() -> None:
    service, repo = _make_service()
    person_a = uuid.uuid4()
    repo.sum_opportunity_amount_for_persons = AsyncMock(
        return_value={person_a: 5400.0}
    )
    out = await service.sum_opportunity_amount_for_persons(
        _TENANT, [person_a]
    )
    assert out == {person_a: 5400.0}
