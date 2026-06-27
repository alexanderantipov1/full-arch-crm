"""CareStack Patient ingest pipeline.

Captures CareStack Patient Sync rows into the canonical ingest path:

1. ``IngestService.capture`` writes the verbatim Patient row to
   ``ingest.raw_event``.
2. ``IngestService.capture_normalized_person_hint`` writes a PHI-minimised
   matching hint for identity.
3. ``IdentityService.resolve_or_create_from_hint`` applies the conservative
   match policy and writes the source link.

The CareStack HTTP client is consumed via a local protocol so this package
does not import ``packages.integrations``.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.identity.schemas import MatchHintIn
from packages.identity.service import IdentityService
from packages.ingest.schemas import (
    CareStackPatientImportOut,
    NormalizedPersonHintIn,
    RawEventIn,
)
from packages.ingest.service import IngestService
from packages.ingest.sync_window import resume_modified_since

log = get_logger("ingest.carestack_patient")

_PATIENT_EVENT_TYPE = "carestack.patient.upsert"
_PATIENT_LIST_KEYS = ("patients", "items", "records", "results", "data")


class CareStackPatientClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the Patient ingest service."""

    async def list_patients_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]: ...


class CareStackPatientIngestService:
    """Pull CareStack Patients, capture raw, and resolve identity conservatively."""

    def __init__(
        self,
        session: AsyncSession,
        carestack_client: CareStackPatientClientProtocol,
    ) -> None:
        self._session = session
        self._carestack = carestack_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)

    async def import_recent_patients(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        page_size: int = 100,
        max_pages: int = 1,
    ) -> CareStackPatientImportOut:
        """Capture recent CareStack Patient Sync rows into ingest.

        ``max_pages`` defaults to one page for a bounded manual import. The
        method follows CareStack ``continueToken`` when requested, but never
        performs appointment ingest or destructive merges.
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

        # Resume from the highest captured ``lastUpdatedOn`` (ENG-381);
        # ``days`` is the first-run fallback.
        watermark = await self._ingest.max_payload_watermark(
            tenant_id, event_type=_PATIENT_EVENT_TYPE
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
            body = await self._carestack.list_patients_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            patients = _extract_patient_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, patients)
            for patient in patients:
                patient_id = _patient_source_id(patient)
                if patient_id is None:
                    skipped_count += 1
                    continue
                stamp = patient.get("lastUpdatedOn")
                if isinstance(stamp, str) and captured_stamps.get(patient_id) == stamp:
                    unchanged_count += 1
                    continue
                if await self._capture_patient_safe(tenant_id, patient, patient_id):
                    imported_count += 1
                else:
                    skipped_count += 1

            continue_token = _continue_token(body)
            if not continue_token:
                break

        return CareStackPatientImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
        )

    async def pull_all_since(
        self,
        tenant_id: TenantId,
        since: datetime,
        *,
        page_size: int = 500,
        page_safety_cap: int = 1000,
    ) -> CareStackPatientImportOut:
        """Full backfill of CareStack Patients modified on or after ``since``.

        Follows ``continueToken`` until exhausted. ``page_safety_cap`` is a
        defensive ceiling (default 1000 pages → 500k records at page_size=500)
        to prevent a misbehaving provider from looping forever. If the cap is
        hit the partial result is returned with ``next_continue_token`` set so
        the operator can resume.
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

        modified_since = (
            since if since.tzinfo is not None else since.replace(tzinfo=UTC)
        )
        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        page_count = 0
        continue_token: str | None = None
        while page_count < page_safety_cap:
            body = await self._carestack.list_patients_modified_since(
                modified_since,
                page_size=page_size,
                continue_token=continue_token,
            )
            page_count += 1
            patients = _extract_patient_rows(body)
            captured_stamps = await self._latest_captured_stamps(tenant_id, patients)
            for patient in patients:
                patient_id = _patient_source_id(patient)
                if patient_id is None:
                    skipped_count += 1
                    continue
                stamp = patient.get("lastUpdatedOn")
                if isinstance(stamp, str) and captured_stamps.get(patient_id) == stamp:
                    unchanged_count += 1
                    continue
                if await self._capture_patient_safe(tenant_id, patient, patient_id):
                    imported_count += 1
                else:
                    skipped_count += 1
            continue_token = _continue_token(body)
            if not continue_token:
                break
        return CareStackPatientImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            page_count=page_count,
            next_continue_token=continue_token,
        )

    async def _latest_captured_stamps(
        self, tenant_id: TenantId, rows: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Captured ``lastUpdatedOn`` per patient id for a page of rows.

        Capture change-guard (ENG-381): rows whose stamp matches are
        healthy overlap re-reads — the caller skips them before any raw
        write or downstream processing.
        """
        candidate_ids = [
            patient_id
            for row in rows
            if (patient_id := _patient_source_id(row)) is not None
        ]
        return await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_PATIENT_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="lastUpdatedOn",
        )

    async def _capture_patient_safe(
        self, tenant_id: TenantId, patient: dict[str, Any], patient_id: str
    ) -> bool:
        """Capture one patient inside a SAVEPOINT (ENG-340).

        A single bad patient row — e.g. a shared household phone that trips
        ``uq_person_identifier_kind_value`` — must roll back only that patient,
        never poison the surrounding session and abort the whole CareStack tick
        (which would also drop appointments, invoices and payments). Returns
        ``True`` when the patient was captured, ``False`` when it was skipped.
        """
        try:
            async with self._session.begin_nested():
                await self._capture_patient(tenant_id, patient, patient_id)
            return True
        except Exception as exc:  # noqa: BLE001 - one bad patient must not abort the tick
            log.warning(
                "carestack.patient.capture_failed",
                patient_id=patient_id,
                error=type(exc).__name__,
            )
            return False

    async def _capture_patient(
        self,
        tenant_id: TenantId,
        patient: dict[str, Any],
        patient_id: str,
    ) -> None:
        observed_at = _parse_carestack_datetime(patient.get("lastUpdatedOn"))
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="carestack",
                event_type=_PATIENT_EVENT_TYPE,
                external_id=patient_id,
                received_at=datetime.now(UTC),
                payload=patient,
            ),
        )

        hint = await self._ingest.capture_normalized_person_hint(
            tenant_id,
            NormalizedPersonHintIn(
                raw_event_id=raw_event.id,
                source_system="carestack",
                source_instance="carestack-main",
                source_kind="patient",
                source_id=patient_id,
                observed_at=observed_at or raw_event.received_at,
                given_name=_string_or_none(patient.get("firstName")),
                family_name=_string_or_none(patient.get("lastName")),
                display_name=_join_name(
                    _string_or_none(patient.get("firstName")),
                    _string_or_none(patient.get("lastName")),
                ),
                email=_string_or_none(patient.get("email")),
                phone=_first_string(patient.get("mobile"), patient.get("phoneWithExt")),
                payload_sha256=_payload_sha256(patient),
            ),
        )

        if hint.source_id is None:
            raise ValidationError("normalized CareStack Patient hint source_id is required")

        # ENG-309: extract DOB / SSN from the raw payload and pass them as
        # identity-strength hard-veto signals into the resolver. They are
        # NOT routed through the normalized_person_hint row (the ingest
        # hint schema is intentionally non-PHI for the staff dashboard's
        # safe surface); they ride directly into MatchHintIn instead, where
        # they are consumed and discarded -- never written to evidence or
        # logs.
        await self._identity.resolve_or_create_from_hint(
            tenant_id,
            MatchHintIn(
                hint_id=hint.id,
                source_system=hint.source_system,
                source_instance=hint.source_instance,
                source_kind=hint.source_kind,
                source_id=hint.source_id,
                given_name=hint.given_name,
                family_name=hint.family_name,
                display_name=hint.display_name,
                email_normalized=hint.email_normalized,
                phone_normalized=hint.phone_normalized,
                dob=_parse_carestack_dob(patient.get("dob")),
                ssn=_normalize_ssn(patient.get("ssn")),
                quality_flags=hint.quality_flags,
                meta=hint.meta,
            ),
        )


def _extract_patient_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _PATIENT_LIST_KEYS:
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


def _patient_source_id(patient: dict[str, Any]) -> str | None:
    for key in ("patientId", "id", "PatientId"):
        value = patient.get(key)
        if isinstance(value, str | int) and str(value).strip():
            return str(value)
    return None


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _first_string(*values: object) -> str | None:
    for value in values:
        candidate = _string_or_none(value)
        if candidate is not None:
            return candidate
    return None


def _join_name(first: str | None, last: str | None) -> str | None:
    parts = [part for part in (first, last) if part]
    return " ".join(parts) if parts else None


def _parse_carestack_datetime(value: object) -> datetime | None:
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


def _payload_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


_SSN_NON_DIGITS = re.compile(r"\D+")


def _parse_carestack_dob(value: object) -> date | None:
    """Parse a CareStack ``dob`` field into a :class:`datetime.date` or None.

    CareStack Patient Sync emits DOB as either ``"YYYY-MM-DD"`` or an ISO
    timestamp like ``"1968-04-19T00:00:00"`` (depending on the field).
    Both reduce to the date portion. Anything malformed returns ``None``
    so a single bad row never blocks ingest; the resolver veto only fires
    when both sides have a usable value.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().split("T", 1)[0]
    try:
        return date.fromisoformat(candidate)
    except ValueError:
        return None


def _normalize_ssn(value: object) -> str | None:
    """Return a digit-only SSN string, or ``None`` for empty / non-string input.

    The resolver's hard-veto compare also strips whitespace + dashes
    defensively, but normalising here keeps the persisted value stable
    across providers (so an operator-side SSN reconciliation is not
    confused by ``"623-35-9385"`` vs ``"623359385"`` vs ``" 623359385 "``).
    """
    if not isinstance(value, str):
        return None
    digits = _SSN_NON_DIGITS.sub("", value)
    return digits or None
