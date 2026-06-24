"""Service-level tests for identity — focus on D2 additions
(``resolve_or_create_person``, ``record_merge``).

Pure-Python validation paths run with mock sessions. Real-DB integration
(unique-constraint collisions, cross-pull idempotency) lands when a Postgres
test container is wired in.

Every service call passes a synthetic ``tenant_id`` (ENG-128) — the
mock repo doesn't care about the value, but the test contract mirrors
the live one.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import PersonUID, TenantId
from packages.identity.models import MergeEvent, Person, SourceLink
from packages.identity.schemas import PersonIdentifierIn, PersonIn
from packages.identity.service import (
    IdentityService,
    ResolveResult,
    normalise_phone,
)

# Synthetic tenant id reused across tests — value irrelevant when the repo
# is mocked, but the call shape must include it.
_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def test_normalise_phone_canonicalizes_us_forms_to_one_e164() -> None:
    """ENG-463: every form of one US number collapses to a single E.164
    match key (Twilio-dialable). This is the fix for the ~3,481 duplicate
    persons caused by 10-digit vs 11-digit storage."""
    canonical = "+19258125438"
    for form in (
        "925-812-5438",
        "9258125438",
        "19258125438",
        "+19258125438",
        "(925) 812-5438",
        "+1 925 812 5438",
    ):
        assert normalise_phone(form) == canonical
    # Explicit international numbers keep their own country code, including
    # the common '00' IDD prefix form.
    assert normalise_phone("+44 7911 123456") == "+447911123456"
    assert normalise_phone("0044 7911 123456") == "+447911123456"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Valid → E.164.
        ("(415) 555-1234", "+14155551234"),
        # Not a valid dialable number → digit-strip fallback (NOT E.164),
        # so junk is never promoted to a confident "+1…".
        ("+1 555 123 4567", "15551234567"),  # fictional 555 area code
        ("0000000000", "0000000000"),  # all-zeros
        ("1234567", "1234567"),  # too short for a US number
    ],
)
def test_normalise_phone_only_valid_numbers_become_e164(
    raw: str, expected: str
) -> None:
    assert normalise_phone(raw) == expected


def test_normalise_phone_rejects_unparseable() -> None:
    with pytest.raises(ValidationError):
        normalise_phone("abc")
    with pytest.raises(ValidationError):
        normalise_phone("12")  # < 7 digits


def _make_service() -> tuple[IdentityService, MagicMock]:
    """Build an IdentityService with a mock AsyncSession and its mock repo."""
    session = MagicMock()
    service = IdentityService(session)
    # Replace the auto-created repo with a mock so we can stub returns.
    service._repo = MagicMock()  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


# --- resolve_or_create_person validation ---


@pytest.mark.asyncio
async def test_resolve_or_create_rejects_unknown_source_system() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError) as excinfo:
        await service.resolve_or_create_person(
            _TENANT_ID,
            source_system="hubspot",  # not in SOURCE_SYSTEMS
            source_kind="lead",
            source_id="123",
        )
    assert "unknown source_system" in str(excinfo.value)


@pytest.mark.asyncio
async def test_resolve_or_create_rejects_unknown_source_kind() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.resolve_or_create_person(
            _TENANT_ID,
            source_system="salesforce",
            source_kind="prospect",  # not in SOURCE_KINDS
            source_id="123",
        )


@pytest.mark.asyncio
async def test_resolve_or_create_rejects_empty_source_id() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.resolve_or_create_person(
            _TENANT_ID,
            source_system="salesforce",
            source_kind="lead",
            source_id="",
        )


# --- resolve_or_create_person idempotency contract ---


@pytest.mark.asyncio
async def test_resolve_or_create_returns_existing_when_link_found() -> None:
    """If a source_link already exists, return its person and bump last_seen_at."""
    service, repo = _make_service()
    person_uid = uuid.uuid4()
    link = SourceLink(
        tenant_id=_TENANT_ID,
        person_uid=person_uid,
        source_system="salesforce",
        source_instance="salesforce-main",
        source_kind="lead",
        source_id="00Q5j000001abcd",
    )
    link.id = uuid.uuid4()
    person = Person()
    person.id = person_uid

    repo.find_source_link = AsyncMock(return_value=link)
    repo.touch_source_link = AsyncMock()
    repo.get_person = AsyncMock(return_value=person)

    result = await service.resolve_or_create_person(
        _TENANT_ID,
        source_system="salesforce",
        source_kind="lead",
        source_id="00Q5j000001abcd",
    )

    assert isinstance(result, ResolveResult)
    assert result.person is person
    assert result.was_created is False
    repo.touch_source_link.assert_awaited_once_with(_TENANT_ID, link.id)


@pytest.mark.asyncio
async def test_resolve_or_create_creates_when_link_missing(monkeypatch: Any) -> None:
    """If no source_link exists, create a Person + SourceLink and return was_created=True."""
    service, repo = _make_service()
    new_person = Person()
    new_person.id = uuid.uuid4()

    repo.find_source_link = AsyncMock(return_value=None)
    repo.add_source_link = AsyncMock()

    # Stub create_person on the service itself (not repo) since we're
    # testing the resolve_or_create flow, not Person creation internals.
    monkeypatch.setattr(service, "create_person", AsyncMock(return_value=new_person))

    result = await service.resolve_or_create_person(
        _TENANT_ID,
        source_system="carestack",
        source_kind="patient",
        source_id="12345",
    )

    assert result.person is new_person
    assert result.was_created is True
    repo.add_source_link.assert_awaited_once()
    # Verify the link was built with the expected fields
    saved_link = repo.add_source_link.await_args.args[0]
    assert saved_link.person_uid == new_person.id
    assert saved_link.source_system == "carestack"
    assert saved_link.source_instance == "carestack-main"
    assert saved_link.source_kind == "patient"
    assert saved_link.source_id == "12345"
    assert saved_link.tenant_id == _TENANT_ID


# --- record_merge validation ---


@pytest.mark.asyncio
async def test_record_merge_rejects_unknown_reason() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.record_merge(
            _TENANT_ID,
            surviving_person_uid=uuid.uuid4(),
            merged_person_uid=uuid.uuid4(),
            reason="just_because",  # not in MERGE_REASONS
        )


@pytest.mark.asyncio
async def test_record_merge_rejects_self_merge() -> None:
    service, _ = _make_service()
    person_uid = uuid.uuid4()
    with pytest.raises(ValidationError) as excinfo:
        await service.record_merge(
            _TENANT_ID,
            surviving_person_uid=person_uid,
            merged_person_uid=person_uid,
            reason="manual",
        )
    assert "merge a person into itself" in str(excinfo.value)


@pytest.mark.asyncio
async def test_record_merge_persists_event_with_evidence() -> None:
    service, repo = _make_service()
    surviving = uuid.uuid4()
    merged = uuid.uuid4()
    actor = uuid.uuid4()

    captured: dict[str, MergeEvent] = {}

    async def _capture(event: MergeEvent) -> MergeEvent:
        captured["event"] = event
        return event

    repo.add_merge_event = AsyncMock(side_effect=_capture)

    await service.record_merge(
        _TENANT_ID,
        surviving_person_uid=surviving,
        merged_person_uid=merged,
        reason="duplicate_email",
        evidence={"email": "shared@example.com"},
        performed_by_actor_id=actor,
    )

    event = captured["event"]
    assert event.surviving_person_uid == surviving
    assert event.merged_person_uid == merged
    assert event.reason == "duplicate_email"
    assert event.evidence == {"email": "shared@example.com"}
    assert event.performed_by_actor_id == actor
    assert event.tenant_id == _TENANT_ID


# --- contract: no-fuzzy-dedup. Two different source_ids = two different persons. ---


@pytest.mark.asyncio
async def test_resolve_or_create_does_not_match_by_email_across_providers(
    monkeypatch: Any,
) -> None:
    """Even if two source records share an email, resolve_or_create matches
    only on the source-instance-scoped external key. It will create separate
    persons and let cross-provider dedup happen later via record_merge.
    """
    service, repo = _make_service()
    new_person = Person()
    new_person.id = uuid.uuid4()

    repo.find_source_link = AsyncMock(return_value=None)
    repo.add_source_link = AsyncMock()
    monkeypatch.setattr(service, "create_person", AsyncMock(return_value=new_person))

    await service.resolve_or_create_person(
        _TENANT_ID,
        source_system="salesforce",
        source_kind="lead",
        source_id="00Q...001",
        hints=None,
    )
    await service.resolve_or_create_person(
        _TENANT_ID,
        source_system="carestack",
        source_kind="patient",
        source_id="12345",
        hints=None,
    )

    # Both calls hit "no link found" and produced separate add_source_link
    # invocations — each call creates an independent person.
    assert repo.add_source_link.await_count == 2


@pytest.mark.asyncio
async def test_resolve_or_create_scopes_same_external_id_by_source_instance(
    monkeypatch: Any,
) -> None:
    """The same provider id in two source instances creates independent links."""
    service, repo = _make_service()
    created_people = [Person(), Person()]
    created_people[0].id = uuid.uuid4()
    created_people[1].id = uuid.uuid4()

    repo.find_source_link = AsyncMock(return_value=None)
    repo.add_source_link = AsyncMock()
    monkeypatch.setattr(
        service,
        "create_person",
        AsyncMock(side_effect=created_people),
    )

    first = await service.resolve_or_create_person(
        _TENANT_ID,
        source_system="carestack",
        source_kind="patient",
        source_id="12345",
        source_instance="carestack-location-a",
    )
    second = await service.resolve_or_create_person(
        _TENANT_ID,
        source_system="carestack",
        source_kind="patient",
        source_id="12345",
        source_instance="carestack-location-b",
    )

    assert first.person.id != second.person.id
    assert repo.find_source_link.await_args_list[0].args == (
        _TENANT_ID,
        "carestack",
        "carestack-location-a",
        "patient",
        "12345",
    )
    assert repo.find_source_link.await_args_list[1].args == (
        _TENANT_ID,
        "carestack",
        "carestack-location-b",
        "patient",
        "12345",
    )
    saved_links = [call.args[0] for call in repo.add_source_link.await_args_list]
    assert [link.source_instance for link in saved_links] == [
        "carestack-location-a",
        "carestack-location-b",
    ]


# --- ENG-341: shared household contact (phone/email) is first-class ---


@pytest.mark.asyncio
async def test_create_person_attaches_shared_phone_owned_by_another() -> None:
    """A phone already owned by another person (household member, different
    DOB) is now ATTACHED to the new person too — shared household contacts are
    first-class (ENG-341 supersedes the ENG-340 skip). The partial unique index
    exempts phone/email, so the insert no longer violates a constraint."""
    service, repo = _make_service()
    repo.add_person = AsyncMock()
    repo.add_identifier = AsyncMock()

    payload = PersonIn(
        given_name="House",
        family_name="Member",
        identifiers=[PersonIdentifierIn(kind="phone", value="9164127886")],
    )

    person = await service.create_person(_TENANT_ID, payload)

    assert isinstance(person, Person)
    # create_person no longer pre-checks ownership for shared kinds — it just
    # attaches. The DB guards (per-person idempotency + partial unique) are the
    # backstop.
    repo.add_identifier.assert_awaited_once()
    added = repo.add_identifier.call_args.args[0]
    assert added.kind == "phone"
    assert added.value == "+19164127886"
    assert added.person_id == person.id


@pytest.mark.asyncio
async def test_create_person_dedupes_repeated_identifier_in_payload() -> None:
    """An identical (kind, value) repeated in ONE payload is inserted once, so
    the per-person ``uq_person_identifier_person_kind_value`` guard is never
    tripped by the caller's own duplicate."""
    service, repo = _make_service()
    repo.add_person = AsyncMock()
    repo.add_identifier = AsyncMock()

    payload = PersonIn(
        given_name="New",
        family_name="Patient",
        identifiers=[
            PersonIdentifierIn(kind="phone", value="9164127886"),
            PersonIdentifierIn(kind="phone", value="(916) 412-7886"),  # same E.164
            PersonIdentifierIn(kind="email", value="A@B.COM"),
        ],
    )

    await service.create_person(_TENANT_ID, payload)

    # phone deduped to one insert; email is a distinct (kind, value).
    assert repo.add_identifier.await_count == 2


