"""Tests for ``IdentityService.resolve_or_create_from_hint`` (ENG-185).

Cover the full tier ladder against a mock :class:`IdentityRepository`:

* Tier 0 — exact source-link recapture (no candidate row written).
* Tier 1 — auto-accept (email_phone_name, phone_name, email_name).
* Tier 2 — open ambiguous (multiple candidates, name conflict, weak match).
* Fallback — brand-new person.
* Idempotency — repeat call with the same ``hint_id`` reuses the
  active candidate row.
* Tenant isolation — the repository is invoked with the calling tenant.
* PHI / raw-payload guard — ``meta`` / ``quality_flags`` deny-list still
  applies at the match policy boundary.

Pure-Python validation paths run with mocks; DB-level integration
(partial-unique collisions under concurrent writes) lands when a Postgres
test container is wired in.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId
from packages.identity.models import (
    MatchCandidate,
    Person,
    PersonIdentifier,
    SourceLink,
)
from packages.identity.schemas import MatchHintIn
from packages.identity.service import IdentityService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


# ----- fixtures / helpers ---------------------------------------------------


def _make_person(
    person_uid: uuid.UUID | None = None,
    *,
    given_name: str | None = "Alex",
    family_name: str | None = "Karpov",
    display_name: str | None = None,
    emails: tuple[str, ...] = (),
    phones: tuple[str, ...] = (),
    tenant_id: TenantId = _TENANT_ID,
) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name,
    )
    person.id = person_uid or uuid.uuid4()
    person.identifiers = []
    for email in emails:
        ident = PersonIdentifier(
            tenant_id=tenant_id,
            person_id=person.id,
            kind="email",
            value=email,
        )
        ident.id = uuid.uuid4()
        person.identifiers.append(ident)
    for phone in phones:
        ident = PersonIdentifier(
            tenant_id=tenant_id,
            person_id=person.id,
            kind="phone",
            value=phone,
        )
        ident.id = uuid.uuid4()
        person.identifiers.append(ident)
    return person


_UNSET = object()


def _hint(
    *,
    source_system: str = "salesforce",
    source_instance: str = "salesforce-main",
    source_kind: str = "lead",
    source_id: str = "00Q5j000001abcd",
    given_name: str | None = "Alex",
    family_name: str | None = "Karpov",
    display_name: str | None = None,
    email: str | None = "alex@example.com",
    phone: str | None = "15551234567",
    quality_flags: dict[str, object] | None = None,
    meta: dict[str, object] | None = None,
    hint_id: Any = _UNSET,
) -> MatchHintIn:
    if hint_id is _UNSET:
        hint_id = uuid.uuid4()
    return MatchHintIn(
        hint_id=hint_id,
        source_system=source_system,
        source_instance=source_instance,
        source_kind=source_kind,
        source_id=source_id,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name,
        email_normalized=email,
        phone_normalized=phone,
        quality_flags=quality_flags or {},
        meta=meta or {},
    )


def _make_service() -> tuple[IdentityService, MagicMock]:
    session = MagicMock()
    service = IdentityService(session)
    repo = MagicMock()
    service._repo = repo  # type: ignore[attr-defined]
    # Default stubs — every test overrides the ones it cares about.
    repo.find_source_link = AsyncMock(return_value=None)
    repo.touch_source_link = AsyncMock()
    # ``add_match_candidate`` calls ``_require_person_in_tenant`` for every
    # person reference; default to a truthy sentinel so tier-1 / tier-2 paths
    # pass the tenant existence check. Tests that need ``get_person`` to
    # return ``None`` (e.g. orphan source link) override this explicitly.
    repo.get_person = AsyncMock(return_value=object())
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[])
    repo.add_source_link = AsyncMock()
    repo.add_match_candidate = AsyncMock()
    repo.find_active_hint_candidate = AsyncMock(return_value=None)
    repo.add_person = AsyncMock()
    repo.add_identifier = AsyncMock()
    return service, repo


def _capture_match_candidates(repo: MagicMock) -> list[MatchCandidate]:
    captured: list[MatchCandidate] = []

    async def _capture(candidate: MatchCandidate) -> MatchCandidate:
        candidate.id = uuid.uuid4()
        captured.append(candidate)
        return candidate

    repo.add_match_candidate.side_effect = _capture
    return captured


def _stub_resolve_or_create_person(
    service: IdentityService, person: Person, was_created: bool = True
) -> AsyncMock:
    """Replace ``service.resolve_or_create_person`` with a deterministic stub.

    The tier-2 / fallback paths call this composite method (which itself
    chains find_source_link, create_person, add_source_link); stubbing it
    keeps the policy assertions focused on the entry-point behaviour.
    """
    from packages.identity.service import ResolveResult

    mock = AsyncMock(return_value=ResolveResult(person=person, was_created=was_created))
    service.resolve_or_create_person = mock  # type: ignore[assignment]
    return mock


# ----- source_system / source_kind validation -------------------------------


@pytest.mark.asyncio
async def test_rejects_unknown_source_system() -> None:
    service, _ = _make_service()
    hint = _hint(source_system="hubspot")
    with pytest.raises(ValidationError) as excinfo:
        await service.resolve_or_create_from_hint(_TENANT_ID, hint)
    assert "unknown source_system" in str(excinfo.value)


@pytest.mark.asyncio
async def test_rejects_unknown_source_kind() -> None:
    service, _ = _make_service()
    hint = _hint(source_kind="prospect")
    with pytest.raises(ValidationError):
        await service.resolve_or_create_from_hint(_TENANT_ID, hint)


# ----- PHI guard on metadata payloads ---------------------------------------


@pytest.mark.asyncio
async def test_rejects_phi_keys_in_meta() -> None:
    service, _ = _make_service()
    hint = _hint(meta={"signals": [{"date_of_birth": "1990-01-01"}]})
    with pytest.raises(ValidationError) as excinfo:
        await service.resolve_or_create_from_hint(_TENANT_ID, hint)
    assert excinfo.value.details["field"] == "meta"


@pytest.mark.asyncio
async def test_rejects_phi_keys_in_quality_flags() -> None:
    service, _ = _make_service()
    hint = _hint(quality_flags={"raw_payload": True})
    with pytest.raises(ValidationError) as excinfo:
        await service.resolve_or_create_from_hint(_TENANT_ID, hint)
    assert excinfo.value.details["field"] == "quality_flags"


# ----- Tier 0: source-link recapture ---------------------------------------


@pytest.mark.asyncio
async def test_tier0_source_link_recapture_returns_existing_person() -> None:
    service, repo = _make_service()
    person = _make_person()
    link = SourceLink(
        tenant_id=_TENANT_ID,
        person_uid=person.id,
        source_system="salesforce",
        source_instance="salesforce-main",
        source_kind="lead",
        source_id="00Q5j000001abcd",
    )
    link.id = uuid.uuid4()

    repo.find_source_link = AsyncMock(return_value=link)
    repo.get_person = AsyncMock(return_value=person)

    captured = _capture_match_candidates(repo)
    result = await service.resolve_or_create_from_hint(_TENANT_ID, _hint())

    assert result.person_uid == person.id
    assert result.was_source_link_recapture is True
    assert result.was_existing_person_match is False
    assert result.was_new_person is False
    assert result.match_candidate_id is None
    assert result.open_candidate is False

    repo.touch_source_link.assert_awaited_once_with(_TENANT_ID, link.id)
    repo.add_source_link.assert_not_awaited()
    assert captured == [], "Tier 0 must not write a match candidate row"
    repo.list_candidate_persons_by_identifiers.assert_not_awaited()


@pytest.mark.asyncio
async def test_tier0_source_link_pointing_at_missing_person_raises() -> None:
    """Defensive: a source_link whose person_uid no longer exists is a FK
    violation in production, but the service must surface it as a typed
    error rather than crash with NoneType."""
    service, repo = _make_service()
    link = SourceLink(
        tenant_id=_TENANT_ID,
        person_uid=uuid.uuid4(),
        source_system="salesforce",
        source_instance="salesforce-main",
        source_kind="lead",
        source_id="orphan",
    )
    link.id = uuid.uuid4()
    repo.find_source_link = AsyncMock(return_value=link)
    repo.get_person = AsyncMock(return_value=None)

    hint = _hint(source_id="orphan")
    with pytest.raises(NotFoundError):
        await service.resolve_or_create_from_hint(_TENANT_ID, hint)


# ----- Tier 1: auto-accept ladder ------------------------------------------


@pytest.mark.asyncio
async def test_tier1_auto_accept_email_phone_name() -> None:
    service, repo = _make_service()
    existing = _make_person(
        emails=("alex@example.com",), phones=("15551234567",),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    add_source_link_mock = AsyncMock()
    service.add_source_link = add_source_link_mock  # type: ignore[assignment]

    captured = _capture_match_candidates(repo)
    repo.get_person = AsyncMock(return_value=existing)

    result = await service.resolve_or_create_from_hint(_TENANT_ID, _hint())

    assert result.person_uid == existing.id
    assert result.was_existing_person_match is True
    assert result.was_new_person is False
    assert result.was_source_link_recapture is False
    assert result.open_candidate is False
    assert result.match_candidate_id is not None

    # Source link MUST be written BEFORE the candidate row so a partial
    # failure cannot leave the candidate row without the link.
    add_source_link_mock.assert_awaited_once()
    assert len(captured) == 1
    row = captured[0]
    assert row.status == "auto_accepted"
    assert row.match_rule == "email_phone_name"
    assert row.confidence == Decimal("0.99")
    assert row.candidate_person_uid == existing.id
    assert row.accepted_person_uid == existing.id
    assert row.source_person_uid is None
    assert row.evidence == {
        "email_match": True,
        "phone_match": True,
        "name_compatible": True,
    }


@pytest.mark.asyncio
async def test_tier1_auto_accept_phone_name() -> None:
    service, repo = _make_service()
    # Candidate has matching phone but no email — phone_name @ 0.95.
    existing = _make_person(emails=(), phones=("15551234567",))
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    # Hint has no email, just phone + name.
    result = await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(email=None)
    )

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "phone_name"
    assert captured[0].confidence == Decimal("0.95")


@pytest.mark.asyncio
async def test_tier1_auto_accept_email_name_no_phone_conflict() -> None:
    service, repo = _make_service()
    # Candidate matches email, has no phone at all → no conflict.
    existing = _make_person(emails=("alex@example.com",), phones=())
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    # Hint has email + phone (the hint's phone is OK because candidate has none).
    result = await service.resolve_or_create_from_hint(_TENANT_ID, _hint())

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "email_name"
    assert captured[0].confidence == Decimal("0.92")


@pytest.mark.asyncio
async def test_tier1_picks_highest_confidence_when_one_eligible() -> None:
    """Multiple candidates surface from the identifier lookup, but only one
    is policy-eligible. The eligible candidate wins."""
    service, repo = _make_service()
    weak = _make_person(
        emails=("alex@example.com",),
        phones=(),
        given_name="Different",
        family_name="Person",
    )
    # name conflict on weak (so it's not eligible despite email match).
    strong = _make_person(
        emails=("alex@example.com",), phones=("15551234567",)
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(
        return_value=[weak, strong]
    )

    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)
    await service.resolve_or_create_from_hint(_TENANT_ID, _hint())

    assert captured[0].candidate_person_uid == strong.id
    assert captured[0].match_rule == "email_phone_name"


# ----- Tier 2: open ambiguous ----------------------------------------------


@pytest.mark.asyncio
async def test_tier2_multiple_auto_accept_candidates_open_a_candidate() -> None:
    """Two candidates clear tier-1 rules → ambiguous, create new person.

    Both candidates have the hint's email and no phone (so neither has a
    phone conflict). Names are compatible. Each one would individually pass
    the ``email_name`` rule; together they collapse into Tier 2.
    """
    service, repo = _make_service()
    a = _make_person(emails=("alex@example.com",), phones=())
    b = _make_person(emails=("alex@example.com",), phones=())
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[a, b])

    new_person = _make_person()
    _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    # Hint with no phone so phone_conflict cannot fire on either candidate.
    result = await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(phone=None)
    )

    assert result.was_new_person is True
    assert result.open_candidate is True
    assert result.person_uid == new_person.id
    assert result.match_candidate_id is not None

    assert len(captured) == 1
    row = captured[0]
    assert row.status == "open"
    assert row.match_rule == "email_only_ambiguous"
    assert row.confidence == Decimal("0.70")
    assert row.candidate_person_uid == a.id  # first candidate is primary
    assert row.source_person_uid == new_person.id
    assert row.accepted_person_uid is None
    assert row.conflicts["auto_accept_eligible"] == 2


@pytest.mark.asyncio
async def test_tier2_name_conflict_blocks_auto_accept() -> None:
    """Single candidate matches email but name differs → open."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("alex@example.com",),
        given_name="Maria",
        family_name="Petrov",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    new_person = _make_person()
    _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    # Hint phone is None so phone_conflict cannot fire — only name mismatch
    # drives the decision.
    result = await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(phone=None)
    )

    assert result.open_candidate is True
    assert result.was_new_person is True
    assert captured[0].status == "open"
    assert captured[0].match_rule == "email_only_ambiguous"
    assert captured[0].conflicts["name_compatible"] is False


