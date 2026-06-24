"""Unit tests for the ENG-544 replay/dedup-merge worker job.

The matching policy is exercised in ``tests/identity/test_replay_open_match_candidate.py``;
here we pin the JOB's orchestration: page cursoring, count aggregation, the
acceptance-pair sample, dry-run-mutates-nothing, and the live ops.lead
reassignment hook. ``async_session`` / ``IdentityService`` / ``OpsService`` are
fully mocked — ZERO real DB calls.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.worker.jobs import replay_identity_matches as job
from packages.identity.schemas import MatchCandidateOut, MatchReplayDecisionOut

_TENANT = uuid.uuid4()
_FOCUS_DUP = uuid.UUID("464cc989-4c87-436b-9ca6-23074cfea7c9")
_FOCUS_CANON = uuid.UUID("73e7523b-e906-4a26-96fe-cbed1c87d277")


def _fake_session_cm(session: MagicMock) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    return _cm


def _candidate(source_uid: uuid.UUID, candidate_uid: uuid.UUID) -> MatchCandidateOut:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return MatchCandidateOut(
        id=uuid.uuid4(),
        hint_id=None,
        source_person_uid=source_uid,
        candidate_person_uid=candidate_uid,
        accepted_person_uid=None,
        merge_event_id=None,
        status="open",
        match_rule="phone_only_ambiguous",
        confidence=Decimal("0.70"),
        evidence={},
        conflicts={},
        person_pair_key=None,
        decided_at=None,
        decided_by_actor_id=None,
        superseded_by_match_id=None,
        created_at=now,
        updated_at=now,
    )


def _decision(cand: MatchCandidateOut, outcome: str, **kw: Any) -> MatchReplayDecisionOut:
    return MatchReplayDecisionOut(
        candidate_id=cand.id,
        source_person_uid=cand.source_person_uid,
        candidate_person_uid=cand.candidate_person_uid,
        outcome=outcome,
        detail=kw.get("detail", outcome),
        match_rule=kw.get("match_rule"),
        merge_reason=kw.get("merge_reason"),
        survivor_person_uid=kw.get("survivor_person_uid"),
        merged_person_uid=kw.get("merged_person_uid"),
        applied=kw.get("applied", False),
    )


def _wire_identity(identity: MagicMock, page: list[MatchCandidateOut]) -> None:
    """``list_open_match_candidates`` returns the page once, then empty (cursor)."""
    calls = {"n": 0}

    async def _list(_tid: Any, *, after_id: Any, limit: int) -> list[MatchCandidateOut]:
        calls["n"] += 1
        return page if calls["n"] == 1 else []

    identity.list_open_match_candidates = AsyncMock(side_effect=_list)


@pytest.mark.asyncio
async def test_dry_run_aggregates_counts_and_samples_focus_pair() -> None:
    focus_cand = _candidate(_FOCUS_DUP, _FOCUS_CANON)
    open_cand = _candidate(uuid.uuid4(), uuid.uuid4())
    skip_cand = _candidate(uuid.uuid4(), uuid.uuid4())
    page = [focus_cand, open_cand, skip_cand]

    identity = MagicMock()
    ops = MagicMock()
    ops.reassign_leads = AsyncMock(return_value=0)
    _wire_identity(identity, page)

    decisions = {
        focus_cand.id: _decision(
            focus_cand,
            "would_merge",
            match_rule="phone_name",
            merge_reason="cross_provider_match",
            survivor_person_uid=_FOCUS_CANON,
            merged_person_uid=_FOCUS_DUP,
        ),
        open_cand.id: _decision(open_cand, "stay_open"),
        skip_cand.id: _decision(skip_cand, "skipped"),
    }

    async def _replay(_tid: Any, cand: MatchCandidateOut, *, apply: bool) -> Any:
        assert apply is False  # dry-run
        return decisions[cand.id]

    identity.replay_open_match_candidate = AsyncMock(side_effect=_replay)

    session = MagicMock()
    with (
        patch.object(job, "async_session", _fake_session_cm(session)),
        patch.object(job, "IdentityService", return_value=identity),
        patch.object(job, "OpsService", return_value=ops),
    ):
        result = await job.replay_identity_matches({}, tenant_id=str(_TENANT), dry_run=True)

    summary = result[0]
    assert summary["scanned"] == 3
    assert summary["would_merge"] == 1
    assert summary["would_stay_open"] == 1
    assert summary["skipped"] == 1
    assert summary["merged_applied"] == 0
    assert summary["leads_reassigned"] == 0
    assert summary["dry_run"] is True
    # Dry-run never touches ops leads.
    ops.reassign_leads.assert_not_called()
    # The acceptance pair is present in the sample, merging into the canonical.
    focus = [s for s in summary["samples"] if s["candidate_id"] == str(focus_cand.id)]
    assert focus and focus[0]["survivor_person_uid"] == str(_FOCUS_CANON)
    assert focus[0]["merged_person_uid"] == str(_FOCUS_DUP)
    # One example of every outcome retained.
    assert {s["outcome"] for s in summary["samples"]} == {
        "would_merge",
        "stay_open",
        "skipped",
    }


@pytest.mark.asyncio
async def test_live_pass_reassigns_leads_for_applied_merges() -> None:
    merge_cand = _candidate(_FOCUS_DUP, _FOCUS_CANON)
    identity = MagicMock()
    ops = MagicMock()
    ops.reassign_leads = AsyncMock(return_value=2)
    _wire_identity(identity, [merge_cand])

    async def _replay(_tid: Any, cand: MatchCandidateOut, *, apply: bool) -> Any:
        assert apply is True  # live
        return _decision(
            cand,
            "would_merge",
            match_rule="phone_name",
            merge_reason="cross_provider_match",
            survivor_person_uid=_FOCUS_CANON,
            merged_person_uid=_FOCUS_DUP,
            applied=True,
        )

    identity.replay_open_match_candidate = AsyncMock(side_effect=_replay)

    session = MagicMock()
    with (
        patch.object(job, "async_session", _fake_session_cm(session)),
        patch.object(job, "IdentityService", return_value=identity),
        patch.object(job, "OpsService", return_value=ops),
    ):
        result = await job.replay_identity_matches({}, tenant_id=str(_TENANT), dry_run=False)

    summary = result[0]
    assert summary["would_merge"] == 1
    assert summary["merged_applied"] == 1
    assert summary["leads_reassigned"] == 2
    ops.reassign_leads.assert_awaited_once_with(_TENANT, _FOCUS_DUP, _FOCUS_CANON)


@pytest.mark.asyncio
async def test_live_pass_dedupes_two_candidates_for_same_source() -> None:
    """ENG-544: two open candidates share one source person. The live pass
    applies the first merge and SKIPS the second without re-evaluating it —
    a source is merged at most once per pass (no double-merge)."""
    source = uuid.uuid4()
    cand_a = _candidate(source, uuid.uuid4())
    cand_b = _candidate(source, uuid.uuid4())
    identity = MagicMock()
    ops = MagicMock()
    ops.reassign_leads = AsyncMock(return_value=1)
    _wire_identity(identity, [cand_a, cand_b])

    async def _replay(_tid: Any, cand: MatchCandidateOut, *, apply: bool) -> Any:
        assert apply is True  # live
        return _decision(
            cand,
            "would_merge",
            match_rule="phone_name",
            survivor_person_uid=cand.candidate_person_uid,
            merged_person_uid=cand.source_person_uid,
            applied=True,
        )

    identity.replay_open_match_candidate = AsyncMock(side_effect=_replay)

    session = MagicMock()
    with (
        patch.object(job, "async_session", _fake_session_cm(session)),
        patch.object(job, "IdentityService", return_value=identity),
        patch.object(job, "OpsService", return_value=ops),
    ):
        result = await job.replay_identity_matches(
            {}, tenant_id=str(_TENANT), dry_run=False
        )

    summary = result[0]
    assert summary["scanned"] == 2
    assert summary["would_merge"] == 1
    assert summary["merged_applied"] == 1
    assert summary["skipped"] == 1
    # The second candidate was short-circuited before re-evaluation.
    assert identity.replay_open_match_candidate.await_count == 1
    ops.reassign_leads.assert_awaited_once_with(_TENANT, source, cand_a.candidate_person_uid)


@pytest.mark.asyncio
async def test_limit_caps_scanned_rows() -> None:
    page = [_candidate(uuid.uuid4(), uuid.uuid4()) for _ in range(5)]
    identity = MagicMock()
    ops = MagicMock()
    ops.reassign_leads = AsyncMock(return_value=0)
    _wire_identity(identity, page)
    identity.replay_open_match_candidate = AsyncMock(
        side_effect=lambda _t, c, *, apply: _decision(c, "skipped")
    )

    session = MagicMock()
    with (
        patch.object(job, "async_session", _fake_session_cm(session)),
        patch.object(job, "IdentityService", return_value=identity),
        patch.object(job, "OpsService", return_value=ops),
    ):
        result = await job.replay_identity_matches(
            {}, tenant_id=str(_TENANT), dry_run=True, limit=2
        )

    assert result[0]["scanned"] == 2
