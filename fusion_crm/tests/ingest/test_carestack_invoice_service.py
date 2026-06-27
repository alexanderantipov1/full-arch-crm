"""Unit tests for ``CareStackInvoiceIngestService`` (ENG-268 slice).

Focused on the location-on-payload contract added in ENG-268:
location resolved + stored, unmapped/missing tolerated, no PHI leakage.
Mirrors the accounting-transaction location tests added by ENG-267 —
the invoice emit side is the only piece the dashboard was missing.
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
from packages.ingest.carestack_invoice_service import (
    CareStackInvoiceIngestService,
    _invoice_location_id,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LOCATION_UID = uuid.uuid4()


# PHI / clinical fixture set — none of these tokens may appear in any
# emitted timeline summary or in the safe event payload. The verbatim
# raw_event payload is allowed to carry them (forensic capture).
_PHI_TOKENS = (
    "must NEVER reach timeline",
    "9985-PHI",
    "patient notes",
    "Dr. Smith",
)


def _invoice(**overrides: object) -> dict[str, Any]:
    """Build a representative Invoice row.

    Defaults mirror the field list in
    ``docs/integrations/carestack/sync/invoices.md``.
    """
    base: dict[str, Any] = {
        "invoiceId": 5501,
        "patientId": 9985,
        "locationId": 10029,
        "providerId": 3,
        "amount": 250.0,
        "unappliedAmount": 0.0,
        "invoiceType": 1,
        "invoiceSource": 1,
        "paymentTypeId": 4,
        "paymentDate": "2026-05-22T14:00:00Z",
        "lastUpdatedOn": "2026-05-22T14:01:00Z",
        "isDeleted": False,
        "isNsf": False,
        # PHI-shaped fields included to assert they stay inside the raw
        # payload and never surface into anything we construct.
        "notes": "must NEVER reach timeline — patient notes",
        "providerName": "Dr. Smith",
    }
    base.update(overrides)
    return base


_LOCATION_DEFAULT = object()  # sentinel: distinguishes "not supplied" from None.


def _make_service(
    body: dict[str, Any] | None = None,
    source_link: SimpleNamespace | None = None,
    location: object = _LOCATION_DEFAULT,
) -> tuple[
    CareStackInvoiceIngestService,
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
    cs_client.list_invoices_modified_since = AsyncMock(
        return_value=body
        or {
            "invoices": [_invoice()],
            "continueToken": None,
        }
    )
    service = CareStackInvoiceIngestService(session, cs_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["capture", "max_payload_watermark", "latest_payload_values"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    # Default: no captured stamps → guard never short-circuits a row.
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(
        return_value=source_link
        if source_link is not None
        else SimpleNamespace(person_uid=_PERSON_UID)
    )
    # ENG-269: CareStack callers call create_event_idempotent so they can
    # distinguish a fresh insert (was_created=True → "imported") from a
    # cross-pull dedup conflict (was_created=False → "skipped").
    service._interaction = MagicMock(spec=["create_event_idempotent"])  # type: ignore[attr-defined]
    service._interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(event=SimpleNamespace(id=uuid.uuid4()), was_created=True)
    )
    service._locations = MagicMock(spec=["find_by_carestack_id"])  # type: ignore[attr-defined]
    # Default: every CS locationId resolves to ``_LOCATION_UID``. Callers
    # override via ``location=None`` (unmapped) or
    # ``location=SimpleNamespace(id=...)`` to model a specific mapped row.
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
async def test_import_captures_raw_then_emits_invoice_created_event() -> None:
    service, _, ingest, identity_repo, interaction, _ = _make_service()

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.page_count == 1
    assert result.next_continue_token is None

    ingest.capture.assert_awaited_once()
    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.source == "carestack"
    assert raw_call.event_type == "carestack.invoice.upsert"
    assert raw_call.external_id == "5501"
    # Capture-then-route: verbatim payload. PHI-shaped fields are present
    # in the raw row by design — they are gated by ingest schema rules.
    assert raw_call.payload["notes"].startswith("must NEVER")

    identity_repo.find_source_link.assert_awaited_once_with(
        _TENANT_ID,
        source_system="carestack",
        source_instance="carestack-main",
        source_kind="patient",
        source_id="9985",
    )

    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "invoice_created"
    assert event_in.source_provider == "carestack"
    assert event_in.source_kind == "carestack_invoice"
    assert event_in.data_class == "billing"
    assert event_in.source_external_id == "5501"
    assert event_in.person_uid == _PERSON_UID


# ---------------------------------------------------------- location resolution


@pytest.mark.asyncio
async def test_mapped_location_id_is_added_to_safe_payload() -> None:
    """A CS locationId that resolves to a tenant.location lands as
    ``location_id`` (str UUID) in the safe event payload."""
    service, _, _, _, interaction, locations = _make_service()

    await service.import_recent_invoices(_TENANT_ID, days=7)

    locations.find_by_carestack_id.assert_awaited_once_with(_TENANT_ID, 10029)
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.payload.get("location_id") == str(_LOCATION_UID)


@pytest.mark.asyncio
async def test_unmapped_location_omits_location_id_but_emits_event() -> None:
    """When the CS locationId has no tenant.location mapping yet, the
    safe payload simply omits ``location_id`` — the event still emits.
    """
    service, _, _, _, interaction, locations = _make_service(location=None)

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.imported_count == 1
    locations.find_by_carestack_id.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


@pytest.mark.asyncio
async def test_missing_location_id_field_skips_resolver_and_emits_event() -> None:
    """An invoice row without ``locationId`` never calls the resolver
    and still emits without ``location_id`` in payload."""
    service, _, _, _, interaction, locations = _make_service(
        body={
            "invoices": [_invoice(locationId=None)],
            "continueToken": None,
        }
    )

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.imported_count == 1
    locations.find_by_carestack_id.assert_not_awaited()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


@pytest.mark.asyncio
async def test_resolver_not_found_error_omits_location_id() -> None:
    """If the resolver raises ``NotFoundError`` (tenant unknown — should
    not happen in practice, but defensive), the event still emits without
    ``location_id``."""
    service, _, _, _, interaction, locations = _make_service()
    locations.find_by_carestack_id = AsyncMock(
        side_effect=NotFoundError("tenant not found", details={})
    )

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


# ---------------------------------------------------------- no-PHI assertion


@pytest.mark.asyncio
async def test_emitted_event_summary_and_payload_carry_no_phi_tokens() -> None:
    """Service-constructed fields must never contain PHI / clinical text.

    The raw_event payload is allowed to carry PHI (capture-then-route);
    every field the service constructs itself (summary, event payload,
    event_type, external_id) must not.
    """
    service, _, _, _, interaction, _ = _make_service()

    await service.import_recent_invoices(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    for token in _PHI_TOKENS:
        assert token not in event_in.summary
        assert all(token not in str(v) for v in event_in.payload.values())

    # Safe payload allowlist: only amount + invoice_type +
    # (optional) location_id are written by this service. Never
    # paymentCategory free-text, never patient identifiers.
    assert set(event_in.payload.keys()).issubset(
        {"amount", "invoice_type", "location_id"}
    )
    assert event_in.payload.get("amount") == pytest.approx(250.0)
    assert event_in.payload.get("invoice_type") == 1


# ---------------------------------------------------------- helper unit tests


def test_invoice_location_id_helper_parses_int_or_string() -> None:
    assert _invoice_location_id({"locationId": 10029}) == 10029
    assert _invoice_location_id({"LocationId": 10029}) == 10029
    assert _invoice_location_id({"locationId": "10029"}) == 10029
    assert _invoice_location_id({"locationId": None}) is None
    assert _invoice_location_id({"locationId": "not-a-number"}) is None
    # ``bool`` is an ``int`` subclass; the helper must reject it so True
    # never becomes location id 1.
    assert _invoice_location_id({"locationId": True}) is None
    assert _invoice_location_id({}) is None


# ---------------------------------------------------------- ENG-269 dedup contract


@pytest.mark.asyncio
async def test_cross_pull_conflict_counts_as_unchanged_not_failed() -> None:
    """ENG-329 — when the cross-pull partial UNIQUE on
    ``interaction.event`` turns ``create_event_idempotent`` into a no-op
    (re-pull of an already-emitted invoice), the import must count the
    row as ``unchanged`` (HEALTHY dedup), NOT ``skipped`` (which the
    sync_run folds into ``failed``). The raw_event capture still happens
    on every pull (capture-then-route is intentional).
    """
    service, _, ingest, _, interaction, _ = _make_service()
    # Simulate the second pull of the same invoice: insert is a no-op,
    # the existing row is returned with was_created=False.
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=False
        )
    )

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0
    # raw_event capture still happens on every pull (forensic record).
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
    page1 = {"invoices": [_invoice(invoiceId=1)], "continueToken": "next"}
    page2 = {"invoices": [_invoice(invoiceId=2)], "continueToken": None}
    service, cs_client, *_ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(side_effect=[page1, page2])
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID, since=datetime(2026, 1, 1, tzinfo=UTC), sleep=sleep
    )

    assert result.imported_count == 2
    assert result.page_count == 2
    assert result.next_continue_token is None
    assert cs_client.list_invoices_modified_since.await_count == 2
    second_call_kwargs = (
        cs_client.list_invoices_modified_since.await_args_list[1].kwargs
    )
    assert second_call_kwargs["continue_token"] == "next"
    # ENG-326: each page is committed (releases per-event SAVEPOINTs).
    assert service._session.commit.await_count == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pull_all_since_default_since_is_2026_01_01() -> None:
    service, cs_client, *_ = _make_service(
        body={"invoices": [_invoice()], "continueToken": None}
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(_TENANT_ID, sleep=sleep)

    cs_client.list_invoices_modified_since.assert_awaited_once()
    modified_since = cs_client.list_invoices_modified_since.await_args.args[0]
    assert modified_since == datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_pull_all_since_dedup_counts_as_unchanged() -> None:
    service, _, ingest, _, interaction, _ = _make_service(
        body={"invoices": [_invoice()], "continueToken": None}
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
    page1 = {"invoices": [_invoice(invoiceId=1)], "continueToken": "tok1"}
    page2 = {"invoices": [_invoice(invoiceId=2)], "continueToken": "tok2"}
    page3 = {"invoices": [_invoice(invoiceId=3)], "continueToken": None}
    service, cs_client, *_ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(
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
    ok_page = {"invoices": [_invoice()], "continueToken": None}
    service, cs_client, *_ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(
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
    assert cs_client.list_invoices_modified_since.await_count == 3


@pytest.mark.asyncio
async def test_pull_all_since_returns_resume_token_when_retries_exhausted() -> None:
    page1 = {"invoices": [_invoice(invoiceId=1)], "continueToken": "resume-here"}
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, cs_client, *_ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(
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
    looping_page = {"invoices": [_invoice()], "continueToken": "never-ends"}
    service, cs_client, *_ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(return_value=looping_page)
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
    assert cs_client.list_invoices_modified_since.await_count == 3


@pytest.mark.asyncio
async def test_pull_all_since_propagates_non_retryable_errors() -> None:
    not_connected = _FakeCareStackApiError("unauthorised", status=401)
    service, cs_client, *_ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(side_effect=not_connected)
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
        body={"invoices": [_invoice()], "continueToken": None}
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(
        _TENANT_ID, since=datetime(2026, 1, 1), sleep=sleep
    )

    modified_since = cs_client.list_invoices_modified_since.await_args.args[0]
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


# ---------------------------------------------------------- ENG-384 capture change-guard


@pytest.mark.asyncio
async def test_capture_guard_skips_row_with_unchanged_stamp() -> None:
    """ENG-384: a row whose captured ``lastUpdatedOn`` matches the
    upstream stamp is a healthy overlap re-read — no raw write, no
    downstream emit, no source-link resolution."""
    invoice = _invoice()
    service, _, ingest, identity_repo, interaction, _ = _make_service(
        body={"invoices": [invoice], "continueToken": None}
    )
    ingest.latest_payload_values = AsyncMock(
        return_value={str(invoice["invoiceId"]): invoice["lastUpdatedOn"]}
    )

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    assert result.skipped_count == 0
    ingest.capture.assert_not_awaited()
    identity_repo.find_source_link.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_capture_guard_captures_row_with_newer_stamp() -> None:
    """A moved provider stamp means a real change — the row is captured."""
    invoice = _invoice()
    service, _, ingest, _, _, _ = _make_service(
        body={"invoices": [invoice], "continueToken": None}
    )
    ingest.latest_payload_values = AsyncMock(
        return_value={str(invoice["invoiceId"]): "2026-04-01T00:00:00Z"}
    )

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.unchanged_count == 0
    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_capture_guard_row_without_stamp_falls_through_to_capture() -> None:
    """A row whose payload has no ``lastUpdatedOn`` cannot be safely
    guarded and falls through to capture — defensive against feeds that
    omit the stamp on a subset of rows."""
    invoice = _invoice(lastUpdatedOn=None)
    service, _, ingest, _, _, _ = _make_service(
        body={"invoices": [invoice], "continueToken": None}
    )

    result = await service.import_recent_invoices(_TENANT_ID, days=7)

    assert result.imported_count == 1
    assert result.unchanged_count == 0
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_pull_all_since_capture_guard_skips_unchanged_rows() -> None:
    """ENG-384: deep backfill applies the same guard so an operator
    re-sweep over already-captured rows writes ZERO new raw events."""
    invoice = _invoice()
    service, cs_client, ingest, _, interaction, _ = _make_service()
    cs_client.list_invoices_modified_since = AsyncMock(
        return_value={"invoices": [invoice], "continueToken": None}
    )
    ingest.latest_payload_values = AsyncMock(
        return_value={str(invoice["invoiceId"]): invoice["lastUpdatedOn"]}
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.0,
        sleep=sleep,
    )

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    assert result.skipped_count == 0
    ingest.capture.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()
