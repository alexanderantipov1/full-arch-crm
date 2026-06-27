"""Service-level tests for ``IdentityService.add_match_candidate`` (ENG-182).

Pure-Python validation paths run with mock sessions. Real-DB integration
(unique-constraint collisions, accepted-status invariants under concurrent
writes) lands when a Postgres test container is wired in.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId
from packages.identity.models import MatchCandidate, make_person_pair_key
from packages.identity.schemas import MatchCandidateIn
from packages.identity.service import IdentityService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_service() -> tuple[IdentityService, MagicMock]:
    session = MagicMock()
    service = IdentityService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._repo.get_person = AsyncMock(return_value=object())  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


def _payload(**overrides: object) -> MatchCandidateIn:
    base: dict[str, object] = {
        "hint_id": uuid.uuid4(),
        "source_person_uid": uuid.uuid4(),
        "candidate_person_uid": uuid.uuid4(),
        "accepted_person_uid": None,
        "status": "open",
        "match_rule": "email_phone_name",
        "confidence": Decimal("0.9000"),
        "evidence": {},
        "conflicts": {},
        "decided_by_actor_id": None,
    }
    base.update(overrides)
    return MatchCandidateIn(**base)


# --- status validation ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_unknown_status() -> None:
    service, _ = _make_service()
    payload = _payload(status="pending")
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "unknown match_candidate status" in str(excinfo.value)


# --- match_rule validation ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_unknown_match_rule() -> None:
    service, _ = _make_service()
    payload = _payload(match_rule="fuzzy_email")
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "unknown match_candidate match_rule" in str(excinfo.value)


# --- confidence validation ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_confidence_above_one() -> None:
    service, _ = _make_service()
    # Pydantic enforces the Decimal range at the DTO boundary; build the
    # payload via direct construct to bypass Pydantic and exercise the
    # service-layer guard.
    payload = MatchCandidateIn.model_construct(
        hint_id=None,
        source_person_uid=None,
        candidate_person_uid=uuid.uuid4(),
        accepted_person_uid=None,
        status="open",
        match_rule="email_name",
        confidence=Decimal("1.5"),
        evidence={},
        conflicts={},
        decided_by_actor_id=None,
    )
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "confidence must be between 0 and 1" in str(excinfo.value)


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_confidence_below_zero() -> None:
    service, _ = _make_service()
    payload = MatchCandidateIn.model_construct(
        hint_id=None,
        source_person_uid=None,
        candidate_person_uid=uuid.uuid4(),
        accepted_person_uid=None,
        status="open",
        match_rule="email_name",
        confidence=Decimal("-0.01"),
        evidence={},
        conflicts={},
        decided_by_actor_id=None,
    )
    with pytest.raises(ValidationError):
        await service.add_match_candidate(_TENANT_ID, payload)


# --- self-match validation ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_self_match() -> None:
    service, _ = _make_service()
    person_uid = uuid.uuid4()
    payload = _payload(
        source_person_uid=person_uid,
        candidate_person_uid=person_uid,
    )
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "must differ" in str(excinfo.value)


# --- accepted-person invariant ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_accepted_uid_on_open_status() -> None:
    service, _ = _make_service()
    payload = _payload(
        status="open",
        accepted_person_uid=uuid.uuid4(),
    )
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "only valid for accepted statuses" in str(excinfo.value)


@pytest.mark.asyncio
async def test_add_match_candidate_requires_accepted_uid_when_accepted() -> None:
    service, _ = _make_service()
    payload = _payload(
        status="accepted",
        accepted_person_uid=None,
    )
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "required for accepted statuses" in str(excinfo.value)


# --- evidence / conflicts PHI rejection ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_phi_keys_in_evidence() -> None:
    service, _ = _make_service()
    payload = _payload(evidence={"dob": "1990-01-01"})
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert "forbidden keys" in str(excinfo.value)
    assert excinfo.value.details["field"] == "evidence"


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_raw_payload_in_conflicts() -> None:
    service, _ = _make_service()
    payload = _payload(conflicts={"raw_payload": {"sf_lead": "..."}})
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert excinfo.value.details["field"] == "conflicts"


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_nested_phi_keys() -> None:
    service, _ = _make_service()
    payload = _payload(evidence={"signals": [{"date_of_birth": "1990-01-01"}]})
    with pytest.raises(ValidationError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)
    assert excinfo.value.details["field"] == "evidence"
    assert excinfo.value.details["keys"] == ["signals[0].date_of_birth"]


# --- tenant-scoped person references ---


@pytest.mark.asyncio
async def test_add_match_candidate_rejects_candidate_person_outside_tenant() -> None:
    service, repo = _make_service()
    repo.get_person = AsyncMock(return_value=None)

    payload = _payload()
    with pytest.raises(NotFoundError) as excinfo:
        await service.add_match_candidate(_TENANT_ID, payload)

    assert excinfo.value.details["field"] == "candidate_person_uid"
    repo.add_match_candidate.assert_not_called()


@pytest.mark.asyncio
async def test_add_match_candidate_checks_all_person_refs_in_tenant() -> None:
    service, repo = _make_service()
    repo.get_person = AsyncMock(return_value=object())
    repo.add_match_candidate = AsyncMock()

    source = uuid.uuid4()
    candidate_uid = uuid.uuid4()
    accepted_uid = candidate_uid
    payload = _payload(
        source_person_uid=source,
        candidate_person_uid=candidate_uid,
        accepted_person_uid=accepted_uid,
        status="accepted",
    )

    await service.add_match_candidate(_TENANT_ID, payload)

    checked_person_uids = [call.args[1] for call in repo.get_person.await_args_list]
    assert checked_person_uids == [candidate_uid, source, accepted_uid]


# --- persistence happy path ---


@pytest.mark.asyncio
async def test_add_match_candidate_persists_open_with_pair_key() -> None:
    service, repo = _make_service()

    captured: dict[str, MatchCandidate] = {}

    async def _capture(candidate: MatchCandidate) -> MatchCandidate:
        captured["row"] = candidate
        return candidate

    repo.add_match_candidate = AsyncMock(side_effect=_capture)

    source = uuid.uuid4()
    candidate_uid = uuid.uuid4()
    actor = uuid.uuid4()
    payload = _payload(
        source_person_uid=source,
        candidate_person_uid=candidate_uid,
        status="open",
        match_rule="phone_name",
        confidence=Decimal("0.85"),
        evidence={"email_match": True},
        conflicts={},
        decided_by_actor_id=actor,
    )

    await service.add_match_candidate(_TENANT_ID, payload)

    row = captured["row"]
    assert row.tenant_id == _TENANT_ID
    assert row.source_person_uid == source
    assert row.candidate_person_uid == candidate_uid
    assert row.status == "open"
    assert row.match_rule == "phone_name"
    assert row.confidence == Decimal("0.85")
    assert row.evidence == {"email_match": True}
    assert row.conflicts == {}
    assert row.person_pair_key == make_person_pair_key(source, candidate_uid)
    assert row.decided_at is None
    assert row.decided_by_actor_id == actor


@pytest.mark.asyncio
async def test_add_match_candidate_sets_decided_at_when_status_not_open() -> None:
    service, repo = _make_service()

    captured: dict[str, MatchCandidate] = {}

    async def _capture(candidate: MatchCandidate) -> MatchCandidate:
        captured["row"] = candidate
        return candidate

    repo.add_match_candidate = AsyncMock(side_effect=_capture)

    candidate_uid = uuid.uuid4()
    accepted_uid = candidate_uid  # accepted into the existing candidate person
    payload = _payload(
        source_person_uid=uuid.uuid4(),
        candidate_person_uid=candidate_uid,
        status="auto_accepted",
        accepted_person_uid=accepted_uid,
        match_rule="email_phone_name",
        confidence=Decimal("0.99"),
    )

    await service.add_match_candidate(_TENANT_ID, payload)

    row = captured["row"]
    assert row.status == "auto_accepted"
    assert row.accepted_person_uid == accepted_uid
    assert row.decided_at is not None


@pytest.mark.asyncio
async def test_add_match_candidate_pair_key_none_when_no_source_person() -> None:
    service, repo = _make_service()

    captured: dict[str, MatchCandidate] = {}

    async def _capture(candidate: MatchCandidate) -> MatchCandidate:
        captured["row"] = candidate
        return candidate

    repo.add_match_candidate = AsyncMock(side_effect=_capture)

    payload = _payload(
        source_person_uid=None,
        candidate_person_uid=uuid.uuid4(),
        status="open",
    )
    await service.add_match_candidate(_TENANT_ID, payload)

    assert captured["row"].person_pair_key is None


# --- find_open_match_for_pair ---


@pytest.mark.asyncio
async def test_find_open_match_for_pair_uses_sorted_key() -> None:
    service, repo = _make_service()
    repo.find_open_match_for_pair = AsyncMock(return_value=None)

    a = uuid.UUID("00000000-0000-0000-0000-00000000000A")
    b = uuid.UUID("00000000-0000-0000-0000-00000000000B")

    await service.find_open_match_for_pair(_TENANT_ID, a, b)
    await service.find_open_match_for_pair(_TENANT_ID, b, a)

    keys = {call.args[1] for call in repo.find_open_match_for_pair.await_args_list}
    assert len(keys) == 1
    assert next(iter(keys)) == make_person_pair_key(a, b)


@pytest.mark.asyncio
async def test_find_open_match_for_pair_short_circuits_on_none() -> None:
    service, repo = _make_service()
    repo.find_open_match_for_pair = AsyncMock(return_value=None)

    result = await service.find_open_match_for_pair(_TENANT_ID, None, uuid.uuid4())  # type: ignore[arg-type]
    assert result is None
    repo.find_open_match_for_pair.assert_not_awaited()
