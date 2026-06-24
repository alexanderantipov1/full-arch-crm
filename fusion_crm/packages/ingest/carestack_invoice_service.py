"""CareStack Invoice ingest pipeline.

For each CareStack invoice row pulled from the sync feed:

1. ``IngestService.capture`` writes the verbatim Invoice row to
   ``ingest.raw_event``. The CareStack feed is PHI-adjacent (invoice
   rows link a ``patientId`` to financial data), so the raw row remains
   gated by the existing ``ingest`` access rules.
2. Look up the canonical ``identity.person`` for the invoice's
   ``patientId`` via the existing ``identity.source_link`` row. If the
   patient is not yet linked (patient ingest has not run), or the
   invoice has no ``patientId`` (practice-level advance payments), the
   invoice is still captured but skipped for timeline emission.
3. Create an ``interaction.event`` timeline entry for the invoice. The
   event summary contains ONLY the invoice ID, total amount, and status
   — NO line items, clinical codes, or patient identifiers.

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
    CareStackInvoiceImportOut,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.tenant.service import LocationService

log = get_logger("ingest.carestack_invoice")

_INVOICE_EVENT_TYPE = "carestack.invoice.upsert"

_RESULT_LIST_KEYS = ("results", "items", "records", "data", "invoices")

# ENG-351: backfill defaults — mirror the accounting-transaction service so
# the deep (hole-filling) sweep anchors at the same fiscal-year start when
# the operator omits ``since``.
_BACKFILL_DEFAULT_SINCE = datetime(2026, 1, 1, tzinfo=UTC)

# HTTP status codes that justify exponential backoff + retry. 429 is
# CareStack's rate-limit signal; the 5xx set covers transient upstream
# outages. Anything else (401, 4xx other than 429, ...) is propagated so
# the caller can close the sync_run with the correct status.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class CareStackInvoiceClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the Invoice ingest."""

    async def list_invoices_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]: ...


