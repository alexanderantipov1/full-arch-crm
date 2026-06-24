"""Service-level tests for the interaction domain — D1 / ENG-2.

Focus: the no-PII summary contract and the idempotency contract on
``InteractionService.create_event``. Pure-Python paths run with mocked
sessions; real-DB integration (partial-UNIQUE collision behaviour against
live Postgres) waits for a test container.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError as PydanticValidationError

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.interaction.models import EVENT_KINDS, Event
from packages.interaction.repository import InteractionRepository
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


@pytest.mark.asyncio
async def test_treatment_payment_quality_evidence_reports_payment_metrics() -> None:
    service, repo = _make_service()
    repo.get_treatment_payment_quality_metrics = AsyncMock(
        return_value={
            "payment_event_count": 8,
            "identity_linked_payment_count": 8,
            "source_attributed_payment_count": 6,
            "unmatched_payment_count": 2,
            "payment_applied_excluded_count": 5,
        }
    )

    result = await service.get_treatment_payment_quality_evidence(_TENANT_ID)

    metrics_payload = result["metrics"]
    assert isinstance(metrics_payload, list)
    metrics = {
        str(metric["id"]): metric
        for metric in metrics_payload
        if isinstance(metric, dict)
    }
    assert metrics["identity_linkage_coverage"]["value"] == 1.0
    assert metrics["source_attribution_coverage"]["value"] == 0.75
    assert metrics["unmatched_payment_count"]["value"] == 2
    assert metrics["payment_applied_excluded_count"]["value"] == 5
    refs = result["refs"]
    assert isinstance(refs, list)
    assert "payment_applied_exclusion.aggregate" in refs
    assert result["blockers"] == []
    assert result["caveats"]


# --- summary_for_event: no-PII contract ---


# This list is the union of fields W2 (CareStack) tests treat as forbidden
# in any rendered summary. If any of these strings appears in the summary
# helper output for ANY input, that's a code-review event.
_PII_FIXTURE_STRINGS = (
    "John",
    "Smith",
    "john@example.com",
    "+15555551234",
    "1980-01-01",
    "123 Main St",
    "MRN-78901",
    "patient reports back pain",  # clinical free-text
)


def test_summary_lead_created_salesforce_no_id() -> None:
    out = summary_for_event(kind="lead_created", source_provider="salesforce")
    assert out == "Lead created from Salesforce"


def test_summary_consultation_rescheduled_carestack_with_id() -> None:
    out = summary_for_event(
        kind="consultation_rescheduled",
        source_provider="carestack",
        source_id="12345",
    )
    assert out == "Consultation rescheduled in CareStack (id=12345)"


def test_summary_consultation_scheduled_carestack_with_id() -> None:
    out = summary_for_event(
        kind="consultation_scheduled",
        source_provider="carestack",
        source_id="appt-12345",
    )
    assert out == "Consultation scheduled in CareStack (id=appt-12345)"


def test_summary_lead_updated_uses_in_preposition() -> None:
    """lead_updated reads as 'updated in <provider>', not 'updated from'."""
    out = summary_for_event(kind="lead_updated", source_provider="salesforce")
    assert out == "Lead updated in Salesforce"


def test_summary_consultation_cancelled_with_id() -> None:
    out = summary_for_event(
        kind="consultation_cancelled",
        source_provider="carestack",
        source_id="9876543",
    )
    assert "Consultation cancelled" in out
    assert "CareStack" in out
    assert "(id=9876543)" in out


def test_summary_unknown_kind_raises() -> None:
    with pytest.raises(ValidationError):
        summary_for_event(kind="patient_admitted", source_provider="carestack")


def test_summary_unknown_provider_raises() -> None:
    with pytest.raises(ValidationError):
        summary_for_event(kind="lead_created", source_provider="hubspot")


def test_summary_strips_blank_source_id() -> None:
    out = summary_for_event(
        kind="lead_created",
        source_provider="salesforce",
        source_id="   ",
    )
    # whitespace-only source_id is silently dropped; no "(id= )" suffix
    assert out == "Lead created from Salesforce"


@pytest.mark.parametrize(
    "kind",
    EVENT_KINDS,
)
@pytest.mark.parametrize("provider", ["salesforce", "carestack"])
def test_summary_never_contains_pii_strings(kind: str, provider: str) -> None:
    """The helper signature accepts only kind / provider / source_id, so
    PII values from any other source CANNOT enter the output. This test
    asserts that across the full kind × provider grid.

    If anyone widens the signature to take a name/email/phone, this test
    catches it (via the import) — the test then needs to be updated to
    accept that field, and that conversation should include "do we have
    an exception to the no-PII rule".
    """
    # source_id = a reasonable provider record id (not PII)
    out = summary_for_event(kind=kind, source_provider=provider, source_id="00Q5j000001abcd")
    for pii in _PII_FIXTURE_STRINGS:
        assert pii not in out, f"PII leak: '{pii}' found in summary {out!r}"


def test_summary_is_allowlisted_and_excludes_raw_payload_fields() -> None:
    raw_provider_payload = {
        "FirstName": "John",
        "LastName": "Smith",
        "Email": "john@example.com",
        "Description": "patient reports back pain",
        "ClinicalNote": "implant consult notes",
        "Phone": "+15555551234",
    }

    out = summary_for_event(
        kind="call_reference_found",
        source_provider="salesforce",
        source_id="00T5j000001abcd",
    )

    assert out == "Call reference found in Salesforce (id=00T5j000001abcd)"
    for field_name, field_value in raw_provider_payload.items():
        assert field_name not in out
        assert field_value not in out


# --- create_event ---


def _make_service() -> tuple[InteractionService, MagicMock]:
    session = MagicMock()
    # ENG-269: create_event runs inside a SAVEPOINT (session.begin_nested)
    # so an IntegrityError on the cross-pull partial UNIQUE only rolls
    # back the failed insert, not the in-flight raw_event capture. Wire
    # the savepoint up here so every unit test sees a usable mock.
    savepoint = MagicMock()
    savepoint.commit = AsyncMock()
    savepoint.rollback = AsyncMock()
    session.begin_nested = AsyncMock(return_value=savepoint)
    service = InteractionService(session)
    repo = MagicMock()
    # ENG-418: list_operational_timeline now also calls
    # list_responsibilities_for_events to attach the per-event
    # responsibility refs. Default to an empty list so legacy tests
    # that only set up list_for_person still pass.
    repo.list_responsibilities_for_events = AsyncMock(return_value=[])
    service._repo = repo  # type: ignore[attr-defined]
    return service, repo


def _make_event_in(*, source_event_id: uuid.UUID | None = None) -> EventIn:
    return EventIn(
        person_uid=uuid.uuid4(),
        kind="lead_created",
        source_provider="salesforce",
        source_event_id=source_event_id,
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="00Q5j000001abcd",
        projection_ref_type="ops_lead",
        projection_ref_id=uuid.uuid4(),
        review_status="auto",
        occurred_at=datetime(2026, 5, 5, tzinfo=UTC),
        summary="Lead created from Salesforce",
        payload={"lead_status": "open", "lead_source": "Web"},
    )


def _make_event(
    *,
    kind: str,
    occurred_at: datetime,
    source_provider: str = "salesforce",
    source_kind: str = "salesforce_lead",
    source_external_id: str = "00Q5j000001abcd",
    data_class: str = "operational",
    review_status: str = "auto",
    summary: str = "Lead created from Salesforce",
    projection_ref_type: str | None = None,
    projection_ref_id: uuid.UUID | None = None,
    payload: dict[str, object] | None = None,
) -> Event:
    event = Event(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        kind=kind,
        source_provider=source_provider,
        source_event_id=uuid.uuid4(),
        data_class=data_class,
        source_kind=source_kind,
        source_external_id=source_external_id,
        projection_ref_type=projection_ref_type,
        projection_ref_id=projection_ref_id,
        review_status=review_status,
        occurred_at=occurred_at,
        summary=summary,
        payload=payload or {},
    )
    event.id = uuid.uuid4()
    return event


@pytest.mark.parametrize("kind", EVENT_KINDS)
def test_event_in_accepts_workflow_ready_kinds(kind: str) -> None:
    payload = _make_event_in().model_dump()
    payload["kind"] = kind
    model = EventIn(**payload)
    assert model.kind == kind


def test_event_in_requires_source_reference_and_data_class() -> None:
    base = _make_event_in().model_dump()

    missing_data_class = dict(base)
    missing_data_class.pop("data_class")
    with pytest.raises(PydanticValidationError):
        EventIn(**missing_data_class)

    missing_source_kind = dict(base)
    missing_source_kind.pop("source_kind")
    with pytest.raises(PydanticValidationError):
        EventIn(**missing_source_kind)

    missing_external_id = dict(base)
    missing_external_id.pop("source_external_id")
    with pytest.raises(PydanticValidationError):
        EventIn(**missing_external_id)


def test_event_in_requires_source_kind_to_match_provider() -> None:
    base = _make_event_in().model_dump()
    base["source_provider"] = "carestack"
    base["source_kind"] = "salesforce_lead"
    with pytest.raises(PydanticValidationError):
        EventIn(**base)


def test_event_in_requires_complete_projection_reference() -> None:
    base = _make_event_in().model_dump()
    base["projection_ref_id"] = None
    with pytest.raises(PydanticValidationError):
        EventIn(**base)


@pytest.mark.asyncio
async def test_create_event_happy_path() -> None:
    service, repo = _make_service()
    saved_event = Event(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        kind="lead_created",
        source_provider="salesforce",
        source_event_id=uuid.uuid4(),
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="00Q5j000001abcd",
        projection_ref_type="ops_lead",
        projection_ref_id=uuid.uuid4(),
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Lead created from Salesforce",
        payload={},
    )
    saved_event.id = uuid.uuid4()
    repo.add_event = AsyncMock(return_value=saved_event)

    payload = _make_event_in(source_event_id=saved_event.source_event_id)
    result = await service.create_event(_TENANT_ID, payload)

    assert result is saved_event
    repo.add_event.assert_awaited_once()
    # The event passed to add_event must carry the tenant_id we forwarded.
    sent_event = repo.add_event.await_args.args[0]
    assert sent_event.tenant_id == _TENANT_ID
    assert sent_event.data_class == "operational"
    assert sent_event.source_kind == "salesforce_lead"
    assert sent_event.source_external_id == "00Q5j000001abcd"
    assert sent_event.projection_ref_type == "ops_lead"
    assert sent_event.projection_ref_id == payload.projection_ref_id
    assert sent_event.review_status == "auto"


@pytest.mark.asyncio
async def test_create_event_returns_existing_on_partial_unique_collision() -> None:
    """If the legacy partial-UNIQUE on (source_provider, source_event_id) fires,
    the service rolls back the SAVEPOINT (ENG-269) and returns the existing
    row instead of raising. The savepoint rollback preserves any other
    pending work in the outer transaction (e.g. an already-flushed
    ``ingest.raw_event`` capture from the same ingest call).
    """
    from sqlalchemy.exc import IntegrityError

    service, repo = _make_service()
    session = cast(Any, service._session)
    savepoint = await session.begin_nested()

    existing_event = Event(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        kind="lead_created",
        source_provider="salesforce",
        source_event_id=uuid.uuid4(),
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="not-the-key-for-this-test",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Lead created from Salesforce",
        payload={},
    )
    existing_event.id = uuid.uuid4()

    # No row found by the new key — fall back to the legacy lookup.
    repo.add_event = AsyncMock(
        side_effect=IntegrityError("partial unique", params=None, orig=Exception("dup"))
    )
    repo.find_provider_event_by_external_id = AsyncMock(return_value=None)
    repo.find_event_by_source = AsyncMock(return_value=existing_event)

    payload = _make_event_in(source_event_id=existing_event.source_event_id)
    result = await service.create_event(_TENANT_ID, payload)

    assert result is existing_event
    savepoint.rollback.assert_awaited_once()
    repo.find_event_by_source.assert_awaited_once_with(
        _TENANT_ID, "salesforce", existing_event.source_event_id
    )


@pytest.mark.asyncio
async def test_create_event_returns_existing_on_provider_source_kind_collision() -> None:
    """ENG-269 — the cross-pull partial UNIQUE on
    (tenant_id, source_provider, source_kind, source_external_id, kind)
    fires whenever a re-pull would re-insert the same provider object
    row. ``create_event`` looks up the existing row by the new key
    (NOT by source_event_id — re-pulls produce a NEW source_event_id
    every time) and returns it instead of raising.
    """
    from sqlalchemy.exc import IntegrityError

    service, repo = _make_service()
    session = cast(Any, service._session)
    savepoint = await session.begin_nested()

    existing_event = Event(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        kind="lead_created",
        source_provider="salesforce",
        source_event_id=uuid.uuid4(),  # earlier raw_event id
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="00Q5j000001abcd",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Lead created from Salesforce",
        payload={},
    )
    existing_event.id = uuid.uuid4()

    repo.add_event = AsyncMock(
        side_effect=IntegrityError(
            "uq_event_provider_source_kind", params=None, orig=Exception("dup")
        )
    )
    repo.find_provider_event_by_external_id = AsyncMock(return_value=existing_event)
    repo.find_event_by_source = AsyncMock(return_value=None)

    payload = _make_event_in(source_event_id=uuid.uuid4())  # NEW raw_event id
    result = await service.create_event(_TENANT_ID, payload)

    assert result is existing_event
    savepoint.rollback.assert_awaited_once()
    repo.find_provider_event_by_external_id.assert_awaited_once_with(
        _TENANT_ID,
        source_provider="salesforce",
        source_kind="salesforce_lead",
        source_external_id="00Q5j000001abcd",
        kind="lead_created",
    )
    # The legacy lookup must NOT have been called — the new key matched.
    repo.find_event_by_source.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_event_idempotent_returns_was_created_true_on_insert() -> None:
    """ENG-269 — ``create_event_idempotent`` exposes whether the row was
    newly inserted so ingest callers can count an insert as ``imported``
    and a conflict as ``skipped``.
    """
    service, repo = _make_service()
    saved_event = Event(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        kind="lead_created",
        source_provider="salesforce",
        source_event_id=uuid.uuid4(),
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="00Q5j000001abcd",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Lead created from Salesforce",
        payload={},
    )
    saved_event.id = uuid.uuid4()
    repo.add_event = AsyncMock(return_value=saved_event)

    payload = _make_event_in(source_event_id=saved_event.source_event_id)
    result = await service.create_event_idempotent(_TENANT_ID, payload)

    assert result.event is saved_event
    assert result.was_created is True


@pytest.mark.asyncio
async def test_create_event_idempotent_returns_was_created_false_on_conflict() -> None:
    """ENG-269 — on cross-pull conflict, the existing row is returned
    with ``was_created=False`` so CareStack ingest counts it as skipped.
    """
    from sqlalchemy.exc import IntegrityError

    service, repo = _make_service()
    session = cast(Any, service._session)
    savepoint = await session.begin_nested()

    existing_event = Event(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        kind="invoice_created",
        source_provider="carestack",
        source_event_id=uuid.uuid4(),
        data_class="billing",
        source_kind="carestack_invoice",
        source_external_id="invoice-42",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Invoice created in CareStack (id=invoice-42)",
        payload={"amount": 100.0},
    )
    existing_event.id = uuid.uuid4()

    repo.add_event = AsyncMock(
        side_effect=IntegrityError(
            "uq_event_provider_source_kind", params=None, orig=Exception("dup")
        )
    )
    repo.find_provider_event_by_external_id = AsyncMock(return_value=existing_event)

    payload = EventIn(
        person_uid=existing_event.person_uid,
        kind="invoice_created",
        source_provider="carestack",
        source_event_id=uuid.uuid4(),  # fresh raw_event for the re-pull
        data_class="billing",
        source_kind="carestack_invoice",
        source_external_id="invoice-42",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Invoice created in CareStack (id=invoice-42)",
        payload={"amount": 100.0},
    )
    result = await service.create_event_idempotent(_TENANT_ID, payload)

    assert result.event is existing_event
    assert result.was_created is False
    savepoint.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_event_reraises_when_existing_not_found_after_collision() -> None:
    """If a partial UNIQUE fires but neither the new nor the legacy
    lookup finds the colliding row, the original IntegrityError surfaces
    — we don't swallow constraint failures silently.
    """
    from sqlalchemy.exc import IntegrityError

    service, repo = _make_service()

    repo.add_event = AsyncMock(
        side_effect=IntegrityError("partial unique", params=None, orig=Exception("dup"))
    )
    repo.find_provider_event_by_external_id = AsyncMock(return_value=None)
    repo.find_event_by_source = AsyncMock(return_value=None)

    payload = _make_event_in(source_event_id=uuid.uuid4())
    with pytest.raises(IntegrityError):
        await service.create_event(_TENANT_ID, payload)


@pytest.mark.asyncio
async def test_create_event_reraises_integrity_when_source_event_id_is_none() -> None:
    """A NULL source_event_id row never collides on either partial UNIQUE.
    If an IntegrityError still fires (some OTHER constraint), surface it.
    """
    from sqlalchemy.exc import IntegrityError

    service, repo = _make_service()

    repo.add_event = AsyncMock(
        side_effect=IntegrityError("some other constraint", params=None, orig=Exception("x"))
    )
    repo.find_provider_event_by_external_id = AsyncMock(return_value=None)
    repo.find_event_by_source = AsyncMock(return_value=None)

    payload = _make_event_in(source_event_id=None)
    with pytest.raises(IntegrityError):
        await service.create_event(_TENANT_ID, payload)


@pytest.mark.asyncio
async def test_create_event_idempotent_different_kind_same_external_id_inserts() -> None:
    """ENG-269 — same provider/source_kind/source_external_id with a
    DIFFERENT ``kind`` is NOT a conflict (treatment_proposed and
    treatment_completed share a source_external_id but are distinct
    timeline events). Both inserts succeed.
    """
    service, repo = _make_service()
    person_uid = uuid.uuid4()
    proposed = Event(
        tenant_id=_TENANT_ID,
        person_uid=person_uid,
        kind="treatment_proposed",
        source_provider="carestack",
        source_event_id=uuid.uuid4(),
        data_class="phi_protected",
        source_kind="carestack_treatment_procedure",
        source_external_id="proc-1",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Treatment proposed in CareStack (id=proc-1)",
        payload={},
    )
    proposed.id = uuid.uuid4()
    completed = Event(
        tenant_id=_TENANT_ID,
        person_uid=person_uid,
        kind="treatment_completed",
        source_provider="carestack",
        source_event_id=uuid.uuid4(),
        data_class="phi_protected",
        source_kind="carestack_treatment_procedure",
        source_external_id="proc-1",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        summary="Treatment completed in CareStack (id=proc-1)",
        payload={},
    )
    completed.id = uuid.uuid4()
    repo.add_event = AsyncMock(side_effect=[proposed, completed])

    base = dict(
        person_uid=person_uid,
        source_provider="carestack",
        data_class="phi_protected",
        source_kind="carestack_treatment_procedure",
        source_external_id="proc-1",
        review_status="auto",
        occurred_at=datetime.now(tz=UTC),
        payload={},
    )

    first = await service.create_event_idempotent(
        _TENANT_ID,
        EventIn(
            **base,  # type: ignore[arg-type]
            kind="treatment_proposed",
            source_event_id=proposed.source_event_id,
            summary="Treatment proposed in CareStack (id=proc-1)",
        ),
    )
    second = await service.create_event_idempotent(
        _TENANT_ID,
        EventIn(
            **base,  # type: ignore[arg-type]
            kind="treatment_completed",
            source_event_id=completed.source_event_id,
            summary="Treatment completed in CareStack (id=proc-1)",
        ),
    )

    assert first.was_created is True
    assert second.was_created is True
    assert first.event is proposed
    assert second.event is completed
    assert repo.add_event.await_count == 2


# --- list_for_person validation ---


@pytest.mark.asyncio
async def test_list_for_person_rejects_invalid_limit() -> None:
    service, repo = _make_service()
    repo.list_for_person = AsyncMock(return_value=[])

    with pytest.raises(ValidationError):
        await service.list_for_person(_TENANT_ID, uuid.uuid4(), limit=0)
    with pytest.raises(ValidationError):
        await service.list_for_person(_TENANT_ID, uuid.uuid4(), limit=501)


@pytest.mark.asyncio
async def test_list_for_person_passes_through_to_repo() -> None:
    service, repo = _make_service()
    sample = [
        Event(
            tenant_id=_TENANT_ID,
            person_uid=uuid.uuid4(),
            kind="lead_created",
            source_provider="salesforce",
            data_class="operational",
            source_kind="salesforce_lead",
            source_external_id="00Q5j000001abcd",
            review_status="auto",
            occurred_at=datetime.now(tz=UTC),
            summary="Lead created from Salesforce",
            payload={},
        )
    ]
    repo.list_for_person = AsyncMock(return_value=sample)

    person_uid = uuid.uuid4()
    result = await service.list_for_person(_TENANT_ID, person_uid, limit=10)

    assert result == sample
    repo.list_for_person.assert_awaited_once_with(_TENANT_ID, person_uid, limit=10, before=None)


@pytest.mark.asyncio
async def test_count_for_person_passes_through_to_repo() -> None:
    service, repo = _make_service()
    repo.count_for_person = AsyncMock(return_value=7)

    person_uid = uuid.uuid4()
    result = await service.count_for_person(_TENANT_ID, person_uid)

    assert result == 7
    repo.count_for_person.assert_awaited_once_with(_TENANT_ID, person_uid)


@pytest.mark.asyncio
async def test_list_operational_timeline_returns_allowlisted_entries() -> None:
    projection_reader = MagicMock()
    projection_reader.get_operational_timeline_projection = AsyncMock(
        return_value={
            "status": "scheduled",
            "scheduled_at": datetime(2026, 6, 3, 15, 0, tzinfo=UTC),
            "Description": "patient reports back pain",
            "raw_payload": {"Email": "john@example.com"},
        }
    )
    service = InteractionService(
        MagicMock(),
        operational_projection_reader=projection_reader,
    )
    service._repo = MagicMock()  # type: ignore[attr-defined]
    # ENG-418: stub the batch responsibility fetch — this test only
    # cares about projection enrichment so empty responsibilities is
    # the right default.
    service._repo.list_responsibilities_for_events = AsyncMock(  # type: ignore[attr-defined]
        return_value=[]
    )

    projection_id = uuid.uuid4()
    newest = _make_event(
        kind="consultation_scheduled",
        occurred_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
        source_provider="carestack",
        source_kind="carestack_appointment",
        source_external_id="appt-123",
        summary="Consultation scheduled in CareStack (id=appt-123)",
        projection_ref_type="ops_consultation",
        projection_ref_id=projection_id,
        payload={
            "Description": "patient reports back pain",
            "Email": "john@example.com",
        },
    )
    older = _make_event(
        kind="lead_created",
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        summary="Lead created from Salesforce (id=00Q5j000001abcd)",
    )
    service._repo.list_for_person = AsyncMock(  # type: ignore[attr-defined]
        return_value=[newest, older]
    )

    result = await service.list_operational_timeline(
        _TENANT_ID,
        newest.person_uid,
        limit=2,
    )

    assert [entry.kind for entry in result] == [
        "consultation_scheduled",
        "lead_created",
    ]
    assert result[0].projection is not None
    assert result[0].projection.type == "ops_consultation"
    assert result[0].projection.id == projection_id
    assert result[0].projection.status == "scheduled"
    assert result[0].projection.scheduled_at == datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
    assert result[0].projection.due_at is None
    assert result[1].projection is None
    service._repo.list_for_person.assert_awaited_once_with(  # type: ignore[attr-defined]
        _TENANT_ID,
        newest.person_uid,
        limit=2,
    )


@pytest.mark.asyncio
async def test_list_operational_timeline_rejects_invalid_limit() -> None:
    service, repo = _make_service()
    repo.list_for_person = AsyncMock(return_value=[])

    with pytest.raises(ValidationError):
        await service.list_operational_timeline(_TENANT_ID, uuid.uuid4(), limit=0)
    with pytest.raises(ValidationError):
        await service.list_operational_timeline(_TENANT_ID, uuid.uuid4(), limit=501)


@pytest.mark.asyncio
async def test_operational_timeline_does_not_leak_raw_payload_or_free_text() -> None:
    service, repo = _make_service()
    event = _make_event(
        kind="call_reference_found",
        occurred_at=datetime(2026, 6, 4, 12, 0, tzinfo=UTC),
        source_kind="salesforce_task",
        source_external_id="https://example.test/call/abc",
        data_class="call_recording_ref",
        review_status="pending_review",
        summary="Call reference found in Salesforce (id=00T5j000001abcd)",
        payload={
            "FirstName": "John",
            "LastName": "Smith",
            "Email": "john@example.com",
            "Description": "patient reports back pain",
            "ClinicalNote": "implant consult notes",
            "raw_payload": {"Phone": "+15555551234"},
        },
    )
    repo.list_for_person = AsyncMock(return_value=[event])

    result = await service.list_operational_timeline(
        _TENANT_ID,
        event.person_uid,
        limit=1,
    )

    rendered = result[0].model_dump_json()
    assert "pending_review" in rendered
    assert "https://example.test/call/abc" in rendered
    for forbidden in (
        "FirstName",
        "LastName",
        "Email",
        "Description",
        "ClinicalNote",
        "John",
        "Smith",
        "john@example.com",
        "patient reports back pain",
        "implant consult notes",
        "+15555551234",
    ):
        assert forbidden not in rendered


def test_interaction_service_is_append_only() -> None:
    assert not hasattr(InteractionService, "update_event")
    assert not hasattr(InteractionService, "delete_event")
    assert not hasattr(InteractionRepository, "update_event")
    assert not hasattr(InteractionRepository, "delete_event")


@pytest.mark.asyncio
async def test_treatment_payment_aggregate_converts_safe_repo_values() -> None:
    service, repo = _make_service()
    start = datetime(2026, 5, 1, tzinfo=UTC)
    end = datetime(2026, 6, 1, tzinfo=UTC)
    repo.get_treatment_payment_aggregate = AsyncMock(
        return_value={
            "treatment_presented_count": 5,
            "treatment_completed_count": 2,
            "invoice_count": 3,
            "payment_total_amount": "1250.50",
            "collected_total": "975.25",
            "payment_event_count": 4,
            "first_payment_at": datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            "last_payment_at": datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        }
    )

    result = await service.get_treatment_payment_aggregate(
        _TENANT_ID,
        occurred_from=start,
        occurred_to=end,
        source_provider="carestack",
    )

    assert result.treatment_presented_count == 5
    assert result.treatment_completed_count == 2
    assert result.invoice_count == 3
    assert result.payment_total_amount == 1250.5
    assert result.collected_total == 975.25
    assert result.payment_event_count == 4
    assert result.first_payment_at == datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    assert result.last_payment_at == datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    repo.get_treatment_payment_aggregate.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=start,
        occurred_to=end,
        location_id=None,
    )


@pytest.mark.asyncio
async def test_treatment_payment_aggregate_forwards_location_id_to_repo() -> None:
    """ENG-267: when the caller supplies ``location_id``, the service passes
    it through to the repository so the aggregate becomes location-scoped.
    """
    service, repo = _make_service()
    location_id = uuid.uuid4()
    repo.get_treatment_payment_aggregate = AsyncMock(
        return_value={
            "treatment_presented_count": 1,
            "treatment_completed_count": 0,
            "invoice_count": 0,
            "payment_total_amount": "0",
            "collected_total": "0",
            "payment_event_count": 0,
            "first_payment_at": None,
            "last_payment_at": None,
        }
    )

    await service.get_treatment_payment_aggregate(
        _TENANT_ID,
        location_id=location_id,
    )

    repo.get_treatment_payment_aggregate.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=None,
        occurred_to=None,
        location_id=location_id,
    )


@pytest.mark.asyncio
async def test_treatment_payment_aggregate_is_zero_for_salesforce_filter() -> None:
    service, repo = _make_service()
    repo.get_treatment_payment_aggregate = AsyncMock()

    result = await service.get_treatment_payment_aggregate(
        _TENANT_ID,
        source_provider="salesforce",
    )

    assert result.treatment_presented_count == 0
    assert result.treatment_completed_count == 0
    assert result.invoice_count == 0
    assert result.payment_total_amount == 0.0
    assert result.collected_total == 0.0
    assert result.payment_event_count == 0
    repo.get_treatment_payment_aggregate.assert_not_awaited()


# --- W3 (ENG-418 + ENG-419) -----------------------------------------------


@pytest.mark.asyncio
async def test_list_operational_timeline_attaches_responsibilities() -> None:
    """ENG-418: each entry carries the operational + clinical refs."""
    service, repo = _make_service()
    event_a = _make_event(
        kind="lead_created",
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    event_b = _make_event(
        kind="consultation_completed",
        occurred_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
        source_provider="carestack",
        source_kind="carestack_appointment",
    )
    repo.list_for_person = AsyncMock(return_value=[event_b, event_a])
    actor_op = uuid.uuid4()
    actor_clinical = uuid.uuid4()

    class _R:
        def __init__(self, event_id, actor_id, role):
            self.event_id = event_id
            self.actor_id = actor_id
            self.role = role

    repo.list_responsibilities_for_events = AsyncMock(
        return_value=[
            _R(event_a.id, actor_op, "operational"),
            _R(event_b.id, actor_op, "operational"),
            _R(event_b.id, actor_clinical, "clinical"),
        ]
    )

    result = await service.list_operational_timeline(
        _TENANT_ID, event_a.person_uid
    )

    assert len(result) == 2
    consultation_entry = result[0]
    lead_entry = result[1]
    assert consultation_entry.kind == "consultation_completed"
    assert {(r.actor_id, r.role) for r in consultation_entry.responsibles} == {
        (actor_op, "operational"),
        (actor_clinical, "clinical"),
    }
    assert [r.role for r in lead_entry.responsibles] == ["operational"]
    assert lead_entry.responsibles[0].actor_id == actor_op


@pytest.mark.asyncio
async def test_funnel_aggregate_rejects_unknown_role() -> None:
    service, _repo = _make_service()
    with pytest.raises(ValidationError):
        await service.funnel_aggregate(_TENANT_ID, role="bogus")


@pytest.mark.asyncio
async def test_funnel_aggregate_forwards_filters() -> None:
    service, repo = _make_service()
    repo.funnel_aggregate_by_actor = AsyncMock(return_value=[])
    occurred_from = datetime(2026, 5, 1, tzinfo=UTC)
    occurred_to = datetime(2026, 6, 1, tzinfo=UTC)
    loc = uuid.uuid4()
    await service.funnel_aggregate(
        _TENANT_ID,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        source_provider="salesforce",
        location_id=loc,
        role="operational",
    )
    repo.funnel_aggregate_by_actor.assert_awaited_once_with(
        _TENANT_ID,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        source_provider="salesforce",
        location_id=loc,
        role="operational",
    )


@pytest.mark.asyncio
async def test_funnel_revenue_by_actor_returns_aggregate() -> None:
    service, repo = _make_service()
    actor_a = uuid.uuid4()
    repo.funnel_revenue_by_actor = AsyncMock(
        return_value=[
            {
                "actor_id": actor_a,
                "role": "operational",
                "collected_total": 12500.0,
                "payment_count": 4,
            }
        ]
    )
    result = await service.funnel_revenue_by_actor(_TENANT_ID)
    assert len(result) == 1
    assert result[0]["actor_id"] == actor_a
    assert result[0]["collected_total"] == 12500.0
    assert result[0]["payment_count"] == 4


@pytest.mark.asyncio
async def test_funnel_totals_returns_per_stage_counts() -> None:
    service, repo = _make_service()
    repo.funnel_aggregate_totals = AsyncMock(
        return_value={
            "lead_new": {"event_count": 100, "person_count": 80},
            "opportunity_won": {"event_count": 12, "person_count": 12},
        }
    )
    out = await service.funnel_totals(_TENANT_ID)
    assert out["lead_new"]["person_count"] == 80
    assert out["opportunity_won"]["event_count"] == 12


@pytest.mark.asyncio
async def test_funnel_distinct_actors_passes_role_filter() -> None:
    service, repo = _make_service()
    repo.funnel_distinct_actors = AsyncMock(return_value=[])
    await service.funnel_distinct_actors(_TENANT_ID, role="clinical")
    repo.funnel_distinct_actors.assert_awaited_once_with(
        _TENANT_ID, role="clinical"
    )


@pytest.mark.asyncio
async def test_funnel_revenue_by_person_forwards_filters() -> None:
    """ENG-418 fix: the per-person revenue lookup forwards filters to repo."""
    service, repo = _make_service()
    person_a = uuid.uuid4()
    repo.funnel_revenue_by_person = AsyncMock(return_value={person_a: 7200.0})
    occurred_from = datetime(2026, 5, 1, tzinfo=UTC)
    out = await service.funnel_revenue_by_person(
        _TENANT_ID,
        person_uids=[person_a],
        occurred_from=occurred_from,
        source_provider="carestack",
    )
    assert out == {person_a: 7200.0}
    repo.funnel_revenue_by_person.assert_awaited_once_with(
        _TENANT_ID,
        person_uids=[person_a],
        occurred_from=occurred_from,
        occurred_to=None,
        source_provider="carestack",
        location_id=None,
    )


@pytest.mark.asyncio
async def test_compute_funnel_dropoff_uses_person_scoped_revenue_for_won() -> None:
    """ENG-418 fix (BLOCKER): won bucket uses person-scoped revenue.

    Two persons drop at ``opportunity_won`` under the same actor; the
    bucket dollar_total must sum their PER-PERSON realized payments,
    NOT the actor-wide aggregate that would double-count or credit
    revenue from non-dropoff persons.
    """
    service, repo = _make_service()
    actor_id = uuid.uuid4()
    person_a = uuid.uuid4()
    person_b = uuid.uuid4()
    repo.funnel_dropoff_by_person = AsyncMock(
        return_value=[
            {
                "person_uid": person_a,
                "stage": "opportunity_won",
                "operational_actor_id": actor_id,
            },
            {
                "person_uid": person_b,
                "stage": "opportunity_won",
                "operational_actor_id": actor_id,
            },
        ]
    )
    repo.funnel_revenue_by_person = AsyncMock(
        return_value={person_a: 3000.0, person_b: 1500.0}
    )

    stages = await service.compute_funnel_dropoff(
        _TENANT_ID,
        opp_amount_by_person={},
    )

    by_stage = {s.stage: s for s in stages}
    won = by_stage["opportunity_won"]
    assert won.person_count == 2
    assert won.dollar_total == 4500.0
    assert len(won.by_actor) == 1
    bucket = won.by_actor[0]
    assert bucket.actor_id == actor_id
    assert bucket.person_count == 2
    assert bucket.dollar_total == 4500.0

    # funnel_revenue_by_person was called with EXACTLY the won persons —
    # not an actor-wide aggregate.
    repo.funnel_revenue_by_person.assert_awaited_once()
    call_kwargs = repo.funnel_revenue_by_person.await_args.kwargs
    assert set(call_kwargs["person_uids"]) == {person_a, person_b}


@pytest.mark.asyncio
async def test_compute_funnel_dropoff_uses_opp_amount_for_non_won() -> None:
    """Non-won stages use the caller-supplied Opportunity.amount lookup."""
    service, repo = _make_service()
    actor_id = uuid.uuid4()
    person_a = uuid.uuid4()
    person_b = uuid.uuid4()
    repo.funnel_dropoff_by_person = AsyncMock(
        return_value=[
            {
                "person_uid": person_a,
                "stage": "consult_no_show",
                "operational_actor_id": actor_id,
            },
            {
                "person_uid": person_b,
                "stage": "consult_no_show",
                "operational_actor_id": actor_id,
            },
        ]
    )
    repo.funnel_revenue_by_person = AsyncMock(return_value={})

    stages = await service.compute_funnel_dropoff(
        _TENANT_ID,
        opp_amount_by_person={person_a: 5000.0, person_b: 8000.0},
    )

    by_stage = {s.stage: s for s in stages}
    no_show = by_stage["consult_no_show"]
    assert no_show.person_count == 2
    assert no_show.dollar_total == 13000.0
    # No revenue lookup needed when no persons dropped at won.
    repo.funnel_revenue_by_person.assert_awaited_once()
    assert (
        repo.funnel_revenue_by_person.await_args.kwargs["person_uids"] == []
    )


@pytest.mark.asyncio
async def test_compute_funnel_dropoff_returns_all_stages_in_order() -> None:
    """Every stage in the canonical axis appears in the result, in order."""
    from packages.interaction.schemas import FUNNEL_STAGE_ORDER

    service, repo = _make_service()
    repo.funnel_dropoff_by_person = AsyncMock(return_value=[])
    repo.funnel_revenue_by_person = AsyncMock(return_value={})

    stages = await service.compute_funnel_dropoff(
        _TENANT_ID, opp_amount_by_person={}
    )
    assert [s.stage for s in stages] == list(FUNNEL_STAGE_ORDER)
    assert all(s.person_count == 0 and s.dollar_total == 0.0 for s in stages)


@pytest.mark.asyncio
async def test_compute_funnel_dropoff_handles_missing_operational_actor() -> None:
    """Legacy events with no operational responsibility row → actor_id=None."""
    service, repo = _make_service()
    person_a = uuid.uuid4()
    repo.funnel_dropoff_by_person = AsyncMock(
        return_value=[
            {
                "person_uid": person_a,
                "stage": "lead_new",
                "operational_actor_id": None,
            },
        ]
    )
    repo.funnel_revenue_by_person = AsyncMock(return_value={})

    stages = await service.compute_funnel_dropoff(
        _TENANT_ID, opp_amount_by_person={person_a: 2000.0}
    )

    lead_stage = next(s for s in stages if s.stage == "lead_new")
    assert lead_stage.person_count == 1
    assert lead_stage.dollar_total == 2000.0
    assert len(lead_stage.by_actor) == 1
    assert lead_stage.by_actor[0].actor_id is None