@pytest.mark.asyncio
async def test_tier2_phone_only_ambiguous_rule() -> None:
    service, repo = _make_service()
    # Candidate matches by phone but name differs; no email at all.
    existing = _make_person(
        emails=(),
        phones=("15551234567",),
        given_name="Different",
        family_name="Person",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    new_person = _make_person()
    mock = _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(email=None)
    )

    assert result.open_candidate is True
    assert captured[0].match_rule == "phone_only_ambiguous"
    assert mock.await_args is not None
    new_person_hints = mock.await_args.kwargs["hints"]
    assert [ident.kind for ident in new_person_hints.identifiers] == []


@pytest.mark.asyncio
async def test_tier2_email_only_ambiguous_omits_matched_identifier_on_new_person() -> None:
    service, repo = _make_service()
    existing = _make_person(
        emails=("alex@example.com",),
        phones=(),
        given_name="Different",
        family_name="Person",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    new_person = _make_person()
    mock = _stub_resolve_or_create_person(service, new_person)
    _capture_match_candidates(repo)

    await service.resolve_or_create_from_hint(_TENANT_ID, _hint(phone=None))

    assert mock.await_args is not None
    new_person_hints = mock.await_args.kwargs["hints"]
    assert [ident.kind for ident in new_person_hints.identifiers] == []


# ----- Fallback: brand-new person ------------------------------------------


@pytest.mark.asyncio
async def test_fallback_creates_brand_new_person_when_no_candidates() -> None:
    service, repo = _make_service()
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[])

    new_person = _make_person()
    mock = _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(_TENANT_ID, _hint())

    assert result.was_new_person is True
    assert result.was_existing_person_match is False
    assert result.was_source_link_recapture is False
    assert result.open_candidate is False
    assert result.match_candidate_id is None
    assert result.person_uid == new_person.id

    mock.assert_awaited_once()
    assert captured == [], "Fallback must not write a match candidate row"


