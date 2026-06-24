"""Unit tests for ``CareStackPaymentSummaryIngestService`` (ENG-257).

The sweep iterates over already-linked CareStack patients and snapshots
each ``GET /billing/payment-summary/{patientId}`` to ``ingest.raw_event``
as ``carestack.payment_summary.snapshot``.

Coverage:
- the sweep queries ``identity.source_link`` with the CareStack +
  ``patient`` scope;
- each linked patient with a usable ``source_id`` produces a captured
  snapshot with the verbatim payload;
- a patient whose source link has no ``source_id`` is skipped;
- a single CareStack API failure does not poison the sweep;
- ``max_patients`` validation rejects out-of-band values;
- nothing in the emitted event_type / external_id leaks PHI tokens.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ingest.carestack_payment_summary_service import (
    CareStackPaymentSummaryIngestService,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())

# PHI/clinical fixture set — none of these tokens may appear in any
# field we set on the raw_event ourselves (event_type, external_id).
_PHI_TOKENS = (
    "Dr. Smith",
    "tooth #14",
    "clinical notes",
    "DOB-1990",
)


def _link(patient_id: str | None = "9985") -> SimpleNamespace:
    return SimpleNamespace(
        person_uid=uuid.uuid4(),
        source_id=patient_id,
        source_system="carestack",
        source_instance="carestack-main",
        source_kind="patient",
    )


def _summary_payload(patient_id: int = 9985) -> dict[str, Any]:
    return {
        "patientId": patient_id,
        "appliedPatientPayment": 200.0,
        "appliedInsPayments": 100.0,
        "balanceDuePatient": 50.0,
        "balanceDueInsurance": 25.0,
        "patientUnappliedCredits": 10.0,
    }


def _make_service(
    *,
    links: list[SimpleNamespace] | None = None,
    summary_side_effect: Any = None,
) -> tuple[
    CareStackPaymentSummaryIngestService,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    session = MagicMock()
    cs_client = MagicMock()
    cs_client.get_payment_summary = AsyncMock(
        return_value=_summary_payload()
        if summary_side_effect is None
        else None,
        side_effect=summary_side_effect,
    )
    service = CareStackPaymentSummaryIngestService(session, cs_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["capture", "latest_payload"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    # Content-dedupe default: no prior snapshot → every snapshot writes.
    service._ingest.latest_payload = AsyncMock(return_value=None)
    service._identity_repo = MagicMock(spec=["list_source_links_for_dashboard"])  # type: ignore[attr-defined]
    service._identity_repo.list_source_links_for_dashboard = AsyncMock(
        return_value=links if links is not None else [_link()]
    )
    return (
        service,
        cs_client,
        service._ingest,  # type: ignore[attr-defined]
        service._identity_repo,  # type: ignore[attr-defined]
    )


# ------------------------------------------------------ happy path


@pytest.mark.asyncio
async def test_sweep_snapshots_each_linked_patient() -> None:
    service, cs_client, ingest, identity_repo = _make_service(
        links=[_link("9985"), _link("9986")]
    )

    result = await service.import_payment_summary_snapshots(
        _TENANT_ID, max_patients=10
    )

    assert result.patient_count == 2
    assert result.snapshot_count == 2
    assert result.skipped_count == 0
    assert result.error_count == 0

    identity_repo.list_source_links_for_dashboard.assert_awaited_once_with(
        _TENANT_ID,
        source_system="carestack",
        source_kind="patient",
        limit=10,
    )
    assert cs_client.get_payment_summary.await_count == 2
    assert ingest.capture.await_count == 2

    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.source == "carestack"
    assert raw_call.event_type == "carestack.payment_summary.snapshot"
    # external_id is the CareStack patient id (a stable non-PII reference).
    assert raw_call.external_id == "9986"
    # Verbatim payload — financial fields preserved exactly.
    assert raw_call.payload["balanceDuePatient"] == 50.0


# ------------------------------------------------------ skip / failure paths


@pytest.mark.asyncio
async def test_link_without_source_id_is_skipped() -> None:
    service, cs_client, ingest, _ = _make_service(
        links=[_link(None), _link("9986")]
    )

    result = await service.import_payment_summary_snapshots(
        _TENANT_ID, max_patients=10
    )

    assert result.patient_count == 2
    assert result.snapshot_count == 1
    assert result.skipped_count == 1
    assert result.error_count == 0

    # We only called CareStack for the patient that had a usable id.
    cs_client.get_payment_summary.assert_awaited_once()
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_with_blank_source_id_is_skipped() -> None:
    service, cs_client, ingest, _ = _make_service(
        links=[_link("   "), _link("9986")]
    )

    result = await service.import_payment_summary_snapshots(
        _TENANT_ID, max_patients=10
    )

    assert result.snapshot_count == 1
    assert result.skipped_count == 1
    cs_client.get_payment_summary.assert_awaited_once()
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_failure_for_one_patient_does_not_break_sweep() -> None:
    """One patient's API failure is logged and the sweep continues.

    Failure isolation per the service docstring: a single 4xx/5xx must
    not poison the whole sweep. The error is counted as ``error_count``;
    other patients' snapshots are still captured.
    """
    service, cs_client, ingest, _ = _make_service(
        links=[_link("9985"), _link("9986"), _link("9987")],
        summary_side_effect=[
            _summary_payload(9985),
            RuntimeError("carestack 500"),
            _summary_payload(9987),
        ],
    )

    result = await service.import_payment_summary_snapshots(
        _TENANT_ID, max_patients=10
    )

    assert result.patient_count == 3
    assert result.snapshot_count == 2
    assert result.error_count == 1
    assert result.skipped_count == 0
    assert cs_client.get_payment_summary.await_count == 3
    assert ingest.capture.await_count == 2


@pytest.mark.asyncio
async def test_empty_link_list_returns_zero_summary() -> None:
    service, cs_client, ingest, _ = _make_service(links=[])

    result = await service.import_payment_summary_snapshots(
        _TENANT_ID, max_patients=10
    )

    assert result.patient_count == 0
    assert result.snapshot_count == 0
    assert result.skipped_count == 0
    assert result.error_count == 0
    cs_client.get_payment_summary.assert_not_awaited()
    ingest.capture.assert_not_awaited()


# ------------------------------------------------------ validation


@pytest.mark.asyncio
async def test_max_patients_rejects_out_of_band_values() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_payment_summary_snapshots(
            _TENANT_ID, max_patients=0
        )
    with pytest.raises(ValidationError):
        await service.import_payment_summary_snapshots(
            _TENANT_ID, max_patients=501
        )


# ------------------------------------------------------ no PHI leak


@pytest.mark.asyncio
async def test_emitted_event_metadata_has_no_phi_tokens() -> None:
    """The fields we set on the raw_event (event_type, external_id) must
    not contain any PHI/clinical token even if the CareStack response
    payload would happen to include such content. The payload itself is
    captured verbatim by design (forensic) and is gated by the ingest
    schema's PHI carve-out rules.
    """
    service, _, ingest, _ = _make_service(links=[_link("9985")])

    await service.import_payment_summary_snapshots(_TENANT_ID, max_patients=5)

    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.event_type == "carestack.payment_summary.snapshot"
    assert raw_call.external_id == "9985"
    assert all(token not in raw_call.event_type for token in _PHI_TOKENS)
    assert all(token not in str(raw_call.external_id) for token in _PHI_TOKENS)


# ---------------------------------------------------------- ENG-285 throttled backfill (pull_all_payment_summaries)


class _FakeCareStackApiError(Exception):
    """Stand-in for ``CareStackApiError`` — duck-types via ``.details``.

    ``packages.ingest`` may not import ``packages.integrations``;
    production retry/backoff checks the exception via
    ``getattr(exc, "details", ...)`` so this fake provides the same
    shape without violating the cross-package import matrix.
    """

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.details = {"status": status}


class _SleepRecorder:
    """Async sleep stand-in: records waits, never blocks."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.mark.asyncio
