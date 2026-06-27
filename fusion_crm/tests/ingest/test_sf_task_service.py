"""Tests for ``SfTaskIngestService`` (ENG-240)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ingest.sf_task_service import (
    SfTaskIngestService,
    build_recent_tasks_soql,
    classify_task,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_RAW_EVENT_ID = uuid.uuid4()
_FOLLOWUP_ID = uuid.uuid4()


def _task(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "Id": "00T5j000001taskA",
        "Subject": "Call patient about implant plan",
        "Status": "Open",
        "Priority": "Normal",
        "ActivityDate": "2026-06-01",
        "CreatedDate": "2026-05-20T15:00:00.000+0000",
        "LastModifiedDate": "2026-05-22T16:00:00.000+0000",
        "WhoId": "00Q5j000001leadX",
        "WhatId": "001RM00000abc",
        "OwnerId": "005RM00000owner",
        "Type": None,
        "CallType": None,
        "CallDurationInSeconds": None,
        "CallObject": None,
        "CallDisposition": None,
        "Description": "PHI MUST STAY RAW ONLY: patient reports pain",
    }
    base.update(overrides)
    return base


def _make_service(
    records: list[dict[str, Any]] | None = None,
    lead_link: SimpleNamespace | None = None,
    contact_link: SimpleNamespace | None = None,
) -> tuple[SfTaskIngestService, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(return_value={"records": records or [_task()]})
    service = SfTaskIngestService(session, sf_client)

    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=[
            "capture",
            "max_payload_watermark",
            "latest_payload_values",
            "get_object_schema",
            "list_latest_by_type_since",
        ]
    )
    service._ingest.capture = AsyncMock(  # type: ignore[attr-defined]
        return_value=SimpleNamespace(id=_RAW_EVENT_ID)
    )
    # First-run defaults: no watermark yet, nothing captured before.
    service._ingest.max_payload_watermark = AsyncMock(  # type: ignore[attr-defined]
        return_value=None
    )
    service._ingest.latest_payload_values = AsyncMock(  # type: ignore[attr-defined]
        return_value={}
    )
    # ENG-427: empty registry → dynamic projection falls back to static.
    service._ingest.get_object_schema = AsyncMock(  # type: ignore[attr-defined]
        return_value=[]
    )

    async def _find(*_args: object, source_kind: str, **_kwargs: object) -> Any:
        if source_kind == "lead":
            return lead_link
        if source_kind == "contact":
            return contact_link
        return None

    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(side_effect=_find)  # type: ignore[attr-defined]

    service._ops = MagicMock(spec=["create_followup"])  # type: ignore[attr-defined]
    service._ops.create_followup = AsyncMock(  # type: ignore[attr-defined]
        return_value=SimpleNamespace(id=_FOLLOWUP_ID)
    )

    service._interaction = MagicMock(  # type: ignore[attr-defined]
        spec=["create_event", "find_provider_event_by_external_id"]
    )
    service._interaction.find_provider_event_by_external_id = AsyncMock(  # type: ignore[attr-defined]
        return_value=None
    )
    service._interaction.create_event = AsyncMock(  # type: ignore[attr-defined]
        side_effect=lambda _tenant_id, payload: payload
    )
    return (
        service,
        sf_client,
        service._ingest,  # type: ignore[attr-defined]
        service._identity_repo,  # type: ignore[attr-defined]
        service._ops,  # type: ignore[attr-defined]
        service._interaction,  # type: ignore[attr-defined]
    )


def test_recent_soql_shape() -> None:
    query = build_recent_tasks_soql(
        since=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
        limit=123,
    )

    assert query.startswith("SELECT Id, Subject, Status, Priority, ActivityDate")
    assert "CallDurationInSeconds, CallObject, CallDisposition, Description" in query
    assert "FROM Task WHERE LastModifiedDate >= 2026-05-20T12:00:00Z" in query
    # ASC is load-bearing for the ENG-381 watermark cursor.
    assert "ORDER BY LastModifiedDate ASC LIMIT 123" in query


def test_classifier_covers_lanes() -> None:
    assert classify_task(_task(Subject="Follow up", Status="Open")).lane == "action"
    assert (
        classify_task(_task(Subject="Follow up", Status="Completed")).lane
        == "historical"
    )
    call = classify_task(_task(CallType="Outbound", Subject="Follow up"))
    assert call.lane == "call"
    assert call.direction == "outbound"
    assert classify_task(_task(CallType=None, Subject="Voicemail from lead")).lane == "call"
    assert classify_task(_task(Status="Deferred", Subject="Follow up")).lane == "action"
    assert classify_task(_task(Status="Cancelled", Subject="Admin task")).lane is None


@pytest.mark.asyncio
async def test_action_task_captures_raw_creates_followup_and_task_event() -> None:
    service, _, ingest, repo, ops, interaction = _make_service(
        records=[_task(Subject="Long clinical free text should not leak")],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.skipped_count == 0
    ingest.capture.assert_awaited_once()
    raw = ingest.capture.await_args.args[1]
    assert raw.event_type == "salesforce.task.upsert"
    assert raw.payload["Description"].startswith("PHI MUST STAY RAW ONLY")
    repo.find_source_link.assert_awaited_once()

    ops.create_followup.assert_awaited_once()
    followup = ops.create_followup.await_args.args[1]
    assert followup.person_uid == _PERSON_UID
    assert followup.title == "Salesforce follow-up task"
    assert followup.description is None

    interaction.create_event.assert_awaited_once()
    event = interaction.create_event.await_args.args[1]
    assert event.kind == "task_created"
    assert event.projection_ref_type == "ops_followup_task"
    assert event.projection_ref_id == _FOLLOWUP_ID
    assert event.data_class == "operational"
    assert event.review_status == "auto"
    assert "clinical free text" not in event.summary
    assert "Description" not in event.payload
    assert "Subject" not in event.payload


@pytest.mark.asyncio
async def test_completed_task_emits_task_completed_without_followup() -> None:
    service, _, ingest, _, ops, interaction = _make_service(
        records=[_task(Status="Completed", Subject="Completed admin note")],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()
    ops.create_followup.assert_not_awaited()
    interaction.create_event.assert_awaited_once()
    event = interaction.create_event.await_args.args[1]
    assert event.kind == "task_completed"
    assert event.projection_ref_type is None
    assert event.projection_ref_id is None


@pytest.mark.asyncio
async def test_call_task_emits_logged_and_reference_events() -> None:
    record = _task(
        Status="Completed",
        Subject="Outbound Call with sensitive details",
        CallType="Outbound",
        CallDurationInSeconds="95",
        CallDisposition="Connected",
        CallObject="https://recordings.example.test/calls/abc123",
    )
    service, _, _, _, ops, interaction = _make_service(
        records=[record],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.imported_count == 1
    ops.create_followup.assert_not_awaited()
    assert interaction.create_event.await_count == 2
    logged = interaction.create_event.await_args_list[0].args[1]
    reference = interaction.create_event.await_args_list[1].args[1]
    assert logged.kind == "call_logged"
    assert logged.payload["call_duration_seconds"] == 95
    assert logged.payload["call_disposition"] == "Connected"
    assert logged.payload["direction"] == "outbound"
    assert "sensitive details" not in logged.summary
    assert "Subject" not in logged.payload

    assert reference.kind == "call_reference_found"
    assert reference.data_class == "call_recording_ref"
    assert reference.review_status == "pending_review"
    assert reference.payload["reference_url"] == "https://recordings.example.test/calls/abc123"
    assert reference.payload["data_class"] == "call_recording_ref"
    assert reference.payload["review_status"] == "pending_review"


@pytest.mark.asyncio
async def test_sofia_call_task_parses_safe_metadata_from_description() -> None:
    record = _task(
        Status="Completed",
        Subject="Sofia AI Call - unqualified",
        CallType=None,
        CallDurationInSeconds=None,
        CallObject=None,
        Description=(
            "Agent: Sofia AI\n"
            "Date: 4/27/2026, 1:26:32 PM\n"
            "Patient: Larry Jensen Unknown\n"
            "Phone: +19169569183\n"
            "Outcome: unqualified\n"
            "Duration: 2 min\n\n"
            "Call Recording: https://storage.vapi.ai/call.wav\n\n"
            "Full Transcript:\n"
            "AI: sensitive transcript must stay raw\n"
        ),
    )
    service, _, _, _, _, interaction = _make_service(
        records=[record],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=45)

    assert result.imported_count == 1
    assert interaction.create_event.await_count == 2
    logged = interaction.create_event.await_args_list[0].args[1]
    reference = interaction.create_event.await_args_list[1].args[1]
    assert logged.kind == "call_logged"
    assert logged.payload["agent"] == "Sofia AI"
    assert logged.payload["call_outcome"] == "unqualified"
    assert logged.payload["duration_label"] == "2 min"
    assert logged.payload["call_duration_seconds"] == 120
    assert "Patient" not in logged.payload
    assert "Phone" not in logged.payload
    assert "transcript" not in str(logged.payload).lower()
    assert reference.payload["reference_url"] == "https://storage.vapi.ai/call.wav"


@pytest.mark.asyncio
async def test_unresolved_who_id_captures_raw_and_skips_projection() -> None:
    service, _, ingest, repo, ops, interaction = _make_service(
        lead_link=None,
        contact_link=None,
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.skipped_count == 1
    ingest.capture.assert_awaited_once()
    assert repo.find_source_link.await_count == 2
    ops.create_followup.assert_not_awaited()
    interaction.create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_reimport_existing_action_task_does_not_duplicate_rows() -> None:
    service, _, ingest, _, ops, interaction = _make_service(
        records=[_task(Subject="Follow up")],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )
    existing = SimpleNamespace(id=uuid.uuid4(), projection_ref_id=_FOLLOWUP_ID)
    interaction.find_provider_event_by_external_id = AsyncMock(return_value=existing)

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()
    ops.create_followup.assert_not_awaited()
    interaction.create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_rejects_invalid_bounds() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_tasks(_TENANT_ID, days=0)
    with pytest.raises(ValidationError):
        await service.import_recent_tasks(_TENANT_ID, limit=0)
    with pytest.raises(ValidationError):
        await service.import_all_since(_TENANT_ID, datetime.now(UTC), batch_size=0)


@pytest.mark.asyncio
async def test_capture_guard_skips_row_with_unchanged_stamp() -> None:
    """ENG-381: a row whose LastModifiedDate is already captured is a
    healthy overlap re-read — no raw write, no downstream processing."""
    task = _task()
    service, _, ingest, _, ops, interaction = _make_service(
        records=[task],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )
    ingest.latest_payload_values = AsyncMock(
        return_value={task["Id"]: task["LastModifiedDate"]}
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    assert result.skipped_count == 0
    ingest.capture.assert_not_awaited()
    ops.create_followup.assert_not_awaited()
    interaction.create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_capture_guard_captures_row_with_newer_stamp() -> None:
    """A moved provider stamp means a real change — the row is captured."""
    task = _task()
    service, _, ingest, _, _, _ = _make_service(
        records=[task],
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )
    ingest.latest_payload_values = AsyncMock(
        return_value={task["Id"]: "2026-05-01T00:00:00.000+0000"}
    )

    result = await service.import_recent_tasks(_TENANT_ID, days=7)

    assert result.unchanged_count == 0
    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_recent_pull_resumes_from_watermark() -> None:
    """ENG-381: the recent pull queries from the stored watermark, not
    from the full fixed window, when a watermark exists."""
    service, sf, ingest, *_ = _make_service(
        records=[], lead_link=SimpleNamespace(person_uid=_PERSON_UID)
    )
    ingest.max_payload_watermark = AsyncMock(
        return_value="2026-06-01T12:00:00.000+0000"
    )

    await service.import_recent_tasks(_TENANT_ID, days=7)

    ingest.max_payload_watermark.assert_awaited_once()
    query = sf.soql.await_args.args[0]
    # resume_modified_since subtracts the 10-minute overlap window.
    assert "LastModifiedDate >= 2026-06-01T11:50:00Z" in query


@pytest.mark.asyncio
async def test_reproject_emits_event_for_now_linked_task() -> None:
    """ENG-462: a task stranded while its lead was unlinked projects on
    reconciliation once the link exists — from raw, no Salesforce call."""
    service, sf_client, ingest, _repo, _ops, interaction = _make_service(
        lead_link=SimpleNamespace(person_uid=_PERSON_UID),
    )
    ingest.list_latest_by_type_since = AsyncMock(  # type: ignore[attr-defined]
        return_value=[(_RAW_EVENT_ID, _task(Subject="Follow up", Status="Open"))]
    )

    result = await service.reproject_tasks_from_raw(
        _TENANT_ID, since=datetime(2026, 5, 1, tzinfo=UTC)
    )

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.queried_count == 1
    # Reconciliation reads stored raw — never Salesforce, never re-captures.
    sf_client.soql.assert_not_awaited()
    ingest.capture.assert_not_awaited()
    interaction.create_event.assert_awaited()
    event = interaction.create_event.await_args.args[1]
    assert event.kind == "task_created"


@pytest.mark.asyncio
async def test_reproject_skips_still_unlinked_task() -> None:
    """A task whose WhoId still resolves to no person stays unprojected."""
    service, _sf, ingest, _repo, _ops, interaction = _make_service(
        lead_link=None,
        contact_link=None,
    )
    ingest.list_latest_by_type_since = AsyncMock(  # type: ignore[attr-defined]
        return_value=[(_RAW_EVENT_ID, _task(Status="Open"))]
    )

    result = await service.reproject_tasks_from_raw(
        _TENANT_ID, since=datetime(2026, 5, 1, tzinfo=UTC)
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1
    interaction.create_event.assert_not_awaited()
