"""Unit tests for ``CareStackTreatmentIngestService`` (ENG-267 slice).

Focused on the location-on-payload contract added in ENG-267:
location resolved + stored, unmapped/missing tolerated, no PHI leakage.
The existing treatment status mapping helpers retain their own
helper-level coverage at the bottom of the file.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId
from packages.ingest.carestack_treatment_service import (
    _IMPLANT_SURGERY_CDT_CODES,
    CareStackTreatmentIngestService,
    _procedure_code_id,
    _procedure_location_id,
    _status_id,
    _treatment_event_kind,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LOCATION_UID = uuid.uuid4()

# PHI / clinical fixture set — none of these tokens may appear in any
# emitted timeline summary or in the safe event payload. The verbatim
# raw_event payload is allowed to carry them (forensic capture).
_PHI_TOKENS = (
    "must NEVER reach timeline",
    "tooth #14",
    "Dr. Smith",
    "implant",
    "occlusal surface",
)


def _procedure(**overrides: object) -> dict[str, Any]:
    """Build a representative TreatmentProcedure row.

    Defaults mirror the field list in
    ``docs/integrations/carestack/sync/treatment-procedures.md``.
    """
    base: dict[str, Any] = {
        "id": 77001,
        "patientId": 9985,
        "locationId": 10029,
        "providerId": 3,
        "statusId": 1,  # proposed
        "dateOfService": "2026-05-22T14:00:00Z",
        "lastUpdatedOn": "2026-05-22T14:01:00Z",
        # PHI-shaped fields included to assert they stay inside the raw
        # payload and never surface into anything we construct.
        "procedureCode": "D6010",
        "toothNumber": "14",
        "surface": "occlusal surface",
        "notes": "must NEVER reach timeline — Dr. Smith implant note",
    }
    base.update(overrides)
    return base


_LOCATION_DEFAULT = object()


def _make_service(
    body: dict[str, Any] | None = None,
    source_link: SimpleNamespace | None = None,
    location: object = _LOCATION_DEFAULT,
) -> tuple[
    CareStackTreatmentIngestService,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    session = MagicMock()
    # ENG-351: pull_all_since checkpoints per page — commit must be awaitable.
    session.commit = AsyncMock()
    cs_client = MagicMock()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        return_value=body
        or {
            "treatmentProcedures": [_procedure()],
            "continueToken": None,
        }
    )
    service = CareStackTreatmentIngestService(session, cs_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["capture", "max_payload_watermark", "latest_payload_values"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    # First-run default: nothing captured before → guard never skips.
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(
        return_value=source_link
        if source_link is not None
        else SimpleNamespace(person_uid=_PERSON_UID)
    )
    # ENG-269: CareStack callers use create_event_idempotent to count
    # was_created=False conflicts as "skipped" instead of "imported".
    service._interaction = MagicMock(spec=["create_event_idempotent"])  # type: ignore[attr-defined]
    service._interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(event=SimpleNamespace(id=uuid.uuid4()), was_created=True)
    )
    service._locations = MagicMock(spec=["find_by_carestack_id"])  # type: ignore[attr-defined]
    resolved = (
        SimpleNamespace(id=_LOCATION_UID) if location is _LOCATION_DEFAULT else location
    )
    service._locations.find_by_carestack_id = AsyncMock(return_value=resolved)
    return (
        service,
        cs_client,
        service._ingest,  # type: ignore[attr-defined]
        service._identity_repo,  # type: ignore[attr-defined]
        service._interaction,  # type: ignore[attr-defined]
        service._locations,  # type: ignore[attr-defined]
    )


# ---------------------------------------------------------- happy path


@pytest.mark.asyncio
async def test_import_emits_event_with_resolved_location_id() -> None:
    service, _, ingest, _, interaction, locations = _make_service()

    result = await service.import_recent_treatments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()
    locations.find_by_carestack_id.assert_awaited_once_with(_TENANT_ID, 10029)
    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_proposed"
    assert event_in.payload == {"location_id": str(_LOCATION_UID)}


@pytest.mark.asyncio
async def test_completed_status_maps_to_treatment_completed() -> None:
    service, _, _, _, interaction, _ = _make_service(
        body={
            "treatmentProcedures": [_procedure(statusId=8)],
            "continueToken": None,
        }
    )

    await service.import_recent_treatments(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_completed"


# ---------------------------------------------------------- location handling


@pytest.mark.asyncio
async def test_unmapped_location_omits_location_id_but_emits_event() -> None:
    service, _, _, _, interaction, _ = _make_service(location=None)

    result = await service.import_recent_treatments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload
    assert event_in.payload == {}


@pytest.mark.asyncio
async def test_missing_location_id_field_skips_resolver_and_emits_event() -> None:
    service, _, _, _, interaction, locations = _make_service(
        body={
            "treatmentProcedures": [_procedure(locationId=None)],
            "continueToken": None,
        }
    )

    result = await service.import_recent_treatments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    locations.find_by_carestack_id.assert_not_awaited()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


@pytest.mark.asyncio
async def test_resolver_not_found_error_omits_location_id() -> None:
    service, _, _, _, interaction, locations = _make_service()
    locations.find_by_carestack_id = AsyncMock(
        side_effect=NotFoundError("tenant not found", details={})
    )

    result = await service.import_recent_treatments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


# ---------------------------------------------------------- no-PHI guard


@pytest.mark.asyncio
async def test_emitted_event_summary_and_payload_carry_no_phi_tokens() -> None:
    """Service-constructed fields must never contain PHI / clinical text.

    The raw_event payload is allowed to carry PHI (capture-then-route);
    every field the service constructs itself (summary, event payload,
    event_type, external_id) must not.
    """
    service, _, _, _, interaction, _ = _make_service()

    await service.import_recent_treatments(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    for token in _PHI_TOKENS:
        assert token not in event_in.summary
        assert all(token not in str(v) for v in event_in.payload.values())

    # Safe payload allowlist: only the optional location_id is written.
    assert set(event_in.payload.keys()).issubset({"location_id"})


# ---------------------------------------------------------- helper unit tests


def test_procedure_location_id_helper_parses_int_or_string() -> None:
    assert _procedure_location_id({"locationId": 10029}) == 10029
    assert _procedure_location_id({"LocationId": 10029}) == 10029
    assert _procedure_location_id({"locationId": "10029"}) == 10029
    assert _procedure_location_id({"locationId": None}) is None
    assert _procedure_location_id({"locationId": "not-a-number"}) is None
    assert _procedure_location_id({"locationId": True}) is None
    assert _procedure_location_id({}) is None


def test_treatment_event_kind_maps_completed_status() -> None:
    assert _treatment_event_kind({"statusId": 8}) == "treatment_completed"
    assert _treatment_event_kind({"statusId": "8"}) == "treatment_completed"
    assert _treatment_event_kind({"statusId": 1}) == "treatment_proposed"
    assert _treatment_event_kind({"statusId": 2}) == "treatment_proposed"
    assert _treatment_event_kind({}) == "treatment_proposed"


def test_procedure_code_id_helper_parses_int_or_string() -> None:
    assert _procedure_code_id({"procedureCodeId": 117408}) == 117408
    assert _procedure_code_id({"ProcedureCodeId": 117408}) == 117408
    assert _procedure_code_id({"procedureCodeId": "117408"}) == 117408
    assert _procedure_code_id({"procedureCodeId": None}) is None
    assert _procedure_code_id({"procedureCodeId": "x"}) is None
    assert _procedure_code_id({"procedureCodeId": True}) is None
    assert _procedure_code_id({}) is None


def test_status_id_helper_parses_int_or_string() -> None:
    assert _status_id({"statusId": 2}) == 2
    assert _status_id({"statusId": "8"}) == 8
    assert _status_id({"statusId": None}) is None
    assert _status_id({"statusId": True}) is None
    assert _status_id({}) is None


# ---------------------------------------------------------- ENG-511 implant-surgery split


def _set_catalog(
    service: CareStackTreatmentIngestService,
    mapping: dict[int, tuple[str, str | None]],
) -> None:
    """Replace the service catalog with a stub resolving the given mapping."""
    service._catalog = MagicMock(spec=["resolve_procedure_codes"])  # type: ignore[attr-defined]
    service._catalog.resolve_procedure_codes = AsyncMock(return_value=mapping)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_implant_scheduled_status_maps_to_surgery_scheduled() -> None:
    service, _, _, _, interaction, _ = _make_service(
        body={
            "treatmentProcedures": [_procedure(statusId=2, procedureCodeId=117408)],
            "continueToken": None,
        },
        location=None,
    )
    _set_catalog(service, {117408: ("D6010", "Surgical placement of implant body")})

    result = await service.import_recent_treatments(_TENANT_ID, days=7)

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "surgery_scheduled"
    assert event_in.payload == {"is_implant_surgery": True}


@pytest.mark.asyncio
async def test_implant_completed_status_maps_to_surgery_completed() -> None:
    service, _, _, _, interaction, _ = _make_service(
        body={
            "treatmentProcedures": [_procedure(statusId=8, procedureCodeId=117408)],
            "continueToken": None,
        },
        location=None,
    )
    _set_catalog(service, {117408: ("D6013", "Surgical placement of mini implant")})

    await service.import_recent_treatments(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "surgery_completed"
    assert event_in.payload["is_implant_surgery"] is True


@pytest.mark.asyncio
async def test_non_implant_cdt_keeps_generic_mapping() -> None:
    # A scheduled non-implant procedure stays treatment_proposed, NO flag.
    service, _, _, _, interaction, _ = _make_service(
        body={
            "treatmentProcedures": [_procedure(statusId=2, procedureCodeId=555)],
            "continueToken": None,
        },
        location=None,
    )
    _set_catalog(service, {555: ("D0120", "Periodic oral evaluation")})

    await service.import_recent_treatments(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_proposed"
    assert "is_implant_surgery" not in event_in.payload


# ---------------------------------------------------------- ENG-538 surgery set + self-fill


def test_implant_surgery_set_includes_operator_confirmed_custom_variants() -> None:
    """ENG-538: the operator-confirmed custom surgical-placement variants
    must be present EXACTLY (matching is ``code.strip().upper() in set``).
    Restorative codes (abutment/crown) must stay excluded."""
    assert "D6010.A" in _IMPLANT_SURGERY_CDT_CODES
    assert "D6011NC" in _IMPLANT_SURGERY_CDT_CODES
    assert "D6011" in _IMPLANT_SURGERY_CDT_CODES  # already present pre-538
    # Restorative codes are NOT surgery.
    assert "D6058" not in _IMPLANT_SURGERY_CDT_CODES
    assert "D6056" not in _IMPLANT_SURGERY_CDT_CODES
    assert "D6057" not in _IMPLANT_SURGERY_CDT_CODES


@pytest.mark.asyncio
async def test_self_fill_resolves_unseen_surgery_code_on_miss() -> None:
    """A procedureCodeId absent from the catalog triggers a best-effort by-id
    self-fill; once resolved to a custom surgical CDT it gates as surgery."""
    service, *_ = _make_service()
    client = MagicMock(
        spec=["list_treatment_procedures_modified_since", "get_procedure_code"]
    )
    client.get_procedure_code = AsyncMock(
        return_value={"id": 228501, "code": "D6010.A", "description": "Implant All on X"}
    )
    service._carestack = client  # type: ignore[attr-defined]

    catalog = MagicMock(spec=["resolve_procedure_codes", "ensure_procedure_codes"])
    # First resolve: miss. After self-fill: hit with the custom surgical code.
    catalog.resolve_procedure_codes = AsyncMock(
        side_effect=[{}, {228501: ("D6010.A", "Implant All on X")}]
    )
    catalog.ensure_procedure_codes = AsyncMock(return_value=[228501])
    service._catalog = catalog  # type: ignore[attr-defined]

    assert await service._is_implant_surgery({"procedureCodeId": 228501}) is True
    catalog.ensure_procedure_codes.assert_awaited_once()
    assert catalog.ensure_procedure_codes.await_args.args[1] == [228501]


@pytest.mark.asyncio
async def test_self_fill_negative_cache_skips_repeat_lookup_on_miss() -> None:
    """ENG-538: an id that resolves-missing once is negative-cached, so a
    second row with the SAME unresolved code does not re-call CareStack."""
    service, *_ = _make_service()
    client = MagicMock(
        spec=["list_treatment_procedures_modified_since", "get_procedure_code"]
    )
    client.get_procedure_code = AsyncMock()
    service._carestack = client  # type: ignore[attr-defined]

    catalog = MagicMock(spec=["resolve_procedure_codes", "ensure_procedure_codes"])
    catalog.resolve_procedure_codes = AsyncMock(return_value={})  # always a miss
    catalog.ensure_procedure_codes = AsyncMock(return_value=[])  # resolved-missing
    service._catalog = catalog  # type: ignore[attr-defined]

    first = await service._is_implant_surgery({"procedureCodeId": 999999})
    second = await service._is_implant_surgery({"procedureCodeId": 999999})

    assert first is False
    assert second is False
    # Self-fill attempted exactly once; the second row hit the negative cache.
    catalog.ensure_procedure_codes.assert_awaited_once()


@pytest.mark.asyncio
async def test_self_fill_failure_is_negative_cached_and_never_breaks_ingest() -> None:
    """ENG-538: a hard self-fill failure (e.g. propagated 401 auth error from
    the by-id fetch) is swallowed AND negative-cached — ingest keeps the
    generic mapping and a repeat row does not re-call CareStack."""
    service, *_ = _make_service()
    client = MagicMock(
        spec=["list_treatment_procedures_modified_since", "get_procedure_code"]
    )
    client.get_procedure_code = AsyncMock()
    service._carestack = client  # type: ignore[attr-defined]

    catalog = MagicMock(spec=["resolve_procedure_codes", "ensure_procedure_codes"])
    catalog.resolve_procedure_codes = AsyncMock(return_value={})
    catalog.ensure_procedure_codes = AsyncMock(
        side_effect=_FakeCareStackApiError("unauthorised", status=401)
    )
    service._catalog = catalog  # type: ignore[attr-defined]

    # Must NOT raise — self-fill is best-effort even on a hard auth failure.
    first = await service._is_implant_surgery({"procedureCodeId": 228501})
    second = await service._is_implant_surgery({"procedureCodeId": 228501})

    assert first is False
    assert second is False
    catalog.ensure_procedure_codes.assert_awaited_once()


@pytest.mark.asyncio
async def test_self_fill_skipped_when_client_lacks_by_id_method() -> None:
    """Lean stub clients without ``get_procedure_code`` stay fail-closed: a
    catalog miss yields "not surgery" and never attempts self-fill."""
    service, *_ = _make_service()
    client = MagicMock(spec=["list_treatment_procedures_modified_since"])
    service._carestack = client  # type: ignore[attr-defined]

    catalog = MagicMock(spec=["resolve_procedure_codes", "ensure_procedure_codes"])
    catalog.resolve_procedure_codes = AsyncMock(return_value={})
    catalog.ensure_procedure_codes = AsyncMock(return_value=[])
    service._catalog = catalog  # type: ignore[attr-defined]

    assert await service._is_implant_surgery({"procedureCodeId": 228501}) is False
    catalog.ensure_procedure_codes.assert_not_awaited()


@pytest.mark.asyncio
async def test_implant_non_surgery_status_keeps_generic_mapping() -> None:
    # An implant CDT in a non-2/8 status (e.g. proposed) is NOT a surgery event.
    service, _, _, _, interaction, _ = _make_service(
        body={
            "treatmentProcedures": [_procedure(statusId=1, procedureCodeId=117408)],
            "continueToken": None,
        },
        location=None,
    )
    _set_catalog(service, {117408: ("D6010", "Surgical placement of implant body")})

    await service.import_recent_treatments(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_proposed"
    assert "is_implant_surgery" not in event_in.payload


@pytest.mark.asyncio
async def test_unresolved_procedure_code_is_not_implant() -> None:
    # procedureCodeId present but not in the catalog → fail closed to generic.
    service, _, _, _, interaction, _ = _make_service(
        body={
            "treatmentProcedures": [_procedure(statusId=8, procedureCodeId=999999)],
            "continueToken": None,
        },
        location=None,
    )
    _set_catalog(service, {})  # nothing resolves

    await service.import_recent_treatments(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_completed"
    assert "is_implant_surgery" not in event_in.payload


# ---------------------------------------------------------- ENG-269 dedup contract


@pytest.mark.asyncio
async def test_cross_pull_conflict_counts_as_unchanged_not_failed() -> None:
    """ENG-329 — a re-pull of an already-emitted treatment procedure hits
    the cross-pull partial UNIQUE on ``interaction.event`` and
    ``create_event_idempotent`` returns ``was_created=False``. That is an
    idempotent dedup — HEALTHY — so it must count as ``unchanged``, NOT
    ``skipped`` (which the sync_run folds into ``failed``).
    """
    service, _, ingest, _, interaction, _ = _make_service()
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=False
        )
    )

    result = await service.import_recent_treatments(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_awaited_once()


# ---------------------------------------------------------- ENG-351 deep backfill (pull_all_since)


class _FakeCareStackApiError(Exception):
    """Stand-in for ``CareStackApiError`` — duck-types via ``.details``."""

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.details = {"status": status}


class _SleepRecorder:
    """Async sleep stand-in that records waits and does not block."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.mark.asyncio