# ----- Idempotency ---------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_auto_accept_reuses_active_candidate() -> None:
    service, repo = _make_service()
    existing = _make_person(
        emails=("alex@example.com",), phones=("15551234567",)
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    existing_row = MatchCandidate(
        tenant_id=_TENANT_ID,
        hint_id=uuid.uuid4(),
        candidate_person_uid=existing.id,
        accepted_person_uid=existing.id,
        status="auto_accepted",
        match_rule="email_phone_name",
        confidence=Decimal("0.99"),
        evidence={},
        conflicts={},
    )
    existing_row.id = uuid.uuid4()
    repo.find_active_hint_candidate = AsyncMock(return_value=existing_row)

    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    hint = _hint(hint_id=existing_row.hint_id)
    result = await service.resolve_or_create_from_hint(_TENANT_ID, hint)

    assert result.match_candidate_id == existing_row.id
    assert result.was_existing_person_match is True
    assert captured == [], "Idempotent re-call must not duplicate the candidate"
    # Source link write is also skipped on the idempotent path — the previous
    # auto-accept already created it.
    assert service.add_source_link.await_count == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_idempotent_open_reuses_active_candidate() -> None:
    service, repo = _make_service()
    a = _make_person(emails=("alex@example.com",), phones=())
    b = _make_person(emails=("alex@example.com",), phones=())
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[a, b])

    new_person = _make_person()
    _stub_resolve_or_create_person(service, new_person)

    existing_row = MatchCandidate(
        tenant_id=_TENANT_ID,
        hint_id=uuid.uuid4(),
        candidate_person_uid=a.id,
        source_person_uid=new_person.id,
        status="open",
        match_rule="email_only_ambiguous",
        confidence=Decimal("0.70"),
        evidence={},
        conflicts={},
    )
    existing_row.id = uuid.uuid4()
    repo.find_active_hint_candidate = AsyncMock(return_value=existing_row)
    captured = _capture_match_candidates(repo)

    hint = _hint(hint_id=existing_row.hint_id, phone=None)
    result = await service.resolve_or_create_from_hint(_TENANT_ID, hint)

    assert result.match_candidate_id == existing_row.id
    assert result.open_candidate is True
    assert captured == [], "Idempotent re-call must not duplicate the open row"


