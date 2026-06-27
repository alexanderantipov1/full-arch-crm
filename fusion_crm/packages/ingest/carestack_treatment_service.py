"""CareStack Treatment Procedure ingest pipeline.

For each CareStack treatment procedure row pulled from the sync feed:

1. ``IngestService.capture`` writes the verbatim Treatment Procedure row
   to ``ingest.raw_event``. The CareStack feed carries PHI (procedure
   codes, tooth numbers, surfaces, financial estimates), so the raw row
   remains gated by the existing ``ingest`` access rules.
2. Look up the canonical ``identity.person`` for the procedure's
   ``patientId`` via the existing ``identity.source_link`` row. If the
   patient is not yet linked (patient ingest has not run), the procedure
   is skipped — operator can re-run after the patient pull.
3. Create an ``interaction.event`` timeline entry for the treatment
   lifecycle. Generic procedures map to ``treatment_proposed`` /
   ``treatment_completed``; implant-surgery procedures (``procedureCodeId``
   resolves to a CDT in ``_IMPLANT_SURGERY_CDT_CODES`` via ``CatalogService``)
   split ``statusId=2`` -> ``surgery_scheduled`` and ``statusId=8`` ->
   ``surgery_completed`` (ENG-511). The event summary contains ONLY the
   procedure ID and status, and the payload carries at most a non-PII
   ``is_implant_surgery`` flag + resolved location UUID — NO clinical details,
   codes, tooth numbers, financial data, or patient identifiers.

The CareStack HTTP client is consumed via a local Protocol so this
package does not import ``packages.integrations``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.catalog.service import CatalogService
from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.schemas import (
    CareStackTreatmentImportOut,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.tenant.service import LocationService

log = get_logger("ingest.carestack_treatment")

_TREATMENT_PROCEDURE_EVENT_TYPE = "carestack.treatment_procedure.upsert"

_RESULT_LIST_KEYS = ("results", "items", "records", "data", "treatmentProcedures")

# ENG-351: backfill defaults — mirror the accounting-transaction service so
# the deep (hole-filling) sweep anchors at the same fiscal-year start when
# the operator omits ``since``.
_BACKFILL_DEFAULT_SINCE = datetime(2026, 1, 1, tzinfo=UTC)

# HTTP status codes that justify exponential backoff + retry. 429 is
# CareStack's rate-limit signal; the 5xx set covers transient upstream
# outages. Anything else (401, 4xx other than 429, ...) is propagated so
# the caller can close the sync_run with the correct status.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# CareStack treatment procedure statusId → event kind.
# Per docs/integrations/carestack/sync/treatment-procedures.md:
#   1=Proposed, 2=Scheduled, 3=Accepted, 4=Rejected, 5=Alternative,
#   6=Hold, 7=Referred Out, 8=Completed.
# Baseline (non-implant) mapping: statusId=8 emits "treatment_completed";
# all others emit "treatment_proposed" to keep the timeline concise.
# ENG-511: implant-surgery procedures additionally split statusId=2 ->
# "surgery_scheduled" and statusId=8 -> "surgery_completed" (see
# _resolve_event_kind + _IMPLANT_SURGERY_CDT_CODES).
_SCHEDULED_STATUS_ID = 2
_COMPLETED_STATUS_ID = 8

# OPERATOR-CONFIRMED 2026-06-19: implant-surgery CDT set (surgical placement only).
# ADA CDT surgical-placement family used to gate the surgery_scheduled /
# surgery_completed split (ENG-511). A treatment procedure whose
# ``procedureCodeId`` resolves (via CatalogService) to one of these CDT codes is
# treated as implant surgery; everything else keeps the generic
# treatment_proposed / treatment_completed mapping. The operator confirmed this
# exact set (surgical placement only; abutment/crown restorative codes excluded).
# Changing the set is an operator decision — record it in the mission decision-log.
_IMPLANT_SURGERY_CDT_CODES: frozenset[str] = frozenset(
    {
        "D6010",  # Surgical placement of implant body: endosteal implant
        "D6011",  # Surgical placement of interim/second-stage implant body
        "D6012",  # Surgical placement of interim implant body for transitional prosthesis: endosteal
        "D6013",  # Surgical placement of mini implant
        "D6040",  # Surgical placement: eposteal implant
        "D6050",  # Surgical placement: transosteal implant
        # ENG-538 (operator-confirmed): the practice's custom surgical-placement
        # variants resolved via the real by-id catalog. Matching is
        # ``code.strip().upper() in set`` so these must be EXACT.
        "D6010.A",  # Custom "Implant All on X" (surgical placement, id 228501)
        "D6011NC",  # Custom uncovery / second-stage variant (id 107024)
    }
)


class CareStackTreatmentClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the Treatment ingest."""

    async def list_treatment_procedures_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]: ...