# --- ENG-542 / ENG-341: attach_identifier (kind-aware backfill primitive) ---


@pytest.mark.asyncio
async def test_attach_identifier_adds_when_value_is_free() -> None:
    service, repo = _make_service()
    person = Person(tenant_id=_TENANT_ID, given_name="Lead", family_name="Person")
    repo.get_person = AsyncMock(return_value=person)
    repo.find_identifier = AsyncMock(return_value=None)
    repo.add_identifier = AsyncMock()
    status = await service.attach_identifier(
        _TENANT_ID, PersonUID(person.id), "phone", "(916) 730-7719"
    )
    assert status == "added"
    repo.add_identifier.assert_awaited_once()
    added = repo.add_identifier.call_args.args[0]
    # Stored value is E.164-normalised, not the raw formatted input.
    assert added.value == "+19167307719"
    assert added.kind == "phone"
    assert added.person_id == person.id


@pytest.mark.asyncio
async def test_attach_identifier_idempotent_when_self_already_holds_value() -> None:
    service, repo = _make_service()
    person = Person(tenant_id=_TENANT_ID, given_name="Lead", family_name="Person")
    existing = MagicMock()
    existing.person_id = person.id
    repo.get_person = AsyncMock(return_value=person)
    repo.find_identifier = AsyncMock(return_value=existing)
    repo.add_identifier = AsyncMock()
    status = await service.attach_identifier(
        _TENANT_ID, PersonUID(person.id), "phone", "+19167307719"
    )
    assert status == "exists"
    repo.add_identifier.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_identifier_attaches_shared_phone_owned_by_another() -> None:
    """ENG-341: a SHARED kind (phone/email) owned by another person is ATTACHED
    to this person too and returns ``"added"`` — no longer a collision."""
    service, repo = _make_service()
    person = Person(tenant_id=_TENANT_ID, given_name="Lead", family_name="Person")
    other_owner = MagicMock()
    other_owner.person_id = uuid.uuid4()  # a DIFFERENT person owns the value
    repo.get_person = AsyncMock(return_value=person)
    repo.find_identifier = AsyncMock(return_value=other_owner)
    repo.add_identifier = AsyncMock()
    status = await service.attach_identifier(
        _TENANT_ID, PersonUID(person.id), "phone", "+19167307719"
    )
    assert status == "added"
    repo.add_identifier.assert_awaited_once()
    added = repo.add_identifier.call_args.args[0]
    assert added.person_id == person.id
    assert added.kind == "phone"