@pytest.mark.asyncio
async def test_hint_id_none_disables_active_candidate_lookup() -> None:
    """Without a hint_id we cannot dedup, so the active-candidate guard is
    skipped and a fresh row is written."""
    service, repo = _make_service()
    existing = _make_person(emails=("alex@example.com",), phones=("15551234567",))
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    hint = _hint(hint_id=None)
    await service.resolve_or_create_from_hint(_TENANT_ID, hint)

    repo.find_active_hint_candidate.assert_not_awaited()
    assert len(captured) == 1


# ----- Tenant scoping ------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_tenant_id_to_candidate_lookup() -> None:
    service, repo = _make_service()
    other_tenant: TenantId = TenantId(uuid.uuid4())
    _stub_resolve_or_create_person(service, _make_person(tenant_id=other_tenant))
    await service.resolve_or_create_from_hint(other_tenant, _hint())
    repo.list_candidate_persons_by_identifiers.assert_awaited_once_with(
        other_tenant, "alex@example.com", "15551234567"
    )


@pytest.mark.asyncio
async def test_tier0_passes_tenant_id_to_source_link_lookup() -> None:
    service, repo = _make_service()
    other_tenant: TenantId = TenantId(uuid.uuid4())
    _stub_resolve_or_create_person(service, _make_person(tenant_id=other_tenant))
    await service.resolve_or_create_from_hint(other_tenant, _hint())
    repo.find_source_link.assert_awaited_once_with(
        other_tenant, "salesforce", "salesforce-main", "lead", "00Q5j000001abcd"
    )


