"""Unit tests for ``SfLeadIngestService``.

Mock-based per the existing test pattern in this codebase (see
``tests/identity/test_service.py`` and ``tests/ops/test_service.py``).
Real-DB integration follows when a Postgres test container lands.

Coverage focus:
  * Salesforce pull captures raw first, then a normalized person hint.
  * The hint row is adapted into the identity-owned match policy DTO.
  * ``ResolveFromHintResult.was_existing_person_match`` is the only source of
    ``ops.lead.extra.is_reactivation``.
  * SOQL parameter shape, limit validation, and read-side DTO mapping.

Every service call passes ``_TENANT_ID`` (ENG-128); the assertions match
the post-sweep call shape.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.identity.schemas import MatchHintIn
from packages.ingest.schemas import NormalizedPersonHintIn, RawEventIn
from packages.ingest.sf_lead_service import SfLeadIngestService
from packages.interaction.schemas import EventIn

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _nested_transaction_cm() -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield

    return _cm()


def _record(
    *,
    sf_id: str = "00Q123",
    first: str | None = "Jane",
    last: str | None = "Doe",
    email: str | None = "jane@example.com",
    phone: str | None = "+15551234567",
    status: str = "Open",
    source: str = "Web",
    company: str | None = "Acme",
) -> dict[str, Any]:
    return {
        "Id": sf_id,
        "FirstName": first,
        "LastName": last,
        "Email": email,
        "Phone": phone,
        "LeadSource": source,
        "Status": status,
        "Company": company,
        "CreatedDate": "2026-05-07T20:00:00.000+0000",
    }


def _make_service(
    sf_records: list[dict[str, Any]] | None = None,
) -> tuple[SfLeadIngestService, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Build SfLeadIngestService with mocked SF + service collaborators."""
    session = MagicMock()
    session.begin_nested.side_effect = _nested_transaction_cm
    sf_client = MagicMock()
    sf_client.soql = AsyncMock(
        return_value={"records": sf_records or [], "totalSize": 0, "done": True}
    )

    service = SfLeadIngestService(session=session, sf_client=sf_client)
    service._ingest = MagicMock(
        spec=[
            "capture",
            "capture_normalized_person_hint",
            "max_payload_watermark",
            "latest_payload_values",
            "get_object_schema",
            "sync_object_schema",
        ]
    )
    service._ingest.capture = AsyncMock()
    service._ingest.capture_normalized_person_hint = AsyncMock()
    # First-run defaults: no watermark yet, nothing captured before.
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    # ENG-427: empty registry → _projection falls back to a live describe
    # (the bare mock client raises → caught) → static _SF_LEAD_PROJECTION.
    service._ingest.get_object_schema = AsyncMock(return_value=[])
    service._ingest.sync_object_schema = AsyncMock()
    service._identity = MagicMock(spec=["resolve_or_create_from_hint", "get_person"])
    service._identity.resolve_or_create_from_hint = AsyncMock()
    service._identity.get_person = AsyncMock()
    service._ops = MagicMock(spec=["upsert_lead", "list_recent_sf_leads"])
    service._ops.upsert_lead = AsyncMock()
    service._ops.list_recent_sf_leads = AsyncMock(return_value=[])
    service._interaction = MagicMock(spec=["create_event"])
    service._interaction.create_event = AsyncMock()
    return service, service._ingest, service._identity, service._ops, sf_client


def _person(
    *,
    person_id: uuid.UUID | None = None,
    display_name: str = "Jane Doe",
    email: str | None = None,
    phone: str | None = None,
) -> MagicMock:
    p = MagicMock()
    p.id = person_id or uuid.uuid4()
    p.display_name = display_name
    p.identifiers = []
    if email:
        ident = MagicMock()
        ident.kind = "email"
        ident.value = email
        p.identifiers.append(ident)
    if phone:
        ident = MagicMock()
        ident.kind = "phone"
        ident.value = phone
        p.identifiers.append(ident)
    return p


def _raw_event(raw_event_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=raw_event_id or uuid.uuid4())


