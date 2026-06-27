"""CareStack Payment Summary snapshot ingest (ENG-257).

CareStack has no bulk feed for per-patient balances. The
``GET /api/v1.0/billing/payment-summary/{patientId}`` endpoint is the
only way to read applied payments, outstanding balances, and
unapplied credits, and it is one-patient-per-request.

This service runs a bounded scheduled sweep over already-linked
CareStack patients (rows in ``identity.source_link`` with
``source_system="carestack"`` and ``source_kind="patient"``). For each
patient we call CareStack once and capture the verbatim PaymentSummary
object to ``ingest.raw_event`` as ``carestack.payment_summary.snapshot``.
``external_id`` is the CareStack patient id — re-runs of the sweep
append additional snapshots (intentional: balances change over time
and the timeline of snapshots is the value).

Trigger decision (documented in the ENG-257 worker report):
  *(a) bounded scheduled sweep* — chosen because it keeps the data
  fresh without a per-call entry point in the API, integrates cleanly
  into the existing scheduled CareStack pull fanout, and is page/limit
  bounded by ``max_patients``. On-demand snapshots can land later as
  a thin wrapper around the same capture method if the dashboard
  needs them.

Failure isolation: an individual patient's call may 4xx/5xx; we log
the error and continue so one bad patient does not poison the sweep.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.schemas import (
    CareStackPaymentSummaryImportOut,
    RawEventIn,
)
from packages.ingest.service import IngestService

log = get_logger("ingest.carestack_payment_summary")

# ENG-285: same retryable status set as the accounting-transactions
# backfill — 429 (CareStack rate limit) + standard transient 5xx.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Safety ceiling for the unbounded sweep. The scheduled sweep caps at
# 50; the backfill walks the full tenant but never more than this many
# patients in a single run so a runaway tenant table never produces an
# unbounded loop.
_BACKFILL_DEFAULT_MAX_PATIENTS = 10000
_PAYMENT_SUMMARY_EVENT_TYPE = "carestack.payment_summary.snapshot"


class CareStackPaymentSummaryClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the snapshot sweep."""

    async def get_payment_summary(
        self, patient_id: int | str
    ) -> dict[str, Any]: ...