@pytest.mark.asyncio
async def test_tier0_source_link_recapture_requires_same_source_instance() -> None:
    service, repo = _make_service()
    first_instance_person = _make_person()
    second_instance_person = _make_person()

    async def find_link(
        _tenant_id: TenantId,
        _source_system: str,
        source_instance: str,
        _source_kind: str,
        _source_id: str,
    ) -> SourceLink | None:
        if source_instance != "carestack-location-a":
            return None
        link = SourceLink(
            tenant_id=_TENANT_ID,
            person_uid=first_instance_person.id,
            source_system="carestack",
            source_instance=source_instance,
            source_kind="patient",
            source_id="12345",
        )
        link.id = uuid.uuid4()
        return link

    repo.find_source_link = AsyncMock(side_effect=find_link)
    repo.get_person = AsyncMock(return_value=first_instance_person)
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[])
    _stub_resolve_or_create_person(service, second_instance_person)

    recaptured = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(
            source_system="carestack",
            source_instance="carestack-location-a",
            source_kind="patient",
            source_id="12345",
            email=None,
            phone=None,
        ),
    )
    created = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(
            source_system="carestack",
            source_instance="carestack-location-b",
            source_kind="patient",
            source_id="12345",
            email=None,
            phone=None,
        ),
    )

    assert recaptured.person_uid == first_instance_person.id
    assert recaptured.was_source_link_recapture is True
    assert created.person_uid == second_instance_person.id
    assert created.was_new_person is True


# ----- ENG-543: word-level name compatibility ------------------------------


@pytest.mark.asyncio
async def test_reversed_first_last_auto_links_no_duplicate() -> None:
    """Reversed First/Last ('Newton Patrick' vs 'Patrick Newton') + a phone
    match must auto-link to the existing person via ``phone_name`` and write
    NO new person."""
    service, repo = _make_service()
    existing = _make_person(
        given_name="Patrick",
        family_name="Newton",
        emails=(),
        phones=("19167307719",),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    repo.get_person = AsyncMock(return_value=existing)
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    create_person_mock = _stub_resolve_or_create_person(service, _make_person())
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(given_name="Newton", family_name="Patrick", email=None,
              phone="19167307719"),
    )

    assert result.was_existing_person_match is True
    assert result.was_new_person is False
    assert result.open_candidate is False
    assert result.person_uid == existing.id
    create_person_mock.assert_not_awaited()  # no duplicate person created
    assert captured[0].status == "auto_accepted"
    assert captured[0].match_rule == "phone_name"
    assert captured[0].confidence == Decimal("0.95")


@pytest.mark.asyncio
async def test_everything_in_one_field_auto_links() -> None:
    """Lead packed the whole name into ``family_name`` (given empty); the
    word-set still matches the existing person, so it auto-links."""
    service, repo = _make_service()
    existing = _make_person(
        given_name="Patrick",
        family_name="Newton",
        phones=("19167307719",),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    repo.get_person = AsyncMock(return_value=existing)
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(given_name=None, family_name="Newton Patrick", email=None,
              phone="19167307719"),
    )

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "phone_name"


