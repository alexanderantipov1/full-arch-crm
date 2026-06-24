"""Unit tests for ``SfEventIngestService`` (ENG-220).

Mirrors the CareStack appointment tests: identity resolution paths,
status inference, validation, and payload safety (Description must NOT
leak into ops.consultation).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ingest.sf_event_service import (
    SfEventIngestService,
    _map_kind,
    _map_status,
)
from packages.ops.models import ConsultationKind, ConsultationStatus
from packages.ops.schemas import ConsultationOut, ConsultationUpsertResult

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_SCHEDULED_AT = datetime(2026, 6, 1, 14, 0, tzinfo=UTC)


def _event(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "Id": "00U5j000001abcd",
        "WhoId": "00Q5j000001leadX",  # Lead prefix
        "WhatId": "001RM00000abc",
        "StartDateTime": "2026-06-01T14:00:00Z",
        "EndDateTime": "2026-06-01T14:30:00Z",
        "Subject": "Initial consult — Implants",
        "Type": "Initial Consultation",
        "ActivityDate": "2026-06-01",
        "LastModifiedDate": "2026-05-22T00:00:00Z",
        "IsAllDayEvent": False,
        "ShowAs": "Busy",
        "Description": "PHI MUST NOT REACH OPS — diagnosis discussion",
    }
    base.update(overrides)
    return base


def _make_service(
    records: list[dict[str, Any]] | None = None,
    lead_link: SimpleNamespace | None = None,
    contact_link: SimpleNamespace | None = None,
) -> tuple[SfEventIngestService, MagicMock, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(
        return_value={"records": records or [_event()]}
    )
    service = SfEventIngestService(session, sf_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=[
            "capture",
            "max_payload_watermark",
            "latest_payload_values",
            "get_object_schema",
        ]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    # First-run defaults: no watermark yet, nothing captured before.
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    # ENG-427: empty registry → dynamic projection falls back to static.
    service._ingest.get_object_schema = AsyncMock(return_value=[])

    # find_source_link is awaited twice per event (lead, then contact).
    # Return lead_link first if present, then contact_link, then None.
    async def _find(*_args: object, source_kind: str, **_kwargs: object) -> Any:
        if source_kind == "lead":
            return lead_link
        if source_kind == "contact":
            return contact_link
        return None

    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(side_effect=_find)
    service._ops = MagicMock(spec=["upsert_consultation_from_hint"])  # type: ignore[attr-defined]
    service._ops.upsert_consultation_from_hint = AsyncMock(
        return_value=_upsert_result()
    )
    service._interaction = MagicMock(  # type: ignore[attr-defined]
        spec=["create_event", "list_provider_events_by_external_id"]
    )
    service._interaction.create_event = AsyncMock()  # type: ignore[attr-defined]
    service._interaction.list_provider_events_by_external_id = AsyncMock(  # type: ignore[attr-defined]
        return_value=[]
    )
    return (
        service,
        sf_client,
        service._ingest,  # type: ignore[attr-defined]
        service._identity_repo,  # type: ignore[attr-defined]
        service._ops,  # type: ignore[attr-defined]
    )


def _upsert_result(
    *,
    status: ConsultationStatus = ConsultationStatus.SCHEDULED,
    was_created: bool = True,
    was_changed: bool = True,
    was_status_change: bool = False,
    was_scheduled_at_change: bool = False,
) -> ConsultationUpsertResult:
    return ConsultationUpsertResult(
        consultation=ConsultationOut(
            id=uuid.uuid4(),
            person_uid=_PERSON_UID,
            source_provider="salesforce",
            source_instance="salesforce-main",
            external_id="00U5j000001abcd",
            scheduled_at=_SCHEDULED_AT,
            duration_minutes=30,
            status=status,
            consultation_kind=ConsultationKind.INITIAL,
            location_id=None,
            provider_clinician_name=None,
            raw_event_id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        was_created=was_created,
        was_changed=was_changed,
        was_status_change=was_status_change,
        was_scheduled_at_change=was_scheduled_at_change,
    )


# ------------------------------------------------------ happy + resolution


@pytest.mark.asyncio
async def test_import_resolves_lead_first_then_upserts_consultation() -> None:
    lead_link = SimpleNamespace(person_uid=_PERSON_UID)
    service, _, ingest, repo, ops = _make_service(lead_link=lead_link)

    result = await service.import_recent_events(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.queried_count == 1

    ingest.capture.assert_awaited_once()
    raw = ingest.capture.await_args.args[1]
    assert raw.source == "salesforce"
    assert raw.event_type == "salesforce.event.upsert"
    assert raw.external_id == "00U5j000001abcd"

    # First lookup tried lead, succeeded — second (contact) never called.
    repo.find_source_link.assert_awaited_once()
    ops.upsert_consultation_from_hint.assert_awaited_once()
    payload = ops.upsert_consultation_from_hint.await_args.args[1]
    assert payload.person_uid == _PERSON_UID
    assert payload.source_provider == "salesforce"
    assert payload.source_instance == "salesforce-main"
    assert payload.external_id == "00U5j000001abcd"
    assert payload.duration_minutes == 30
    assert payload.consultation_kind == ConsultationKind.INITIAL
    # PHI must not have leaked.
    assert not hasattr(payload, "description")


@pytest.mark.asyncio
async def test_first_import_emits_consultation_scheduled_event() -> None:
    lead_link = SimpleNamespace(person_uid=_PERSON_UID)
    raw_event_id = uuid.uuid4()
    service, _, ingest, _, ops = _make_service(lead_link=lead_link)
    upsert = _upsert_result()
    ops.upsert_consultation_from_hint.return_value = upsert
    ingest.capture.return_value = SimpleNamespace(
        id=raw_event_id, received_at=datetime.now(UTC)
    )

    result = await service.import_recent_events(_TENANT_ID, days=7)

    assert result.imported_count == 1
    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_awaited_once()
    await_args = create_event.await_args
    assert await_args is not None
    event = await_args.args[1]
    assert event.kind == "consultation_scheduled"
    assert event.source_provider == "salesforce"
    assert event.source_kind == "salesforce_event"
    assert event.source_external_id == "00U5j000001abcd"
    assert event.source_event_id == raw_event_id
    assert event.projection_ref_type == "ops_consultation"
    assert event.projection_ref_id == upsert.consultation.id
    assert event.data_class == "operational"
    assert event.review_status == "auto"
    assert event.payload == {}
    assert "PHI" not in event.summary
    assert "diagnosis" not in event.summary


@pytest.mark.asyncio
async def test_event_description_call_refs_emit_metadata_only_events() -> None:
    raw_event_id = uuid.uuid4()
    record = _event(
        Description=(
            "PHI MUST NOT LEAK. Join https://fusion.zoom.us/j/987654321 "
            "recording https://api.twilio.com/2010-04-01/Accounts/AC123/"
            "Recordings/REabc123"
        )
    )
    service, _, ingest, _, ops = _make_service(
        records=[record],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )
    ops.upsert_consultation_from_hint.return_value = _upsert_result()
    ingest.capture.return_value = SimpleNamespace(
        id=raw_event_id, received_at=datetime.now(UTC)
    )

    result = await service.import_recent_events(_TENANT_ID, days=7)

    assert result.imported_count == 1
    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    assert create_event.await_count == 3
    consultation_event = create_event.await_args_list[0].args[1]
    zoom_ref = create_event.await_args_list[1].args[1]
    twilio_ref = create_event.await_args_list[2].args[1]

    assert consultation_event.kind == "consultation_scheduled"
    assert zoom_ref.kind == "call_reference_found"
    assert zoom_ref.source_kind == "salesforce_event"
    assert zoom_ref.source_external_id == "00U5j000001abcd"
    assert zoom_ref.source_event_id is None
    assert zoom_ref.data_class == "call_recording_ref"
    assert zoom_ref.review_status == "pending_review"
    assert zoom_ref.payload == {
        "source_provider": "salesforce",
        "source_object_id": "00U5j000001abcd",
        "raw_event_id": str(raw_event_id),
        "data_class": "call_recording_ref",
        "review_status": "pending_review",
        "provider": "zoom",
        "kind": "meeting",
        "url": "https://fusion.zoom.us/j/987654321",
        "external_id": "987654321",
    }
    assert twilio_ref.payload["provider"] == "twilio"
    assert twilio_ref.payload["kind"] == "recording"
    assert twilio_ref.payload["external_id"] == "REabc123"
    assert "PHI MUST NOT LEAK" not in zoom_ref.summary
    assert "PHI MUST NOT LEAK" not in str(zoom_ref.payload)
    assert "Join " not in str(zoom_ref.payload)


@pytest.mark.asyncio
async def test_event_call_ref_reimport_skips_existing_url() -> None:
    record = _event(Description="Recording https://fusion.zoom.us/rec/share/abc123")
    service, _, _, _, ops = _make_service(
        records=[record],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )
    ops.upsert_consultation_from_hint.return_value = _upsert_result(
        was_created=False,
        was_changed=False,
    )
    service._interaction.list_provider_events_by_external_id.return_value = [  # type: ignore[attr-defined]
        SimpleNamespace(payload={"url": "https://fusion.zoom.us/rec/share/abc123"})
    ]

    await service.import_recent_events(_TENANT_ID, days=7)

    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_status_change_emits_consultation_completed_event() -> None:
    service, _, _, _, ops = _make_service(lead_link=SimpleNamespace(person_uid=_PERSON_UID))
    ops.upsert_consultation_from_hint.return_value = _upsert_result(
        status=ConsultationStatus.COMPLETED,
        was_created=False,
        was_changed=True,
        was_status_change=True,
        was_scheduled_at_change=False,
    )

    await service.import_recent_events(_TENANT_ID, days=7)

    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_awaited_once()
    await_args = create_event.await_args
    assert await_args is not None
    event = await_args.args[1]
    assert event.kind == "consultation_completed"
    assert event.payload == {}


@pytest.mark.asyncio
async def test_reimport_without_change_emits_no_event() -> None:
    service, _, _, _, ops = _make_service(lead_link=SimpleNamespace(person_uid=_PERSON_UID))
    ops.upsert_consultation_from_hint.return_value = _upsert_result(
        was_created=False,
        was_changed=False,
        was_status_change=False,
        was_scheduled_at_change=False,
    )

    await service.import_recent_events(_TENANT_ID, days=7)

    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_falls_back_to_contact_when_lead_missing() -> None:
    contact_link = SimpleNamespace(person_uid=_PERSON_UID)
    # Contact WhoId prefix typically `003`.
    record = _event(WhoId="003RM00000xyz")
    service, _, _, repo, ops = _make_service(
        records=[record], lead_link=None, contact_link=contact_link
    )

    result = await service.import_recent_events(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.skipped_count == 0
    # Two repo lookups: lead miss, then contact hit.
    assert repo.find_source_link.await_count == 2
    ops.upsert_consultation_from_hint.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_skips_when_neither_lead_nor_contact_match() -> None:
    service, _, ingest, repo, ops = _make_service(
        lead_link=None, contact_link=None
    )

    result = await service.import_recent_events(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.skipped_count == 1
    # Raw still captured (forensic audit).
    ingest.capture.assert_awaited_once()
    # Two repo lookups attempted before giving up.
    assert repo.find_source_link.await_count == 2
    ops.upsert_consultation_from_hint.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_skips_when_no_who_id() -> None:
    record = _event(WhoId=None)
    service, _, _, _, ops = _make_service(records=[record])

    result = await service.import_recent_events(_TENANT_ID, days=7)
    assert result.imported_count == 0
    assert result.skipped_count == 1
    ops.upsert_consultation_from_hint.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_skips_when_no_start_or_activity_date() -> None:
    record = _event(StartDateTime=None, ActivityDate=None)
    service, _, _, _, ops = _make_service(
        records=[record], lead_link=SimpleNamespace(person_uid=_PERSON_UID)
    )

    result = await service.import_recent_events(_TENANT_ID, days=7)
    assert result.imported_count == 0
    assert result.skipped_count == 1


# ------------------------------------------------------ status inference


def test_map_status_future_event_is_scheduled() -> None:
    future = (datetime.now(UTC) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert (
        _map_status({"StartDateTime": future, "EndDateTime": None})
        == ConsultationStatus.SCHEDULED
    )


def test_map_status_past_event_with_end_is_completed() -> None:
    past_start = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    past_end = (datetime.now(UTC) - timedelta(days=2, hours=-1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert (
        _map_status({"StartDateTime": past_start, "EndDateTime": past_end})
        == ConsultationStatus.COMPLETED
    )


def test_map_status_past_start_no_end_is_completed() -> None:
    past = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert (
        _map_status({"StartDateTime": past, "EndDateTime": None})
        == ConsultationStatus.COMPLETED
    )


# ------------------------------------------------------ kind inference


def test_map_kind_initial_keywords() -> None:
    assert _map_kind({"Type": "Initial Consultation"}) == ConsultationKind.INITIAL
    assert _map_kind({"Type": "New patient consult"}) == ConsultationKind.INITIAL
    assert _map_kind({"Type": "Intake meeting"}) == ConsultationKind.INITIAL


def test_map_kind_followup() -> None:
    assert _map_kind({"Type": "Follow up"}) == ConsultationKind.FOLLOW_UP
    assert _map_kind({"Type": "Followup call"}) == ConsultationKind.FOLLOW_UP


def test_map_kind_treatment() -> None:
    assert _map_kind({"Type": "Treatment session"}) == ConsultationKind.TREATMENT
    assert _map_kind({"Type": "Procedure"}) == ConsultationKind.TREATMENT


def test_map_kind_default_other() -> None:
    assert _map_kind({"Type": "Coffee chat"}) == ConsultationKind.OTHER
    assert _map_kind({"Type": None}) == ConsultationKind.OTHER
    assert _map_kind({}) == ConsultationKind.OTHER


# ------------------------------------------------------ validation


@pytest.mark.asyncio
async def test_import_rejects_invalid_days() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_events(_TENANT_ID, days=0)
    with pytest.raises(ValidationError):
        await service.import_recent_events(_TENANT_ID, days=400)


@pytest.mark.asyncio
async def test_import_rejects_invalid_limit() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_events(_TENANT_ID, limit=0)
    with pytest.raises(ValidationError):
        await service.import_recent_events(_TENANT_ID, limit=600)