async def test_pull_all_since_paginates_until_null_continue_token() -> None:
    page1 = {
        "treatmentProcedures": [_procedure(id=1)],
        "continueToken": "next",
    }
    page2 = {
        "treatmentProcedures": [_procedure(id=2)],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        side_effect=[page1, page2]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep=sleep,
    )

    assert result.imported_count == 2
    assert result.page_count == 2
    assert result.next_continue_token is None
    assert cs_client.list_treatment_procedures_modified_since.await_count == 2
    second_call_kwargs = (
        cs_client.list_treatment_procedures_modified_since.await_args_list[1].kwargs
    )
    assert second_call_kwargs["continue_token"] == "next"
    # ENG-326: each page is committed (releases per-event SAVEPOINTs).
    assert service._session.commit.await_count == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pull_all_since_default_since_is_2026_01_01() -> None:
    service, cs_client, *_ = _make_service(
        body={"treatmentProcedures": [_procedure()], "continueToken": None}
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(_TENANT_ID, sleep=sleep)

    cs_client.list_treatment_procedures_modified_since.assert_awaited_once()
    modified_since = (
        cs_client.list_treatment_procedures_modified_since.await_args.args[0]
    )
    assert modified_since == datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_pull_all_since_dedup_counts_as_unchanged() -> None:
    """A re-pull of an already-emitted procedure deduplicates → unchanged."""
    service, _, ingest, _, interaction, _ = _make_service(
        body={"treatmentProcedures": [_procedure()], "continueToken": None}
    )
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=False
        )
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID, since=datetime(2026, 1, 1, tzinfo=UTC), sleep=sleep
    )

    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_pull_all_since_sleeps_between_pages_but_not_after_last() -> None:
    page1 = {"treatmentProcedures": [_procedure(id=1)], "continueToken": "tok1"}
    page2 = {"treatmentProcedures": [_procedure(id=2)], "continueToken": "tok2"}
    page3 = {"treatmentProcedures": [_procedure(id=3)], "continueToken": None}
    service, cs_client, *_ = _make_service()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        side_effect=[page1, page2, page3]
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.75,
        sleep=sleep,
    )

    assert sleep.waits == [0.75, 0.75]