@pytest.mark.asyncio
async def test_empty_lead_name_and_phone_no_email_auto_links_via_phone_name() -> None:
    """Empty-ish lead: only a name + phone (no email) still auto-links to the
    existing person through ``phone_name``."""
    service, repo = _make_service()
    existing = _make_person(
        given_name="Patrick",
        family_name="Newton",
        emails=(),
        phones=("19167307719",),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    repo.get_person = AsyncMock(return_value=existing)
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(given_name="Patrick", family_name="Newton", email=None,
              phone="19167307719"),
    )

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "phone_name"
    assert captured[0].confidence == Decimal("0.95")


@pytest.mark.asyncio
async def test_phone_match_with_different_name_stays_open() -> None:
    """A shared phone but a genuinely DIFFERENT name (household member) must
    NOT auto-merge — it stays Tier-2/open."""
    service, repo = _make_service()
    existing = _make_person(
        given_name="Maria",
        family_name="Petrov",
        emails=(),
        phones=("19167307719",),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    new_person = _make_person()
    _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(given_name="Patrick", family_name="Newton", email=None,
              phone="19167307719"),
    )

    assert result.open_candidate is True
    assert result.was_new_person is True
    assert captured[0].status == "open"
    assert captured[0].match_rule == "phone_only_ambiguous"
    assert captured[0].conflicts["name_compatible"] is False


@pytest.mark.asyncio
async def test_middle_name_subset_auto_links() -> None:
    """A middle name / initial present on only one side ('John Smith' vs
    'John A Smith') is a subset, so it auto-links."""
    service, repo = _make_service()
    existing = _make_person(
        given_name="John",
        family_name="Smith",
        display_name="John A Smith",
        phones=("15551234567",),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    repo.get_person = AsyncMock(return_value=existing)
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(given_name="John", family_name="Smith", email=None,
              phone="15551234567"),
    )

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "phone_name"


@pytest.mark.asyncio
async def test_dob_veto_wins_over_phone_and_name_match() -> None:
    """ENG-309 DOB hard veto still fires ahead of a phone+name match: a
    different DOB blocks the auto-accept even though phone and (reversed)
    name are compatible. The candidate is dropped → brand-new person, no
    candidate row."""
    from datetime import date

    service, repo = _make_service()
    existing = _make_person(
        given_name="Patrick",
        family_name="Newton",
        phones=("19167307719",),
    )
    existing.dob = date(1968, 4, 19)
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    new_person = _make_person()
    mock = _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    hint = _hint(
        given_name="Newton", family_name="Patrick", email=None,
        phone="19167307719",
    )
    hint = hint.model_copy(update={"dob": date(1990, 1, 1)})
    result = await service.resolve_or_create_from_hint(_TENANT_ID, hint)

    assert result.was_new_person is True
    assert result.was_existing_person_match is False
    assert result.open_candidate is False
    assert result.person_uid == new_person.id
    mock.assert_awaited_once()
    assert captured == [], "DOB-vetoed candidate must not write a candidate row"


# ----- Source-link write order under auto-accept ---------------------------


@pytest.mark.asyncio
async def test_auto_accept_writes_source_link_before_candidate() -> None:
    service, repo = _make_service()
    existing = _make_person(emails=("alex@example.com",), phones=("15551234567",))
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    call_order: list[str] = []

    async def _record_link(*args: Any, **kwargs: Any) -> SourceLink:
        call_order.append("source_link")
        out = SourceLink(
            tenant_id=_TENANT_ID,
            person_uid=existing.id,
            source_system="salesforce",
            source_instance="salesforce-main",
            source_kind="lead",
            source_id="00Q5j000001abcd",
        )
        out.id = uuid.uuid4()
        return out

    async def _record_candidate(candidate: MatchCandidate) -> MatchCandidate:
        call_order.append("match_candidate")
        candidate.id = uuid.uuid4()
        return candidate

    service.add_source_link = AsyncMock(side_effect=_record_link)  # type: ignore[assignment]
    repo.add_match_candidate = AsyncMock(side_effect=_record_candidate)

    await service.resolve_or_create_from_hint(_TENANT_ID, _hint())
    assert call_order == ["source_link", "match_candidate"]