@pytest.mark.asyncio
async def test_attach_identifier_collides_unique_kind_owned_by_another() -> None:
    """ENG-341: a UNIQUE kind (e.g. ``carestack_patient_id``) owned by another
    person STILL returns ``"collision"`` and is not attached — the partial
    unique index keeps these 1:1."""
    service, repo = _make_service()
    person = Person(tenant_id=_TENANT_ID, given_name="Lead", family_name="Person")
    other_owner = MagicMock()
    other_owner.person_id = uuid.uuid4()  # a DIFFERENT person owns the value
    repo.get_person = AsyncMock(return_value=person)
    repo.find_identifier = AsyncMock(return_value=other_owner)
    repo.add_identifier = AsyncMock()
    status = await service.attach_identifier(
        _TENANT_ID, PersonUID(person.id), "carestack_patient_id", "CS-123"
    )
    assert status == "collision"
    repo.add_identifier.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_identifier_returns_invalid_for_junk_phone() -> None:
    service, repo = _make_service()
    person = Person(tenant_id=_TENANT_ID)
    repo.get_person = AsyncMock(return_value=person)
    repo.find_identifier = AsyncMock(return_value=None)
    repo.add_identifier = AsyncMock()
    status = await service.attach_identifier(_TENANT_ID, PersonUID(person.id), "phone", "123")
    assert status == "invalid"
    repo.add_identifier.assert_not_awaited()