async def test_pull_all_walks_every_linked_patient_unbounded() -> None:
    """The backfill sweep iterates ALL linked CareStack patients, unbounded.

    The scheduled sweep caps at ``max_patients=50``; the backfill is
    operator-triggered and walks the full tenant. The default ceiling
    is a high safety value (avoid infinite tenant table), not a small
    operational quota.
    """
    service, cs_client, ingest, identity_repo = _make_service(
        links=[_link("9985"), _link("9986"), _link("9987")]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_payment_summaries(_TENANT_ID, sleep=sleep)

    assert result.patient_count == 3
    assert result.snapshot_count == 3
    assert result.error_count == 0
    assert result.skipped_count == 0
    assert cs_client.get_payment_summary.await_count == 3
    assert ingest.capture.await_count == 3
    identity_repo.list_source_links_for_dashboard.assert_awaited_once()
    call_kwargs = identity_repo.list_source_links_for_dashboard.await_args.kwargs
    assert call_kwargs["source_system"] == "carestack"
    assert call_kwargs["source_kind"] == "patient"


@pytest.mark.asyncio
async def test_pull_all_sleeps_between_patients_but_not_after_last() -> None:
    service, _, _, _ = _make_service(
        links=[_link("9985"), _link("9986"), _link("9987")]
    )
    sleep = _SleepRecorder()

    await service.pull_all_payment_summaries(
        _TENANT_ID, sleep_seconds=0.75, sleep=sleep
    )

    # 3 patients → 2 between-patient throttle sleeps.
    assert sleep.waits == [0.75, 0.75]


@pytest.mark.asyncio
async def test_pull_all_retries_with_exponential_backoff_on_429() -> None:
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, cs_client, _, _ = _make_service(
        links=[_link("9985")],
        summary_side_effect=[rate_limit, rate_limit, _summary_payload(9985)],
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_payment_summaries(
        _TENANT_ID,
        sleep_seconds=0.0,
        max_retries=5,
        backoff_base_seconds=1.0,
        sleep=sleep,
    )

    assert result.snapshot_count == 1
    assert result.error_count == 0
    # Two retries → two backoff sleeps (1s, 2s).
    assert sleep.waits == [1.0, 2.0]
    assert cs_client.get_payment_summary.await_count == 3


@pytest.mark.asyncio
async def test_pull_all_counts_patient_as_error_when_retries_exhausted() -> None:
    """Failure isolation: a single patient's retries exhausting must NOT
    abort the whole sweep — that patient is counted as an error and the
    sweep continues to the next patient.

    The operator can re-run the backfill later (idempotent) once the
    rate limit window passes.
    """
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, cs_client, ingest, _ = _make_service(
        links=[_link("9985"), _link("9986"), _link("9987")],
        # Patient 9985: succeeds.
        # Patient 9986: 429, 429, 429 (retries exhausted at max_retries=2).
        # Patient 9987: succeeds.
        summary_side_effect=[
            _summary_payload(9985),
            rate_limit,
            rate_limit,
            rate_limit,
            _summary_payload(9987),
        ],
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_payment_summaries(
        _TENANT_ID,
        sleep_seconds=0.0,
        max_retries=2,
        backoff_base_seconds=0.5,
        sleep=sleep,
    )

    assert result.patient_count == 3
    assert result.snapshot_count == 2
    assert result.error_count == 1
    assert result.skipped_count == 0
    assert ingest.capture.await_count == 2
    # The two backoff waits for patient 9986 are recorded.
    assert 0.5 in sleep.waits
    assert 1.0 in sleep.waits
    # Sweep still made all 3 patient attempts (initial + 2 retries for 9986).
    assert cs_client.get_payment_summary.await_count == 5


@pytest.mark.asyncio
async def test_pull_all_non_retryable_error_is_counted_and_skipped() -> None:
    """A 401 / non-retryable error per-patient is still failure-isolated.

    The existing scheduled sweep already swallows arbitrary exceptions
    so one bad patient does not poison the sweep. The backfill must
    keep that behaviour — but only retryable status codes incur the
    backoff path.
    """
    not_connected = _FakeCareStackApiError("unauthorised", status=401)
    service, cs_client, _, _ = _make_service(
        links=[_link("9985"), _link("9986")],
        summary_side_effect=[not_connected, _summary_payload(9986)],
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_payment_summaries(
        _TENANT_ID,
        sleep_seconds=0.0,
        max_retries=5,
        backoff_base_seconds=1.0,
        sleep=sleep,
    )

    assert result.patient_count == 2
    assert result.snapshot_count == 1
    assert result.error_count == 1
    # No backoff sleeps — the 401 short-circuits the retry loop.
    assert sleep.waits == []
    assert cs_client.get_payment_summary.await_count == 2


@pytest.mark.asyncio
async def test_pull_all_skips_links_without_usable_source_id() -> None:
    service, cs_client, ingest, _ = _make_service(
        links=[_link(None), _link("   "), _link("9986")]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_payment_summaries(
        _TENANT_ID, sleep_seconds=0.0, sleep=sleep
    )

    assert result.patient_count == 3
    assert result.snapshot_count == 1
    assert result.skipped_count == 2
    assert result.error_count == 0
    cs_client.get_payment_summary.assert_awaited_once()
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_pull_all_empty_tenant_returns_zero_summary() -> None:
    service, cs_client, ingest, _ = _make_service(links=[])
    sleep = _SleepRecorder()

    result = await service.pull_all_payment_summaries(
        _TENANT_ID, sleep_seconds=0.0, sleep=sleep
    )

    assert result.patient_count == 0
    assert result.snapshot_count == 0
    cs_client.get_payment_summary.assert_not_awaited()
    ingest.capture.assert_not_awaited()
    assert sleep.waits == []


@pytest.mark.asyncio
async def test_pull_all_rejects_invalid_arguments() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.pull_all_payment_summaries(_TENANT_ID, max_patients=0)
    with pytest.raises(ValidationError):
        await service.pull_all_payment_summaries(_TENANT_ID, max_retries=-1)
    with pytest.raises(ValidationError):
        await service.pull_all_payment_summaries(_TENANT_ID, sleep_seconds=-1.0)
    with pytest.raises(ValidationError):
        await service.pull_all_payment_summaries(_TENANT_ID, backoff_base_seconds=-1.0)


@pytest.mark.asyncio
async def test_pull_all_honours_max_patients_safety_cap() -> None:
    """Defensive ceiling: the sweep never walks more than ``max_patients``."""
    service, cs_client, _, identity_repo = _make_service(
        links=[_link(str(p)) for p in range(1000, 1010)]
    )
    sleep = _SleepRecorder()

    await service.pull_all_payment_summaries(
        _TENANT_ID, max_patients=3, sleep_seconds=0.0, sleep=sleep
    )

    # The repo was queried with the operator-supplied cap.
    call_kwargs = identity_repo.list_source_links_for_dashboard.await_args.kwargs
    assert call_kwargs["limit"] == 3


# ---------------------------------------------------------- ENG-305 caller-supplied patient_ids sweep


@pytest.mark.asyncio
async def test_import_for_patients_calls_carestack_once_per_id() -> None:
    """``import_payment_summary_for_patients`` covers every input patient_id.

    The new entry point bypasses the source-link listing: the caller
    resolves the set and hands the sweep the patient_id list directly
    (used by the live signal in the scheduled job and by the backfill
    script).
    """
    service, cs_client, ingest, identity_repo = _make_service()
    sleep = _SleepRecorder()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["9985", "9986", "9987"],
        sleep_seconds=0.0,
        sleep=sleep,
    )

    assert result.patient_count == 3
    assert result.snapshot_count == 3
    assert result.error_count == 0
    assert result.skipped_count == 0
    assert cs_client.get_payment_summary.await_count == 3
    assert ingest.capture.await_count == 3
    # No source-link listing — the caller owns the patient set now.
    identity_repo.list_source_links_for_dashboard.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_for_patients_throttles_between_patients() -> None:
    """Throttle is between patients only — no sleep before the first call."""
    service, _, _, _ = _make_service()
    sleep = _SleepRecorder()

    await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["9985", "9986", "9987"],
        sleep_seconds=0.5,
        sleep=sleep,
    )

    # 3 patients → 2 between-patient throttle sleeps.
    assert sleep.waits == [0.5, 0.5]


@pytest.mark.asyncio
async def test_import_for_patients_failure_isolation_continues_sweep() -> None:
    """One patient's retries exhausting does not stop the sweep — that
    patient is counted as ``error_count`` and the sweep keeps going."""
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, cs_client, ingest, _ = _make_service(
        summary_side_effect=[
            _summary_payload(9985),
            rate_limit,
            rate_limit,
            rate_limit,
            _summary_payload(9987),
        ],
    )
    sleep = _SleepRecorder()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["9985", "9986", "9987"],
        sleep_seconds=0.0,
        max_retries=2,
        backoff_base_seconds=0.5,
        sleep=sleep,
    )

    assert result.patient_count == 3
    assert result.snapshot_count == 2
    assert result.error_count == 1
    assert result.skipped_count == 0
    assert ingest.capture.await_count == 2
    # All three patients were attempted (initial + 2 retries for 9986 = 5 total).
    assert cs_client.get_payment_summary.await_count == 5


@pytest.mark.asyncio
async def test_import_for_patients_commits_in_batches_and_flushes_final() -> None:
    """``commit_every=2`` over 5 patients → 2 in-flight commits + 1 final flush."""
    service, cs_client, _, _ = _make_service()
    cs_client.get_payment_summary = AsyncMock(  # type: ignore[method-assign]
        side_effect=[_summary_payload(int(pid)) for pid in (10, 11, 12, 13, 14)]
    )
    commit = AsyncMock()
    sleep = _SleepRecorder()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["10", "11", "12", "13", "14"],
        sleep_seconds=0.0,
        commit_every=2,
        commit=commit,
        sleep=sleep,
    )

    assert result.snapshot_count == 5
    # Two batches of 2 (commits after patient 2 and 4) + a final flush.
    assert commit.await_count == 3


@pytest.mark.asyncio
async def test_import_for_patients_commits_on_error_batches_too() -> None:
    """Errors still count toward the commit window — the sweep must flush
    raw_event captures even when some patients in the batch errored."""
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, _, _, _ = _make_service(
        summary_side_effect=[
            _summary_payload(10),
            rate_limit,
            rate_limit,
            rate_limit,
            _summary_payload(12),
            _summary_payload(13),
        ],
    )
    commit = AsyncMock()
    sleep = _SleepRecorder()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["10", "11", "12", "13"],
        sleep_seconds=0.0,
        max_retries=2,
        backoff_base_seconds=0.0,
        commit_every=2,
        commit=commit,
        sleep=sleep,
    )

    # Patient 11 errors (retry exhausted) but still consumes one slot in the
    # commit window — after patient 11 the in-flight commit fires.
    assert result.patient_count == 4
    assert result.snapshot_count == 3
    assert result.error_count == 1
    # Two windowed commits (after 2 and 4) + final flush.
    assert commit.await_count == 3


