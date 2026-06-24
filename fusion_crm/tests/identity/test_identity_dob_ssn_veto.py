"""Tests for the ENG-309 DOB / SSN hard veto in
:meth:`IdentityService.resolve_or_create_from_hint`.

The veto matters because the Torosyan card in production merged two distinct
humans (Eduard, DOB 1968-04-19, SSN 623-35-9385; Gaiane, DOB 1972-08-20,
SSN 602-37-8893) into one ``person.id`` -- household signals (phone, last
name, address, accountId) all matched but they are different patients. The
veto refuses to merge across mismatched DOB or SSN regardless of how many
soft signals overlap. Soft signals (phone, email, name) still drive the
positive tier ladder when the veto is silent (both sides agree or one side
is missing).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.identity.models import MatchCandidate, Person, PersonIdentifier
from packages.identity.schemas import MatchHintIn
from packages.identity.service import IdentityService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_person(
    person_uid: uuid.UUID | None = None,
    *,
    given_name: str | None = "Eduard",
    family_name: str | None = "Torosyan",
    display_name: str | None = None,
    emails: tuple[str, ...] = (),
    phones: tuple[str, ...] = (),
    dob: date | None = None,
    ssn: str | None = None,
    tenant_id: TenantId = _TENANT_ID,
) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name,
        dob=dob,
        ssn=ssn,
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
    source_system: str = "carestack",
    source_instance: str = "carestack-main",
    source_kind: str = "patient",
    source_id: str = "1460847",
    given_name: str | None = "Eduard",
    family_name: str | None = "Torosyan",
    display_name: str | None = None,
    email: str | None = "torosyan@example.com",
    phone: str | None = "15551234567",
    dob: date | None = None,
    ssn: str | None = None,
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
        dob=dob,
        ssn=ssn,
    )


def _make_service() -> tuple[IdentityService, MagicMock]:
    session = MagicMock()
    service = IdentityService(session)
    repo = MagicMock()
    service._repo = repo  # type: ignore[attr-defined]
    repo.find_source_link = AsyncMock(return_value=None)
    repo.touch_source_link = AsyncMock()
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
    from packages.identity.service import ResolveResult

    mock = AsyncMock(return_value=ResolveResult(person=person, was_created=was_created))
    service.resolve_or_create_person = mock  # type: ignore[assignment]
    return mock


# ----- positive paths: veto silent -----------------------------------------


@pytest.mark.asyncio
async def test_same_dob_same_ssn_phone_match_auto_accepts() -> None:
    """Same human re-observed: DOB+SSN agree, phone+name match -> tier 1."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn="623359385",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(dob=date(1968, 4, 19), ssn="623-35-9385"),
    )

    assert result.was_existing_person_match is True
    assert result.was_new_person is False
    assert captured[0].match_rule == "email_phone_name"
    assert captured[0].confidence == Decimal("0.99")


@pytest.mark.asyncio
async def test_same_dob_no_ssn_either_side_auto_accepts_on_soft_signals() -> None:
    """Soft path: DOB agrees, neither side has SSN -> tier 1 still fires."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn=None,
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(dob=date(1968, 4, 19), ssn=None),
    )

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "email_phone_name"


@pytest.mark.asyncio
async def test_dob_present_one_side_ssn_missing_still_auto_accepts() -> None:
    """Real-world: provider sometimes pushes DOB without SSN; the partial
    signal is enough as long as DOB agrees and soft signals match."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn="623359385",  # candidate has SSN
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    # Hint missing SSN -> veto cannot fire on SSN, DOB agrees.
    await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(dob=date(1968, 4, 19), ssn=None),
    )

    assert len(captured) == 1
    assert captured[0].match_rule == "email_phone_name"


