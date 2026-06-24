"""Tests for the Salesforce Opportunity ingest service (ENG-414).

Pins the new behavior:

- ``Owner.Name`` is in the SOQL projection.
- Every captured Opportunity is projected into ``ops.opportunity`` —
  even when the AccountId → person fallback misses.
- The ``extra`` JSONB blob carries the owner_id / owner_name mirror
  so the funnel-responsibility surface can resolve TCs.

The existing raw-event capture + timeline-event emit behaviour is
preserved.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.sf_opportunity_service import (
    _SF_OPPORTUNITY_COLUMNS,
    SfOpportunityIngestService,
    _opportunity_extra,
    _owner_name_from_record,
    _safe_float,
)
from packages.ops.schemas import OpportunityIn

_TENANT = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_RAW_EVENT_ID = uuid.uuid4()


def _record(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "Id": "006xx00000ABC",
        "Name": "Implant case — Jones",
        "StageName": "Consult Booked",
        "Amount": 12500.0,
        "CloseDate": "2026-07-01",
        "AccountId": "001xx00000ACC",
        "OwnerId": "005xx0000001abc",
        "Owner": {
            "attributes": {"type": "User", "url": "..."},
            "Name": "Anna Coordinator",
        },
        "CreatedDate": "2026-06-01T12:00:00.000+0000",
        "LastModifiedDate": "2026-06-13T10:00:00.000+0000",
        "Type": "New Patient",
        "LeadSource": "Google",
        "Probability": 50.0,
        "IsClosed": False,
        "IsWon": False,
    }
    base.update(overrides)
    return base


def _make_service() -> tuple[SfOpportunityIngestService, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    svc = SfOpportunityIngestService(session=session, sf_client=sf_client)

    raw_event = MagicMock()
    raw_event.id = _RAW_EVENT_ID

    svc._ingest = MagicMock()  # type: ignore[attr-defined]
    svc._ingest.capture = AsyncMock(return_value=raw_event)

    svc._identity_repo = MagicMock()  # type: ignore[attr-defined]
    svc._identity_repo.find_source_link = AsyncMock(return_value=None)

    svc._interaction = MagicMock()  # type: ignore[attr-defined]
    svc._interaction.find_provider_event_by_external_id = AsyncMock(
        return_value=None
    )
    svc._interaction.create_event = AsyncMock(return_value=MagicMock())

    svc._ops = MagicMock()  # type: ignore[attr-defined]
    svc._ops.upsert_opportunity = AsyncMock(return_value=MagicMock())
    # origin/main person-resolution fallback used by _capture_opportunity when
    # the AccountId source-link misses — must be awaitable.
    svc._ops.find_lead_person_by_converted_opportunity = AsyncMock(return_value=None)

    return svc, sf_client


# ----------------------------------------------------------------- SOQL projection


def test_soql_projection_includes_owner_name() -> None:
    """Owner.Name must be in the SOQL columns string (ENG-414 enrichment)."""
    assert "Owner.Name" in _SF_OPPORTUNITY_COLUMNS


# ----------------------------------------------------------------- helpers


def test_owner_name_from_record_reads_relation() -> None:
    record = _record()
    assert _owner_name_from_record(record) == "Anna Coordinator"


def test_owner_name_from_record_handles_missing_owner() -> None:
    assert _owner_name_from_record({"Id": "x"}) is None
    assert _owner_name_from_record({"Owner": "not-a-dict"}) is None
    assert _owner_name_from_record({"Owner": {"Name": "   "}}) is None


def test_safe_float_parses_numbers_and_strings() -> None:
    assert _safe_float(12.5) == 12.5
    assert _safe_float(12) == 12.0
    assert _safe_float("12.50") == 12.5
    assert _safe_float(None) is None
    assert _safe_float("not a number") is None
    assert _safe_float(True) is None  # ``bool`` is not a valid Amount


def test_opportunity_extra_mirrors_owner_and_stage() -> None:
    extra = _opportunity_extra(_record())
    assert extra["owner_id"] == "005xx0000001abc"
    assert extra["owner_name"] == "Anna Coordinator"
    assert extra["opportunity_stage"] == "Consult Booked"
    assert extra["account_id"] == "001xx00000ACC"
    assert extra["lead_source"] == "Google"
    assert extra["sf_opportunity_id"] == "006xx00000ABC"
    assert extra["is_closed"] is False
    assert extra["is_won"] is False
    assert extra["probability"] == 50.0


# ----------------------------------------------------------------- projection wiring


@pytest.mark.asyncio
async def test_capture_projects_into_ops_opportunity_when_person_resolves() -> None:
    svc, _ = _make_service()

    # Source-link returns a person_uid for the AccountId fallback.
    svc._identity_repo.find_source_link = AsyncMock(  # type: ignore[attr-defined]
        return_value=MagicMock(person_uid=_PERSON_UID)
    )

    await svc._capture_opportunity(_TENANT, _record(), "006xx00000ABC")

    svc._ops.upsert_opportunity.assert_awaited_once()  # type: ignore[attr-defined]
    payload: OpportunityIn = svc._ops.upsert_opportunity.await_args.args[1]  # type: ignore[attr-defined]
    assert isinstance(payload, OpportunityIn)
    assert payload.person_uid == _PERSON_UID
    assert payload.source_provider == "salesforce"
    assert payload.source_instance == "salesforce-main"
    assert payload.external_id == "006xx00000ABC"
    assert payload.name == "Implant case — Jones"
    assert payload.stage == "Consult Booked"
    assert payload.amount == 12500.0
    assert payload.raw_event_id == _RAW_EVENT_ID
    assert payload.extra["owner_id"] == "005xx0000001abc"
    assert payload.extra["owner_name"] == "Anna Coordinator"


@pytest.mark.asyncio
async def test_capture_projects_into_ops_opportunity_when_person_missing() -> None:
    """The TC must still land on the row even when AccountId fallback misses."""
    svc, _ = _make_service()
    # find_source_link already returns None by default.

    await svc._capture_opportunity(_TENANT, _record(), "006xx00000ABC")

    svc._ops.upsert_opportunity.assert_awaited_once()  # type: ignore[attr-defined]
    payload: OpportunityIn = svc._ops.upsert_opportunity.await_args.args[1]  # type: ignore[attr-defined]
    assert payload.person_uid is None
    assert payload.extra["owner_id"] == "005xx0000001abc"
    # And no timeline event is emitted when there is no person link.
    svc._interaction.create_event.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_capture_still_writes_raw_event() -> None:
    """The raw_event capture contract is preserved (per CLAUDE.md)."""
    svc, _ = _make_service()
    await svc._capture_opportunity(_TENANT, _record(), "006xx00000ABC")
    svc._ingest.capture.assert_awaited_once()  # type: ignore[attr-defined]