def _hint(
    *,
    hint_id: uuid.UUID | None = None,
    raw_event_id: uuid.UUID | None = None,
    source_id: str = "00Q123",
    given_name: str | None = "Jane",
    family_name: str | None = "Doe",
    display_name: str | None = "Jane Doe",
    email_normalized: str | None = "jane@example.com",
    phone_normalized: str | None = "15551234567",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=hint_id or uuid.uuid4(),
        raw_event_id=raw_event_id or uuid.uuid4(),
        source_system="salesforce",
        source_kind="lead",
        source_id=source_id,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name,
        email_normalized=email_normalized,
        phone_normalized=phone_normalized,
        quality_flags={},
        meta={},
    )


def _resolve_result(
    person_uid: uuid.UUID,
    *,
    was_new_person: bool = False,
    was_existing_person_match: bool = False,
    was_source_link_recapture: bool = False,
    open_candidate: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        person_uid=person_uid,
        was_new_person=was_new_person,
        was_existing_person_match=was_existing_person_match,
        was_source_link_recapture=was_source_link_recapture,
        match_candidate_id=uuid.uuid4() if (was_existing_person_match or open_candidate) else None,
        open_candidate=open_candidate,
    )


def _upsert_result(
    *,
    was_created: bool = True,
    was_changed: bool = True,
    lead_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Mock UpsertLeadResult with .lead.id + .lead.created_at."""
    return SimpleNamespace(
        lead=SimpleNamespace(
            id=lead_id or uuid.uuid4(),
            created_at=datetime.now(UTC),
        ),
        was_created=was_created,
        was_changed=was_changed,
    )


def _wire_pull_result(
    *,
    ingest: MagicMock,
    identity: MagicMock,
    ops: MagicMock,
    raw_event: SimpleNamespace | None = None,
    hint: SimpleNamespace | None = None,
    person: Any | None = None,
    resolve_result: SimpleNamespace | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace, Any, SimpleNamespace]:
    raw_event = raw_event or _raw_event()
    hint = hint or _hint(raw_event_id=raw_event.id)
    person = person or _person(person_id=uuid.uuid4())
    resolve_result = resolve_result or _resolve_result(person.id, was_new_person=True)
    ingest.capture.return_value = raw_event
    ingest.capture_normalized_person_hint.return_value = hint
    identity.resolve_or_create_from_hint.return_value = resolve_result
    identity.get_person.return_value = person
    ops.upsert_lead.return_value = _upsert_result()
    return raw_event, hint, person, resolve_result


def _assert_match_hint(identity: MagicMock, hint: SimpleNamespace) -> MatchHintIn:
    identity.resolve_or_create_from_hint.assert_awaited_once()
    call = identity.resolve_or_create_from_hint.await_args
    assert call.args[0] == _TENANT_ID
    match_hint = call.args[1]
    assert isinstance(match_hint, MatchHintIn)
    assert match_hint.hint_id == hint.id
    assert match_hint.source_system == hint.source_system
    assert match_hint.source_kind == hint.source_kind
    assert match_hint.source_id == hint.source_id
    assert match_hint.given_name == hint.given_name
    assert match_hint.family_name == hint.family_name
    assert match_hint.display_name == hint.display_name
    assert match_hint.email_normalized == hint.email_normalized
    assert match_hint.phone_normalized == hint.phone_normalized
    assert match_hint.quality_flags == hint.quality_flags
    assert match_hint.meta == hint.meta
    return match_hint


def _event_payload_from(service: SfLeadIngestService) -> EventIn:
    interaction: Any = service._interaction
    interaction.create_event.assert_awaited_once()
    call = interaction.create_event.await_args
    assert call.args[0] == _TENANT_ID
    payload = call.args[1]
    assert isinstance(payload, EventIn)
    return payload


# --- limit validation ---


@pytest.mark.asyncio
async def test_pull_recent_rejects_limit_zero() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValueError):
        await service.pull_recent(_TENANT_ID, limit=0)


@pytest.mark.asyncio
async def test_pull_recent_rejects_limit_too_high() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValueError):
        await service.pull_recent(_TENANT_ID, limit=51)


# --- pull_recent: match-policy outcomes ---


@pytest.mark.asyncio
async def test_pull_recent_brand_new_person_maps_reactivation_false() -> None:
    rec = _record(sf_id="00Q1")
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    person = _person(email="jane@example.com", phone="+15551234567")
    raw_event, hint, _, _ = _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        person=person,
        resolve_result=_resolve_result(person.id, was_new_person=True),
    )

    out = await service.pull_recent(_TENANT_ID, limit=1)

    assert len(out) == 1
    assert out[0].sf_lead_id == "00Q1"
    assert out[0].is_reactivation is False
    assert out[0].email == "jane@example.com"
    assert out[0].phone == "+15551234567"
    _assert_match_hint(identity, hint)
    identity.get_person.assert_awaited_once_with(_TENANT_ID, person.id)
    upsert_meta = ops.upsert_lead.await_args.kwargs["provider_metadata"]
    assert upsert_meta["sf_lead_id"] == "00Q1"
    assert upsert_meta["is_reactivation"] is False

    capture_call = ingest.capture.await_args
    assert capture_call.args[0] == _TENANT_ID
    assert isinstance(capture_call.args[1], RawEventIn)
    assert capture_call.args[1].payload == rec
    hint_capture_call = ingest.capture_normalized_person_hint.await_args
    assert hint_capture_call.args[0] == _TENANT_ID
    hint_payload = hint_capture_call.args[1]
    assert isinstance(hint_payload, NormalizedPersonHintIn)
    assert hint_payload.raw_event_id == raw_event.id


@pytest.mark.asyncio
async def test_pull_recent_source_link_recapture_maps_reactivation_false() -> None:
    rec = _record(sf_id="00Q2")
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    person = _person()
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        person=person,
        resolve_result=_resolve_result(
            person.id, was_source_link_recapture=True
        ),
    )

    out = await service.pull_recent(_TENANT_ID, limit=1)

    assert out[0].is_reactivation is False
    assert ops.upsert_lead.await_args.kwargs["provider_metadata"][
        "is_reactivation"
    ] is False


@pytest.mark.asyncio
async def test_pull_recent_existing_person_match_maps_reactivation_true() -> None:
    rec = _record(sf_id="00Q3")
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    person = _person(email="jane@example.com", phone="+15551234567")
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        person=person,
        resolve_result=_resolve_result(
            person.id, was_existing_person_match=True
        ),
    )

    out = await service.pull_recent(_TENANT_ID, limit=1)

    assert out[0].is_reactivation is True
    assert ops.upsert_lead.await_args.kwargs["provider_metadata"][
        "is_reactivation"
    ] is True


@pytest.mark.asyncio
async def test_pull_recent_open_ambiguous_match_does_not_block_and_maps_false() -> None:
    rec = _record(sf_id="00Q4")
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    person = _person()
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        person=person,
        resolve_result=_resolve_result(
            person.id, was_new_person=True, open_candidate=True
        ),
    )

    out = await service.pull_recent(_TENANT_ID, limit=1)

    assert len(out) == 1
    assert out[0].person_uid == person.id
    assert out[0].is_reactivation is False
    assert ops.upsert_lead.await_args.kwargs["person_uid"] == person.id
    assert ops.upsert_lead.await_args.kwargs["provider_metadata"][
        "is_reactivation"
    ] is False


@pytest.mark.asyncio
async def test_pull_recent_no_identifiers_still_captures_hint_and_creates_new_person() -> None:
    rec = _record(sf_id="00Q5", email=None, phone=None)
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    raw_event = _raw_event()
    hint = _hint(
        raw_event_id=raw_event.id,
        source_id="00Q5",
        email_normalized=None,
        phone_normalized=None,
    )
    person = _person(email=None, phone=None)
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        raw_event=raw_event,
        hint=hint,
        person=person,
        resolve_result=_resolve_result(person.id, was_new_person=True),
    )

    out = await service.pull_recent(_TENANT_ID, limit=1)

    assert out[0].is_reactivation is False
    hint_capture_call = ingest.capture_normalized_person_hint.await_args
    hint_payload = hint_capture_call.args[1]
    assert hint_payload.raw_event_id == raw_event.id
    assert hint_payload.email is None
    assert hint_payload.phone is None
    match_hint = _assert_match_hint(identity, hint)
    assert match_hint.email_normalized is None
    assert match_hint.phone_normalized is None


@pytest.mark.asyncio
async def test_pull_recent_captures_raw_before_hint_and_identity_resolution() -> None:
    rec = _record(sf_id="00Q6")
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    raw_event = _raw_event()
    hint = _hint(raw_event_id=raw_event.id, source_id="00Q6")
    person = _person()
    calls: list[str] = []

    async def capture(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append("raw")
        return raw_event

    async def capture_hint(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append("hint")
        return hint

    async def resolve(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls.append("identity")
        return _resolve_result(person.id, was_new_person=True)

    ingest.capture.side_effect = capture
    ingest.capture_normalized_person_hint.side_effect = capture_hint
    identity.resolve_or_create_from_hint.side_effect = resolve
    identity.get_person.return_value = person
    ops.upsert_lead.return_value = _upsert_result()

    await service.pull_recent(_TENANT_ID, limit=1)

    assert calls == ["raw", "hint", "identity"]
    hint_payload = ingest.capture_normalized_person_hint.await_args.args[1]
    assert hint_payload.raw_event_id == raw_event.id


# --- pull_recent: interaction event emission ---


@pytest.mark.asyncio
async def test_pull_recent_new_lead_emits_lead_created_event() -> None:
    rec = {
        **_record(sf_id="00Q7"),
        "LastModifiedDate": "2026-05-08T20:00:00.000+0000",
        "Description": "free text must stay out",
    }
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    raw_event = _raw_event()
    lead_id = uuid.uuid4()
    person = _person(email="jane@example.com", phone="+15551234567")
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        raw_event=raw_event,
        hint=_hint(raw_event_id=raw_event.id, source_id="00Q7"),
        person=person,
        resolve_result=_resolve_result(person.id, was_new_person=True),
    )
    ops.upsert_lead.return_value = _upsert_result(
        was_created=True,
        was_changed=True,
        lead_id=lead_id,
    )

    await service.pull_recent(_TENANT_ID, limit=1)

    event = _event_payload_from(service)
    assert event.kind == "lead_created"
    assert event.person_uid == person.id
    assert event.source_provider == "salesforce"
    assert event.source_event_id == raw_event.id
    assert event.source_kind == "salesforce_lead"
    assert event.source_external_id == "00Q7"
    assert event.projection_ref_type == "ops_lead"
    assert event.projection_ref_id == lead_id
    assert event.data_class == "operational"
    assert event.review_status == "auto"
    assert event.payload == {
        "Status": "Open",
        "LeadSource": "Web",
        "Id": "00Q7",
        "CreatedDate": "2026-05-07T20:00:00.000+0000",
        "LastModifiedDate": "2026-05-08T20:00:00.000+0000",
    }
    assert event.occurred_at == datetime(2026, 5, 7, 20, 0, tzinfo=UTC)
    assert event.summary == "Lead created from Salesforce (id=00Q7)"
    assert "Jane" not in event.summary
    assert "jane@example.com" not in event.summary
    assert "Description" not in event.payload
    assert "Company" not in event.payload
    assert "Email" not in event.payload
    assert "Phone" not in event.payload
    assert "FirstName" not in event.payload
    assert "LastName" not in event.payload


@pytest.mark.asyncio
async def test_pull_recent_unchanged_lead_emits_no_interaction_event() -> None:
    rec = _record(sf_id="00Q8")
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    person = _person()
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        person=person,
        resolve_result=_resolve_result(person.id, was_source_link_recapture=True),
    )
    ops.upsert_lead.return_value = _upsert_result(
        was_created=False,
        was_changed=False,
    )

    await service.pull_recent(_TENANT_ID, limit=1)

    interaction: Any = service._interaction
    interaction.create_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changed_field", "record_updates"),
    [
        ("Status", {"Status": "Working - Contacted"}),
        ("LeadSource", {"LeadSource": "Phone Inquiry"}),
    ],
)
async def test_pull_recent_changed_lead_emits_lead_updated_event(
    changed_field: str,
    record_updates: dict[str, str],
) -> None:
    rec = {
        **_record(sf_id="00Q9"),
        **record_updates,
        "LastModifiedDate": "2026-05-09T21:30:00.000+0000",
    }
    service, ingest, identity, ops, _sf = _make_service(sf_records=[rec])
    raw_event = _raw_event()
    lead_id = uuid.uuid4()
    person = _person()
    _wire_pull_result(
        ingest=ingest,
        identity=identity,
        ops=ops,
        raw_event=raw_event,
        hint=_hint(raw_event_id=raw_event.id, source_id="00Q9"),
        person=person,
        resolve_result=_resolve_result(person.id, was_source_link_recapture=True),
    )
    ops.upsert_lead.return_value = _upsert_result(
        was_created=False,
        was_changed=True,
        lead_id=lead_id,
    )

    await service.pull_recent(_TENANT_ID, limit=1)

    event = _event_payload_from(service)
    assert changed_field in event.payload
    assert event.kind == "lead_updated"
    assert event.source_kind == "salesforce_lead"
    assert event.source_external_id == "00Q9"
    assert event.projection_ref_type == "ops_lead"
    assert event.projection_ref_id == lead_id
    assert event.data_class == "operational"
    assert event.review_status == "auto"
    assert event.occurred_at == datetime(2026, 5, 9, 21, 30, tzinfo=UTC)
    assert event.summary == "Lead updated in Salesforce (id=00Q9)"
    assert set(event.payload) <= {
        "Status",
        "LeadSource",
        "Id",
        "CreatedDate",
        "LastModifiedDate",
    }


# --- pull_recent: SOQL invocation shape ---


@pytest.mark.asyncio
async def test_pull_recent_invokes_soql_with_limit() -> None:
    service, _ingest, _identity, _ops, sf = _make_service(sf_records=[])
    await service.pull_recent(_TENANT_ID, limit=7)
    sf.soql.assert_awaited_once()
    query = sf.soql.await_args.args[0]
    assert "LIMIT 7" in query
    assert "FROM Lead" in query
    assert "ORDER BY CreatedDate DESC" in query


@pytest.mark.asyncio
async def test_pull_recent_for_sync_skips_bad_record_and_continues() -> None:
    good_a = _record(sf_id="00QGOODA", email="a@example.com")
    bad = _record(sf_id="00QBAD", email="bad@example.com")
    good_b = _record(sf_id="00QGOODB", email="b@example.com")
    service, _ingest, _identity, _ops, sf = _make_service(
        sf_records=[good_a, bad, good_b]
    )
    imported = [
        SimpleNamespace(sf_lead_id="00QGOODA"),
        SimpleNamespace(sf_lead_id="00QGOODB"),
    ]
    cast(Any, service)._capture_lead = AsyncMock(
        side_effect=[imported[0], ValueError("duplicate email"), imported[1]]
    )

    result = await service.pull_recent_for_sync(_TENANT_ID, limit=3)

    assert result.imported == imported
    assert result.imported_count == 2
    assert result.skipped_count == 1
    assert result.queried_count == 3
    assert result.model_dump() == {
        "imported_count": 2,
        "unchanged_count": 0,
        "skipped_count": 1,
        "queried_count": 3,
    }
    assert cast(Any, service)._capture_lead.await_count == 3
    assert sf.soql.await_args.args[0].endswith("LIMIT 3")


# --- list_recent ---


@pytest.mark.asyncio
async def test_list_recent_maps_lead_extra_to_dto() -> None:
    service, _ingest, identity, ops, _sf = _make_service()

    lead = MagicMock()
    lead.id = uuid.uuid4()
    lead.person_uid = uuid.uuid4()
    lead.created_at = datetime.now(UTC)
    lead.extra = {
        "sf_lead_id": "00Q9",
        "is_reactivation": True,
        "sf_created_at": "2026-05-07T20:00:00.000+0000",
        "company": "Acme",
        "lead_source": "Web",
        "lead_status": "Open",
    }
    ops.list_recent_sf_leads.return_value = [lead]
    person = _person(
        person_id=lead.person_uid,
        display_name="Jane Doe",
        email="jane@example.com",
        phone="+15551234567",
    )
    identity.get_person.return_value = person

    out = await service.list_recent(_TENANT_ID, limit=5)

    assert len(out) == 1
    assert out[0].sf_lead_id == "00Q9"
    assert out[0].is_reactivation is True
    assert out[0].email == "jane@example.com"
    assert out[0].phone == "+15551234567"
    assert out[0].company == "Acme"
    assert out[0].display_name == "Jane Doe"
