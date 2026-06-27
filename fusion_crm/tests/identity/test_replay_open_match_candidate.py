"""Tests for ``IdentityService.replay_open_match_candidate`` (ENG-544).

Re-evaluates an OPEN ``identity.match_candidate`` under the CURRENT (ENG-543
word-level) policy and classifies it as ``would_merge`` / ``stay_open`` /
``skipped``. Dry-run (``apply=False``) must mutate nothing; the live pass
(``apply=True``) must record an append-only merge, move the merged person's
source links onto the survivor, and decide the candidate ``accepted``.

The acceptance scenario (the 'Newton Patrick' lead duplicate collapsing into
'Patrick Newton' on the shared phone) is exercised directly against a mock
repository — the matching itself reuses ``_evaluate_match_policy``; these tests
pin the replay classification + live-merge side effects around it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.identity.models import MergeEvent, Person, PersonIdentifier
from packages.identity.schemas import MatchCandidateOut
from packages.identity.service import IdentityService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


# ----- helpers --------------------------------------------------------------


def _make_person(
    person_uid: uuid.UUID | None = None,
    *,
    given_name: str | None = None,
    family_name: str | None = None,
    display_name: str | None = None,
    emails: tuple[str, ...] = (),
    phones: tuple[str, ...] = (),
) -> Person:
    person = Person(
        tenant_id=_TENANT_ID,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name,
    )
    person.id = person_uid or uuid.uuid4()
    person.identifiers = []
    for email in emails:
        ident = PersonIdentifier(
            tenant_id=_TENANT_ID, person_id=person.id, kind="email", value=email
        )
        ident.id = uuid.uuid4()
        person.identifiers.append(ident)
    for phone in phones:
        ident = PersonIdentifier(
            tenant_id=_TENANT_ID, person_id=person.id, kind="phone", value=phone
        )
        ident.id = uuid.uuid4()
        person.identifiers.append(ident)
    return person


def _candidate_out(
    *,
    source_uid: uuid.UUID | None,
    candidate_uid: uuid.UUID,
    match_rule: str = "phone_only_ambiguous",
) -> MatchCandidateOut:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return MatchCandidateOut(
        id=uuid.uuid4(),
        hint_id=None,
        source_person_uid=source_uid,
        candidate_person_uid=candidate_uid,
        accepted_person_uid=None,
        merge_event_id=None,
        status="open",
        match_rule=match_rule,
        confidence=Decimal("0.70"),
        evidence={"phone_match_any": True},
        conflicts={},
        person_pair_key=None,
        decided_at=None,
        decided_by_actor_id=None,
        superseded_by_match_id=None,
        created_at=now,
        updated_at=now,
    )


def _make_service(
    *,
    source: Person,
    candidate: Person,
    policy_candidates: list[Person] | None = None,
    providers: dict[uuid.UUID, list[str]] | None = None,
) -> tuple[IdentityService, MagicMock]:
    session = MagicMock()
    service = IdentityService(session)
    repo = MagicMock()
    service._repo = repo  # type: ignore[attr-defined]

    by_id = {source.id: source, candidate.id: candidate}

    async def _list_by_ids(_tenant: TenantId, uids: list[uuid.UUID]) -> list[Person]:
        return [by_id[u] for u in uids if u in by_id]

    repo.list_by_ids = AsyncMock(side_effect=_list_by_ids)
    repo.list_candidate_persons_by_identifiers = AsyncMock(
        return_value=policy_candidates if policy_candidates is not None else [candidate]
    )
    repo.list_source_providers_for = AsyncMock(
        return_value=providers
        if providers is not None
        else {source.id: ["salesforce"], candidate.id: ["carestack"]}
    )
    repo.reassign_source_links = AsyncMock(return_value=1)
    repo.update_match_candidate_status = AsyncMock()

    # Track retired (merged) source uids so the idempotency guard sees, within
    # this mock "transaction", a source that an earlier merge already retired.
    retired: set[uuid.UUID] = set()

    async def _add_merge_event(event: MergeEvent) -> MergeEvent:
        event.id = uuid.uuid4()
        retired.add(event.merged_person_uid)
        return event

    async def _is_person_retired(_tenant: TenantId, person_uid: uuid.UUID) -> bool:
        return person_uid in retired

    repo.add_merge_event = AsyncMock(side_effect=_add_merge_event)
    repo.is_person_retired = AsyncMock(side_effect=_is_person_retired)
    return service, repo


# ----- the acceptance pair: would_merge -------------------------------------


@pytest.mark.asyncio
async def test_reversed_packed_name_would_merge_dry_run() -> None:
    """'Newton Patrick' (given empty) vs 'Patrick Newton' on a shared phone now
    yields a single Tier-1 auto-accept → would_merge into the canonical person.
    Dry-run must mutate nothing."""
    canonical = _make_person(given_name="Patrick", family_name="Newton", phones=("+19167307719",))
    # The lead duplicate dropped its phone under the ENG-340 shared-contact
    # guard: zero identifiers, name packed into family.
    dup = _make_person(family_name="Newton Patrick", display_name="Newton Patrick")
    service, repo = _make_service(source=dup, candidate=canonical)
    cand = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=False)

    assert decision.outcome == "would_merge"
    assert decision.match_rule == "phone_name"
    assert decision.survivor_person_uid == canonical.id
    assert decision.merged_person_uid == dup.id
    assert decision.merge_reason == "cross_provider_match"
    assert decision.applied is False
    # Dry-run: no mutation at all.
    repo.add_merge_event.assert_not_called()
    repo.reassign_source_links.assert_not_called()
    repo.update_match_candidate_status.assert_not_called()


@pytest.mark.asyncio
async def test_would_merge_live_records_merge_and_moves_links() -> None:
    canonical = _make_person(given_name="Patrick", family_name="Newton", phones=("+19167307719",))
    dup = _make_person(family_name="Newton Patrick")
    service, repo = _make_service(source=dup, candidate=canonical)
    cand = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=True)

    assert decision.outcome == "would_merge"
    assert decision.applied is True
    # Survivor is the existing canonical person; merged is the lead duplicate.
    merge_call = repo.add_merge_event.await_args.args[0]
    assert merge_call.surviving_person_uid == canonical.id
    assert merge_call.merged_person_uid == dup.id
    assert merge_call.reason == "cross_provider_match"
    assert "dob" not in merge_call.evidence and "ssn" not in merge_call.evidence
    repo.reassign_source_links.assert_awaited_once_with(_TENANT_ID, dup.id, canonical.id)
    status_kwargs = repo.update_match_candidate_status.await_args.kwargs
    assert status_kwargs["status"] == "accepted"
    assert status_kwargs["accepted_person_uid"] == canonical.id
    assert status_kwargs["merge_event_id"] is not None


# ----- still ambiguous / no match -------------------------------------------


@pytest.mark.asyncio
async def test_double_merge_guard_skips_already_retired_source() -> None:
    """ENG-544 idempotency: one source person with TWO open candidates must be
    merged exactly once. The live pass applies the first; the second sees the
    source already retired and skips — no second merge_event."""
    canonical = _make_person(given_name="Patrick", family_name="Newton", phones=("+19167307719",))
    dup = _make_person(family_name="Newton Patrick")
    service, repo = _make_service(source=dup, candidate=canonical)
    cand_a = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)
    cand_b = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    first = await service.replay_open_match_candidate(_TENANT_ID, cand_a, apply=True)
    second = await service.replay_open_match_candidate(_TENANT_ID, cand_b, apply=True)

    assert first.outcome == "would_merge"
    assert first.applied is True
    # The second candidate for the same (now retired) source is skipped.
    assert second.outcome == "skipped"
    assert second.detail == "source_already_retired"
    assert second.applied is False
    assert second.merged_person_uid == dup.id
    # Exactly ONE merge_event for the tombstone source — no double-merge.
    assert repo.add_merge_event.await_count == 1
    assert repo.add_merge_event.await_args.args[0].merged_person_uid == dup.id


@pytest.mark.asyncio
async def test_real_name_disagreement_stays_open() -> None:
    """A genuine name conflict (John Smith vs Jane Smith) on a shared phone must
    stay open — a strong phone match must not override a real name disagreement."""
    canonical = _make_person(given_name="John", family_name="Smith", phones=("+19167307719",))
    dup = _make_person(given_name="Jane", family_name="Smith")
    service, repo = _make_service(source=dup, candidate=canonical)
    cand = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=True)

    assert decision.outcome == "stay_open"
    repo.add_merge_event.assert_not_called()
    repo.update_match_candidate_status.assert_not_called()


@pytest.mark.asyncio
async def test_two_compatible_candidates_stay_open() -> None:
    """When more than one person clears Tier-1 (auto_accept_eligible > 1), the
    pair stays open even with compatible names."""
    canonical = _make_person(given_name="Patrick", family_name="Newton", phones=("+19167307719",))
    other = _make_person(given_name="Patrick", family_name="Newton", emails=("p@example.com",))
    dup = _make_person(family_name="Newton Patrick", emails=("p@example.com",))
    # Policy sees BOTH canonical (via phone) and other (via the shared email).
    service, repo = _make_service(
        source=dup,
        candidate=canonical,
        policy_candidates=[canonical, other],
    )
    cand = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=True)

    assert decision.outcome == "stay_open"
    repo.add_merge_event.assert_not_called()


@pytest.mark.asyncio
async def test_no_current_match_is_skipped() -> None:
    """If the shared identifier no longer resolves to any person, skip."""
    canonical = _make_person(given_name="Patrick", family_name="Newton")
    dup = _make_person(family_name="Newton Patrick")
    service, repo = _make_service(source=dup, candidate=canonical, policy_candidates=[])
    cand = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=True)

    assert decision.outcome == "skipped"
    assert decision.detail == "no_current_match"
    repo.add_merge_event.assert_not_called()


@pytest.mark.asyncio
async def test_missing_source_person_is_skipped() -> None:
    canonical = _make_person(given_name="Patrick", family_name="Newton")
    dup = _make_person(family_name="Newton Patrick")
    service, _ = _make_service(source=dup, candidate=canonical)
    cand = _candidate_out(source_uid=None, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=True)

    assert decision.outcome == "skipped"
    assert decision.detail == "missing_source_person"


@pytest.mark.asyncio
async def test_same_provider_duplicate_uses_duplicate_phone_reason() -> None:
    """Two persons from the SAME provider merge under reason 'duplicate_phone'."""
    canonical = _make_person(given_name="Patrick", family_name="Newton", phones=("+19167307719",))
    dup = _make_person(family_name="Newton Patrick")
    service, repo = _make_service(
        source=dup,
        candidate=canonical,
        providers={dup.id: ["salesforce"], canonical.id: ["salesforce"]},
    )
    cand = _candidate_out(source_uid=dup.id, candidate_uid=canonical.id)

    decision = await service.replay_open_match_candidate(_TENANT_ID, cand, apply=False)

    assert decision.outcome == "would_merge"
    assert decision.merge_reason == "duplicate_phone"