@pytest.mark.asyncio
async def test_pull_all_since_retries_with_exponential_backoff() -> None:
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    ok_page = {"treatmentProcedures": [_procedure()], "continueToken": None}
    service, cs_client, *_ = _make_service()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        side_effect=[rate_limit, rate_limit, ok_page]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.0,
        max_retries=5,
        backoff_base_seconds=1.0,
        sleep=sleep,
    )

    assert result.imported_count == 1
    assert sleep.waits == [1.0, 2.0]
    assert cs_client.list_treatment_procedures_modified_since.await_count == 3


@pytest.mark.asyncio
async def test_pull_all_since_returns_resume_token_when_retries_exhausted() -> None:
    page1 = {"treatmentProcedures": [_procedure(id=1)], "continueToken": "resume-here"}
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, cs_client, *_ = _make_service()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        side_effect=[page1, rate_limit, rate_limit, rate_limit]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.0,
        max_retries=2,
        backoff_base_seconds=0.25,
        sleep=sleep,
    )

    assert result.page_count == 1
    assert result.next_continue_token == "resume-here"
    assert sleep.waits == [0.25, 0.5]


@pytest.mark.asyncio
async def test_pull_all_since_stops_at_page_safety_cap() -> None:
    looping_page = {
        "treatmentProcedures": [_procedure()],
        "continueToken": "never-ends",
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        return_value=looping_page
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        page_safety_cap=3,
        sleep_seconds=0.0,
        sleep=sleep,
    )

    assert result.page_count == 3
    assert result.next_continue_token == "never-ends"
    assert cs_client.list_treatment_procedures_modified_since.await_count == 3