@pytest.mark.asyncio
async def test_import_for_patients_without_commit_does_not_crash() -> None:
    """``commit=None`` (default) means the caller owns the unit of work — the
    sweep simply skips every commit call without raising."""
    service, _, ingest, _ = _make_service()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["9985", "9986"],
        sleep_seconds=0.0,
    )

    assert result.snapshot_count == 2
    assert ingest.capture.await_count == 2


@pytest.mark.asyncio
async def test_import_for_patients_dedups_input_preserving_order() -> None:
    """Duplicate input patient_ids must not double-call CareStack."""
    service, cs_client, ingest, _ = _make_service()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID,
        ["A", "B", "A", "C", "B"],
        sleep_seconds=0.0,
    )

    assert result.patient_count == 3
    assert result.snapshot_count == 3
    assert cs_client.get_payment_summary.await_count == 3
    assert ingest.capture.await_count == 3
    # Order preserved: first occurrence wins.
    called_ids = [
        call.args[0] for call in cs_client.get_payment_summary.await_args_list
    ]
    assert called_ids == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_import_for_patients_empty_input_returns_zero_summary() -> None:
    service, cs_client, ingest, _ = _make_service()
    commit = AsyncMock()

    result = await service.import_payment_summary_for_patients(
        _TENANT_ID, [], commit=commit
    )

    assert result.patient_count == 0
    assert result.snapshot_count == 0
    assert result.error_count == 0
    cs_client.get_payment_summary.assert_not_awaited()
    ingest.capture.assert_not_awaited()
    # No work was done → no commit call either.
    commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_identical_to_latest_is_skipped() -> None:
    """ENG-381 owner decision: identical snapshot content → no raw write."""
    service, cs_client, ingest, _ = _make_service()
    summary_payload = await cs_client.get_payment_summary("1")
    cs_client.get_payment_summary = AsyncMock(return_value=summary_payload)
    ingest.latest_payload = AsyncMock(return_value=dict(summary_payload))

    result = await service.import_payment_summary_snapshots(_TENANT_ID)

    assert result.snapshot_count == 0
    assert result.unchanged_count == 1
    assert result.error_count == 0
    ingest.capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_with_changed_content_is_captured() -> None:
    """A changed balance writes a fresh snapshot row."""
    service, cs_client, ingest, _ = _make_service()
    summary_payload = await cs_client.get_payment_summary("1")
    cs_client.get_payment_summary = AsyncMock(return_value=summary_payload)
    changed = dict(summary_payload)
    changed["balanceDuePatient"] = -999.0
    ingest.latest_payload = AsyncMock(return_value=changed)

    result = await service.import_payment_summary_snapshots(_TENANT_ID)

    assert result.snapshot_count == 1
    assert result.unchanged_count == 0
    ingest.capture.assert_awaited_once()
