"""CareStack Accounting Transaction ingest pipeline (ENG-257; ENG-283).

The CareStack accounting-transactions sync feed is the partial-payment
ledger — debits, credits, adjustments, refunds, reversals, payor
allocations, advance payments. We do NOT model it in a domain schema in
this slice (a canonical ``billing`` projection is a separate,
structurally-gated ticket); this service captures every row verbatim to
``ingest.raw_event`` for later replay AND emits a workflow-ready
``interaction.event`` for PAYMENT-flavoured rows so partial payments
become visible on the person operational timeline and the PM
treatment/payments dashboard widget.

Per row:

1. ``IngestService.capture`` writes the verbatim AccountingTransaction
   row to ``ingest.raw_event`` as
   ``carestack.accounting_transaction.upsert``. ``external_id`` encodes
   the spec's ``(id, lastUpdatedOn)`` idempotency key so re-pulls of an
   unchanged row produce identical raw-event ``external_id`` values,
   while a CareStack-side edit produces a new external_id. We never
   reshape the payload — this is forensic capture.
2. We look up the canonical ``identity.person`` for the row's optional
   ``patientId`` via the existing ``identity.source_link`` row. The row
   is still captured if ``patientId`` is missing (practice-level
   advance payments) or the patient is not yet linked (patient ingest
   has not run) — those rows are counted as ``skipped`` for linkage but
   the raw_event remains for replay once the patient lands.
3. We emit an ``interaction.event`` ONLY for PAYMENT rows. ENG-283
   replaced the earlier ``folioType`` mapping with a ``transactionCode``
   classifier because the ``folioType=PATIENTCREDIT`` filter caught
   both legs of CareStack's double-entry ledger (cash received AND its
   subsequent allocation onto an invoice), inflating the Collected
   total ~3.3x. ENG-284 then made classification a STRICT allow-list
   because the original ``isReversed``-first rule promoted reversed
   non-payment rows (``PROCEDURECOMPLETED`` charges,
   ``PATIENTADJUSTMENT`` adjustments, ``FEEUPDATION`` fee changes)
   into ``payment_reversed`` — which the Collected aggregate
   subtracts — and the dashboard Collected total went negative.
   Codes that drive emission (uppercased before lookup):

   * ``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` → ``payment_recorded``
     — REAL cash received from a patient or insurance carrier.
   * ``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED`` → ``payment_applied``
     — the offsetting debit that allocates a recorded payment onto an
     invoice. Visible on the timeline but excluded from cash totals.
   * ``PATIENTPAYMENTSDELETE`` → ``payment_reversed`` (deleted payment).
   * Explicit refund codes (``REFUND`` / ``PATIENTREFUND`` /
     ``INSURANCEREFUND``) → ``payment_refunded``.
   * ``isReversed=true`` reclassifies the mapped kind to
     ``payment_reversed`` ONLY for CASH codes
     (``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` / refund codes).
     Reversed allocation legs (``PATPAYMENTAPPLIED`` /
     ``INSPAYMENTAPPLIED``) stay as ``payment_applied`` — the cash
     side of a reversed allocation is the paired
     ``PATIENTPAYMENTSDELETE`` row; promoting the allocation reversal
     to ``payment_reversed`` would double-subtract from the Collected
     formula and re-create the negative-Collected bug.
     ``isReversed=true`` NEVER promotes a non-payment code to a
     payment event.
   * Every other code (charges ``PROCEDURECOMPLETED``, adjustments,
     fee updates, etc.) and rows without a payment code stay raw-only —
     no timeline event, even when ``isReversed=true``.

   The emitted summary and payload carry the amount and the
   ``transactionType`` (debit/credit) ONLY. No clinical codes, no
   procedure codes, no provider names, no patient identifiers.

The CareStack HTTP client is consumed via a local Protocol so this
package does not import ``packages.integrations``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.schemas import (
    CareStackAccountingTransactionImportOut,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.tenant.service import LocationService

_ACCOUNTING_TRANSACTION_EVENT_TYPE = "carestack.accounting_transaction.upsert"

log = get_logger("ingest.carestack_accounting_transaction")

# ENG-285: backfill defaults. The fiscal year the operator is
# reconstructing is 2026 — the scheduled pull keeps a small modified-
# since window, so a separate "since 2026-01-01" anchor is the safe
# default for the historical sweep.
_BACKFILL_DEFAULT_SINCE = datetime(2026, 1, 1, tzinfo=UTC)

# HTTP status codes that justify exponential backoff + retry. 429 is
# CareStack's rate-limit signal; the 5xx set covers transient upstream
# outages. Anything else (401, 4xx other than 429, ...) is propagated
# so the caller can close the sync_run with the correct status —
# retrying invalid credentials would just burn the token budget.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

_RESULT_LIST_KEYS = (
    "accountingTransactions",
    "results",
    "items",
    "records",
    "data",
    "transactions",
)

# transactionCode → payment-event kind mapping (ENG-283). Anything not
# in this map (and not an isReversed override) stays raw-only.
#
# docs: apps/web/lib/docs/paymentsDoc.ts — staff-facing explanation of this
# classification. If this map (or _CASH_REVERSAL_CODES below) changes, update
# that doc (BOTH `en` and `ru`) in the same change. See apps/web/CLAUDE.md.
#
# Cash IN (payment_recorded) is restricted to the two codes that mean
# "money actually arrived from a payer". The earlier folio-based
# classifier conflated these with PATPAYMENTAPPLIED, the offset entry
# that allocates the recorded payment onto an invoice — that's the
# double-entry leg, not new cash, so it now maps to the dedicated
# `payment_applied` kind and is excluded from Collected totals.
_PAYMENT_CODE_TO_KIND: dict[str, str] = {
    "PATIENTPAYMENTS": "payment_recorded",
    "INSURANCEPAYMENTS": "payment_recorded",
    "PATPAYMENTAPPLIED": "payment_applied",
    "INSPAYMENTAPPLIED": "payment_applied",
    "PATIENTPAYMENTSDELETE": "payment_reversed",
}
_REFUND_TRANSACTION_CODES: frozenset[str] = frozenset(
    {"REFUND", "PATIENTREFUND", "INSURANCEREFUND"}
)

# ENG-284: ``isReversed=true`` flips a payment row to
# ``payment_reversed`` ONLY when the underlying code maps to a CASH
# event — a recorded payment or a refund. Allocation legs
# (``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED``) and the explicit
# delete code (``PATIENTPAYMENTSDELETE``) keep their mapped kind even
# with ``isReversed=true``: a reversed allocation is still an
# allocation (excluded from Collected by design), and a
# ``PATIENTPAYMENTSDELETE`` row is already a cash reversal via its
# code mapping. Without this restriction the 70 reversed
# ``PATPAYMENTAPPLIED`` rows in the dev DB pull the Collected
# aggregate negative by ~$40k — the formula
# ``collected = recorded − refunded − reversed`` treats
# ``payment_reversed`` as a cash event, so dropping allocation
# reversals into that bucket double-subtracts the cash the matching
# ``PATIENTPAYMENTSDELETE`` row already removed.
_CASH_REVERSAL_CODES: frozenset[str] = frozenset(
    {"PATIENTPAYMENTS", "INSURANCEPAYMENTS"} | _REFUND_TRANSACTION_CODES
)


class CareStackAccountingTransactionClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the AT ingest."""

    async def list_accounting_transactions_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]: ...