@pytest.mark.asyncio
async def test_pull_all_since_propagates_non_retryable_errors() -> None:
    not_connected = _FakeCareStackApiError("unauthorised", status=401)
    service, cs_client, *_ = _make_service()
    cs_client.list_treatment_procedures_modified_since = AsyncMock(
        side_effect=not_connected
    )
    sleep = _SleepRecorder()

    with pytest.raises(_FakeCareStackApiError):
        await service.pull_all_since(
            _TENANT_ID,
            since=datetime(2026, 1, 1, tzinfo=UTC),
            sleep_seconds=0.0,
            sleep=sleep,
        )

    assert sleep.waits == []


@pytest.mark.asyncio
async def test_pull_all_since_naive_since_is_treated_as_utc() -> None:
    service, cs_client, *_ = _make_service(
        body={"treatmentProcedures": [_procedure()], "continueToken": None}
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(
        _TENANT_ID, since=datetime(2026, 1, 1), sleep=sleep
    )

    modified_since = (
        cs_client.list_treatment_procedures_modified_since.await_args.args[0]
    )
    assert modified_since.tzinfo is not None
    assert modified_since == datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_pull_all_since_rejects_invalid_arguments() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.pull_all_since(_TENANT_ID, page_size=0)
    with pytest.raises(ValidationError):
        await service.pull_all_since(_TENANT_ID, page_size=600)
    with pytest.raises(ValidationError):
        await service.pull_all_since(_TENANT_ID, page_safety_cap=0)
    with pytest.raises(ValidationError):
        await service.pull_all_since(_TENANT_ID, max_retries=-1)
    with pytest.raises(ValidationError):
        await service.pull_all_since(_TENANT_ID, sleep_seconds=-0.1)
    with pytest.raises(ValidationError):
        await service.pull_all_since(_TENANT_ID, backoff_base_seconds=-0.1)


# ---------------------------------------------------------- ENG-540 replay (reproject_treatments_from_raw)


@pytest.mark.asyncio
async def test_replay_emits_surgery_scheduled_for_historical_implant() -> None:
    """ENG-540: a historical implant procedure (statusId=2, implant CDT) that a
    normal re-pull would dedup-skip emits ``surgery_scheduled`` on replay —
    WITHOUT re-capturing raw and WITHOUT pulling the CareStack feed."""
    service, cs_client, ingest, _, interaction, _ = _make_service()
    _set_catalog(service, {117408: ("D6010", "Surgical placement of implant body")})
    raw_event_id = uuid.uuid4()
    row = _procedure(statusId=2, procedureCodeId=117408, locationId=None)

    result = await service.reproject_treatments_from_raw(
        _TENANT_ID, rows=[(raw_event_id, row)]
    )

    assert result.imported_count == 1
    assert result.unchanged_count == 0
    assert result.skipped_count == 0
    assert result.page_count == 0
    # Replay must NOT re-capture raw and must NOT pull the CareStack feed.
    ingest.capture.assert_not_awaited()
    cs_client.list_treatment_procedures_modified_since.assert_not_awaited()
    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "surgery_scheduled"
    assert event_in.payload == {"is_implant_surgery": True}
    # The emitted event points at the EXISTING raw_event, not a fresh capture.
    assert event_in.source_event_id == raw_event_id


@pytest.mark.asyncio
async def test_replay_emits_surgery_completed_for_historical_implant() -> None:
    service, _, _, _, interaction, _ = _make_service()
    _set_catalog(service, {117408: ("D6013", "Surgical placement of mini implant")})
    row = _procedure(statusId=8, procedureCodeId=117408, locationId=None)

    result = await service.reproject_treatments_from_raw(
        _TENANT_ID, rows=[(uuid.uuid4(), row)]
    )

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "surgery_completed"
    assert event_in.payload["is_implant_surgery"] is True


@pytest.mark.asyncio
async def test_replay_is_idempotent_second_run_emits_zero_new_events() -> None:
    """ENG-540 idempotency: when the event already exists,
    ``create_event_idempotent`` returns ``was_created=False`` so the replay
    reports zero imported (all ``unchanged``)."""
    service, _, _, _, interaction, _ = _make_service()
    _set_catalog(service, {117408: ("D6010", "Surgical placement of implant body")})
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=False
        )
    )
    row = _procedure(statusId=2, procedureCodeId=117408, locationId=None)

    result = await service.reproject_treatments_from_raw(
        _TENANT_ID, rows=[(uuid.uuid4(), row)]
    )

    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0


