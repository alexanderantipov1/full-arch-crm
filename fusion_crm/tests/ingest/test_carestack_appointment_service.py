"""Unit tests for ``CareStackAppointmentIngestService`` (ENG-219).

Cover the patient-not-linked skip path, the status mapping, and the
happy upsert path. The full integration with ``IdentityService`` /
``OpsService`` is exercised in the API HTTP test; here we mock both.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ingest.carestack_appointment_service import (
    CareStackAppointmentIngestService,
    _appointment_location_id,
    _map_status,
    _source_status,
)
from packages.ops.models import ConsultationKind, ConsultationStatus
from packages.ops.schemas import ConsultationOut, ConsultationUpsertResult

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LOCATION_ID = uuid.uuid4()
_SCHEDULED_AT = datetime(2026, 6, 1, 14, 0, tzinfo=UTC)


def _appointment(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 7821,
        "patientId": 9985,
        "startDateTime": "2026-06-01T14:00:00Z",
        "duration": 30,
        "status": "Scheduled",
        "locationId": 10029,
        "providerIds": [1, 2],
        "providerName": "Dr. Smith",
        "notes": "must NEVER reach ops.consultation — PHI",
        "lastUpdatedOn": "2026-05-22T00:00:00Z",
    }
    base.update(overrides)
    return base


def _make_service(
    body: dict[str, Any] | None = None,
    source_link: SimpleNamespace | None = None,
) -> tuple[
    CareStackAppointmentIngestService,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    session = MagicMock()
    cs_client = MagicMock()
    cs_client.list_appointments_modified_since = AsyncMock(
        return_value=body
        or {"appointments": [_appointment()], "continueToken": None}
    )
    service = CareStackAppointmentIngestService(session, cs_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["capture", "max_payload_watermark", "latest_payload_values"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    # First-run defaults: no watermark yet, nothing captured before.
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(
        return_value=source_link
        if source_link is not None
        else SimpleNamespace(person_uid=_PERSON_UID)
    )
    service._ops = MagicMock(spec=["upsert_consultation_from_hint"])  # type: ignore[attr-defined]
    service._ops.upsert_consultation_from_hint = AsyncMock(
        return_value=_upsert_result()
    )
    service._interaction = MagicMock(spec=["create_event"])  # type: ignore[attr-defined]
    service._interaction.create_event = AsyncMock()  # type: ignore[attr-defined]
    service._locations = MagicMock(spec=["find_by_carestack_id"])  # type: ignore[attr-defined]
    service._locations.find_by_carestack_id = AsyncMock(  # type: ignore[attr-defined]
        return_value=SimpleNamespace(id=_LOCATION_ID)
    )
    return (
        service,
        cs_client,
        service._ingest,  # type: ignore[attr-defined]
        service._identity_repo,  # type: ignore[attr-defined]
        service._ops,  # type: ignore[attr-defined]
        service._locations,  # type: ignore[attr-defined]
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
            source_provider="carestack",
            source_instance="carestack-main",
            external_id="7821",
            scheduled_at=_SCHEDULED_AT,
            duration_minutes=30,
            status=status,
            consultation_kind=ConsultationKind.OTHER,
            location_id=_LOCATION_ID,
            provider_clinician_name="Dr. Smith",
            raw_event_id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        was_created=was_created,
        was_changed=was_changed,
        was_status_change=was_status_change,
        was_scheduled_at_change=was_scheduled_at_change,
    )


# ----------------------------------------------------- happy path + identity


@pytest.mark.asyncio
async def test_import_captures_raw_then_resolves_then_upserts() -> None:
    service, _, ingest, identity_repo, ops, locations = _make_service()
    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.page_count == 1
    assert result.next_continue_token is None

    ingest.capture.assert_awaited_once()
    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.source == "carestack"
    assert raw_call.event_type == "carestack.appointment.upsert"
    assert raw_call.external_id == "7821"

    identity_repo.find_source_link.assert_awaited_once_with(
        _TENANT_ID,
        source_system="carestack",
        source_instance="carestack-main",
        source_kind="patient",
        source_id="9985",
    )

    ops.upsert_consultation_from_hint.assert_awaited_once()
    payload = ops.upsert_consultation_from_hint.await_args.args[1]
    assert payload.person_uid == _PERSON_UID
    assert payload.source_provider == "carestack"
    assert payload.source_instance == "carestack-main"
    assert payload.external_id == "7821"
    assert payload.duration_minutes == 30
    assert payload.status == ConsultationStatus.SCHEDULED
    # ENG-487: verbatim provider status threaded alongside the bucket.
    assert payload.source_status == "Scheduled"
    assert payload.location_id == _LOCATION_ID
    assert payload.provider_clinician_name == "Dr. Smith"
    # PHI must not have leaked into the payload.
    assert not hasattr(payload, "notes")
    locations.find_by_carestack_id.assert_awaited_once_with(_TENANT_ID, 10029)


def test_source_status_preserves_confirmed_that_bucket_collapses() -> None:
    # ENG-487: the bucketed _map_status collapses "Confirmed" into SCHEDULED;
    # _source_status keeps the verbatim signal the T-15m reminder needs.
    assert _map_status("Confirmed") == ConsultationStatus.SCHEDULED
    assert _source_status("Confirmed") == "Confirmed"
    assert _source_status("  Ready to Seat ") == "Ready to Seat"
    assert _source_status("") is None
    assert _source_status(None) is None
    assert _source_status(123) is None


@pytest.mark.asyncio
async def test_first_import_emits_consultation_scheduled_event() -> None:
    raw_event_id = uuid.uuid4()
    service, _, ingest, _, ops, _ = _make_service()
    upsert = _upsert_result()
    ops.upsert_consultation_from_hint.return_value = upsert
    ingest.capture.return_value = SimpleNamespace(
        id=raw_event_id, received_at=datetime.now(UTC)
    )

    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_awaited_once()
    await_args = create_event.await_args
    assert await_args is not None
    event = await_args.args[1]
    assert event.kind == "consultation_scheduled"
    assert event.source_provider == "carestack"
    assert event.source_kind == "carestack_appointment"
    assert event.source_external_id == "7821"
    assert event.source_event_id == raw_event_id
    assert event.projection_ref_type == "ops_consultation"
    assert event.projection_ref_id == upsert.consultation.id
    assert event.data_class == "operational"
    assert event.review_status == "auto"
    assert event.payload == {}
    assert "PHI" not in event.summary
    assert "notes" not in event.summary


@pytest.mark.asyncio
async def test_status_change_emits_consultation_cancelled_event() -> None:
    service, _, _, _, ops, _ = _make_service()
    ops.upsert_consultation_from_hint.return_value = _upsert_result(
        status=ConsultationStatus.CANCELLED,
        was_created=False,
        was_changed=True,
        was_status_change=True,
        was_scheduled_at_change=False,
    )

    await service.import_recent_appointments(_TENANT_ID, days=7)

    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_awaited_once()
    await_args = create_event.await_args
    assert await_args is not None
    event = await_args.args[1]
    assert event.kind == "consultation_cancelled"
    assert event.payload == {}


@pytest.mark.asyncio
async def test_reschedule_change_emits_consultation_rescheduled_event() -> None:
    service, _, _, _, ops, _ = _make_service()
    ops.upsert_consultation_from_hint.return_value = _upsert_result(
        status=ConsultationStatus.SCHEDULED,
        was_created=False,
        was_changed=True,
        was_status_change=False,
        was_scheduled_at_change=True,
    )

    await service.import_recent_appointments(_TENANT_ID, days=7)

    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_awaited_once()
    await_args = create_event.await_args
    assert await_args is not None
    event = await_args.args[1]
    assert event.kind == "consultation_rescheduled"
    assert event.payload == {}


@pytest.mark.asyncio
async def test_reimport_without_change_emits_no_event() -> None:
    service, _, _, _, ops, _ = _make_service()
    ops.upsert_consultation_from_hint.return_value = _upsert_result(
        was_created=False,
        was_changed=False,
        was_status_change=False,
        was_scheduled_at_change=False,
    )

    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    create_event = cast(AsyncMock, service._interaction.create_event)  # type: ignore[attr-defined]
    create_event.assert_not_awaited()
    # ENG-329: an unchanged re-pull is a HEALTHY idempotent dedup, counted
    # as ``unchanged`` rather than ``skipped``/``imported``.
    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0


@pytest.mark.asyncio
async def test_import_skips_when_patient_not_linked() -> None:
    service, _, ingest, identity_repo, ops, _ = _make_service(source_link=None)
    # Override AsyncMock default — must return None for this branch.
    identity_repo.find_source_link = AsyncMock(return_value=None)

    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.skipped_count == 1
    # Raw event was captured even though we skipped — forensic audit trail.
    ingest.capture.assert_awaited_once()
    ops.upsert_consultation_from_hint.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_skips_when_no_scheduled_at() -> None:
    body = {
        "appointments": [_appointment(startDateTime=None, startTime=None, dateTime=None)],
        "continueToken": None,
    }
    service, _, _, _, ops, _ = _make_service(body=body)

    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.skipped_count == 1
    ops.upsert_consultation_from_hint.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_skips_when_appointment_id_missing() -> None:
    body = {
        "appointments": [_appointment(id=None)],
        "continueToken": None,
    }
    service, _, _, _, _, _ = _make_service(body=body)
    result = await service.import_recent_appointments(_TENANT_ID, days=7)
    assert result.imported_count == 0
    assert result.skipped_count == 1


@pytest.mark.asyncio
async def test_import_keeps_consultation_when_location_not_linked() -> None:
    service, _, _, _, ops, locations = _make_service()
    locations.find_by_carestack_id = AsyncMock(return_value=None)

    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    payload = ops.upsert_consultation_from_hint.await_args.args[1]
    assert payload.location_id is None


# ----------------------------------------------------- ENG-465 doctor mapping


@pytest.mark.asyncio
async def test_provider_id_resolves_to_clinician_name_and_is_stored() -> None:
    """ENG-465: ``providerIds[0]`` resolves to the clinician display name via
    the injected ``ActorNameResolver`` and is stored in
    ``provider_clinician_name`` (overriding any payload-carried name)."""
    service, _, _, _, ops, _ = _make_service()
    # Inject an actor-name resolver that maps provider id 1 → real doctor.
    resolver = MagicMock(spec=["resolve_actor_name"])
    resolver.resolve_actor_name = AsyncMock(return_value="Dr. André-David Kahwach")
    service._actor_names = resolver  # type: ignore[attr-defined]

    result = await service.import_recent_appointments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    # Resolver was asked for the carestack_provider_id of the FIRST provider.
    resolver.resolve_actor_name.assert_awaited_once_with(
        _TENANT_ID, "carestack_provider_id", "1"
    )
    payload = ops.upsert_consultation_from_hint.await_args.args[1]
    # The resolved actor name wins over the payload's "Dr. Smith".
    assert payload.provider_clinician_name == "Dr. André-David Kahwach"


@pytest.mark.asyncio
async def test_provider_name_falls_back_to_payload_when_resolver_misses() -> None:
    """A resolver miss (unknown provider id) falls back to the payload name."""
    service, _, _, _, ops, _ = _make_service()
    resolver = MagicMock(spec=["resolve_actor_name"])
    resolver.resolve_actor_name = AsyncMock(return_value=None)
    service._actor_names = resolver  # type: ignore[attr-defined]

    await service.import_recent_appointments(_TENANT_ID, days=7)

    payload = ops.upsert_consultation_from_hint.await_args.args[1]
    assert payload.provider_clinician_name == "Dr. Smith"


# ----------------------------------------------------- status mapping


def test_map_status_known_values() -> None:
    assert _map_status("Scheduled") == ConsultationStatus.SCHEDULED
    assert _map_status("Confirmed") == ConsultationStatus.SCHEDULED
    # Full Funnel v2 (ENG-480..483) treats a patient physically present in the
    # office as having "showed" → COMPLETED, even before they leave: "Checked
    # In" / "In Chair" / "In Operatory" / "Ready To Seat" / "Arrived".
    assert _map_status("Checked In") == ConsultationStatus.COMPLETED
    assert _map_status("CheckedIn") == ConsultationStatus.COMPLETED
    assert _map_status("In Chair") == ConsultationStatus.COMPLETED
    assert _map_status("Completed") == ConsultationStatus.COMPLETED
    # CareStack emits "Checked Out" after the visit happened — must be
    # COMPLETED, NOT scheduled (was a contract drift on ~65k rows).
    assert _map_status("Checked Out") == ConsultationStatus.COMPLETED
    assert _map_status("CheckedOut") == ConsultationStatus.COMPLETED
    assert _map_status("checked out") == ConsultationStatus.COMPLETED
    assert _map_status("Cancelled") == ConsultationStatus.CANCELLED
    assert _map_status("Canceled") == ConsultationStatus.CANCELLED  # US spelling
    assert _map_status("NoShow") == ConsultationStatus.NO_SHOW
    assert _map_status("No-Show") == ConsultationStatus.NO_SHOW
    assert _map_status("Rescheduled") == ConsultationStatus.RESCHEDULED


def test_map_status_unknown_falls_back_to_scheduled() -> None:
    # Contract-drift guard: unknown statuses default to SCHEDULED so we
    # never silently mislabel rows. (A `Contract drift:` warn log fires
    # alongside this fallback in real runs.)
    assert _map_status("FlossWaltzInProgress") == ConsultationStatus.SCHEDULED
    assert _map_status(None) == ConsultationStatus.SCHEDULED
    assert _map_status(42) == ConsultationStatus.SCHEDULED


def test_map_status_handles_case_and_whitespace() -> None:
    assert _map_status("  scheduled  ") == ConsultationStatus.SCHEDULED
    assert _map_status("no_show") == ConsultationStatus.NO_SHOW


def test_appointment_location_id_accepts_int_and_digit_string() -> None:
    assert _appointment_location_id({"locationId": 10029}) == 10029
    assert _appointment_location_id({"LocationId": "10029"}) == 10029
    assert _appointment_location_id({"locationId": "main"}) is None


# ----------------------------------------------------- validation


@pytest.mark.asyncio
async def test_import_rejects_invalid_days() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_appointments(_TENANT_ID, days=0)
    with pytest.raises(ValidationError):
        await service.import_recent_appointments(_TENANT_ID, days=400)


@pytest.mark.asyncio
async def test_import_rejects_invalid_page_size() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_appointments(_TENANT_ID, page_size=0)
    with pytest.raises(ValidationError):
        await service.import_recent_appointments(_TENANT_ID, page_size=600)


# ----------------------------------------------------- pagination + idempotency


@pytest.mark.asyncio
async def test_import_follows_continue_token_up_to_max_pages() -> None:
    page1 = {
        "appointments": [_appointment(id=1)],
        "continueToken": "next-page-token",
    }
    page2 = {
        "appointments": [_appointment(id=2)],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_appointments_modified_since = AsyncMock(side_effect=[page1, page2])

    result = await service.import_recent_appointments(
        _TENANT_ID, days=7, max_pages=2
    )

    assert result.imported_count == 2
    assert result.page_count == 2
    assert result.next_continue_token is None
    assert cs_client.list_appointments_modified_since.await_count == 2


@pytest.mark.asyncio
async def test_import_stops_at_max_pages_with_remaining_token() -> None:
    page1 = {
        "appointments": [_appointment(id=1)],
        "continueToken": "still-more",
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_appointments_modified_since = AsyncMock(return_value=page1)

    result = await service.import_recent_appointments(
        _TENANT_ID, days=7, max_pages=1
    )

    assert result.page_count == 1
    assert result.next_continue_token == "still-more"
