"""Service-level tests for ``IngestService.capture_normalized_person_hint``.

Pure-Python validation paths run with mock sessions. Real-DB integration
(unique-constraint collisions, FK behavior) lands when a Postgres test
container is wired in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ingest.models import NormalizedPersonHint, RawEvent
from packages.ingest.schemas import NormalizedPersonHintIn, RawEventIn
from packages.ingest.service import IngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_service() -> tuple[IngestService, MagicMock]:
    session = MagicMock()
    service = IngestService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._repo.add_normalized_person_hint = AsyncMock(
        side_effect=lambda h: h
    )
    return service, service._repo  # type: ignore[attr-defined]


def _payload(**overrides: object) -> NormalizedPersonHintIn:
    base: dict[str, object] = {
        "raw_event_id": uuid.uuid4(),
        "source_system": "salesforce",
        "source_kind": "lead",
        "source_id": "00Q123",
        "observed_at": datetime(2026, 5, 18, 18, 0, tzinfo=UTC),
        "given_name": "Jane",
        "family_name": "Doe",
        "display_name": "Jane Doe",
        "email": "Jane@Example.COM",
        "phone": "+1 (415) 555-1234",
        "payload_sha256": None,
        "quality_flags": {},
        "meta": {},
    }
    base.update(overrides)
    return NormalizedPersonHintIn(**base)


# --- source_system / source_kind validation ---


@pytest.mark.asyncio
async def test_capture_hint_rejects_unknown_source_system() -> None:
    service, _ = _make_service()
    payload = _payload(source_system="hubspot")
    with pytest.raises(ValidationError) as excinfo:
        await service.capture_normalized_person_hint(_TENANT_ID, payload)
    assert "unknown source_system" in str(excinfo.value)


@pytest.mark.asyncio
async def test_capture_hint_rejects_unknown_source_kind() -> None:
    service, _ = _make_service()
    payload = _payload(source_kind="opportunity")
    with pytest.raises(ValidationError) as excinfo:
        await service.capture_normalized_person_hint(_TENANT_ID, payload)
    assert "unknown source_kind" in str(excinfo.value)


# --- email/phone normalisation ---


@pytest.mark.asyncio
async def test_capture_hint_normalises_email_and_phone() -> None:
    service, repo = _make_service()
    captured: dict[str, NormalizedPersonHint] = {}

    async def _capture(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured["row"] = row
        return row

    repo.add_normalized_person_hint = AsyncMock(side_effect=_capture)

    await service.capture_normalized_person_hint(_TENANT_ID, _payload())

    row = captured["row"]
    assert row.email_normalized == "jane@example.com"
    assert row.phone_normalized == "+14155551234"
    assert row.quality_flags == {}


@pytest.mark.asyncio
async def test_capture_hint_records_invalid_email_as_quality_flag() -> None:
    service, repo = _make_service()
    captured: dict[str, NormalizedPersonHint] = {}

    async def _capture(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured["row"] = row
        return row

    repo.add_normalized_person_hint = AsyncMock(side_effect=_capture)

    payload = _payload(email="not-an-email")
    await service.capture_normalized_person_hint(_TENANT_ID, payload)

    row = captured["row"]
    assert row.email_normalized is None
    assert row.quality_flags.get("invalid_email") is True


@pytest.mark.asyncio
async def test_capture_hint_records_invalid_phone_as_quality_flag() -> None:
    service, repo = _make_service()
    captured: dict[str, NormalizedPersonHint] = {}

    async def _capture(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured["row"] = row
        return row

    repo.add_normalized_person_hint = AsyncMock(side_effect=_capture)

    payload = _payload(phone="123")  # < 7 digits
    await service.capture_normalized_person_hint(_TENANT_ID, payload)

    row = captured["row"]
    assert row.phone_normalized is None
    assert row.quality_flags.get("invalid_phone") is True


@pytest.mark.asyncio
async def test_capture_hint_records_missing_identifiers_as_quality_flags() -> None:
    service, repo = _make_service()
    captured: dict[str, NormalizedPersonHint] = {}

    async def _capture(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured["row"] = row
        return row

    repo.add_normalized_person_hint = AsyncMock(side_effect=_capture)

    payload = _payload(
        email=None,
        phone=None,
        given_name=None,
        family_name=None,
        display_name=None,
    )
    await service.capture_normalized_person_hint(_TENANT_ID, payload)

    row = captured["row"]
    assert row.email_normalized is None
    assert row.phone_normalized is None
    assert row.quality_flags == {
        "missing_email": True,
        "missing_phone": True,
        "missing_name": True,
    }


# --- PHI / raw-payload guard ---


@pytest.mark.asyncio
async def test_capture_hint_rejects_phi_keys_in_meta() -> None:
    service, _ = _make_service()
    payload = _payload(meta={"dob": "1990-01-01"})
    with pytest.raises(ValidationError) as excinfo:
        await service.capture_normalized_person_hint(_TENANT_ID, payload)
    assert excinfo.value.details["field"] == "meta"


@pytest.mark.asyncio
async def test_capture_hint_rejects_raw_payload_in_quality_flags() -> None:
    service, _ = _make_service()
    payload = _payload(quality_flags={"raw_payload": {"sf_lead": "..."}})
    with pytest.raises(ValidationError) as excinfo:
        await service.capture_normalized_person_hint(_TENANT_ID, payload)
    assert excinfo.value.details["field"] == "quality_flags"


@pytest.mark.asyncio
async def test_capture_hint_rejects_nested_phi_keys() -> None:
    service, _ = _make_service()
    payload = _payload(meta={"parser": {"clinical_notes": "..."}})
    with pytest.raises(ValidationError) as excinfo:
        await service.capture_normalized_person_hint(_TENANT_ID, payload)
    assert excinfo.value.details["field"] == "meta"
    assert excinfo.value.details["keys"] == ["parser.clinical_notes"]


# --- hint_hash determinism ---


@pytest.mark.asyncio
async def test_capture_hint_hash_is_stable_across_runs() -> None:
    """Same inputs → same ``hint_hash`` regardless of call order."""
    service_a, repo_a = _make_service()
    service_b, repo_b = _make_service()
    captured_a: dict[str, NormalizedPersonHint] = {}
    captured_b: dict[str, NormalizedPersonHint] = {}

    async def _capture_a(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured_a["row"] = row
        return row

    async def _capture_b(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured_b["row"] = row
        return row

    repo_a.add_normalized_person_hint = AsyncMock(side_effect=_capture_a)
    repo_b.add_normalized_person_hint = AsyncMock(side_effect=_capture_b)

    raw_event_id = uuid.uuid4()
    payload = _payload(raw_event_id=raw_event_id)
    await service_a.capture_normalized_person_hint(_TENANT_ID, payload)
    await service_b.capture_normalized_person_hint(_TENANT_ID, payload)

    assert captured_a["row"].hint_hash == captured_b["row"].hint_hash
    assert len(captured_a["row"].hint_hash) == 64  # sha256 hex digest


@pytest.mark.asyncio
async def test_capture_hint_hash_differs_when_identifiers_differ() -> None:
    service, repo = _make_service()
    captured: list[NormalizedPersonHint] = []

    async def _capture(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured.append(row)
        return row

    repo.add_normalized_person_hint = AsyncMock(side_effect=_capture)

    await service.capture_normalized_person_hint(
        _TENANT_ID, _payload(email="a@example.com")
    )
    await service.capture_normalized_person_hint(
        _TENANT_ID, _payload(email="b@example.com")
    )

    assert captured[0].hint_hash != captured[1].hint_hash


# --- persistence happy path ---


@pytest.mark.asyncio
async def test_capture_hint_persists_full_row_with_tenant_and_pointers_null() -> None:
    service, repo = _make_service()
    captured: dict[str, NormalizedPersonHint] = {}

    async def _capture(row: NormalizedPersonHint) -> NormalizedPersonHint:
        captured["row"] = row
        return row

    repo.add_normalized_person_hint = AsyncMock(side_effect=_capture)

    raw_event_id = uuid.uuid4()
    payload = _payload(
        raw_event_id=raw_event_id,
        payload_sha256="a" * 64,
        meta={"parser": "sf_lead_v1"},
    )
    await service.capture_normalized_person_hint(_TENANT_ID, payload)

    row = captured["row"]
    assert row.tenant_id == _TENANT_ID
    assert row.raw_event_id == raw_event_id
    assert row.source_system == "salesforce"
    assert row.source_kind == "lead"
    assert row.source_id == "00Q123"
    assert row.observed_at == payload.observed_at
    assert row.given_name == "Jane"
    assert row.family_name == "Doe"
    assert row.display_name == "Jane Doe"
    assert row.email_normalized == "jane@example.com"
    assert row.phone_normalized == "+14155551234"
    assert row.payload_sha256 == "a" * 64
    assert row.meta == {"parser": "sf_lead_v1"}
    # Match-policy writes these later; they MUST start NULL.
    assert row.person_uid is None
    assert row.source_link_id is None


# --- capture() does not touch hint state ---


@pytest.mark.asyncio
async def test_raw_event_capture_does_not_mutate_payload_or_create_hint() -> None:
    """The existing ``capture`` path stays unchanged.

    Captures the verbatim raw payload; does NOT extract a normalised
    hint (that is a deliberate, separate service call).
    """
    session = MagicMock()
    service = IngestService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]

    captured_event: dict[str, RawEvent] = {}

    async def _add(event: RawEvent) -> RawEvent:
        captured_event["row"] = event
        return event

    service._repo.add = AsyncMock(side_effect=_add)  # type: ignore[attr-defined]
    service._repo.add_normalized_person_hint = AsyncMock()  # type: ignore[attr-defined]

    raw_payload = {"FirstName": "Jane", "Email": "Jane@Example.COM"}
    raw_event = RawEventIn(
        source="salesforce",
        event_type="lead",
        external_id="00Q123",
        received_at=datetime(2026, 5, 18, 18, 0, tzinfo=UTC),
        payload=raw_payload,
    )

    await service.capture(_TENANT_ID, raw_event)

    assert captured_event["row"].payload == raw_payload  # verbatim
    service._repo.add_normalized_person_hint.assert_not_awaited()  # type: ignore[attr-defined]