@pytest.mark.asyncio
async def test_both_sides_missing_dob_and_ssn_regression_path_still_works() -> None:
    """Persons pre-dating ENG-309 have no DOB/SSN. Without the new signal,
    the old tier ladder must still produce the same auto-accept."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=None,
        ssn=None,
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(dob=None, ssn=None)
    )

    assert result.was_existing_person_match is True
    assert captured[0].match_rule == "email_phone_name"


@pytest.mark.asyncio
async def test_ssn_normalisation_dashes_and_whitespace_compare_equal() -> None:
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn="623359385",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    # Hint has the dash-separated form; resolver must strip + compare equal.
    result = await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(dob=date(1968, 4, 19), ssn="  623-35-9385  ")
    )

    assert result.was_existing_person_match is True
    assert len(captured) == 1


# ----- veto paths: must refuse to merge ------------------------------------


@pytest.mark.asyncio
async def test_dob_mismatch_refuses_merge_even_with_all_soft_signals() -> None:
    """The Torosyan reproducer.

    Existing person is Gaiane (DOB 1972-08-20). Incoming hint is Eduard
    (DOB 1968-04-19). Phone, email, last name, even accountId-style
    soft signals all match (same household). The veto must REFUSE to
    auto-accept and a brand-new person must be created.
    """
    service, repo = _make_service()
    gaiane = _make_person(
        person_uid=uuid.uuid4(),
        given_name="Gaiane",
        family_name="Torosyan",
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1972, 8, 20),
        ssn="602378893",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[gaiane])

    eduard = _make_person(
        given_name="Eduard",
        family_name="Torosyan",
        dob=date(1968, 4, 19),
        ssn="623359385",
    )
    mock = _stub_resolve_or_create_person(service, eduard)
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(
            source_id="1460847",
            given_name="Eduard",
            family_name="Torosyan",
            email="torosyan@example.com",
            phone="15551234567",
            dob=date(1968, 4, 19),
            ssn="623359385",
        ),
    )

    assert result.was_new_person is True
    assert result.was_existing_person_match is False
    assert result.person_uid == eduard.id
    assert result.person_uid != gaiane.id, "must NEVER merge across DOB mismatch"
    # Vetoed candidate must not become a tier-2 open primary either.
    assert captured == [], "vetoed candidate cannot leave an open match row"
    mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_ssn_mismatch_refuses_merge_even_with_all_soft_signals() -> None:
    """Mirror of the DOB case: SSN differs (same household, e.g. spouses
    sharing every soft signal except SSN). Must not merge."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn="602378893",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])

    new_person = _make_person(dob=date(1968, 4, 19), ssn="623359385")
    _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(dob=date(1968, 4, 19), ssn="623-35-9385"),
    )

    assert result.was_new_person is True
    assert result.person_uid != existing.id
    assert captured == []


@pytest.mark.asyncio
async def test_dob_mismatch_with_multiple_candidates_drops_vetoed_only() -> None:
    """One candidate is vetoed by DOB, another agrees. Eligible one wins
    via tier 1."""
    service, repo = _make_service()
    gaiane = _make_person(
        given_name="Gaiane",
        family_name="Torosyan",
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1972, 8, 20),
        ssn="602378893",
    )
    eduard = _make_person(
        given_name="Eduard",
        family_name="Torosyan",
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn="623359385",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(
        return_value=[gaiane, eduard]
    )
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(
            given_name="Eduard",
            family_name="Torosyan",
            dob=date(1968, 4, 19),
            ssn="623359385",
        ),
    )

    assert result.person_uid == eduard.id
    assert result.was_existing_person_match is True
    assert len(captured) == 1
    assert captured[0].candidate_person_uid == eduard.id


@pytest.mark.asyncio
async def test_all_candidates_vetoed_creates_new_person() -> None:
    service, repo = _make_service()
    a = _make_person(
        emails=("shared@example.com",),
        phones=("15551234567",),
        dob=date(1972, 8, 20),
    )
    b = _make_person(
        emails=("shared@example.com",),
        phones=("15551234567",),
        dob=date(1975, 1, 1),
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[a, b])

    new_person = _make_person(dob=date(1968, 4, 19))
    mock = _stub_resolve_or_create_person(service, new_person)
    captured = _capture_match_candidates(repo)

    result = await service.resolve_or_create_from_hint(
        _TENANT_ID,
        _hint(email="shared@example.com", phone="15551234567", dob=date(1968, 4, 19)),
    )

    assert result.was_new_person is True
    assert captured == []
    mock.assert_awaited_once()


# ----- backfill behavior on auto-accept ------------------------------------


@pytest.mark.asyncio
async def test_auto_accept_backfills_missing_dob_on_matched_person() -> None:
    """When the matched person has no DOB stored but the hint does, the
    backfill writes the hint's value -- otherwise the next provider with a
    DOB-mismatch couldn't be vetoed against this person."""
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=None,
        ssn=None,
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    _capture_match_candidates(repo)

    await service.resolve_or_create_from_hint(
        _TENANT_ID, _hint(dob=date(1968, 4, 19), ssn="623-35-9385")
    )

    assert existing.dob == date(1968, 4, 19)
    assert existing.ssn == "623359385"  # normalised digit-only form


@pytest.mark.asyncio
async def test_auto_accept_does_not_overwrite_existing_dob() -> None:
    """If the matched person already has a stored DOB and the hint also
    carries one, the veto would have fired if they differed. By the time we
    get here, either they agree or the hint's value is None. Either way we
    must not overwrite the stored value with None or with a duplicate.
    """
    service, repo = _make_service()
    existing = _make_person(
        emails=("torosyan@example.com",),
        phones=("15551234567",),
        dob=date(1968, 4, 19),
        ssn="623359385",
    )
    repo.list_candidate_persons_by_identifiers = AsyncMock(return_value=[existing])
    service.add_source_link = AsyncMock()  # type: ignore[assignment]
    _capture_match_candidates(repo)

    # Hint has no DOB / SSN; backfill must be a no-op.
    await service.resolve_or_create_from_hint(_TENANT_ID, _hint(dob=None, ssn=None))

    assert existing.dob == date(1968, 4, 19)
    assert existing.ssn == "623359385"