class CareStackTreatmentIngestService:
    """Pull CareStack Treatment Procedures, capture raw, link identity, emit timeline."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackTreatmentClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._interaction = InteractionService(session)
        self._locations = LocationService(session)
        # ENG-511: resolve procedureCodeId -> CDT to gate the implant-surgery
        # split. ``ingest`` may import ``catalog`` (packages/CLAUDE.md matrix).
        self._catalog = CatalogService(session)
        # ENG-538: per-run negative cache for the self-fill hot path. A
        # ``procedureCodeId`` that resolved-missing (404/410) or failed once
        # during this pull is recorded here so repeated rows carrying the same
        # unresolved/failing id do NOT re-hit CareStack. In-memory, instance-
        # scoped → naturally reset every pull (a fresh service per invocation).
        self._procedure_code_self_fill_misses: set[int] = set()

    async def import_recent_treatments(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        page_size: int = 100,
        max_pages: int = 5,
    ) -> CareStackTreatmentImportOut:
        """Capture recent CareStack Treatment Procedure Sync rows into ingest.

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
            tenant_id, event_type=_TREATMENT_PROCEDURE_EVENT_TYPE
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
            body = await self._carestack.list_treatment_procedures_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            rows = _extract_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, rows)
            for row in rows:
                procedure_id = _procedure_source_id(row)
                patient_id = _procedure_patient_id(row)
                if procedure_id is None:
                    skipped_count += 1
                    continue
                stamp = row.get("lastUpdatedOn")
                if (
                    isinstance(stamp, str)
                    and captured_stamps.get(procedure_id) == stamp
                ):
                    unchanged_count += 1
                    continue
                outcome = await self._capture_treatment(
                    tenant_id, row, procedure_id, patient_id
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
            "carestack.treatment.import_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            pages=page_count,
        )
        return CareStackTreatmentImportOut(
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
    ) -> CareStackTreatmentImportOut:
        """Throttled historical backfill of CareStack treatment procedures (ENG-351).

        Unlike :meth:`import_recent_treatments` (which the scheduled pull
        uses with a small ``modified_since`` watermark window and a 5-page
        cap), this method is the operator-triggered DEEP backfill path that
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
                    "carestack.treatment.backfill_backoff_exhausted",
                    tenant_id=str(tenant_id),
                    page_count=page_count,
                )
                break

            page_count += 1
            rows = _extract_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, rows)
            for row in rows:
                procedure_id = _procedure_source_id(row)
                patient_id = _procedure_patient_id(row)
                if procedure_id is None:
                    skipped_count += 1
                    continue
                stamp = row.get("lastUpdatedOn")
                if (
                    isinstance(stamp, str)
                    and captured_stamps.get(procedure_id) == stamp
                ):
                    unchanged_count += 1
                    continue
                outcome = await self._capture_treatment(
                    tenant_id, row, procedure_id, patient_id
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
            "carestack.treatment.backfill_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            pages=page_count,
            resume_token_set=continue_token is not None,
        )
        return CareStackTreatmentImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
        )

    async def reproject_treatments_from_raw(
        self,
        tenant_id: TenantId,
        *,
        rows: list[tuple[UUID, dict[str, Any]]],
    ) -> CareStackTreatmentImportOut:
        """Re-project already-captured treatment procedures (ENG-540).

        Re-runs the CURRENT projection (identity link + surgery-split event
        emit, ENG-511/538) over a batch of EXISTING
        ``carestack.treatment_procedure.upsert`` raw_events — WITHOUT a
        CareStack feed pull and WITHOUT the ``lastUpdatedOn`` dedup-skip that
        makes a normal re-pull a no-op. Historical implant surgeries captured
        under the OLD logic therefore emit ``surgery_scheduled`` /
        ``surgery_completed`` on the timeline so the funnel sees them.

        ``rows`` is a caller-supplied batch of ``(raw_event_id, payload)`` —
        the operator script owns enumeration (oldest→newest, bounded +
        resumable) and the unit of work (commit per batch). This method never
        captures raw and never commits. Idempotency is delegated to
        ``create_event_idempotent``: a second replay over the same rows
        reports ``imported_count == 0`` (every event already exists →
        ``unchanged``). Self-fill (ENG-538) still resolves missing catalog
        codes via the injected client's by-id endpoint when present; the
        feed-pull method is never called.

        ``page_count`` is always ``0`` here — pagination lives in the caller,
        not this per-batch projection.
        """
        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for raw_event_id, row in rows:
            procedure_id = _procedure_source_id(row)
            if procedure_id is None:
                skipped_count += 1
                continue
            patient_id = _procedure_patient_id(row)
            outcome = await self._project_treatment_event(
                tenant_id,
                row,
                procedure_id=procedure_id,
                patient_id=patient_id,
                raw_event_id=raw_event_id,
            )
            if outcome == "imported":
                imported_count += 1
            elif outcome == "unchanged":
                unchanged_count += 1
            else:
                skipped_count += 1

        log.info(
            "carestack.treatment.replay_batch_done",
            tenant_id=str(tenant_id),
            imported=imported_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            rows=len(rows),
        )
        return CareStackTreatmentImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=0,
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
                return await self._carestack.list_treatment_procedures_modified_since(
                    modified_since,
                    page_size=page_size,
                    continue_token=continue_token,
                )
            except Exception as exc:  # noqa: BLE001 — retry funnel
                if not _is_retryable_carestack_error(exc):
                    raise
                if attempt >= max_retries:
                    log.warning(
                        "carestack.treatment.retries_exhausted",
                        attempts=attempt,
                        status=_carestack_error_status(exc),
                    )
                    return None
                attempt += 1
                wait_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                log.warning(
                    "carestack.treatment.retrying_after_backoff",
                    attempt=attempt,
                    wait_seconds=wait_seconds,
                    status=_carestack_error_status(exc),
                )
                await sleep_fn(wait_seconds)

    async def _latest_captured_stamps(
        self, tenant_id: TenantId, rows: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Captured ``lastUpdatedOn`` per procedure id for a page of rows.

        Capture change-guard (ENG-381): rows whose stamp matches are
        healthy overlap re-reads — the caller skips them before any raw
        write or downstream processing.
        """
        candidate_ids = [
            procedure_id
            for row in rows
            if (procedure_id := _procedure_source_id(row)) is not None
        ]
        return await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_TREATMENT_PROCEDURE_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="lastUpdatedOn",
        )

    async def _capture_treatment(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        procedure_id: str,
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

        Raw capture happens FIRST (full-fidelity forensic copy), then the
        projection runs via :meth:`_project_treatment_event` keyed on the
        captured ``raw_event.id``. The replay path (ENG-540) skips this
        method entirely and calls :meth:`_project_treatment_event` against
        an already-captured raw_event id — same projection, no re-capture.
        """
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type="carestack.treatment_procedure.upsert",
                external_id=procedure_id,
                received_at=datetime.now(UTC),
                payload=row,
            ),
        )
        return await self._project_treatment_event(
            tenant_id,
            row,
            procedure_id=procedure_id,
            patient_id=patient_id,
            raw_event_id=raw_event.id,
        )

    async def _project_treatment_event(
        self,
        tenant_id: TenantId,
        row: dict[str, Any],
        *,
        procedure_id: str,
        patient_id: str | None,
        raw_event_id: UUID,
    ) -> str:
        """Resolve identity + emit the timeline event for one treatment row.

        The projection half of :meth:`_capture_treatment`, split out so the
        ENG-540 replay can re-run it against an EXISTING ``ingest.raw_event``
        WITHOUT (a) a CareStack feed pull and (b) the ``lastUpdatedOn``
        dedup-skip — re-projecting historical procedures through the CURRENT
        surgery split (ENG-511/538). ``raw_event_id`` is the
        ``source_event_id`` recorded on the emitted ``interaction.event``;
        the live pull passes the freshly-captured id, the replay passes the
        stored one. Idempotency is delegated to ``create_event_idempotent``
        (same ``(person, kind, source_external_id)`` key), so a re-run emits
        zero new events. Self-fill (ENG-538) still runs via
        :meth:`_resolve_event_kind`. Returns ``"imported"`` / ``"unchanged"``
        / ``"skipped"`` exactly as :meth:`_capture_treatment` documents.
        """
        if patient_id is None:
            log.warning(
                "carestack.treatment.skipped: no patientId in payload",
                extra={
                    "procedure_id": procedure_id,
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
                "carestack.treatment.skipped: patient not yet linked",
                extra={
                    "procedure_id": procedure_id,
                    "patient_id": patient_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        # Determine the event kind based on statusId, splitting implant-surgery
        # procedures into surgery_scheduled / surgery_completed (ENG-511).
        kind, is_implant_surgery = await self._resolve_event_kind(row)

        # Use lastUpdatedOn or dateOfService as the event timestamp;
        # fall back to now() if neither is available.
        occurred_at = (
            _parse_carestack_datetime(row.get("dateOfService"))
            or _parse_carestack_datetime(row.get("lastUpdatedOn"))
            or datetime.now(UTC)
        )

        # Safe summary: procedure ID + status only. NO clinical details,
        # tooth numbers, codes, or financial data.
        summary = summary_for_event(
            kind=kind,
            source_provider="carestack",
            source_id=procedure_id,
        )

        # Safe non-PII payload: only the resolved tenant.location UUID
        # when the CareStack row carries a mapped ``locationId``. Treatment
        # rows otherwise stay payload-free — clinical fields stay in the
        # gated raw_event.
        safe_payload: dict[str, object] = {}
        location_uid = await self._resolve_location_uid(
            tenant_id, _procedure_location_id(row)
        )
        if location_uid is not None:
            safe_payload["location_id"] = location_uid
        # ENG-511: non-PII surgical flag for the surgery_* events. NEVER the
        # procedureCodeId / CDT / tooth / surfaces / financials — those stay in
        # the gated raw_event only.
        if is_implant_surgery:
            safe_payload["is_implant_surgery"] = True

        # ENG-269: cross-pull dedup — conflicts count as skipped, not imported.
        result = await self._interaction.create_event_idempotent(
            tenant_id,
            EventIn(
                person_uid=source_link.person_uid,
                kind=kind,
                source_provider="carestack",
                source_event_id=raw_event_id,
                data_class="phi_protected",
                source_kind="carestack_treatment_procedure",
                source_external_id=procedure_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary,
                payload=safe_payload,
            ),
        )
        return "imported" if result.was_created else "unchanged"

    async def _resolve_event_kind(self, row: dict[str, Any]) -> tuple[str, bool]:
        """Map a treatment procedure row to ``(event_kind, is_implant_surgery)``.

        Implant-surgery procedures (``procedureCodeId`` resolves to a CDT in
        :data:`_IMPLANT_SURGERY_CDT_CODES`) split the lifecycle:

        * ``statusId=2`` (Scheduled) -> ``surgery_scheduled``
        * ``statusId=8`` (Completed) -> ``surgery_completed``

        Every other procedure (and an implant procedure in any other status)
        keeps the generic baseline: ``statusId=8`` -> ``treatment_completed``,
        else ``treatment_proposed``. The boolean is ``True`` ONLY for the two
        surgery events, so the safe payload carries the non-PII surgical flag
        exactly where it is meaningful.
        """
        status_id = _status_id(row)
        if await self._is_implant_surgery(row):
            if status_id == _SCHEDULED_STATUS_ID:
                return "surgery_scheduled", True
            if status_id == _COMPLETED_STATUS_ID:
                return "surgery_completed", True
        return _treatment_event_kind(row), False

    async def _is_implant_surgery(self, row: dict[str, Any]) -> bool:
        """True when the row's ``procedureCodeId`` resolves to an implant CDT.

        Resolves the CareStack ``procedureCodeId`` to its CDT ``code`` via
        :class:`CatalogService` and tests membership in the operator-gated
        :data:`_IMPLANT_SURGERY_CDT_CODES` set. On a catalog miss, attempts a
        best-effort by-id self-fill (ENG-538) so a brand-new custom code is
        resolved+inserted on first sight and the surgery gate works without a
        manual backfill. Unknown / unresolvable codes are NOT implant surgery
        (fail closed to the generic mapping) so a missing catalog row never
        mislabels a procedure as surgery.
        """
        code_id = _procedure_code_id(row)
        if code_id is None:
            return False
        resolved = await self._catalog.resolve_procedure_codes([code_id])
        entry = resolved.get(code_id)
        if entry is None:
            entry = await self._self_fill_procedure_code(code_id)
        if entry is None:
            return False
        code, _description = entry
        return code.strip().upper() in _IMPLANT_SURGERY_CDT_CODES

    async def _self_fill_procedure_code(
        self, code_id: int
    ) -> tuple[str, str | None] | None:
        """Resolve+insert one missing procedure code via the by-id endpoint.

        Best-effort (ENG-538): only fires on a catalog miss, only when the
        injected CareStack client exposes ``get_procedure_code`` (the deep
        backfill / scheduled pull inject the real client; lean test stubs do
        not, so they stay fail-closed). Bounded — once a code is inserted,
        subsequent rows hit the catalog and never call CareStack again.

        Hot-path guards (ENG-538 Codex review):

        * **Low retry** — :meth:`CatalogService.ensure_procedure_codes` is
          invoked with its single-attempt / no-throttle defaults, so one flaky
          or rate-limited lookup never holds the ingest unit of work for the
          full multi-second backoff the standalone backfill uses.
        * **Per-run negative cache** — an id that resolves-missing OR fails once
          is remembered in ``_procedure_code_self_fill_misses`` and skipped for
          the rest of the pull, so repeated rows with the same bad id don't
          re-call CareStack.

        Any failure is swallowed (logged) so a flaky procedure-code lookup —
        including a hard auth failure now that the catalog by-id fetch
        propagates 401/403 — never breaks treatment ingest; the row simply
        keeps the generic mapping. Returns the resolved ``(code, description)``
        or ``None``.
        """
        if code_id in self._procedure_code_self_fill_misses:
            return None
        getter = getattr(self._carestack, "get_procedure_code", None)
        if not callable(getter):
            return None
        from typing import cast

        from packages.catalog.service import (
            CareStackProcedureCodeByIdClientProtocol,
        )

        client = cast(CareStackProcedureCodeByIdClientProtocol, self._carestack)
        try:
            newly = await self._catalog.ensure_procedure_codes(client, [code_id])
        except Exception as exc:  # noqa: BLE001 — self-fill is best-effort
            # Includes a propagated auth/config failure or exhausted retry from
            # the by-id fetch. Swallow + log so ingest never breaks, and remember
            # the miss so we don't re-call CareStack for this id this run.
            log.warning(
                "carestack.treatment.procedure_code_self_fill_failed",
                procedure_code_id=code_id,
                error=str(exc)[:200],
            )
            self._procedure_code_self_fill_misses.add(code_id)
            return None
        if not newly:
            # Resolved-missing (404/410) or nothing inserted — negative-cache it.
            self._procedure_code_self_fill_misses.add(code_id)
            return None
        resolved = await self._catalog.resolve_procedure_codes([code_id])
        entry = resolved.get(code_id)
        if entry is None:
            self._procedure_code_self_fill_misses.add(code_id)
        return entry

    async def _resolve_location_uid(
        self, tenant_id: TenantId, carestack_location_id: int | None
    ) -> str | None:
        """Resolve a CareStack ``locationId`` to our tenant.location UUID.

        Returns ``str(uuid)`` when the CareStack id maps to a known
        location for this tenant. Returns ``None`` when the row carries
        no ``locationId`` OR the id is not mapped. The event still emits
        in the unmapped case — location is enrichment, not gating.
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
                "carestack.treatment.location_resolve_failed",
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
    """Extract the list of treatment procedure records from the envelope."""
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


def _procedure_source_id(row: dict[str, Any]) -> str | None:
    """Extract the treatment procedure ID from the row.

    Per the CareStack sync spec, the field is ``id`` (integer).
    """
    for key in ("id", "procedureId", "treatmentProcedureId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _procedure_patient_id(row: dict[str, Any]) -> str | None:
    """Extract patientId from the treatment procedure payload.

    Per docs/integrations/carestack/sync/treatment-procedures.md the
    field is ``patientId`` (integer).
    """
    for key in ("patientId", "PatientId"):
        value = row.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _procedure_location_id(row: dict[str, Any]) -> int | None:
    """Extract the CareStack ``locationId`` (integer FK) from the row.

    Per ``docs/integrations/carestack/sync/treatment-procedures.md`` the
    field is ``locationId`` (integer). Strings that look like ints are
    accepted for defensiveness; anything unparseable returns ``None`` so
    the caller omits ``location_id`` from the safe payload.
    """
    for key in ("locationId", "LocationId"):
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _status_id(row: dict[str, Any]) -> int | None:
    """Parse the CareStack ``statusId`` (int) from the row, tolerating strings."""
    value = row.get("statusId")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _procedure_code_id(row: dict[str, Any]) -> int | None:
    """Extract the CareStack ``procedureCodeId`` (integer FK) from the row.

    Per ``docs/integrations/carestack/sync/treatment-procedures.md`` the field
    is ``procedureCodeId`` (integer). Strings that look like ints are accepted
    defensively; anything unparseable returns ``None`` so the caller falls back
    to the generic (non-implant) mapping.
    """
    for key in ("procedureCodeId", "ProcedureCodeId"):
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _treatment_event_kind(row: dict[str, Any]) -> str:
    """Map the CareStack statusId to an event kind.

    statusId=8 -> "treatment_completed"; everything else ->
    "treatment_proposed".
    """
    status_id = row.get("statusId")
    if isinstance(status_id, int) and status_id == _COMPLETED_STATUS_ID:
        return "treatment_completed"
    if isinstance(status_id, str) and status_id.strip() == str(_COMPLETED_STATUS_ID):
        return "treatment_completed"
    return "treatment_proposed"


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