class CareStackPaymentSummaryIngestService:
    """Sweep already-linked CareStack patients, capture balance snapshots."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackPaymentSummaryClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)

    async def import_payment_summary_snapshots(
        self,
        tenant_id: TenantId,
        *,
        max_patients: int = 50,
    ) -> CareStackPaymentSummaryImportOut:
        """Bounded sweep: snapshot the N most-recently-linked CareStack patients.

        ``max_patients`` is the hard cap. The sweep walks
        ``identity.source_link`` ordered by ``first_seen_at`` desc — the
        same ordering the dashboard uses — so a single tick covers the
        most-recently-imported patients first.
        """
        if max_patients < 1 or max_patients > 500:
            raise ValidationError(
                "max_patients must be between 1 and 500",
                details={"max_patients": max_patients},
            )

        links = await self._identity_repo.list_source_links_for_dashboard(
            tenant_id,
            source_system="carestack",
            source_kind="patient",
            limit=max_patients,
        )

        snapshot_count = 0
        unchanged_count = 0
        skipped_count = 0
        error_count = 0
        patient_count = len(links)

        for link in links:
            patient_id = link.source_id
            if patient_id is None or not str(patient_id).strip():
                skipped_count += 1
                continue
            try:
                summary = await self._carestack.get_payment_summary(patient_id)
            except Exception as exc:
                # Failure isolation per module docstring; do not let one
                # patient's API failure stop the sweep. PHI-safe log: only
                # the CareStack patient id (a stable non-PII reference) and
                # the exception class name.
                log.warning(
                    "carestack.payment_summary.fetch_failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "patient_id": str(patient_id),
                        "error_class": type(exc).__name__,
                    },
                )
                error_count += 1
                continue

            if await self._capture_snapshot_if_changed(
                tenant_id, str(patient_id), summary
            ):
                snapshot_count += 1
            else:
                unchanged_count += 1

        log.info(
            "carestack.payment_summary.sweep_done",
            tenant_id=str(tenant_id),
            patients=patient_count,
            snapshots=snapshot_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            errors=error_count,
        )
        return CareStackPaymentSummaryImportOut(
            snapshot_count=snapshot_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            error_count=error_count,
            patient_count=patient_count,
        )

    async def pull_all_payment_summaries(
        self,
        tenant_id: TenantId,
        *,
        max_patients: int = _BACKFILL_DEFAULT_MAX_PATIENTS,
        sleep_seconds: float = 0.5,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> CareStackPaymentSummaryImportOut:
        """Throttled historical backfill sweep over linked CareStack patients (ENG-285).

        Unlike :meth:`import_payment_summary_snapshots` (which the
        scheduled sweep uses with a small ``max_patients=50`` cap), this
        method is the operator-triggered backfill path:

        * Walks ALL linked CareStack patients up to ``max_patients`` —
          a defensive ceiling (default 10000) against an unbounded
          tenant table, not a small operational quota.
        * ``sleep_seconds`` (default 0.5s) is awaited between patients
          to stay well below CareStack's rate limit. The CareStack
          tenant throttled this account for ~24h once before —
          backfill must stay gentle.
        * Per-patient retry policy: retryable status codes (429, 5xx —
          see :data:`_RETRYABLE_STATUS_CODES`) trigger exponential
          backoff ``backoff_base_seconds * 2 ** (attempt - 1)``,
          bounded by ``max_retries``. If retries exhaust for one
          patient, that patient is counted as ``error_count`` and the
          sweep CONTINUES to the next patient (failure isolation —
          one bad patient must not poison the whole sweep). The
          operator can re-run later (capture is append-only and the
          dashboard reads LATEST) once the rate-limit window passes.
        * Non-retryable errors per patient (e.g. 401) are also
          failure-isolated — counted as ``error_count`` and the sweep
          continues. Auth errors are surfaced via the leg helper's
          ``sync_run`` close path on the credential-resolution step,
          not here.

        ``sleep`` is injected for tests so the throttle + backoff paths
        complete instantly without actually blocking the event loop.
        """
        if max_patients < 1 or max_patients > _BACKFILL_DEFAULT_MAX_PATIENTS:
            raise ValidationError(
                "max_patients must be between 1 and "
                f"{_BACKFILL_DEFAULT_MAX_PATIENTS}",
                details={"max_patients": max_patients},
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

        links = await self._identity_repo.list_source_links_for_dashboard(
            tenant_id,
            source_system="carestack",
            source_kind="patient",
            limit=max_patients,
        )

        patient_count = len(links)
        usable_patient_ids: list[str] = []
        skipped_count = 0
        for link in links:
            patient_id = link.source_id
            if patient_id is None or not str(patient_id).strip():
                skipped_count += 1
                continue
            usable_patient_ids.append(str(patient_id))

        snapshot_count, unchanged_count, error_count = await self._sweep_patient_ids(
            tenant_id,
            usable_patient_ids,
            sleep_seconds=sleep_seconds,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            sleep_fn=sleep_fn,
            commit_every=1,
            commit=None,
        )

        log.info(
            "carestack.payment_summary.backfill_done",
            tenant_id=str(tenant_id),
            patients=patient_count,
            snapshots=snapshot_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            errors=error_count,
        )
        return CareStackPaymentSummaryImportOut(
            snapshot_count=snapshot_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            error_count=error_count,
            patient_count=patient_count,
        )

    async def import_payment_summary_for_patients(
        self,
        tenant_id: TenantId,
        patient_ids: Iterable[str],
        *,
        sleep_seconds: float = 0.5,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        commit_every: int = 50,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> CareStackPaymentSummaryImportOut:
        """Snapshot ``payment-summary`` for a caller-supplied patient_id set (ENG-305).

        Unlike :meth:`pull_all_payment_summaries`, the caller owns the
        patient set — the live signal in
        :mod:`apps.worker.jobs.ingest_scheduled` passes patient_ids
        derived from the latest accounting-transactions pull, and the
        backfill script (``infra/scripts/backfill_payment_summary.py``)
        resolves them off ``identity.source_link``. This entry point
        keeps the throttle + backoff + failure-isolation behaviour of
        :meth:`pull_all_payment_summaries` and adds batched commits so a
        long sweep never wraps in one giant transaction.

        Input is deduped preserving insertion order so a caller can pass
        the raw output of an accumulator without worrying about repeats.
        ``commit`` is the unit-of-work flush; the sweep calls it every
        ``commit_every`` patients and once more at the end if any
        patient was processed. ``commit=None`` means the caller flushes
        outside the sweep (the existing
        :meth:`pull_all_payment_summaries` path).
        """
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
        if commit_every < 1:
            raise ValidationError(
                "commit_every must be >= 1",
                details={"commit_every": commit_every},
            )

        sleep_fn: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )

        # Dedup preserving insertion order — dict.fromkeys is the canonical
        # idiom; the caller may pass an accumulator with repeats.
        deduped_ids = list(dict.fromkeys(str(pid) for pid in patient_ids))

        snapshot_count, unchanged_count, error_count = await self._sweep_patient_ids(
            tenant_id,
            deduped_ids,
            sleep_seconds=sleep_seconds,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            sleep_fn=sleep_fn,
            commit_every=commit_every,
            commit=commit,
        )

        log.info(
            "carestack.payment_summary.targeted_sweep_done",
            tenant_id=str(tenant_id),
            patients=len(deduped_ids),
            snapshots=snapshot_count,
            unchanged=unchanged_count,
            errors=error_count,
        )
        return CareStackPaymentSummaryImportOut(
            snapshot_count=snapshot_count,
            unchanged_count=unchanged_count,
            skipped_count=0,
            error_count=error_count,
            patient_count=len(deduped_ids),
        )

    async def _sweep_patient_ids(
        self,
        tenant_id: TenantId,
        patient_ids: Iterable[str],
        *,
        sleep_seconds: float,
        max_retries: int,
        backoff_base_seconds: float,
        sleep_fn: Callable[[float], Awaitable[None]],
        commit_every: int,
        commit: Callable[[], Awaitable[None]] | None,
    ) -> tuple[int, int, int]:
        """Iterate a resolved patient_id set, snapshot each changed one.

        Returns ``(success, unchanged, error)`` counts. Shared loop body
        for :meth:`pull_all_payment_summaries` and
        :meth:`import_payment_summary_for_patients`. Per-patient backoff
        is delegated to :meth:`_fetch_summary_with_backoff` — failure
        isolation is the contract: one patient's retries exhausting
        increments ``error_count`` and the sweep continues.

        Throttle: ``sleep_fn(sleep_seconds)`` is awaited between
        patients (no sleep before the first). Errors are still counted
        toward the commit window so the raw_event captures already
        written get flushed even when later patients in the same batch
        fail. The final flush at end is unconditional when any work was
        done — better one redundant commit than a lost batch.
        """
        success_count = 0
        unchanged_count = 0
        error_count = 0
        processed = 0
        did_any_work = False
        for index, patient_id in enumerate(patient_ids):
            if index > 0 and sleep_seconds > 0:
                await sleep_fn(sleep_seconds)

            summary = await self._fetch_summary_with_backoff(
                patient_id,
                tenant_id=tenant_id,
                max_retries=max_retries,
                backoff_base_seconds=backoff_base_seconds,
                sleep_fn=sleep_fn,
            )
            if summary is None:
                error_count += 1
            elif await self._capture_snapshot_if_changed(
                tenant_id, str(patient_id), summary
            ):
                success_count += 1
            else:
                unchanged_count += 1

            processed += 1
            did_any_work = True
            if commit is not None and processed % commit_every == 0:
                await commit()

        if did_any_work and commit is not None:
            await commit()

        return success_count, unchanged_count, error_count

    async def _capture_snapshot_if_changed(
        self,
        tenant_id: TenantId,
        patient_id: str,
        summary: dict[str, Any],
    ) -> bool:
        """Capture the snapshot unless it equals the latest stored one.

        Content-level dedupe (ENG-381, owner decision): payment-summary
        responses carry no provider modified-stamp, so the guard compares
        the WHOLE payload against the newest captured snapshot for the
        patient. Identical → skip (returns False); the patient's latest
        snapshot row keeps serving reads. Side effect accepted by the
        owner: "Last snapshot" surfaces now show when the balance last
        CHANGED (or was first seen), not when it was last polled.
        """
        latest = await self._ingest.latest_payload(
            tenant_id,
            event_type=_PAYMENT_SUMMARY_EVENT_TYPE,
            external_id=patient_id,
        )
        if latest is not None and latest == summary:
            return False
        await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type=_PAYMENT_SUMMARY_EVENT_TYPE,
                external_id=patient_id,
                received_at=datetime.now(UTC),
                payload=summary,
            ),
        )
        return True

    async def _fetch_summary_with_backoff(
        self,
        patient_id: int | str,
        *,
        tenant_id: TenantId,
        max_retries: int,
        backoff_base_seconds: float,
        sleep_fn: Callable[[float], Awaitable[None]],
    ) -> dict[str, Any] | None:
        """Fetch one patient's summary with bounded exponential backoff.

        Returns ``None`` on any unrecoverable error (retries exhausted
        OR non-retryable status). The caller treats ``None`` as a
        per-patient ``error_count`` increment and continues the sweep.
        """
        attempt = 0
        while True:
            try:
                return await self._carestack.get_payment_summary(patient_id)
            except Exception as exc:  # noqa: BLE001 — failure isolation per patient
                status = _carestack_error_status(exc)
                if status not in _RETRYABLE_STATUS_CODES:
                    log.warning(
                        "carestack.payment_summary.fetch_failed",
                        extra={
                            "tenant_id": str(tenant_id),
                            "patient_id": str(patient_id),
                            "error_class": type(exc).__name__,
                            "status": status,
                        },
                    )
                    return None
                if attempt >= max_retries:
                    log.warning(
                        "carestack.payment_summary.retries_exhausted",
                        extra={
                            "tenant_id": str(tenant_id),
                            "patient_id": str(patient_id),
                            "attempts": attempt,
                            "status": status,
                        },
                    )
                    return None
                attempt += 1
                wait_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                log.warning(
                    "carestack.payment_summary.retrying_after_backoff",
                    extra={
                        "tenant_id": str(tenant_id),
                        "patient_id": str(patient_id),
                        "attempt": attempt,
                        "wait_seconds": wait_seconds,
                        "status": status,
                    },
                )
                await sleep_fn(wait_seconds)


def _carestack_error_status(exc: BaseException) -> int | None:
    """Read the HTTP status from a CareStack-shaped exception, if present.

    ``packages.ingest`` may not import ``packages.integrations`` (cross-
    package matrix), so we duck-type on the ``.details`` attribute the
    integrations layer attaches to its typed exceptions.
    """
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        status = details.get("status")
        if isinstance(status, int):
            return status
    return None
