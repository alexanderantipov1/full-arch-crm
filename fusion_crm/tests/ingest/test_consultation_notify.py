"""Unit tests for the consultation.scheduled ingest-boundary wiring (ENG-457).

These assert the boundary CONTRACT without a DB:

* the helper derives dedupe_key / source_created_at / context correctly and
  emits ONLY on a genuinely-new consultation;
* notifier=None (backfill) is a no-op;
* the SF Event + CareStack Appointment ``import_recent_*`` paths thread a
  notifier through and call it once per created consult, but never call it on
  an update / no-op upsert.

The notifier is a mock satisfying ``ConsultationNotifier``; the full
rule→ledger→outbox path is covered by the real-Postgres test in
``tests/integrations/test_consultation_scheduled_emit.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.ingest.consultation_notify import (
    CONSULTATION_SCHEDULED_EVENT,
    emit_consultation_scheduled_notification,
)
from packages.ops.models import ConsultationKind, ConsultationStatus
from packages.ops.schemas import ConsultationOut, ConsultationUpsertResult

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_SCHEDULED_AT = datetime(2026, 6, 12, 14, 0, tzinfo=UTC)
_PROVIDER_CREATED_AT = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)


def _principal() -> Principal:
    return Principal(
        id=None, email=None, tenant_id=_TENANT_ID, roles=frozenset({Role.SYSTEM})
    )


def _upsert_result(
    *,
    consultation_id: uuid.UUID | None = None,
    was_created: bool = True,
    provider_created_at: datetime | None = _PROVIDER_CREATED_AT,
    status: ConsultationStatus = ConsultationStatus.SCHEDULED,
) -> ConsultationUpsertResult:
    return ConsultationUpsertResult(
        consultation=ConsultationOut(
            id=consultation_id or uuid.uuid4(),
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
            provider_created_at=provider_created_at,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        was_created=was_created,
        was_changed=was_created,
    )


# ------------------------------------------------------------- helper


@pytest.mark.asyncio
async def test_emit_on_created_passes_dedupe_key_and_cutoff() -> None:
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()
    consultation_id = uuid.uuid4()

    await emit_consultation_scheduled_notification(
        notifier,
        _TENANT_ID,
        _upsert_result(consultation_id=consultation_id),
        source_provider="carestack",
        principal=_principal(),
        person_name="Ghausuddin Nezami",
        person_phone="19254918047",
        doctor_name="Dr. André-David Kahwach",
        clinic_name="Fusion Dental Implants",
        owner_name="Olga Antipova",
    )

    notifier.emit.assert_awaited_once()
    call = notifier.emit.await_args
    assert call.args[0] == _TENANT_ID
    assert call.args[1] == CONSULTATION_SCHEDULED_EVENT
    context = call.args[2]
    # dedupe_key is the consultation id; cutoff signal is provider_created_at.
    assert call.kwargs["dedupe_key"] == str(consultation_id)
    assert call.kwargs["source_created_at"] == _PROVIDER_CREATED_AT
    assert call.kwargs["person_uid"] == _PERSON_UID
    # Categorical context + the ENG-460 real name + the ENG-465 enrichment
    # (doctor / clinic / owner / phone / readable when). ENG-465b dropped Kind +
    # Duration; ENG-465c dropped Confirmation (premature at booking time).
    assert context == {
        "provider": "carestack",
        "status": "scheduled",
        "scheduled_at": _SCHEDULED_AT.isoformat(),
        "scheduled_when": "Jun 12, 2026 2:00 PM UTC",
        "name": "Ghausuddin Nezami",
        "phone": "19254918047",
        "doctor": "Dr. André-David Kahwach",
        "clinic": "Fusion Dental Implants",
        "owner": "Olga Antipova",
    }


@pytest.mark.asyncio
async def test_emit_without_name_carries_none() -> None:
    """ENG-460: ``person_name`` defaults to None (renders blank in full mode);
    the boundary still emits the categorical context."""
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()

    await emit_consultation_scheduled_notification(
        notifier,
        _TENANT_ID,
        _upsert_result(),
        source_provider="carestack",
        principal=_principal(),
    )

    context = notifier.emit.await_args.args[2]
    assert context["name"] is None
    assert context["provider"] == "carestack"


@pytest.mark.asyncio
async def test_emit_eng465_card_fields_default_to_none() -> None:
    """ENG-465: doctor / clinic / owner / phone default to None when the caller
    cannot resolve them. They render [redacted] and the renderer prunes the
    field — the boundary still emits the categorical + readable-time context."""
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()

    await emit_consultation_scheduled_notification(
        notifier,
        _TENANT_ID,
        _upsert_result(),
        source_provider="carestack",
        principal=_principal(),
        person_name="Ghausuddin Nezami",
        doctor_name="Olga Antipova",
        # clinic / owner / phone deliberately omitted (unresolvable)
    )

    context = notifier.emit.await_args.args[2]
    assert context["doctor"] == "Olga Antipova"
    assert context["clinic"] is None
    assert context["owner"] is None
    assert context["phone"] is None
    # Readable time is always present.
    assert context["scheduled_when"] == "Jun 12, 2026 2:00 PM UTC"
    # ENG-465b declutter: Kind + Duration no longer in the context.
    # ENG-465c: Confirmation removed (premature at booking time).
    assert "consultation_kind" not in context
    assert "duration" not in context
    assert "confirmation" not in context


@pytest.mark.asyncio
async def test_emit_skips_when_not_created() -> None:
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()

    await emit_consultation_scheduled_notification(
        notifier,
        _TENANT_ID,
        _upsert_result(was_created=False),
        source_provider="salesforce",
        principal=_principal(),
    )

    notifier.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_emit_noop_when_notifier_none() -> None:
    # Backfill path: notifier is None → no error, no emit.
    await emit_consultation_scheduled_notification(
        None,
        _TENANT_ID,
        _upsert_result(),
        source_provider="salesforce",
        principal=_principal(),
    )


@pytest.mark.asyncio
async def test_naive_provider_created_at_normalised_to_utc() -> None:
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()
    naive = datetime(2026, 6, 10, 12, 0)  # noqa: DTZ001 — deliberately naive

    await emit_consultation_scheduled_notification(
        notifier,
        _TENANT_ID,
        _upsert_result(provider_created_at=naive),
        source_provider="salesforce",
        principal=_principal(),
    )

    passed = notifier.emit.await_args.kwargs["source_created_at"]
    assert passed.tzinfo is not None
    assert passed == naive.replace(tzinfo=UTC)


# --------------------------------------------------- SF Event wiring


def _sf_event() -> dict[str, Any]:
    return {
        "Id": "00U5j000001abcd",
        "WhoId": "00Q5j000001leadX",
        "StartDateTime": "2026-06-12T14:00:00Z",
        "EndDateTime": "2026-06-12T14:30:00Z",
        "Type": "Initial Consultation",
        "ActivityDate": "2026-06-12",
        "LastModifiedDate": "2026-06-11T00:00:00Z",
        "CreatedDate": "2026-06-10T12:00:00Z",
    }


def _make_sf_service(upsert: ConsultationUpsertResult) -> Any:
    from packages.ingest.sf_event_service import SfEventIngestService

    sf_client = MagicMock()
    sf_client.soql = AsyncMock(return_value={"records": [_sf_event()]})
    service = SfEventIngestService(MagicMock(), sf_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["capture", "max_payload_watermark", "latest_payload_values",
              "get_object_schema"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    service._ingest.get_object_schema = AsyncMock(return_value=[])
    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(
        return_value=SimpleNamespace(person_uid=_PERSON_UID)
    )
    # ENG-460: the recent-pull boundary resolves the real name via IdentityService.
    service._identity = MagicMock(spec=["get_person"])  # type: ignore[attr-defined]
    service._identity.get_person = AsyncMock(
        return_value=SimpleNamespace(
            display_name="Ghausuddin Nezami",
            given_name="Ghausuddin",
            family_name="Nezami",
        )
    )
    service._ops = MagicMock(spec=["upsert_consultation_from_hint"])  # type: ignore[attr-defined]
    service._ops.upsert_consultation_from_hint = AsyncMock(return_value=upsert)
    service._interaction = MagicMock(  # type: ignore[attr-defined]
        spec=["create_event", "list_provider_events_by_external_id"]
    )
    service._interaction.create_event = AsyncMock()
    service._interaction.list_provider_events_by_external_id = AsyncMock(
        return_value=[]
    )
    return service


@pytest.mark.asyncio
async def test_sf_recent_pull_notifies_on_created() -> None:
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()
    service = _make_sf_service(_upsert_result(was_created=True))

    await service.import_recent_events(
        _TENANT_ID, days=7, notifier=notifier, principal=_principal()
    )

    notifier.emit.assert_awaited_once()
    assert notifier.emit.await_args.args[1] == CONSULTATION_SCHEDULED_EVENT
    # ENG-460: the resolved real name rides into the context.
    assert notifier.emit.await_args.args[2]["name"] == "Ghausuddin Nezami"


@pytest.mark.asyncio
async def test_sf_recent_pull_does_not_notify_on_update() -> None:
    notifier = MagicMock(spec=["emit"])
    notifier.emit = AsyncMock()
    service = _make_sf_service(_upsert_result(was_created=False))

    await service.import_recent_events(
        _TENANT_ID, days=7, notifier=notifier, principal=_principal()
    )

    notifier.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_sf_backfill_never_notifies() -> None:
    # import_all_since has no notifier parameter; the recent path without a
    # notifier must also stay silent (defaults None).
    service = _make_sf_service(_upsert_result(was_created=True))
    # No notifier passed → boundary is silent (no attribute error).
    await service.import_recent_events(_TENANT_ID, days=7)