class CareStackAccountingTransactionIngestService:
    """Pull CareStack Accounting Transactions, capture raw, link identity,
    and emit payment timeline events for ledger PAYMENT rows.
    """

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackAccountingTransactionClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._interaction = InteractionService(session)
        self._locations = LocationService(session)

    async def import_recent_accounting_transactions(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        page_size: int = 100,
        max_pages: int = 5,
    ) -> CareStackAccountingTransactionImportOut:
        """Capture recent CareStack accounting transactions into ingest.

        Bounded by ``max_pages`` to keep scheduled imports predictable.
        ``continue_token`` from the last page is returned so the caller
        can resume.
        """
        if days < 1 or days > 365:
            raise ValidationError(
                "days must be between 1 and 365",
                details={"days": days},
            )
        if page_size < 1 or page_size > 500:
            raise ValidationError(
                "page_size must be between 1 and 500",
                details={"page_size": page_size},
            )
        if max_pages < 1 or max_pages > 20:
            raise ValidationError(
                "max_pages must be between 1 and 20",
                details={"max_pages": max_pages},
            )

        # Resume from the highest ``lastUpdatedOn`` already captured so the
        # pull walks FORWARD to the newest rows instead of re-reading the
        # oldest edge of a fixed ``now - days`` window every run (which on a
        # busy tenant never reaches recent payments — the import date stays
        # pinned ~``days`` behind). ``days`` is the first-run fallback.
        watermark = await self._ingest.max_payload_watermark(
            tenant_id, event_type=_ACCOUNTING_TRANSACTION_EVENT_TYPE
        )
        modified_since = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        page_count = 0
        continue_token: str | None = None
        # ENG-305: collect patient_ids that actually imported (a payment
        # event was emitted). The scheduled job feeds this set into
        # ``CareStackPaymentSummaryIngestService.import_payment_summary_for_patients``
        # so the authoritative balance is refreshed for patients who
        # just moved money. Skipped rows (no patientId, unlinked patient,
        # non-payment folio, dedup conflict) must NOT appear here.
        imported_patient_ids: set[str] = set()

        while page_count < max_pages:
            body = await self._carestack.list_accounting_transactions_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            rows = _extract_rows(body)
            captured_keys = await self._latest_captured_keys(tenant_id, rows)
            for row in rows:
                transaction_id = _transaction_source_id(row)
                last_updated_on = _transaction_last_updated_on(row)
                patient_id = _transaction_patient_id(row)
                if transaction_id is None:
                    skipped_count += 1
                    continue
                if (
                    last_updated_on is not None
                    and captured_keys.get(
                        _compose_idempotency_key(transaction_id, last_updated_on)
                    )
                    == last_updated_on
                ):
                    # ENG-384: capture change-guard — the upstream row is
                    # byte-identical to one already in raw_event. A healthy
                    # overlap re-read; no raw write, no downstream emit.
                    unchanged_count += 1
                    continue
                outcome = await self._capture_transaction(
                    tenant_id,
                    row,
                    transaction_id=transaction_id,
                    last_updated_on=last_updated_on,
                    patient_id=patient_id,
                )
                if outcome == "imported":
                    imported_count += 1
                    if patient_id is not None:
                        imported_patient_ids.add(patient_id)
                elif outcome == "unchanged":
                    unchanged_count += 1
                else:
                    skipped_count += 1

            continue_token = _continue_token(body)
            if not continue_token:
                break

        log.info(
            "carestack.accounting_transaction.import_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            pages=page_count,
            imported_patients=len(imported_patient_ids),
        )
        return CareStackAccountingTransactionImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
            patient_ids=sorted(imported_patient_ids),
        )

    async def pull_all_since(
        self,
        tenant_id: TenantId,
        since: datetime | None = None,
        *,
        page_size: int = 500,
        page_safety_cap: int = 2000,
        sleep_seconds: float = 0.5,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> CareStackAccountingTransactionImportOut:
        """Throttled historical backfill of CareStack accounting transactions (ENG-285).

        Unlike :meth:`import_recent_accounting_transactions` (which the
        scheduled pull uses with a small ``modified_since`` window and a
        5-page cap), this method is the operator-triggered backfill path:

        * ``since`` defaults to ``2026-01-01T00:00:00Z`` — the fiscal
          year the operator is reconstructing. Naive datetimes are
          assumed UTC.
        * Pagination follows ``continueToken`` until exhausted OR the
          ``page_safety_cap`` (default 2000 pages) is reached.
        * ``sleep_seconds`` (default 0.5s) is awaited between pages to
          stay well below CareStack's rate limit. The CareStack tenant
          throttled this account for ~24h once before — backfill must
          stay gentle.
        * Retryable status codes (429, 5xx — see
          :data:`_RETRYABLE_STATUS_CODES`) trigger exponential backoff:
          ``backoff_base_seconds * 2 ** (attempt - 1)`` waits, bounded
          by ``max_retries``. If retries exhaust the loop STOPS and
          returns the last continueToken so the operator can resume
          with the same call. Non-retryable errors propagate so the
          leg helper can close the ``sync_run`` as
          ``skipped_credential`` / ``failed``.
        * Idempotent: raw_event re-capture is forensic, and the event
          layer dedupes via ``create_event_idempotent`` (ENG-269) —
          re-runs report ``imported_count == 0`` for already-emitted
          rows.

        ``sleep`` is injected for tests so the throttle + backoff paths
        complete instantly without actually blocking the event loop.
        """
        if page_size < 1 or page_size > 500:
            raise ValidationError(
                "page_size must be between 1 and 500",
                details={"page_size": page_size},
            )
        if page_safety_cap < 1:
            raise ValidationError(
                "page_safety_cap must be >= 1",
                details={"page_safety_cap": page_safety_cap},
            )
        if max_retries < 0:
            raise ValidationError(
                "max_retries must be >= 0",
                details={"max_retries": max_retries},
            )
        if sleep_seconds < 0:
            raise ValidationError(
                "sleep_seconds must be >= 0",
                details={"sleep_seconds": sleep_seconds},
            )
        if backoff_base_seconds < 0:
            raise ValidationError(
                "backoff_base_seconds must be >= 0",
                details={"backoff_base_seconds": backoff_base_seconds},
            )

        sleep_fn: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )

        effective_since = since if since is not None else _BACKFILL_DEFAULT_SINCE
        modified_since = (
            effective_since
            if effective_since.tzinfo is not None
            else effective_since.replace(tzinfo=UTC)
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        page_count = 0
        continue_token: str | None = None

        while page_count < page_safety_cap:
            if page_count > 0 and sleep_seconds > 0:
                await sleep_fn(sleep_seconds)

            body = await self._fetch_page_with_backoff(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
                max_retries=max_retries,
                backoff_base_seconds=backoff_base_seconds,
                sleep_fn=sleep_fn,
            )
            if body is None:
                # Backoff exhausted; stop with the current continue_token
                # so the operator can resume without losing position.
                log.warning(
                    "carestack.accounting_transaction.backfill_backoff_exhausted",
                    tenant_id=str(tenant_id),
                    page_count=page_count,
                )
                break

            page_count += 1
            rows = _extract_rows(body)
            captured_keys = await self._latest_captured_keys(tenant_id, rows)
            for row in rows:
                transaction_id = _transaction_source_id(row)
                last_updated_on = _transaction_last_updated_on(row)
                patient_id = _transaction_patient_id(row)
                if transaction_id is None:
                    skipped_count += 1
                    continue
                if (
                    last_updated_on is not None
                    and captured_keys.get(
                        _compose_idempotency_key(transaction_id, last_updated_on)
                    )
                    == last_updated_on
                ):
                    # ENG-384: deep-backfill re-runs hit the guard so an
                    # operator-triggered sweep over already-captured rows
                    # writes ZERO new raw events (matches the recent path).
                    unchanged_count += 1
                    continue
                outcome = await self._capture_transaction(
                    tenant_id,
                    row,
                    transaction_id=transaction_id,
                    last_updated_on=last_updated_on,
                    patient_id=patient_id,
                )
                if outcome == "imported":
                    imported_count += 1
                elif outcome == "unchanged":
                    unchanged_count += 1
                else:
                    skipped_count += 1

            # Per-page checkpoint (ENG-326). ``create_event_idempotent``
            # opens a SAVEPOINT per event; a full-year drain emits tens of
            # thousands of them. Holding all in one outer transaction
            # exhausts Postgres subtransaction shared memory
            # ("out of shared memory"). Commit each page to release the
            # page's SAVEPOINTs and persist progress so a mid-run failure
            # resumes from the next continue token instead of rolling the
            # whole backfill back. This streaming backfill is a documented
            # exception to the "services never commit" invariant.
            await self._session.commit()

            continue_token = _continue_token(body)
            if not continue_token:
                break

        log.info(
            "carestack.accounting_transaction.backfill_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            pages=page_count,
            resume_token_set=continue_token is not None,
        )
        return CareStackAccountingTransactionImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
        )

    async def _fetch_page_with_backoff(
        self,
        modified_since: datetime,
        *,
        page_size: int,
        continue_token: str | None,
        max_retries: int,
        backoff_base_seconds: float,
        sleep_fn: Callable[[float], Awaitable[None]],
    ) -> dict[str, Any] | None:
        """Fetch one page with bounded exponential backoff on retryable errors.

        Returns the page body on success, ``None`` when retries are
        exhausted (the caller stops and returns the current continue
        token so the operator can resume). Non-retryable errors are
        propagated to the caller.
        """
        attempt = 0
        while True:
            try:
                return await self._carestack.list_accounting_transactions_modified_since(
                    modified_since,
                    page_size=page_size,
                    continue_token=continue_token,
                )
            except Exception as exc:  # noqa: BLE001 — retry funnel
                if not _is_retryable_carestack_error(exc):
                    raise
                if attempt >= max_retries:
                    log.warning(
                        "carestack.accounting_transaction.retries_exhausted",
                        attempts=attempt,
                        status=_carestack_error_status(exc),
                    )
                    return None
                attempt += 1
                wait_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                log.warning(
                    "carestack.accounting_transaction.retrying_after_backoff",
                    attempt=attempt,
                    wait_seconds=wait_seconds,
                    status=_carestack_error_status(exc),
                )
                await sleep_fn(wait_seconds)

    async def _latest_captured_keys(
        self, tenant_id: TenantId, rows: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Captured ``lastUpdatedOn`` per composed external_id for a page.

        ENG-384 capture change-guard: the spec idempotency key
        ``(id, lastUpdatedOn)`` is encoded INTO ``raw_event.external_id``
        (see :func:`_compose_idempotency_key`). Looking up the captured
        ``lastUpdatedOn`` payload value at the composed key is itself the
        "this exact (id, stamp) was already captured" probe — the caller
        skips the row before any raw write or downstream emit.

        Rows without a usable id or stamp are excluded from the candidate
        set: they fall through to capture as before (the bare-id fallback
        path is intentionally NOT guarded so a row first seen without a
        stamp is captured at least once).
        """
        candidate_keys: list[str] = []
        for row in rows:
            transaction_id = _transaction_source_id(row)
            last_updated_on = _transaction_last_updated_on(row)
            if transaction_id is None or last_updated_on is None:
                continue
            candidate_keys.append(
                _compose_idempotency_key(transaction_id, last_updated_on)
            )
        return await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_ACCOUNTING_TRANSACTION_EVENT_TYPE,
            external_ids=candidate_keys,
            payload_key="lastUpdatedOn",
        )

    async def _capture_transaction(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        *,
        transaction_id: str,
        last_updated_on: str | None,
        patient_id: str | None,
    ) -> str:
        """Capture raw + resolve identity + emit payment event.

        Returns one of:

        * ``"imported"`` — ``patientId`` resolved to a linked Person,
          the row mapped to a payment kind, AND a fresh
          ``interaction.event`` was created.
        * ``"unchanged"`` — same as imported but the event already
          existed and ``create_event_idempotent`` deduped it
          (``was_created is False``). HEALTHY idempotent re-pull, NOT a
          failure.
        * ``"skipped"`` — genuine non-import: the patient is unlinked,
          ``patientId`` is absent, or the row is a non-payment folio
          (charges, internal adjustments). In every case the verbatim
          raw_event is captured.
        """
        external_id = _compose_idempotency_key(transaction_id, last_updated_on)
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type="carestack.accounting_transaction.upsert",
                external_id=external_id,
                received_at=datetime.now(UTC),
                payload=row,
            ),
        )

        if patient_id is None:
            log.warning(
                "carestack.accounting_transaction.skipped: no patientId in payload",
                extra={
                    "transaction_id": transaction_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        source_link = await self._identity_repo.find_source_link(
            tenant_id,
            source_system="carestack",
            source_instance="carestack-main",
            source_kind="patient",
            source_id=patient_id,
        )
        if source_link is None:
            log.warning(
                "carestack.accounting_transaction.skipped: patient not yet linked",
                extra={
                    "transaction_id": transaction_id,
                    "patient_id": patient_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        payment_kind = _payment_event_kind(row)
        if payment_kind is None:
            # Non-payment folio (charges, internal adjustments). Raw row
            # is preserved for replay; no timeline event by design.
            return "skipped"

        occurred_at = (
            _parse_carestack_datetime(row.get("transactionDate"))
            or _parse_carestack_datetime(row.get("lastUpdatedOn"))
            or datetime.now(UTC)
        )

        # Safe summary: action verb + provider + transaction id. The
        # helper enforces the no-PII contract.
        summary = summary_for_event(
            kind=payment_kind,
            source_provider="carestack",
            source_id=transaction_id,
        )

        # Safe non-PII payload: only the amount and the debit/credit
        # transactionType indicator, plus an optional resolved location
        # id (tenant.location UUID). NO clinical codes, NO provider
        # names, NO patient identifiers, NO procedure codes.
        safe_payload: dict[str, object] = {}
        amount = _transaction_amount(row)
        if amount is not None:
            safe_payload["amount"] = amount
        transaction_type = _transaction_type(row)
        if transaction_type is not None:
            safe_payload["transaction_type"] = transaction_type
        location_uid = await self._resolve_location_uid(
            tenant_id, _transaction_location_id(row)
        )
        if location_uid is not None:
            safe_payload["location_id"] = location_uid
        invoice_id = _transaction_invoice_id(row)
        if invoice_id is not None:
            safe_payload["invoice_id"] = invoice_id

        # ENG-269: cross-pull dedup — conflicts count as skipped, not imported.
        result = await self._interaction.create_event_idempotent(
            tenant_id,
            EventIn(
                person_uid=source_link.person_uid,
                kind=payment_kind,  # type: ignore[arg-type]
                source_provider="carestack",
                source_event_id=raw_event.id,
                data_class="billing",
                source_kind="carestack_accounting_transaction",
                source_external_id=transaction_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary,
                payload=safe_payload,
            ),
        )
        return "imported" if result.was_created else "unchanged"

    async def _resolve_location_uid(
        self, tenant_id: TenantId, carestack_location_id: int | None
    ) -> str | None:
        """Resolve a CareStack ``locationId`` to our tenant.location UUID.

        Returns ``str(uuid)`` when the CareStack id maps to a known
        location for this tenant. Returns ``None`` when the row carries
        no ``locationId`` OR when the id is not mapped yet (the operator
        has not imported CareStack locations OR the upstream id is
        truly unknown). The event still emits in the unmapped case —
        location is enrichment, not gating.
        """
        if carestack_location_id is None:
            return None
        try:
            location = await self._locations.find_by_carestack_id(
                tenant_id, carestack_location_id
            )
        except NotFoundError:
            return None
        except Exception:
            log.warning(
                "carestack.accounting_transaction.location_resolve_failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "carestack_location_id": carestack_location_id,
                },
            )
            return None
        if location is None:
            return None
        return str(location.id)


# ---------------------------------------------------------- payload helpers


def _extract_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the list of accounting transaction records from the envelope."""
    for key in _RESULT_LIST_KEYS:
        value = body.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _continue_token(body: dict[str, Any]) -> str | None:
    for key in ("continueToken", "nextContinueToken", "continuationToken"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _transaction_source_id(row: dict[str, Any]) -> str | None:
    """Extract the transaction id from the row.

    Per the CareStack accounting-transactions spec the field is ``id``
    (integer).
    """
    for key in ("id", "transactionId", "TransactionId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _transaction_last_updated_on(row: dict[str, Any]) -> str | None:
    """Extract the watermark field from the row.

    Per the spec the field is ``lastUpdatedOn`` (ISO datetime). Returned
    verbatim — composing with :func:`_compose_idempotency_key` matches
    the spec idempotency key ``(id, lastUpdatedOn)`` byte-for-byte, so
    re-pulls of an unchanged row dedupe on ``external_id`` and a real
    edit produces a fresh ``external_id``.
    """
    for key in ("lastUpdatedOn", "LastUpdatedOn"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _transaction_patient_id(row: dict[str, Any]) -> str | None:
    """Extract patientId from the row (optional per spec)."""
    for key in ("patientId", "PatientId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _transaction_location_id(row: dict[str, Any]) -> int | None:
    """Extract the CareStack ``locationId`` (integer FK) from the row.

    Per ``docs/integrations/carestack/sync/accounting-transactions.md`` the
    field is ``locationId`` (integer). Strings that look like ints are
    accepted for defensiveness; anything unparseable returns ``None`` so
    the caller omits ``location_id`` from the safe payload.
    """
    for key in ("locationId", "LocationId"):
        value = row.get(key)
        if isinstance(value, bool):
            # ``bool`` is an ``int`` subclass in Python; reject it so
            # ``True``/``False`` never become a location id.
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _transaction_invoice_id(row: dict[str, Any]) -> str | None:
    """Extract the CareStack ``invoiceId`` the transaction is applied to.

    A billing-document id (non-PII, same safety level as the transaction id
    we already store as ``source_external_id``). Stored in the safe payload so
    the PM Payments page can show which invoice a payment belongs to and join
    the invoice number/date (ENG-303). Returns ``None`` when absent (e.g. an
    unallocated payment leg).
    """
    for key in ("invoiceId", "InvoiceId"):
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _transaction_amount(row: dict[str, Any]) -> float | None:
    """Extract the transaction amount as a safe numeric value.

    Returns None if the field is missing or unparseable.
    """
    value = row.get("amount")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _transaction_type(row: dict[str, Any]) -> str | None:
    """Extract the debit/credit indicator from the row.

    Per the spec ``transactionType`` is "a string indicator of debit or
    credit". We pass it through normalised to lowercase so the safe
    payload keeps a small allowed set, never the free-text categorical
    ``transactionCode``.
    """
    value = row.get("transactionType")
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


def _payment_event_kind(row: dict[str, Any]) -> str | None:
    """Map a row to a payment-event kind, or ``None`` for non-payment rows.

    ENG-283 / ENG-284: classification is a STRICT ``transactionCode``
    allow-list. A row produces a payment event ONLY if its
    ``transactionCode`` is a recognised payment code. The
    ``isReversed`` flag flips a recognised CASH code
    (``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` / refund codes) to
    ``payment_reversed``; it leaves allocation codes
    (``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED``) and the explicit
    delete code (``PATIENTPAYMENTSDELETE``) at their mapped kind.

    Rules, in priority order:

    1. Look up ``transactionCode`` in the allow-list
       (:data:`_PAYMENT_CODE_TO_KIND` + :data:`_REFUND_TRANSACTION_CODES`).
       If the code is missing or not in the allow-list → ``None``.
       The raw row is still captured for replay; no timeline event
       emits. This step happens BEFORE the ``isReversed`` check so a
       reversed charge / adjustment / fee update cannot leak into the
       Collected aggregate.
    2. If the row is marked ``isReversed=True`` AND its code is in the
       cash-reversal set (:data:`_CASH_REVERSAL_CODES`), the mapped
       kind is overridden to ``payment_reversed`` — a CareStack-side
       reversal of cash flips the row to the cash-out side of the
       Collected formula. Allocation reversals are NOT promoted to
       ``payment_reversed``: their cash counterpart is the paired
       ``PATIENTPAYMENTSDELETE`` row, and double-subtracting them
       would re-create the negative-Collected bug from a different
       angle.
    3. Otherwise the row emits as the mapped kind
       (``payment_recorded`` for real cash codes,
       ``payment_applied`` for allocation codes,
       ``payment_refunded`` for refund codes,
       ``payment_reversed`` for ``PATIENTPAYMENTSDELETE``).

    The ENG-284 follow-up made this an allow-list because the earlier
    ``isReversed``-first rule promoted reversed ``PROCEDURECOMPLETED``
    and ``PATIENTADJUSTMENT`` rows to ``payment_reversed``, which the
    Collected aggregate subtracts — and the Project Manager Payments
    page Collected total went negative as a result.
    """
    transaction_code = _transaction_code(row)
    if transaction_code is None:
        return None
    if transaction_code in _REFUND_TRANSACTION_CODES:
        mapped_kind: str | None = "payment_refunded"
    else:
        mapped_kind = _PAYMENT_CODE_TO_KIND.get(transaction_code)
    if mapped_kind is None:
        return None
    if _is_reversed(row) and transaction_code in _CASH_REVERSAL_CODES:
        return "payment_reversed"
    return mapped_kind


def _is_reversed(row: dict[str, Any]) -> bool:
    """Return ``True`` when ``isReversed`` is truthy in the row."""
    for key in ("isReversed", "IsReversed"):
        value = row.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        if isinstance(value, int):
            return bool(value)
    return False


def _transaction_code(row: dict[str, Any]) -> str | None:
    for key in ("transactionCode", "TransactionCode"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _parse_carestack_datetime(value: object) -> datetime | None:
    """Parse a CareStack datetime string or passthrough a datetime object."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _carestack_error_status(exc: BaseException) -> int | None:
    """Read the HTTP status from a CareStack-shaped exception, if present.

    ``packages.ingest`` may not import ``packages.integrations`` (cross-
    package matrix), so we duck-type on the ``.details`` attribute the
    integrations layer attaches to its typed exceptions. Returns
    ``None`` when the exception is not CareStack-shaped or lacks a
    status — the caller treats that as non-retryable.
    """
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        status = details.get("status")
        if isinstance(status, int):
            return status
    return None


def _is_retryable_carestack_error(exc: BaseException) -> bool:
    """ENG-285: only 429 + 5xx warrant retry; other errors propagate."""
    status = _carestack_error_status(exc)
    if status is None:
        return False
    return status in _RETRYABLE_STATUS_CODES


def _compose_idempotency_key(
    transaction_id: str, last_updated_on: str | None
) -> str:
    """Encode the spec's ``(id, lastUpdatedOn)`` idempotency key.

    The composed string lands in ``ingest.raw_event.external_id`` so
    forensic queries can dedupe by row+watermark without parsing the
    payload. When ``lastUpdatedOn`` is missing, fall back to the bare
    ``id`` — re-pulls then collide, which is the conservative choice
    (extra forensic copies, never missed edits).
    """
    if last_updated_on is None:
        return transaction_id
    return f"{transaction_id}:{last_updated_on}"
