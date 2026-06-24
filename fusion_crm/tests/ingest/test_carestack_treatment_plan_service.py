"""Unit tests for ``CareStackTreatmentPlanIngestService`` (ENG-511, B1.3).

Mock-based: the ingest / identity / interaction surfaces are replaced with
mocks so these lock the acceptance logic (emit treatment_accepted ONLY on
StatusId=3, NOT 8/10/9), the content-dedup raw capture, the idempotent
event-existence pre-check, and the no-PHI safe payload — without a Postgres.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.carestack_treatment_plan_service import (
    CareStackTreatmentPlanIngestService,
    _plan_source_id,
    _plan_status_id,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_PATIENT_ID = "9985"

# Clinical tokens that must never leak into the emitted timeline event.
_PHI_TOKENS = (
    "Full arch implant reconstruction",  # plan name
    "12,13,14",  # condition ids
)


def _plan(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "TreatmentPlanId": 5001,
        "TreatmentPlanName": "Full arch implant reconstruction",
        "StatusId": 3,  # Accepted
        "ConditionIds": "12,13,14",
        "Duration": 6,
    }
    base.update(overrides)
    return base


def _make_service(
    plans: list[dict[str, Any]] | None = None,
    *,
    existing_event: object | None = None,
    latest_payload: dict[str, Any] | None = None,
) -> tuple[CareStackTreatmentPlanIngestService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    cs_client = MagicMock()
    cs_client.get_treatment_plans = AsyncMock(
        return_value=plans if plans is not None else [_plan()]
    )
    service = CareStackTreatmentPlanIngestService(session, cs_client)

    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["latest_payload", "capture", "capture_normalized_person_hint"]
    )
    service._ingest.latest_payload = AsyncMock(return_value=latest_payload)
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.capture_normalized_person_hint = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())
    )

    service._identity = MagicMock(  # type: ignore[attr-defined]
        spec=[
            "source_links_for_dashboard",
            "resolve_or_create_from_hint",
            "get_person",
        ]
    )
    service._identity.source_links_for_dashboard = AsyncMock(
        return_value=[
            SimpleNamespace(source_id=_PATIENT_ID, person_uid=_PERSON_UID)
        ]
    )
    service._identity.resolve_or_create_from_hint = AsyncMock(
        return_value=SimpleNamespace(person_uid=_PERSON_UID)
    )
    service._identity.get_person = AsyncMock(
        return_value=SimpleNamespace(id=_PERSON_UID)
    )

    service._interaction = MagicMock(  # type: ignore[attr-defined]
        spec=["find_provider_event_by_external_id", "create_event_idempotent"]
    )
    service._interaction.find_provider_event_by_external_id = AsyncMock(
        return_value=existing_event
    )
    service._interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=True
        )
    )
    return service, cs_client, service._ingest, service._interaction  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_accepted_plan_emits_treatment_accepted() -> None:
    service, _, ingest, interaction = _make_service()

    result = await service.import_treatment_plans(_TENANT_ID)

    assert result.accepted_count == 1
    assert result.captured_count == 1
    ingest.capture.assert_awaited()  # raw captured (full fidelity)
    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_accepted"
    assert event_in.source_kind == "carestack_treatment_plan"
    assert event_in.source_external_id == "5001"
    assert event_in.person_uid == _PERSON_UID
    # No-PII payload — clinical detail stays in raw only.
    assert event_in.payload == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [1, 2, 8, 9, 10])
async def test_non_accepted_status_does_not_emit(status: int) -> None:
    # Only StatusId=3 is acceptance. 8/10 (completed), 9 (presented), 1/2 are NOT.
    service, _, _, interaction = _make_service(plans=[_plan(StatusId=status)])

    result = await service.import_treatment_plans(_TENANT_ID)

    assert result.accepted_count == 0
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_event_skips_hint_roundtrip() -> None:
    # An idempotent re-pull: the acceptance event already exists.
    service, _, ingest, interaction = _make_service(
        existing_event=SimpleNamespace(id=uuid.uuid4())
    )

    result = await service.import_treatment_plans(_TENANT_ID)

    assert result.accepted_count == 0
    interaction.create_event_idempotent.assert_not_awaited()
    # No redundant hint row written when the event already exists.
    ingest.capture_normalized_person_hint.assert_not_awaited()


@pytest.mark.asyncio
async def test_content_dedup_skips_recapture() -> None:
    # latest_payload equals the incoming plan → no raw write, counts unchanged.
    plan = _plan(StatusId=1)  # non-accepted to isolate the dedup path
    service, _, ingest, _ = _make_service(plans=[plan], latest_payload=plan)

    result = await service.import_treatment_plans(_TENANT_ID)

    assert result.captured_count == 0
    assert result.unchanged_count == 1
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_accepted_event_carries_no_phi() -> None:
    service, _, _, interaction = _make_service()

    await service.import_treatment_plans(_TENANT_ID)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    for token in _PHI_TOKENS:
        assert token not in event_in.summary
        assert all(token not in str(v) for v in event_in.payload.values())


@pytest.mark.asyncio
async def test_patient_with_no_source_id_is_skipped() -> None:
    service, cs_client, _, _ = _make_service()
    service._identity.source_links_for_dashboard = AsyncMock(  # type: ignore[attr-defined]
        return_value=[SimpleNamespace(source_id=None, person_uid=_PERSON_UID)]
    )

    result = await service.import_treatment_plans(_TENANT_ID)

    assert result.skipped_count == 1
    cs_client.get_treatment_plans.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_failure_is_isolated() -> None:
    service, cs_client, _, _ = _make_service()
    cs_client.get_treatment_plans = AsyncMock(side_effect=RuntimeError("boom"))

    result = await service.import_treatment_plans(_TENANT_ID)

    assert result.error_count == 1
    assert result.accepted_count == 0


def test_plan_status_id_helper() -> None:
    assert _plan_status_id({"StatusId": 3}) == 3
    assert _plan_status_id({"statusId": "8"}) == 8
    assert _plan_status_id({"StatusId": True}) is None
    assert _plan_status_id({}) is None


def test_plan_source_id_helper() -> None:
    assert _plan_source_id({"TreatmentPlanId": 5001}) == "5001"
    assert _plan_source_id({"treatmentPlanId": "5001"}) == "5001"
    assert _plan_source_id({"id": 7}) == "7"
    assert _plan_source_id({"TreatmentPlanId": True}) is None
    assert _plan_source_id({}) is None
