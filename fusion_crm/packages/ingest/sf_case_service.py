"""Salesforce Case ingest service with identity linking and timeline events.

Pulls standard ``Case`` rows via SOQL, captures each row verbatim into
``ingest.raw_event``, resolves ``ContactId`` to a canonical ``person_uid``
via ``identity.source_link``, then emits workflow-ready interaction events.

PHI safety:
- Case records may contain clinical context in free-text fields such
  as ``Subject`` and ``Description``.  We intentionally exclude
  ``Description`` from the SOQL SELECT to avoid ingesting free-text
  PHI.  ``Subject`` is used only for deterministic classification in
  the event summary (capped, no free text). It is stored solely in
  ``ingest.raw_event`` (PHI-carrier schema); reads are gated.
- Timeline summaries use Case Subject + Status only. No Description,
  no free text beyond Subject.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.schemas import RawEventIn, SchemaDiffOut, SfCaseImportOut
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.models import Event
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event

logger = logging.getLogger(__name__)


class SfCaseClientProtocol(Protocol):
    """Minimum Salesforce client surface used by the Case ingest service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


# Static fallback projection (ENG-427); normal pulls use the dynamic projection.
_SF_CASE_COLUMNS = (
    "Id, Subject, Status, Priority, Origin, Type, AccountId, "
    "ContactId, OwnerId, CreatedDate, LastModifiedDate, IsClosed, "
    "ClosedDate"
)
_SF_CASE_EVENT_TYPE = "salesforce.case.upsert"
# Ascending order is load-bearing for the watermark cursor (ENG-381):
# oldest pending changes are captured first so the watermark never
# advances past changes that were cut off by ``limit``.
_SF_CASE_SOQL = (
    "SELECT {projection} FROM Case "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {limit}"
)