class CareStackInvoiceIngestService:
    """Pull CareStack Invoices, capture raw, link identity, emit timeline."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackInvoiceClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._interaction = InteractionService(session)
        self._locations = LocationService(session)

    async def import_recent_invoices(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        page_size: int = 100,
        max_pages: int = 5,
    ) -> CareStackInvoiceImportOut:
        """Capture recent CareStack Invoice Sync rows into ingest.

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

        # Resume from the highest captured ``lastUpdatedOn`` so the pull
        # advances to the newest rows instead of re-reading the oldest edge
        # of a fixed window each run. ``days`` is the first-run fallback.
        watermark = await self._ingest.max_payload_watermark(
            tenant_id, event_type=_INVOICE_EVENT_TYPE
        )
        modified_since = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        page_count = 0
        continue_token: str | None = None

        while page_count < max_pages:
            body = await self._carestack.list_invoices_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            rows = _extract_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, rows)
            for row in rows:
                invoice_id = _invoice_source_id(row)
                patient_id = _invoice_patient_id(row)
                if invoice_id is None:
                    skipped_count += 1
                    continue
                stamp = row.get("lastUpdatedOn")
                if (
                    isinstance(stamp, str)
                    and captured_stamps.get(invoice_id) == stamp
                ):
                    # ENG-384: the captured ``lastUpdatedOn`` already
                    # matches the upstream stamp — healthy overlap
                    # re-read. Skip without raw write or downstream emit.
                    unchanged_count += 1
                    continue
                outcome = await self._capture_invoice(
                    tenant_id, row, invoice_id, patient_id
                )
                if outcome == "imported":
                    imported_count += 1
                elif outcome == "unchanged":
                    unchanged_count += 1
                else:
                    skipped_count += 1

            continue_token = _continue_token(body)
            if not continue_token:
                break

        log.info(
            "carestack.invoice.import_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            pages=page_count,
        )
        return CareStackInvoiceImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
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
    ) -> CareStackInvoiceImportOut:
        """Throttled historical backfill of CareStack invoices (ENG-351).

        Unlike :meth:`import_recent_invoices` (which the scheduled pull uses
        with a small ``modified_since`` watermark window and a 5-page cap),
        this method is the operator-triggered DEEP backfill path that
        re-fills historical holes — it scans the feed forward from ``since``
        to exhaustion, IGNORING the watermark, so a day the local worker was
        asleep is back-filled:

        * ``since`` defaults to ``2026-01-01T00:00:00Z``. Naive datetimes
          are assumed UTC.
        * Pagination follows ``continueToken`` until exhausted OR the
          ``page_safety_cap`` (default 2000 pages) is reached.
        * ``sleep_seconds`` (default 0.5s) is awaited between pages to stay
          well below CareStack's rate limit.
        * Retryable status codes (429, 5xx — see
          :data:`_RETRYABLE_STATUS_CODES`) trigger exponential backoff:
          ``backoff_base_seconds * 2 ** (attempt - 1)`` waits, bounded by
          ``max_retries``. If retries exhaust the loop STOPS and returns the
          last continueToken so the operator can resume. Non-retryable
          errors propagate so the leg helper can close the ``sync_run``.
        * Idempotent: raw_event re-capture is forensic, and the event layer
          dedupes via ``create_event_idempotent`` (ENG-269) — re-runs report
          ``imported_count == 0`` / ``unchanged_count`` for already-emitted
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
                    "carestack.invoice.backfill_backoff_exhausted",
                    tenant_id=str(tenant_id),
                    page_count=page_count,
                )
                break

            page_count += 1
            rows = _extract_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, rows)
            for row in rows:
                invoice_id = _invoice_source_id(row)
                patient_id = _invoice_patient_id(row)
                if invoice_id is None:
                    skipped_count += 1
                    continue
                stamp = row.get("lastUpdatedOn")
                if (
                    isinstance(stamp, str)
                    and captured_stamps.get(invoice_id) == stamp
                ):
                    # ENG-384: deep-backfill re-runs hit the guard so an
                    # operator-triggered sweep over already-captured rows
                    # writes ZERO new raw events (matches the recent path).
                    unchanged_count += 1
                    continue
                outcome = await self._capture_invoice(
                    tenant_id, row, invoice_id, patient_id
                )
                if outcome == "imported":
                    imported_count += 1
                elif outcome == "unchanged":
                    unchanged_count += 1
                else:
                    skipped_count += 1

            # Per-page checkpoint (ENG-326). ``create_event_idempotent``
            # opens a SAVEPOINT per event; a full-year drain emits tens of
            # thousands of them. Commit each page to release the page's
            # SAVEPOINTs and persist progress so a mid-run failure resumes
            # from the next continue token instead of rolling the whole
            # backfill back. This streaming backfill is a documented
            # exception to the "services never commit" invariant.
            await self._session.commit()

            continue_token = _continue_token(body)
            if not continue_token:
                break

        log.info(
            "carestack.invoice.backfill_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            pages=page_count,
            resume_token_set=continue_token is not None,
        )
        return CareStackInvoiceImportOut(
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
        exhausted (the caller stops and returns the current continue token
        so the operator can resume). Non-retryable errors are propagated.
        """
        attempt = 0
        while True:
            try:
                return await self._carestack.list_invoices_modified_since(
                    modified_since,
                    page_size=page_size,
                    continue_token=continue_token,
                )
            except Exception as exc:  # noqa: BLE001 — retry funnel
                if not _is_retryable_carestack_error(exc):
                    raise
                if attempt >= max_retries:
                    log.warning(
                        "carestack.invoice.retries_exhausted",
                        attempts=attempt,
                        status=_carestack_error_status(exc),
                    )
                    return None
                attempt += 1
                wait_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                log.warning(
                    "carestack.invoice.retrying_after_backoff",
                    attempt=attempt,
                    wait_seconds=wait_seconds,
                    status=_carestack_error_status(exc),
                )
                await sleep_fn(wait_seconds)

    async def _latest_captured_stamps(
        self, tenant_id: TenantId, rows: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Captured ``lastUpdatedOn`` per invoice id for a page of rows.

        ENG-384 capture change-guard: rows whose upstream stamp matches
        the captured one are healthy overlap re-reads — the caller skips
        them before any raw write or downstream emit. Mirrors the
        appointment-service helper (the invoice external_id is the bare
        invoice id, so the appointment pattern fits directly).
        """
        candidate_ids = [
            invoice_id
            for row in rows
            if (invoice_id := _invoice_source_id(row)) is not None
        ]
        return await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_INVOICE_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="lastUpdatedOn",
        )

    async def _capture_invoice(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        invoice_id: str,
        patient_id: str | None,
    ) -> str:
        """Capture raw + resolve identity + emit timeline event.

        Returns one of:

        * ``"imported"`` — a fresh ``interaction.event`` was created.
        * ``"unchanged"`` — the event already existed and
          ``create_event_idempotent`` deduped it (``was_created is
          False``). HEALTHY idempotent re-pull, NOT a failure.
        * ``"skipped"`` — genuine non-import: ``patientId`` missing or
          the patient is not yet linked. The raw_event is still captured.
        """
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type="carestack.invoice.upsert",
                external_id=invoice_id,
                received_at=datetime.now(UTC),
                payload=row,
            ),
        )

        if patient_id is None:
            log.warning(
                "carestack.invoice.skipped: no patientId in payload",
                extra={
                    "invoice_id": invoice_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        # Resolve patientId -> person_uid via the source_link from a prior
        # patient pull. Two-pass design — patient pull must run first.
        source_link = await self._identity_repo.find_source_link(
            tenant_id,
            source_system="carestack",
            source_instance="carestack-main",
            source_kind="patient",
            source_id=patient_id,
        )
        if source_link is None:
            log.warning(
                "carestack.invoice.skipped: patient not yet linked",
                extra={
                    "invoice_id": invoice_id,
                    "patient_id": patient_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        # Use paymentDate or lastUpdatedOn as the event timestamp;
        # fall back to now() if neither is available.
        occurred_at = (
            _parse_carestack_datetime(row.get("paymentDate"))
            or _parse_carestack_datetime(row.get("lastUpdatedOn"))
            or datetime.now(UTC)
        )

        # Safe summary: invoice ID only. The amount is billing-sensitive
        # but the invoice external ID is a stable non-PII reference.
        summary = summary_for_event(
            kind="invoice_created",
            source_provider="carestack",
            source_id=invoice_id,
        )

        # Safe non-PII payload: only the invoice amount, invoice type,
        # and the resolved tenant.location UUID (when the CS locationId
        # maps to a known location). NO line items, clinical codes,
        # payment category details, or patient identifiers.
        safe_payload: dict[str, object] = {}
        amount = _invoice_amount(row)
        if amount is not None:
            safe_payload["amount"] = amount
        invoice_type = row.get("invoiceType")
        if isinstance(invoice_type, int) and not isinstance(invoice_type, bool):
            safe_payload["invoice_type"] = invoice_type
        location_uid = await self._resolve_location_uid(
            tenant_id, _invoice_location_id(row)
        )
        if location_uid is not None:
            safe_payload["location_id"] = location_uid

        # ENG-269: count a cross-pull dedup conflict as "skipped" so
        # dashboard counters stay truthful across re-pulls.
        result = await self._interaction.create_event_idempotent(
            tenant_id,
            EventIn(
                person_uid=source_link.person_uid,
                kind="invoice_created",
                source_provider="carestack",
                source_event_id=raw_event.id,
                data_class="billing",
                source_kind="carestack_invoice",
                source_external_id=invoice_id,
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
                "carestack.invoice.location_resolve_failed",
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
    """Extract the list of invoice records from the envelope."""
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


def _invoice_source_id(row: dict[str, Any]) -> str | None:
    """Extract the invoice ID from the row.

    Per the CareStack sync spec, the field is ``invoiceId`` (integer).
    """
    for key in ("invoiceId", "id", "InvoiceId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _invoice_patient_id(row: dict[str, Any]) -> str | None:
    """Extract patientId from the invoice payload.

    Per docs/integrations/carestack/sync/invoices.md the field is
    ``patientId`` (integer, optional — may be absent for practice-level
    advance payments).
    """
    for key in ("patientId", "PatientId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _invoice_location_id(row: dict[str, Any]) -> int | None:
    """Extract the CareStack ``locationId`` (integer FK) from the row.

    Per ``docs/integrations/carestack/sync/invoices.md`` the field is
    ``locationId`` (integer). Strings that look like ints are accepted
    for defensiveness; anything unparseable returns ``None`` so the
    caller omits ``location_id`` from the safe payload.
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


def _invoice_amount(row: dict[str, Any]) -> float | None:
    """Extract the invoice amount as a safe numeric value.

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
    integrations layer attaches to its typed exceptions. Returns ``None``
    when the exception is not CareStack-shaped or lacks a status — the
    caller treats that as non-retryable.
    """
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        status = details.get("status")
        if isinstance(status, int):
            return status
    return None


def _is_retryable_carestack_error(exc: BaseException) -> bool:
    """ENG-351: only 429 + 5xx warrant retry; other errors propagate."""
    status = _carestack_error_status(exc)
    if status is None:
        return False
    return status in _RETRYABLE_STATUS_CODES