@pytest.mark.asyncio
async def test_replay_non_implant_row_keeps_generic_mapping() -> None:
    """A non-implant procedure replays to the generic mapping — no surgery
    event, no surgical flag — so other statuses are unaffected."""
    service, _, _, _, interaction, _ = _make_service()
    _set_catalog(service, {555: ("D0120", "Periodic oral evaluation")})
    row = _procedure(statusId=2, procedureCodeId=555, locationId=None)

    result = await service.reproject_treatments_from_raw(
        _TENANT_ID, rows=[(uuid.uuid4(), row)]
    )

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "treatment_proposed"
    assert "is_implant_surgery" not in event_in.payload


@pytest.mark.asyncio
async def test_replay_skips_unlinked_patient_without_capturing_raw() -> None:
    """A row whose patient is not yet linked is skipped (no event) and the
    replay never re-captures raw."""
    service, _, ingest, identity_repo, interaction, _ = _make_service()
    identity_repo.find_source_link = AsyncMock(return_value=None)
    row = _procedure(statusId=2, procedureCodeId=117408, locationId=None)

    result = await service.reproject_treatments_from_raw(
        _TENANT_ID, rows=[(uuid.uuid4(), row)]
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1
    ingest.capture.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_skips_row_without_procedure_id() -> None:
    service, *_ = _make_service()
    row = {"patientId": 9985, "statusId": 2}  # no id/procedureId

    result = await service.reproject_treatments_from_raw(
        _TENANT_ID, rows=[(uuid.uuid4(), row)]
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1


@pytest.mark.asyncio
async def test_replay_empty_batch_is_a_noop() -> None:
    service, _, ingest, _, interaction, _ = _make_service()

    result = await service.reproject_treatments_from_raw(_TENANT_ID, rows=[])

    assert result.imported_count == 0
    assert result.unchanged_count == 0
    assert result.skipped_count == 0
    ingest.capture.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()