class SfCaseIngestService:
    """Pull SF Cases, capture raw, resolve person, emit timeline events."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfCaseClientProtocol,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._interaction = InteractionService(session)

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Case",
            static_projection=_SF_CASE_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_cases(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 200,
    ) -> SfCaseImportOut:
        """Pull Cases modified within the last ``days`` days."""
        if days < 1 or days > 365:
            raise ValidationError(
                "days must be between 1 and 365", details={"days": days}
            )
        if limit < 1 or limit > 500:
            raise ValidationError(
                "limit must be between 1 and 500", details={"limit": limit}
            )

        # Resume from the highest captured LastModifiedDate (ENG-381);
        # ``days`` is the first-run fallback.
        watermark = await self._ingest.max_payload_watermark(
            tenant_id,
            event_type=_SF_CASE_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        query = _SF_CASE_SOQL.format(
            projection=await self._projection(tenant_id), since=since, limit=limit
        )
        body = await self._sf.soql(query)
        records: list[dict[str, Any]] = body.get("records", []) or []

        # Capture change-guard: skip rows whose LastModifiedDate is
        # already captured (healthy overlap re-reads).
        candidate_ids = [
            case_id for record in records if (case_id := _record_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_CASE_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            case_id = _record_id(record)
            if case_id is None:
                skipped_count += 1
                continue

            stamp = record.get("LastModifiedDate")
            if isinstance(stamp, str) and captured_stamps.get(case_id) == stamp:
                unchanged_count += 1
                continue

            imported = await self._capture_case(tenant_id, record, case_id)
            if imported:
                imported_count += 1
            else:
                skipped_count += 1

        return SfCaseImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
        )

    async def _capture_case(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        case_id: str,
    ) -> bool:
        """Capture raw event, resolve person, emit timeline event.

        Returns True if the case was fully imported (raw capture +
        timeline event), False if person resolution failed (raw capture
        still happened; the case is counted as skipped for timeline
        purposes).
        """
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_CASE_EVENT_TYPE,
                external_id=case_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        contact_id = _contact_id(record)
        if contact_id is None:
            logger.warning(
                "salesforce.case.skipped: no ContactId on record",
                extra={
                    "case_id": case_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return False

        person_uid = await self._resolve_contact(tenant_id, contact_id)
        if person_uid is None:
            logger.warning(
                "salesforce.case.skipped: ContactId not yet linked",
                extra={
                    "case_id": case_id,
                    "contact_id": contact_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return False

        kind = _case_event_kind(record)
        occurred_at = _case_occurred_at(record, kind)

        await self._create_event_once(
            tenant_id,
            kind=kind,
            person_uid=person_uid,
            case_id=case_id,
            raw_event_id=raw_event.id,
            occurred_at=occurred_at,
            payload=_source_payload(case_id, raw_event.id, record),
        )
        return True

    async def _create_event_once(
        self,
        tenant_id: TenantId,
        *,
        kind: Literal["case_opened", "case_closed"],
        person_uid: UUID,
        case_id: str,
        raw_event_id: UUID,
        occurred_at: datetime,
        payload: dict[str, object],
    ) -> Event:
        """Idempotent timeline event creation for a Case."""
        existing = await self._interaction.find_provider_event_by_external_id(
            tenant_id,
            source_provider="salesforce",
            source_kind="salesforce_case",
            source_external_id=case_id,
            kind=kind,
        )
        if existing is not None:
            return existing

        return await self._interaction.create_event(
            tenant_id,
            EventIn(
                person_uid=person_uid,
                kind=kind,
                source_provider="salesforce",
                source_event_id=raw_event_id,
                data_class="operational",
                source_kind="salesforce_case",
                source_external_id=case_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary_for_event(
                    kind=kind,
                    source_provider="salesforce",
                    source_id=case_id,
                ),
                payload=payload,
            ),
        )

    async def _resolve_contact(
        self, tenant_id: TenantId, contact_id: str
    ) -> UUID | None:
        """Resolve a Salesforce ContactId to a person_uid.

        Follows the same pattern as ``SfTaskIngestService._resolve_who``:
        checks source_link for ``source_kind="lead"`` and
        ``source_kind="contact"`` with the given contact_id.
        """
        for source_kind in ("lead", "contact"):
            link = await self._identity_repo.find_source_link(
                tenant_id,
                source_system="salesforce",
                source_instance="salesforce-main",
                source_kind=source_kind,
                source_id=contact_id,
            )
            if link is not None:
                return link.person_uid
        return None


# ---------------------------------------------------------- helpers


def _record_id(record: dict[str, Any]) -> str | None:
    """Extract the Salesforce record Id, returning None if absent."""
    value = record.get("Id")
    if isinstance(value, str | int) and str(value).strip():
        return str(value).strip()
    return None


def _contact_id(record: dict[str, Any]) -> str | None:
    """Extract the ContactId from a Case record."""
    value = record.get("ContactId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _case_event_kind(
    record: dict[str, Any],
) -> Literal["case_opened", "case_closed"]:
    """Determine event kind based on IsClosed flag."""
    is_closed = record.get("IsClosed")
    if is_closed is True or (isinstance(is_closed, str) and is_closed.lower() == "true"):
        return "case_closed"
    return "case_opened"


def _case_occurred_at(
    record: dict[str, Any],
    kind: Literal["case_opened", "case_closed"],
) -> datetime:
    """Determine the occurred_at timestamp for a Case event.

    For closed cases, prefer ClosedDate. For open cases, prefer CreatedDate.
    """
    if kind == "case_closed":
        closed = _parse_sf_datetime(record.get("ClosedDate"))
        if closed is not None:
            return closed
    created = _parse_sf_datetime(record.get("CreatedDate"))
    if created is not None:
        return created
    modified = _parse_sf_datetime(record.get("LastModifiedDate"))
    if modified is not None:
        return modified
    return datetime.now(UTC)


def _source_payload(
    case_id: str,
    raw_event_id: UUID,
    record: dict[str, Any],
) -> dict[str, object]:
    """Build a no-PII event payload for a Case.

    Subject excluded — may contain clinical context. Only structured
    status/priority/origin fields are safe for timeline payloads.
    """
    payload: dict[str, object] = {
        "source_provider": "salesforce",
        "source_object_id": case_id,
        "raw_event_id": str(raw_event_id),
    }
    status = _stripped(record.get("Status"))
    if status is not None:
        payload["case_status"] = status
    priority = _stripped(record.get("Priority"))
    if priority is not None:
        payload["case_priority"] = priority
    origin = _stripped(record.get("Origin"))
    if origin is not None:
        payload["case_origin"] = origin
    return payload


def _stripped(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_sf_datetime(value: object) -> datetime | None:
    """Parse a Salesforce datetime string into a timezone-aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    if len(candidate) >= 5 and candidate[-5] in {"+", "-"} and candidate[-3] != ":":
        candidate = f"{candidate[:-2]}:{candidate[-2:]}"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_sf_date(value: object) -> datetime | None:
    """Parse a Salesforce date-only string into a midnight UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed_date = date.fromisoformat(value.strip())
    except ValueError:
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=UTC)
