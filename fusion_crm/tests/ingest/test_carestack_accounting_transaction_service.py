"""Unit tests for ``CareStackAccountingTransactionIngestService`` (ENG-257; ENG-283).

Cover the capture + idempotency behaviour AND the ENG-283 payment event
emission path: ``transactionCode``-based mapping
(``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` → ``payment_recorded``;
``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED`` → ``payment_applied``;
``PATIENTPAYMENTSDELETE`` → ``payment_reversed``; refund codes →
``payment_refunded``; ``isReversed`` overrides to ``payment_reversed``);
non-payment codes and rows without a code stay raw-only (no event); safe
summary + payload carry amount + transactionType only (NO PHI / clinical
codes / patient identifiers); pagination follows ``continueToken``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId
from packages.ingest.carestack_accounting_transaction_service import (
    CareStackAccountingTransactionIngestService,
    _compose_idempotency_key,
    _extract_rows,
    _payment_event_kind,
    _transaction_last_updated_on,
    _transaction_location_id,
    _transaction_patient_id,
    _transaction_source_id,
)

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID = uuid.uuid4()
_LOCATION_UID = uuid.uuid4()


# PHI / clinical fixture set — none of these tokens may appear in any
# emitted timeline summary or in the safe event payload. The verbatim
# raw_event payload is allowed to carry them (forensic capture), but no
# field this service constructs itself may include them.
_PHI_TOKENS = (
    "must NEVER reach timeline",
    "9985-PHI",
    "tooth #14",
    "Dr. Smith",
    "patient notes",
)


def _transaction(**overrides: object) -> dict[str, Any]:
    """Build a representative AccountingTransaction row.

    Defaults mirror the field list in
    ``docs/integrations/carestack/sync/accounting-transactions.md``.
    """
    base: dict[str, Any] = {
        "id": 88001,
        "accountId": 17,
        "transactionDate": "2026-05-22T14:00:00Z",
        "providerId": 3,
        "procedureCodeId": 9,
        "transactionType": "credit",
        "amount": 125.50,
        "folioType": "PATIENTCREDIT",
        "transactionCode": "PATIENTPAYMENTS",
        "invoiceId": 5501,
        "locationId": 10029,
        "isReversed": False,
        "entryGroupId": "egid-abc",
        "lastUpdatedOn": "2026-05-22T14:01:00Z",
        "patientId": 9985,
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
    CareStackAccountingTransactionIngestService,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    session = MagicMock()
    # pull_all_since checkpoints per page (ENG-326) — commit must be awaitable.
    session.commit = AsyncMock()
    cs_client = MagicMock()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        return_value=body
        or {
            "accountingTransactions": [_transaction()],
            "continueToken": None,
        }
    )
    service = CareStackAccountingTransactionIngestService(session, cs_client)
    service._ingest = MagicMock(  # type: ignore[attr-defined]
        spec=["capture", "max_payload_watermark", "latest_payload_values"]
    )
    service._ingest.capture = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4(), received_at=datetime.now(UTC))
    )
    # Default: no prior watermark → falls back to the ``now - days`` window.
    service._ingest.max_payload_watermark = AsyncMock(return_value=None)
    # Default: no captured stamps → guard never short-circuits a row.
    service._ingest.latest_payload_values = AsyncMock(return_value={})
    service._identity_repo = MagicMock(spec=["find_source_link"])  # type: ignore[attr-defined]
    service._identity_repo.find_source_link = AsyncMock(
        return_value=source_link
        if source_link is not None
        else SimpleNamespace(person_uid=_PERSON_UID)
    )
    # ENG-269: CareStack callers use create_event_idempotent so cross-pull
    # dedup conflicts count as "skipped" instead of "imported".
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
async def test_import_captures_raw_then_emits_payment_event() -> None:
    service, _, ingest, identity_repo, interaction, _ = _make_service()

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 1
    assert result.skipped_count == 0
    assert result.page_count == 1
    assert result.next_continue_token is None

    ingest.capture.assert_awaited_once()
    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.source == "carestack"
    assert raw_call.event_type == "carestack.accounting_transaction.upsert"
    # external_id encodes the spec idempotency key (id, lastUpdatedOn).
    assert raw_call.external_id == "88001:2026-05-22T14:01:00Z"
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
    assert event_in.kind == "payment_recorded"
    assert event_in.source_provider == "carestack"
    assert event_in.source_kind == "carestack_accounting_transaction"
    assert event_in.data_class == "billing"
    assert event_in.source_external_id == "88001"
    assert event_in.person_uid == _PERSON_UID


# ------------------------------------------------------ transactionCode → kind mapping (ENG-283)


@pytest.mark.parametrize(
    ("transaction_code", "expected_kind"),
    [
        ("PATIENTPAYMENTS", "payment_recorded"),
        ("INSURANCEPAYMENTS", "payment_recorded"),
        ("PATPAYMENTAPPLIED", "payment_applied"),
        ("INSPAYMENTAPPLIED", "payment_applied"),
        ("PATIENTPAYMENTSDELETE", "payment_reversed"),
        ("REFUND", "payment_refunded"),
        ("PATIENTREFUND", "payment_refunded"),
        ("INSURANCEREFUND", "payment_refunded"),
    ],
)
@pytest.mark.asyncio
async def test_payment_codes_map_to_expected_kinds(
    transaction_code: str, expected_kind: str
) -> None:
    """ENG-283: classification keys off ``transactionCode``, not ``folioType``."""
    service, _, _, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [_transaction(transactionCode=transaction_code)],
            "continueToken": None,
        }
    )

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    interaction.create_event_idempotent.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == expected_kind


@pytest.mark.asyncio
async def test_reversed_cash_payment_code_emits_payment_reversed() -> None:
    """ENG-284: ``isReversed=True`` flips a CASH code
    (``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` / refund) to
    ``payment_reversed``. The allow-list is the strict pre-condition
    for emission; see
    :func:`test_reversed_non_payment_code_emits_no_event` for the
    counter-test on non-payment codes and
    :func:`test_reversed_allocation_code_stays_payment_applied` for
    the counter-test on allocation codes.
    """
    service, _, _, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(transactionCode="PATIENTPAYMENTS", isReversed=True)
            ],
            "continueToken": None,
        }
    )

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "payment_reversed"


@pytest.mark.parametrize(
    "allocation_code", ["PATPAYMENTAPPLIED", "INSPAYMENTAPPLIED"]
)
@pytest.mark.asyncio
async def test_reversed_allocation_code_stays_payment_applied(
    allocation_code: str,
) -> None:
    """ENG-284: ``isReversed=True`` on an ALLOCATION code keeps the
    event at ``payment_applied`` — the reversed allocation is still an
    allocation event, and the paired ``PATIENTPAYMENTSDELETE`` row
    carries the cash reversal. Promoting the allocation reversal to
    ``payment_reversed`` would double-subtract the cash from the
    Collected aggregate (recreating the negative-Collected bug from a
    different angle: 70 reversed PATPAYMENTAPPLIED rows in the dev DB
    contributed ~$40k to the reversed bucket under the old rule).
    """
    service, _, _, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(transactionCode=allocation_code, isReversed=True)
            ],
            "continueToken": None,
        }
    )

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.kind == "payment_applied"


@pytest.mark.parametrize(
    "transaction_code",
    [
        "PROCEDURECOMPLETED",
        "PATIENTADJUSTMENT",
        "FEEUPDATION",
        "UNKNOWNCODE",
    ],
)
@pytest.mark.asyncio
async def test_non_payment_codes_emit_no_event(transaction_code: str) -> None:
    """Charges, adjustments, fee updates, and unknown codes stay raw-only."""
    service, _, ingest, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(transactionCode=transaction_code, folioType="PATIENTCREDIT")
            ],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    # Raw row is still captured (forensic), no timeline event is emitted.
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_not_awaited()
    assert result.imported_count == 0
    assert result.skipped_count == 1


@pytest.mark.parametrize(
    "transaction_code",
    [
        "PROCEDURECOMPLETED",
        "PATIENTADJUSTMENT",
        "FEEUPDATION",
        "UNKNOWNCODE",
    ],
)
@pytest.mark.asyncio
async def test_reversed_non_payment_code_emits_no_event(
    transaction_code: str,
) -> None:
    """ENG-284: ``isReversed=True`` on a non-payment code stays raw-only.

    The ENG-283 override flipped EVERY ``isReversed=True`` row to
    ``payment_reversed``, which promoted reversed charges and reversed
    adjustments into the Collected aggregate and made the dashboard
    total go negative. The strict allow-list says: if the code is not
    a payment code, no event is emitted — ``isReversed`` cannot
    promote a non-payment row into the payment kind set.
    """
    service, _, ingest, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(transactionCode=transaction_code, isReversed=True)
            ],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_not_awaited()
    assert result.imported_count == 0
    assert result.skipped_count == 1


@pytest.mark.asyncio
async def test_reversed_row_without_transaction_code_emits_no_event() -> None:
    """ENG-284: ``isReversed=True`` on a row with no ``transactionCode``
    stays raw-only — the allow-list check happens BEFORE the
    ``isReversed`` override."""
    service, _, ingest, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(transactionCode=None, isReversed=True)
            ],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_not_awaited()
    assert result.imported_count == 0
    assert result.skipped_count == 1


@pytest.mark.asyncio
async def test_row_without_transaction_code_emits_no_event() -> None:
    """No ``transactionCode`` at all → raw-only, even with a payment-looking folio."""
    service, _, ingest, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(transactionCode=None, folioType="PATIENTCREDIT")
            ],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_not_awaited()
    assert result.imported_count == 0
    assert result.skipped_count == 1


# ------------------------------------------------------ no-PHI assertion


@pytest.mark.asyncio
async def test_emitted_event_summary_and_payload_carry_no_phi_tokens() -> None:
    """Service-constructed fields must never contain PHI / clinical text.

    The raw_event payload is allowed to carry PHI (capture-then-route);
    every field the service constructs itself (summary, event payload,
    event_type, external_id) must not.
    """
    service, _, _, _, interaction, _ = _make_service()

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    event_in = interaction.create_event_idempotent.await_args.args[1]
    for token in _PHI_TOKENS:
        assert token not in event_in.summary
        assert all(token not in str(v) for v in event_in.payload.values())

    # Safe payload allowlist: only amount + transaction_type +
    # (optional) location_id + (optional) invoice_id are written by this
    # service. transactionCode (free-text categorical) is NOT passed through.
    assert set(event_in.payload.keys()).issubset(
        {"amount", "transaction_type", "location_id", "invoice_id"}
    )
    assert event_in.payload.get("amount") == pytest.approx(125.50)
    assert event_in.payload.get("transaction_type") == "credit"
    # ENG-303: the CareStack invoiceId (a non-PII billing-document id) is
    # carried so the PM Payments page can link a payment to its invoice.
    assert event_in.payload.get("invoice_id") == "5501"


# ------------------------------------------------------ idempotency key


@pytest.mark.asyncio
async def test_external_id_includes_last_updated_on() -> None:
    service, _, ingest, _, _, _ = _make_service(
        body={
            "accountingTransactions": [
                _transaction(id=42, lastUpdatedOn="2026-04-01T00:00:00Z")
            ],
            "continueToken": None,
        }
    )

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.external_id == "42:2026-04-01T00:00:00Z"


@pytest.mark.asyncio
async def test_external_id_falls_back_to_id_when_last_updated_on_missing() -> None:
    service, _, ingest, _, _, _ = _make_service(
        body={
            "accountingTransactions": [_transaction(id=77, lastUpdatedOn=None)],
            "continueToken": None,
        }
    )

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    raw_call = ingest.capture.await_args.args[1]
    assert raw_call.external_id == "77"


def test_compose_idempotency_key_round_trip() -> None:
    assert _compose_idempotency_key("1", "2026-01-01T00:00:00Z") == (
        "1:2026-01-01T00:00:00Z"
    )
    assert _compose_idempotency_key("1", None) == "1"


# ------------------------------------------------------ patient-link skip


@pytest.mark.asyncio
async def test_row_without_patient_id_is_captured_but_skipped() -> None:
    service, _, ingest, identity_repo, interaction, _ = _make_service(
        body={
            "accountingTransactions": [_transaction(patientId=None)],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1
    # Raw event captured for replay even though linkage was skipped.
    ingest.capture.assert_awaited_once()
    identity_repo.find_source_link.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_row_with_unlinked_patient_is_captured_but_skipped() -> None:
    service, _, ingest, identity_repo, interaction, _ = _make_service(source_link=None)
    identity_repo.find_source_link = AsyncMock(return_value=None)

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_row_without_id_is_skipped() -> None:
    service, _, ingest, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [_transaction(id=None)],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 0
    assert result.skipped_count == 1
    ingest.capture.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()


# ------------------------------------------------------ validation


@pytest.mark.asyncio
async def test_import_rejects_invalid_days() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_accounting_transactions(_TENANT_ID, days=0)
    with pytest.raises(ValidationError):
        await service.import_recent_accounting_transactions(_TENANT_ID, days=400)


@pytest.mark.asyncio
async def test_import_rejects_invalid_page_size() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_accounting_transactions(
            _TENANT_ID, page_size=0
        )
    with pytest.raises(ValidationError):
        await service.import_recent_accounting_transactions(
            _TENANT_ID, page_size=600
        )


@pytest.mark.asyncio
async def test_import_rejects_invalid_max_pages() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.import_recent_accounting_transactions(
            _TENANT_ID, max_pages=0
        )
    with pytest.raises(ValidationError):
        await service.import_recent_accounting_transactions(
            _TENANT_ID, max_pages=21
        )


# ------------------------------------------------------ pagination


@pytest.mark.asyncio
async def test_import_follows_continue_token_up_to_max_pages() -> None:
    page1 = {
        "accountingTransactions": [_transaction(id=1)],
        "continueToken": "next-page-token",
    }
    page2 = {
        "accountingTransactions": [_transaction(id=2)],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        side_effect=[page1, page2]
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7, max_pages=2
    )

    assert result.imported_count == 2
    assert result.page_count == 2
    assert result.next_continue_token is None
    assert cs_client.list_accounting_transactions_modified_since.await_count == 2


@pytest.mark.asyncio
async def test_import_stops_at_max_pages_with_remaining_token() -> None:
    page1 = {
        "accountingTransactions": [_transaction(id=1)],
        "continueToken": "still-more",
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        return_value=page1
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7, max_pages=1
    )

    assert result.page_count == 1
    assert result.next_continue_token == "still-more"


# -------------------------------------------------- watermark resume (ENG)


@pytest.mark.asyncio
async def test_modified_since_falls_back_to_days_window_without_watermark() -> None:
    """No prior watermark → request ``modifiedSince ≈ now - days``."""
    service, cs_client, ingest, *_ = _make_service()
    ingest.max_payload_watermark = AsyncMock(return_value=None)

    before = datetime.now(UTC)
    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    sent = cs_client.list_accounting_transactions_modified_since.await_args.args[0]
    expected = before - timedelta(days=7)
    # Within a generous tolerance of the ``now - days`` boundary.
    assert abs((sent - expected).total_seconds()) < 60


@pytest.mark.asyncio
async def test_resumes_from_watermark_minus_overlap() -> None:
    """A stored watermark drives ``modifiedSince`` forward, minus overlap."""
    service, cs_client, ingest, *_ = _make_service()
    ingest.max_payload_watermark = AsyncMock(
        return_value="2026-06-02T23:52:17.7406657"  # 7-digit fraction, no tz
    )

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    sent = cs_client.list_accounting_transactions_modified_since.await_args.args[0]
    expected = datetime(2026, 6, 2, 23, 52, 17, 740665, tzinfo=UTC) - timedelta(
        minutes=10
    )
    # Microsecond truncation of the 7th fractional digit is acceptable.
    assert abs((sent - expected).total_seconds()) < 1
    # Resumed far ahead of the ``now - 7d`` fallback window.
    assert sent.year == 2026 and sent.month == 6


# ------------------------------------------------------ helper unit tests


def test_extract_rows_supports_spec_envelope_key() -> None:
    body = {"accountingTransactions": [{"id": 1}], "continueToken": None}
    assert _extract_rows(body) == [{"id": 1}]


def test_extract_rows_supports_generic_results_envelope() -> None:
    body = {"results": [{"id": 1}]}
    assert _extract_rows(body) == [{"id": 1}]


def test_extract_rows_returns_empty_when_no_known_key() -> None:
    assert _extract_rows({"unknown": [{"id": 1}]}) == []


def test_extract_rows_filters_non_dict_entries() -> None:
    assert _extract_rows({"results": [{"id": 1}, "garbage", 42]}) == [{"id": 1}]


def test_transaction_source_id_accepts_int_or_string() -> None:
    assert _transaction_source_id({"id": 42}) == "42"
    assert _transaction_source_id({"id": "42"}) == "42"
    assert _transaction_source_id({"transactionId": 9}) == "9"
    assert _transaction_source_id({}) is None


def test_transaction_last_updated_on_passthrough() -> None:
    assert (
        _transaction_last_updated_on({"lastUpdatedOn": "2026-01-01T00:00:00Z"})
        == "2026-01-01T00:00:00Z"
    )
    # CamelCase variant from the spec dump:
    assert (
        _transaction_last_updated_on({"LastUpdatedOn": "2026-02-02T00:00:00Z"})
        == "2026-02-02T00:00:00Z"
    )
    assert _transaction_last_updated_on({"lastUpdatedOn": ""}) is None
    assert _transaction_last_updated_on({}) is None


def test_transaction_patient_id_optional() -> None:
    assert _transaction_patient_id({"patientId": 1}) == "1"
    assert _transaction_patient_id({"PatientId": "2"}) == "2"
    # Spec marks patientId optional — practice-level advance payments
    # have no patient linkage.
    assert _transaction_patient_id({}) is None


# ---------------------------------------------------------- location resolution (ENG-267)


@pytest.mark.asyncio
async def test_mapped_location_id_is_added_to_safe_payload() -> None:
    """A CS locationId that resolves to a tenant.location lands as
    ``location_id`` (str UUID) in the safe event payload."""
    service, _, _, _, interaction, locations = _make_service()

    await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    locations.find_by_carestack_id.assert_awaited_once_with(_TENANT_ID, 10029)
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert event_in.payload.get("location_id") == str(_LOCATION_UID)


@pytest.mark.asyncio
async def test_unmapped_location_omits_location_id_but_emits_event() -> None:
    """When the CS locationId has no tenant.location mapping yet, the
    safe payload simply omits ``location_id`` — the event still emits.
    """
    service, _, _, _, interaction, locations = _make_service(location=None)

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 1
    locations.find_by_carestack_id.assert_awaited_once()
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


@pytest.mark.asyncio
async def test_missing_location_id_field_skips_resolver_and_emits_event() -> None:
    """A payment row without ``locationId`` never calls the resolver
    and still emits without ``location_id`` in payload."""
    service, _, _, _, interaction, locations = _make_service(
        body={
            "accountingTransactions": [_transaction(locationId=None)],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

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

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 1
    event_in = interaction.create_event_idempotent.await_args.args[1]
    assert "location_id" not in event_in.payload


def test_transaction_location_id_helper_parses_int_or_string() -> None:
    assert _transaction_location_id({"locationId": 10029}) == 10029
    assert _transaction_location_id({"LocationId": 10029}) == 10029
    assert _transaction_location_id({"locationId": "10029"}) == 10029
    assert _transaction_location_id({"locationId": None}) is None
    assert _transaction_location_id({"locationId": "not-a-number"}) is None
    # ``bool`` is an ``int`` subclass; the helper must reject it so True
    # never becomes location id 1.
    assert _transaction_location_id({"locationId": True}) is None
    assert _transaction_location_id({}) is None


def test_payment_event_kind_helper_covers_locked_decisions() -> None:
    """ENG-283 / ENG-284: classification is now a strict transactionCode allow-list.

    A row produces a payment event ONLY if its ``transactionCode`` is in
    the allow-list. ``isReversed=True`` flips the kind to
    ``payment_reversed`` ONLY for CASH codes
    (``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` / refund codes);
    allocation codes (``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED``)
    keep ``payment_applied`` even when reversed (a reversed allocation
    is still an allocation — its cash counterpart is the paired
    ``PATIENTPAYMENTSDELETE`` row). ``isReversed=True`` NEVER promotes
    a non-payment code to a payment event.
    """
    # Cash IN — real payments from a payer.
    assert _payment_event_kind({"transactionCode": "PATIENTPAYMENTS"}) == "payment_recorded"
    assert _payment_event_kind({"transactionCode": "INSURANCEPAYMENTS"}) == "payment_recorded"
    # Allocation legs — visible on the timeline, excluded from Collected.
    assert _payment_event_kind({"transactionCode": "PATPAYMENTAPPLIED"}) == "payment_applied"
    assert _payment_event_kind({"transactionCode": "INSPAYMENTAPPLIED"}) == "payment_applied"
    # Deletes and refunds.
    assert (
        _payment_event_kind({"transactionCode": "PATIENTPAYMENTSDELETE"}) == "payment_reversed"
    )
    assert _payment_event_kind({"transactionCode": "REFUND"}) == "payment_refunded"
    assert _payment_event_kind({"transactionCode": "PATIENTREFUND"}) == "payment_refunded"
    assert _payment_event_kind({"transactionCode": "INSURANCEREFUND"}) == "payment_refunded"
    # ENG-284: isReversed flips a CASH code to reversed.
    assert (
        _payment_event_kind({"transactionCode": "PATIENTPAYMENTS", "isReversed": True})
        == "payment_reversed"
    )
    assert (
        _payment_event_kind({"transactionCode": "INSURANCEPAYMENTS", "isReversed": True})
        == "payment_reversed"
    )
    # Refund codes are cash codes; a reversed refund still reads as reversed.
    assert (
        _payment_event_kind({"transactionCode": "PATIENTREFUND", "isReversed": True})
        == "payment_reversed"
    )
    # ENG-284: isReversed on an ALLOCATION code keeps payment_applied —
    # the reversed-allocation row's cash counterpart is the paired
    # PATIENTPAYMENTSDELETE row; double-classifying both as reversed
    # would re-create the negative-Collected bug from a different angle.
    assert (
        _payment_event_kind({"transactionCode": "PATPAYMENTAPPLIED", "isReversed": True})
        == "payment_applied"
    )
    assert (
        _payment_event_kind({"transactionCode": "INSPAYMENTAPPLIED", "isReversed": True})
        == "payment_applied"
    )
    # PATIENTPAYMENTSDELETE stays as payment_reversed regardless of
    # isReversed (the code itself already says "cash reversal").
    assert (
        _payment_event_kind({"transactionCode": "PATIENTPAYMENTSDELETE", "isReversed": True})
        == "payment_reversed"
    )
    # Non-payment codes — raw-only.
    assert _payment_event_kind({"transactionCode": "PROCEDURECOMPLETED"}) is None
    assert _payment_event_kind({"transactionCode": "PATIENTADJUSTMENT"}) is None
    assert _payment_event_kind({"transactionCode": "FEEUPDATION"}) is None
    # ENG-284: isReversed must NOT promote a non-payment code to a payment event.
    assert (
        _payment_event_kind({"transactionCode": "PROCEDURECOMPLETED", "isReversed": True})
        is None
    )
    assert (
        _payment_event_kind({"transactionCode": "PATIENTADJUSTMENT", "isReversed": True})
        is None
    )
    assert (
        _payment_event_kind({"transactionCode": "FEEUPDATION", "isReversed": True}) is None
    )
    # folioType on its own is no longer enough — must have a recognised code.
    assert _payment_event_kind({"folioType": "PATIENTCREDIT"}) is None
    # Missing code + isReversed → still no event (allow-list check is first).
    assert _payment_event_kind({"isReversed": True}) is None
    # Missing fields are safe.
    assert _payment_event_kind({}) is None


# ---------------------------------------------------------- ENG-269 dedup contract


@pytest.mark.asyncio
async def test_cross_pull_conflict_counts_as_unchanged_not_failed() -> None:
    """ENG-329 — re-pull of an already-emitted payment folio hits the
    cross-pull partial UNIQUE on ``interaction.event``;
    ``create_event_idempotent`` returns ``was_created=False``. That is an
    idempotent dedup — HEALTHY — so the import counter must mark the row
    as ``unchanged``, NOT ``skipped`` (which the sync_run folds into
    ``failed``).
    """
    service, _, ingest, _, interaction, _ = _make_service()
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=False
        )
    )

    result = await service.import_recent_accounting_transactions(_TENANT_ID, days=7)

    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_awaited_once()


# ---------------------------------------------------------- ENG-285 throttled backfill (pull_all_since)


class _FakeCareStackApiError(Exception):
    """Stand-in for ``CareStackApiError`` — duck-types via ``.details``.

    ``packages.ingest`` may not import ``packages.integrations`` (cross-
    package matrix), so the production retry/backoff path checks the
    exception via ``getattr(exc, "details", ...)``. This fake provides
    the same shape so the tests stay isolated from the integrations
    package.
    """

    def __init__(self, message: str, *, status: int) -> None:
        super().__init__(message)
        self.details = {"status": status}


class _SleepRecorder:
    """Async sleep stand-in that records waits and does not block.

    Tests inject this so the throttle/backoff loops complete instantly
    while still exercising the sleep contract (between-page throttle,
    exponential backoff on retryable status codes).
    """

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.mark.asyncio
async def test_pull_all_since_paginates_until_null_continue_token() -> None:
    page1 = {
        "accountingTransactions": [_transaction(id=1)],
        "continueToken": "next",
    }
    page2 = {
        "accountingTransactions": [_transaction(id=2)],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
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
    assert cs_client.list_accounting_transactions_modified_since.await_count == 2
    # Second call must forward the continueToken from page 1.
    second_call_kwargs = (
        cs_client.list_accounting_transactions_modified_since.await_args_list[1].kwargs
    )
    assert second_call_kwargs["continue_token"] == "next"
    # ENG-326: each page is committed (releases per-event SAVEPOINTs).
    assert service._session.commit.await_count == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pull_all_since_default_since_is_2026_01_01() -> None:
    """ENG-285: when ``since`` is omitted the backfill anchors at 2026-01-01.

    The scheduled pull uses a small modified_since window; the backfill
    is an explicit, operator-triggered historical sweep so the default
    is the start of the fiscal year the operator is reconstructing.
    """
    service, cs_client, *_ = _make_service(
        body={
            "accountingTransactions": [_transaction()],
            "continueToken": None,
        }
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(_TENANT_ID, sleep=sleep)

    cs_client.list_accounting_transactions_modified_since.assert_awaited_once()
    call_args = cs_client.list_accounting_transactions_modified_since.await_args
    modified_since = call_args.args[0]
    assert modified_since == datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_pull_all_since_sleeps_between_pages_but_not_after_last_page() -> None:
    """Between-page throttle: sleep is called N-1 times for N pages."""
    page1 = {
        "accountingTransactions": [_transaction(id=1)],
        "continueToken": "tok1",
    }
    page2 = {
        "accountingTransactions": [_transaction(id=2)],
        "continueToken": "tok2",
    }
    page3 = {
        "accountingTransactions": [_transaction(id=3)],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        side_effect=[page1, page2, page3]
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.75,
        sleep=sleep,
    )

    # 3 pages → 2 between-page sleeps (no leading or trailing sleep).
    assert sleep.waits == [0.75, 0.75]


@pytest.mark.asyncio
async def test_pull_all_since_retries_with_exponential_backoff_on_429_then_succeeds() -> None:
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    ok_page = {
        "accountingTransactions": [_transaction()],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        side_effect=[rate_limit, rate_limit, ok_page]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.0,  # disable between-page sleep so we observe only backoff
        max_retries=5,
        backoff_base_seconds=1.0,
        sleep=sleep,
    )

    assert result.imported_count == 1
    assert result.page_count == 1
    # Two retries → two backoff sleeps of base * 2**(attempt-1) = 1s, 2s.
    assert sleep.waits == [1.0, 2.0]
    assert cs_client.list_accounting_transactions_modified_since.await_count == 3


@pytest.mark.parametrize("retryable_status", [429, 500, 502, 503, 504])
@pytest.mark.asyncio
async def test_pull_all_since_retries_on_retryable_status_codes(
    retryable_status: int,
) -> None:
    error = _FakeCareStackApiError("server hiccup", status=retryable_status)
    ok_page = {
        "accountingTransactions": [_transaction()],
        "continueToken": None,
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        side_effect=[error, ok_page]
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.0,
        max_retries=3,
        backoff_base_seconds=0.5,
        sleep=sleep,
    )

    assert result.imported_count == 1
    assert sleep.waits == [0.5]
    assert cs_client.list_accounting_transactions_modified_since.await_count == 2


@pytest.mark.asyncio
async def test_pull_all_since_returns_resume_token_when_retries_exhausted() -> None:
    """Retries exhausted → stop and return the last continueToken (resume).

    The operator can re-invoke with the returned token and pick up
    exactly where the loop stopped. Never hammer.
    """
    # Page 1 succeeds and yields a continueToken; every subsequent call
    # raises 429. Backoff exhausts after ``max_retries`` retries and the
    # loop stops with the page-1 continueToken still in hand.
    page1 = {
        "accountingTransactions": [_transaction(id=1)],
        "continueToken": "resume-here",
    }
    rate_limit = _FakeCareStackApiError("rate limited", status=429)
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
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
    assert result.imported_count == 1
    assert result.next_continue_token == "resume-here"
    # 2 retries → 2 backoff sleeps; no real CareStack pounding past that.
    assert sleep.waits == [0.25, 0.5]
    # 1 successful call + 1 initial + 2 retries on the second page = 4
    assert cs_client.list_accounting_transactions_modified_since.await_count == 4


@pytest.mark.asyncio
async def test_pull_all_since_stops_at_page_safety_cap_and_returns_token() -> None:
    """The cap is a defensive ceiling against an infinite continueToken loop."""
    looping_page = {
        "accountingTransactions": [_transaction()],
        "continueToken": "never-ends",
    }
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
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
    assert cs_client.list_accounting_transactions_modified_since.await_count == 3


@pytest.mark.asyncio
async def test_pull_all_since_propagates_non_retryable_errors() -> None:
    """Non-rate-limit / non-5xx errors are not part of the retry policy.

    A 401 means credentials are invalid — retrying with the same token
    will not help. A connection error from missing credentials should
    bubble up to the leg helper which closes the sync_run as
    ``skipped_credential``.
    """
    not_connected = _FakeCareStackApiError("unauthorised", status=401)
    service, cs_client, *_ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
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

    # No sleeps (no retry attempt — the status is not retryable).
    assert sleep.waits == []


@pytest.mark.asyncio
async def test_pull_all_since_idempotent_rerun_via_create_event_idempotent() -> None:
    """Re-running the backfill with the same rows must not double-emit events.

    ENG-269 idempotent emission: the second pull sees
    ``was_created=False`` on every row, so ``imported_count`` is 0 even
    though every row was captured to ``ingest.raw_event`` again
    (forensic).
    """
    service, _, ingest, _, interaction, _ = _make_service(
        body={
            "accountingTransactions": [_transaction()],
            "continueToken": None,
        }
    )
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()), was_created=False
        )
    )
    sleep = _SleepRecorder()

    result = await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1, tzinfo=UTC),
        sleep_seconds=0.0,
        sleep=sleep,
    )

    # ENG-329: the idempotent backfill re-run deduped the row — HEALTHY,
    # counted as ``unchanged`` rather than ``skipped``.
    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0
    ingest.capture.assert_awaited_once()
    interaction.create_event_idempotent.assert_awaited_once()


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


@pytest.mark.asyncio
async def test_pull_all_since_naive_since_is_treated_as_utc() -> None:
    """Defensive: an operator-supplied naive datetime should not crash.

    The CareStack client requires timezone-aware UTC; mirror the
    behaviour of the existing ``pull_all_since`` paths in the patient /
    appointment services and assume UTC for naive inputs.
    """
    service, cs_client, *_ = _make_service(
        body={"accountingTransactions": [_transaction()], "continueToken": None}
    )
    sleep = _SleepRecorder()

    await service.pull_all_since(
        _TENANT_ID,
        since=datetime(2026, 1, 1),  # naive — no tzinfo
        sleep=sleep,
    )

    modified_since = (
        cs_client.list_accounting_transactions_modified_since.await_args.args[0]
    )
    assert modified_since.tzinfo is not None
    assert modified_since == datetime(2026, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------- ENG-305 imported patient_ids


@pytest.mark.asyncio
async def test_import_returns_distinct_sorted_imported_patient_ids() -> None:
    """``patient_ids`` is the live signal the scheduled job feeds into the
    payment-summary refresh: distinct, sorted, and limited to rows that
    actually imported (a payment event was emitted)."""
    body = {
        "accountingTransactions": [
            _transaction(id=1, patientId=9001),  # imported
            _transaction(  # skipped: non-payment code, no event emitted
                id=2,
                patientId=9002,
                transactionCode="PROCEDURECOMPLETED",
            ),
            _transaction(id=3, patientId=8800),  # imported (smaller id)
        ],
        "continueToken": None,
    }
    service, _, _, _, interaction, _ = _make_service(body=body)
    # Make every row's source-link resolution succeed AND every event
    # creation a fresh insert so we hit the "imported" branch.
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()),
            was_created=True,
        )
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 2
    # Sorted lexicographically (str sort), distinct.
    assert result.patient_ids == ["8800", "9001"]


@pytest.mark.asyncio
async def test_import_dedups_repeated_imported_patient_ids() -> None:
    """Two imported rows for the same patient → patient appears once."""
    body = {
        "accountingTransactions": [
            _transaction(id=1, patientId=9001),
            _transaction(id=2, patientId=9001, transactionCode="INSURANCEPAYMENTS"),
        ],
        "continueToken": None,
    }
    service, _, _, _, interaction, _ = _make_service(body=body)
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()),
            was_created=True,
        )
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 2
    assert result.patient_ids == ["9001"]


@pytest.mark.asyncio
async def test_import_patient_ids_excludes_skipped_unlinked_and_non_payment_rows() -> None:
    """Skipped rows (no patientId, unlinked patient, non-payment folio) must
    NOT contribute to ``patient_ids`` — the live signal is for refresh of
    patients who actually moved money."""
    body = {
        "accountingTransactions": [
            # Imported: linked patient + payment code.
            _transaction(id=1, patientId=9001),
            # Skipped: row has patientId, code is non-payment.
            _transaction(
                id=2, patientId=9002, transactionCode="PROCEDURECOMPLETED"
            ),
            # Skipped: no patientId at all.
            _transaction(id=3, patientId=None),
        ],
        "continueToken": None,
    }
    service, _, _, _, interaction, _ = _make_service(body=body)
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()),
            was_created=True,
        )
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 1
    assert result.skipped_count == 2
    assert result.patient_ids == ["9001"]


@pytest.mark.asyncio
async def test_import_patient_ids_excludes_dedup_conflicts() -> None:
    """ENG-329 dedup conflicts return ``was_created=False`` and count as
    ``unchanged`` (not ``skipped``) — and must not appear in
    ``patient_ids`` either (the live signal is for fresh imports)."""
    body = {
        "accountingTransactions": [
            _transaction(id=1, patientId=9001),
        ],
        "continueToken": None,
    }
    service, _, _, _, interaction, _ = _make_service(body=body)
    interaction.create_event_idempotent = AsyncMock(
        return_value=SimpleNamespace(
            event=SimpleNamespace(id=uuid.uuid4()),
            was_created=False,
        )
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 0
    assert result.unchanged_count == 1
    assert result.skipped_count == 0
    assert result.patient_ids == []


@pytest.mark.asyncio
async def test_import_empty_rows_returns_empty_patient_ids() -> None:
    body: dict[str, Any] = {"accountingTransactions": [], "continueToken": None}
    service, _, _, _, _, _ = _make_service(body=body)

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 0
    assert result.patient_ids == []


# ---------------------------------------------------------- ENG-384 capture change-guard


@pytest.mark.asyncio
async def test_capture_guard_skips_row_with_unchanged_stamp() -> None:
    """ENG-384: a row whose composed (id, lastUpdatedOn) external_id is
    already captured is a healthy overlap re-read — no raw write, no
    downstream emit, no source-link resolution."""
    transaction = _transaction()
    service, _, ingest, identity_repo, interaction, _ = _make_service(
        body={
            "accountingTransactions": [transaction],
            "continueToken": None,
        }
    )
    composed_key = (
        f"{transaction['id']}:{transaction['lastUpdatedOn']}"
    )
    ingest.latest_payload_values = AsyncMock(
        return_value={composed_key: transaction["lastUpdatedOn"]}
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.unchanged_count == 1
    assert result.imported_count == 0
    assert result.skipped_count == 0
    ingest.capture.assert_not_awaited()
    identity_repo.find_source_link.assert_not_awaited()
    interaction.create_event_idempotent.assert_not_awaited()


@pytest.mark.asyncio
async def test_capture_guard_captures_row_with_newer_stamp() -> None:
    """A moved provider stamp means a real change — the row is captured."""
    transaction = _transaction()
    service, _, ingest, _, _, _ = _make_service(
        body={
            "accountingTransactions": [transaction],
            "continueToken": None,
        }
    )
    # Some earlier captured stamp; the upstream row carries a newer one,
    # so the composed key does not match the existing entry.
    ingest.latest_payload_values = AsyncMock(
        return_value={"88001:2026-04-01T00:00:00Z": "2026-04-01T00:00:00Z"}
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.unchanged_count == 0
    assert result.imported_count == 1
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_capture_guard_row_without_stamp_falls_through_to_capture() -> None:
    """A row whose payload has no ``lastUpdatedOn`` cannot be safely
    guarded (no stamp to compare), so it falls through to capture under
    the bare-id fallback external_id — matches the spec ``no stamp =
    forensic copy on every run``."""
    transaction = _transaction(lastUpdatedOn=None)
    service, _, ingest, _, _, _ = _make_service(
        body={
            "accountingTransactions": [transaction],
            "continueToken": None,
        }
    )

    result = await service.import_recent_accounting_transactions(
        _TENANT_ID, days=7
    )

    assert result.imported_count == 1
    assert result.unchanged_count == 0
    ingest.capture.assert_awaited_once()


@pytest.mark.asyncio
async def test_pull_all_since_capture_guard_skips_unchanged_rows() -> None:
    """ENG-384: the deep backfill path applies the same guard so a
    re-run over already-captured rows writes ZERO new raw events."""
    transaction = _transaction()
    service, cs_client, ingest, _, interaction, _ = _make_service()
    cs_client.list_accounting_transactions_modified_since = AsyncMock(
        return_value={
            "accountingTransactions": [transaction],
            "continueToken": None,
        }
    )
    composed_key = f"{transaction['id']}:{transaction['lastUpdatedOn']}"
    ingest.latest_payload_values = AsyncMock(
        return_value={composed_key: transaction["lastUpdatedOn"]}
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
