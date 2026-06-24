"""Unit tests for ``CareStackPatientIngestService``."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.identity.schemas import MatchHintIn
from packages.ingest.carestack_patient_service import CareStackPatientIngestService
from packages.ingest.schemas import NormalizedPersonHintIn, RawEventIn

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _patient(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": 123,
        "firstName": "Jane",
        "lastName": "Doe",
        "email": "jane@example.com",
        "mobile": "(555) 123-4567",
        "dob": "1980-01-01",
        "ssn": "111-11-1111",
        "clinicalNotes": "never surface this outside raw_event",
        "defaultLocationId": 10029,
        "lastUpdatedOn": "2026-05-19T12:30:00Z",
        "status": 1,
    }
    base.update(overrides)
    return base


def _make_service(
    body: dict[str, Any] | None = None,
) -> tuple[CareStackPatientIngestService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    # ENG-340: per-patient ingest now runs inside ``session.begin_nested()``;
    # make it a working async context manager for the mock session.
    _nested = MagicMock()
    _nested.__aenter__ = AsyncMock(return_value=None)
    _nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=_nested)
    cs_client = MagicMock()
    cs_client.list_patients_modified_since = AsyncMock(
        return_value=body or {"patients": [_patient()], "continueToken": None}
    )
    service = CareStackPatientIngestService(session, cs_client)
    service._ingest = MagicMock(
        spec=[
            "capture",
            "capture_normalized_person_hint",
            "max_payload_watermark",
            "latest_payload_values",
        ]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    # First-run defaults: no watermark yet, nothing captured before.
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    service._ingest.capture_normalized_person_hint = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            source_system="carestack",
            source_instance="carestack-main",
            source_kind="patient",
            source_id="123",
            given_name="Jane",
            family_name="Doe",
            display_name="Jane Doe",
            email_normalized="jane@example.com",
            phone_normalized="5551234567",
            quality_flags={},
            meta={},
        )
    )
    service._identity = MagicMock(spec=["resolve_or_create_from_hint"])
    service._identity.resolve_or_create_from_hint = AsyncMock(
        return_value=SimpleNamespace(person_uid=uuid.uuid4(), was_new_person=True)
    )
    return service, cs_client, service._ingest, service._identity


@pytest.mark.asyncio
async def test_import_recent_patients_captures_raw_then_hint_then_identity() -> None:
    patient = _patient()
    service, cs_client, ingest, identity = _make_service(
        {"patients": [patient], "continueToken": None}
    )
    calls: list[str] = []
    raw_event_id = uuid.uuid4()

    async def capture(*_args: object) -> SimpleNamespace:
        calls.append("raw")
        return SimpleNamespace(id=raw_event_id, received_at=datetime.now(UTC))

    async def capture_hint(*_args: object) -> SimpleNamespace:
        calls.append("hint")
        return SimpleNamespace(
            id=uuid.uuid4(),
            source_system="carestack",
            source_instance="carestack-main",
            source_kind="patient",
            source_id="123",
            given_name="Jane",
            family_name="Doe",
            display_name="Jane Doe",
            email_normalized="jane@example.com",
            phone_normalized="5551234567",
            quality_flags={},
            meta={},
        )

    async def resolve(*_args: object) -> SimpleNamespace:
        calls.append("identity")
        return SimpleNamespace(person_uid=uuid.uuid4(), was_new_person=True)

    ingest.capture.side_effect = capture
    ingest.capture_normalized_person_hint.side_effect = capture_hint
    identity.resolve_or_create_from_hint.side_effect = resolve

    out = await service.import_recent_patients(_TENANT_ID, days=7, page_size=50)

    assert out.imported_count == 1
    assert out.skipped_count == 0
    assert calls == ["raw", "hint", "identity"]
    cs_client.list_patients_modified_since.assert_awaited_once()

    raw_payload = ingest.capture.await_args.args[1]
    assert isinstance(raw_payload, RawEventIn)
    assert raw_payload.source == "carestack"
    assert raw_payload.event_type == "carestack.patient.upsert"
    assert raw_payload.external_id == "123"
    assert raw_payload.payload == patient
    assert raw_payload.payload["dob"] == "1980-01-01"
    assert raw_payload.payload["clinicalNotes"] == "never surface this outside raw_event"

    hint_payload = ingest.capture_normalized_person_hint.await_args.args[1]
    assert isinstance(hint_payload, NormalizedPersonHintIn)
    assert hint_payload.raw_event_id == raw_event_id
    assert hint_payload.source_system == "carestack"
    assert hint_payload.source_instance == "carestack-main"
    assert hint_payload.source_kind == "patient"
    assert hint_payload.source_id == "123"
    assert hint_payload.given_name == "Jane"
    assert hint_payload.family_name == "Doe"
    assert hint_payload.email == "jane@example.com"
    assert hint_payload.phone == "(555) 123-4567"
    assert hint_payload.meta == {}
    assert hint_payload.quality_flags == {}

    match_hint = identity.resolve_or_create_from_hint.await_args.args[1]
    assert isinstance(match_hint, MatchHintIn)
    assert match_hint.source_system == "carestack"
    assert match_hint.source_instance == "carestack-main"
    assert match_hint.source_kind == "patient"
    assert match_hint.source_id == "123"


@pytest.mark.asyncio
async def test_import_recent_patients_skips_rows_without_patient_id() -> None:
    service, _cs_client, ingest, identity = _make_service(
        {"patients": [_patient(id=None, patientId=None, PatientId=None)]}
    )

    out = await service.import_recent_patients(_TENANT_ID)

    assert out.imported_count == 0
    assert out.skipped_count == 1
    ingest.capture.assert_not_awaited()
    identity.resolve_or_create_from_hint.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_recent_patients_follows_continue_token_with_page_limit() -> None:
    service, cs_client, _ingest, _identity = _make_service()
    cs_client.list_patients_modified_since.side_effect = [
        {"patients": [_patient(id=1)], "continueToken": "next-page"},
        {"patients": [_patient(id=2)], "continueToken": "ignored-page"},
    ]

    out = await service.import_recent_patients(
        _TENANT_ID,
        page_size=10,
        max_pages=2,
    )

    assert out.imported_count == 2
    assert out.page_count == 2
    assert out.next_continue_token == "ignored-page"
    assert cs_client.list_patients_modified_since.await_count == 2
    second_call = cs_client.list_patients_modified_since.await_args_list[1]
    assert second_call.kwargs["continue_token"] == "next-page"


# ----- ENG-309: DOB / SSN propagation into MatchHintIn ---------------------


@pytest.mark.asyncio
async def test_patient_with_dob_and_ssn_passes_them_into_match_hint() -> None:
    service, _cs_client, _ingest, identity = _make_service(
        {
            "patients": [
                _patient(
                    id=1460847,
                    dob="1968-04-19",
                    ssn="623-35-9385",
                )
            ]
        }
    )

    await service.import_recent_patients(_TENANT_ID, days=7, page_size=50)

    match_hint = identity.resolve_or_create_from_hint.await_args.args[1]
    assert isinstance(match_hint, MatchHintIn)
    assert match_hint.dob == date(1968, 4, 19)
    assert match_hint.ssn == "623359385"  # dashes stripped


@pytest.mark.asyncio
async def test_patient_with_iso_timestamp_dob_parses_to_date() -> None:
    service, _cs_client, _ingest, identity = _make_service(
        {"patients": [_patient(dob="1968-04-19T00:00:00", ssn=None)]}
    )

    await service.import_recent_patients(_TENANT_ID, days=7, page_size=50)

    match_hint = identity.resolve_or_create_from_hint.await_args.args[1]
    assert match_hint.dob == date(1968, 4, 19)
    assert match_hint.ssn is None


@pytest.mark.asyncio
async def test_patient_without_dob_or_ssn_passes_none() -> None:
    service, _cs_client, _ingest, identity = _make_service(
        {"patients": [_patient(dob=None, ssn=None)]}
    )

    await service.import_recent_patients(_TENANT_ID, days=7, page_size=50)

    match_hint = identity.resolve_or_create_from_hint.await_args.args[1]
    assert match_hint.dob is None
    assert match_hint.ssn is None


@pytest.mark.asyncio
async def test_patient_with_malformed_dob_passes_none_and_does_not_raise() -> None:
    service, _cs_client, _ingest, identity = _make_service(
        {"patients": [_patient(dob="not-a-date", ssn="   ")]}
    )

    out = await service.import_recent_patients(_TENANT_ID, days=7, page_size=50)

    # Malformed values are silently dropped; ingest still imports the row.
    assert out.imported_count == 1
    match_hint = identity.resolve_or_create_from_hint.await_args.args[1]
    assert match_hint.dob is None
    assert match_hint.ssn is None


@pytest.mark.asyncio
async def test_one_failing_patient_does_not_abort_the_tick(
    monkeypatch: Any,
) -> None:
    """ENG-340: a single bad patient (e.g. a shared-phone constraint
    violation) is isolated by a SAVEPOINT and skipped; the remaining patients
    in the tick still import instead of the whole CareStack pull aborting."""
    service, _cs_client, _ingest, _identity = _make_service(
        body={
            "patients": [_patient(id=1), _patient(id=2), _patient(id=3)],
            "continueToken": None,
        }
    )

    real_capture = service._capture_patient

    async def flaky_capture(
        tenant_id: TenantId, patient: dict[str, Any], patient_id: str
    ) -> None:
        if patient_id == "2":
            raise RuntimeError("duplicate key value violates unique constraint")
        await real_capture(tenant_id, patient, patient_id)

    monkeypatch.setattr(service, "_capture_patient", flaky_capture)

    out = await service.import_recent_patients(_TENANT_ID, days=1)

    assert out.imported_count == 2  # patients 1 and 3
    assert out.skipped_count == 1  # patient 2 isolated and skipped
