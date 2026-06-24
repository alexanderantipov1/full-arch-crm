"""Salesforce Event ingest pipeline (ENG-220).

Mirrors the CareStack appointment service (ENG-219): pull standard
``Event`` rows via SOQL, capture them verbatim into ``ingest.raw_event``,
resolve the WhoId to a canonical ``person_uid`` via the existing
``identity.source_link``, and upsert a marketing-safe consultation row
in ``ops.consultation``.

PHI safety:
- ``Description`` is a free-text field that operators sometimes use for
  clinical context. It MUST NOT enter ``ops.consultation`` — the
  ``ConsultationIn`` schema has no description column, so the allowlist
  is enforced by construction. Raw payload still goes to
  ``ingest.raw_event`` (PHI carrier; gated).

Identity resolution:
- SF Event.WhoId points to either a Lead or a Contact. We try
  ``source_kind="lead"`` first (most common in marketing flows), fall
  back to ``source_kind="contact"``. If neither resolves, the event is
  counted as skipped — patient/lead pull must run first.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.identity.service import IdentityService
from packages.ingest.call_reference import CallReference, detect_call_references
from packages.ingest.consultation_notify import (
    ConsultationNotifier,
    emit_consultation_scheduled_notification,
)
from packages.ingest.consultation_timeline import emit_consultation_timeline_event
from packages.ingest.schemas import RawEventIn, SchemaDiffOut, SfEventImportOut
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.models import ConsultationKind, ConsultationStatus
from packages.ops.schemas import ConsultationIn
from packages.ops.service import OpsService

logger = logging.getLogger(__name__)


class SfEventClientProtocol(Protocol):
    """Minimum Salesforce client surface used by the Event ingest service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


_SF_EVENT_EVENT_TYPE = "salesforce.event.upsert"
# Static fallback projection (ENG-427); normal pulls use the dynamic projection.
_SF_EVENT_COLUMNS = (
    "Id, CreatedDate, StartDateTime, EndDateTime, WhoId, WhatId, Subject, "
    "Type, ActivityDate, LastModifiedDate, IsAllDayEvent, ShowAs, Description"
)
# Ascending order is load-bearing for the watermark cursor (ENG-381):
# oldest pending changes are captured first so the watermark never
# advances past changes that were cut off by ``limit``.
_SF_EVENT_SOQL = (
    "SELECT {projection} FROM Event "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {limit}"
)

# Backfill SOQL: ASC sort so the cursor walks forward across batches.
_SF_EVENT_SOQL_BACKFILL = (
    "SELECT {projection} FROM Event "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {batch}"
)
_SF_EVENT_BACKFILL_MAX_BATCH = 2000


class SfEventIngestService:
    """Pull SF Events, capture raw, upsert ops.consultation."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfEventClientProtocol,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        self._identity_repo = IdentityRepository(session)
        self._ops = OpsService(session)
        self._interaction = InteractionService(session)

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Event",
            static_projection=_SF_EVENT_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_events(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 100,
        notifier: ConsultationNotifier | None = None,
        principal: Principal | None = None,
    ) -> SfEventImportOut:
        """Capture recent SF Events into ingest + ops.

        ENG-457: when a ``notifier`` (and ``principal``) is supplied, a
        genuinely-new consultation also announces ``consultation.scheduled``
        to the messenger. The backfill path (``import_all_since``) never
        supplies one, so backfill never notifies.
        """
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
            event_type=_SF_EVENT_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        query = _SF_EVENT_SOQL.format(
            projection=await self._projection(tenant_id), since=since, limit=limit
        )

        body = await self._sf.soql(query)
        records: list[dict[str, Any]] = body.get("records", []) or []

        # Capture change-guard: skip rows whose LastModifiedDate is
        # already captured (healthy overlap re-reads).
        candidate_ids = [
            event_id
            for record in records
            if (event_id := _event_source_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_EVENT_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            event_id = _event_source_id(record)
            who_id = _event_who_id(record)
            if event_id is None or who_id is None:
                skipped_count += 1
                continue
            stamp = record.get("LastModifiedDate")
            if isinstance(stamp, str) and captured_stamps.get(event_id) == stamp:
                unchanged_count += 1
                continue
            outcome = await self._capture_event(
                tenant_id,
                record,
                event_id,
                who_id,
                notifier=notifier,
                principal=principal,
            )
            if outcome == "imported":
                imported_count += 1
            else:
                skipped_count += 1

        return SfEventImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
        )

    async def import_all_since(
        self,
        tenant_id: TenantId,
        since: datetime,
        *,
        batch_size: int = 500,
    ) -> SfEventImportOut:
        """Full backfill of SF Events modified on or after ``since``.

        Cursor-by-LastModifiedDate ascending. Returns aggregate counts
        across all pages. WhoIds that have not been linked yet (lead /
        contact ingest hasn't run) are counted as skipped; rerunning
        backfill after the matching lead/patient pull resolves them.
        """
        if batch_size < 1 or batch_size > _SF_EVENT_BACKFILL_MAX_BATCH:
            raise ValidationError(
                f"batch_size must be between 1 and {_SF_EVENT_BACKFILL_MAX_BATCH}",
                details={"batch_size": batch_size},
            )
        cursor = since if since.tzinfo is not None else since.replace(tzinfo=UTC)
        imported_total = 0
        skipped_total = 0
        queried_total = 0
        projection = await self._projection(tenant_id)
        while True:
            cursor_str = cursor.strftime("%Y-%m-%dT%H:%M:%SZ")
            query = _SF_EVENT_SOQL_BACKFILL.format(
                projection=projection, since=cursor_str, batch=batch_size
            )
            body = await self._sf.soql(query)
            records: list[dict[str, Any]] = body.get("records", []) or []
            queried_total += len(records)
            if not records:
                break
            last_modified: datetime | None = None
            for record in records:
                event_id = _event_source_id(record)
                who_id = _event_who_id(record)
                if event_id is None or who_id is None:
                    skipped_total += 1
                else:
                    outcome = await self._capture_event(
                        tenant_id, record, event_id, who_id
                    )
                    if outcome == "imported":
                        imported_total += 1
                    else:
                        skipped_total += 1
                parsed = _parse_sf_datetime(record.get("LastModifiedDate"))
                if parsed is not None and (
                    last_modified is None or parsed > last_modified
                ):
                    last_modified = parsed
            if len(records) < batch_size:
                break
            cursor = (
                (last_modified + timedelta(milliseconds=1))
                if last_modified is not None
                else cursor + timedelta(milliseconds=1)
            )
        return SfEventImportOut(
            imported_count=imported_total,
            skipped_count=skipped_total,
            queried_count=queried_total,
        )

    async def _capture_event(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        event_id: str,
        who_id: str,
        *,
        notifier: ConsultationNotifier | None = None,
        principal: Principal | None = None,
    ) -> str:
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type="salesforce.event.upsert",
                external_id=event_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        person_uid = await self._resolve_who(tenant_id, who_id)
        if person_uid is None:
            logger.warning(
                "salesforce.event.skipped: WhoId not yet linked",
                extra={
                    "event_id": event_id,
                    "who_id": who_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return "skipped"

        scheduled_at = _event_scheduled_at(record)
        if scheduled_at is None:
            logger.warning(
                "salesforce.event.skipped: no StartDateTime",
                extra={"event_id": event_id},
            )
            return "skipped"

        upsert = await self._ops.upsert_consultation_from_hint(
            tenant_id,
            ConsultationIn(
                person_uid=person_uid,
                source_provider="salesforce",
                source_instance="salesforce-main",
                external_id=event_id,
                scheduled_at=scheduled_at,
                provider_created_at=_parse_sf_datetime(record.get("CreatedDate")),
                duration_minutes=_event_duration(record),
                status=_map_status(record),
                consultation_kind=_map_kind(record),
                location_id=None,
                provider_clinician_name=None,
                raw_event_id=raw_event.id,
            ),
        )
        await emit_consultation_timeline_event(
            self._interaction,
            tenant_id,
            upsert,
            source_provider="salesforce",
            source_kind="salesforce_event",
            source_external_id=event_id,
            source_event_id=raw_event.id,
        )
        # ENG-457: announce a genuinely-new consultation to #scheduls. No-op
        # unless a notifier+principal were threaded in (recent pull only, never
        # backfill) and the upsert actually created the row.
        if notifier is not None and principal is not None:
            # ENG-460: resolve the real patient name at the boundary so the
            # #scheduls card is useful to staff (authorized PHI surface). A
            # missing person never blocks the notify.
            person_name: str | None = None
            try:
                person = await self._identity.get_person(tenant_id, person_uid)
                person_name = (
                    person.display_name
                    or person.given_name
                    or person.family_name
                )
            except NotFoundError:
                logger.info(
                    "sf.event.notify.person_unresolved",
                    extra={"person_uid": str(person_uid)},
                )
            await emit_consultation_scheduled_notification(
                notifier,
                tenant_id,
                upsert,
                source_provider="salesforce",
                principal=principal,
                person_name=person_name,
            )
        await self._emit_call_reference_events(
            tenant_id,
            record,
            event_id,
            person_uid,
            raw_event.id,
            scheduled_at,
        )
        return "imported"

    async def _resolve_who(self, tenant_id: TenantId, who_id: str) -> Any:
        for source_kind in ("lead", "contact"):
            link = await self._identity_repo.find_source_link(
                tenant_id,
                source_system="salesforce",
                source_instance="salesforce-main",
                source_kind=source_kind,
                source_id=who_id,
            )
            if link is not None:
                return link.person_uid
        return None

    async def _emit_call_reference_events(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        event_id: str,
        person_uid: UUID,
        raw_event_id: UUID,
        occurred_at: datetime,
    ) -> None:
        references = detect_call_references(_event_description(record))
        if not references:
            return

        existing_events = await self._interaction.list_provider_events_by_external_id(
            tenant_id,
            source_provider="salesforce",
            source_kind="salesforce_event",
            source_external_id=event_id,
            kind="call_reference_found",
        )
        existing_keys = {
            _call_reference_dedupe_key_from_payload(event.payload)
            for event in existing_events
        }

        for reference in references:
            dedupe_key = _call_reference_dedupe_key(reference)
            if dedupe_key in existing_keys:
                continue
            await self._interaction.create_event(
                tenant_id,
                EventIn(
                    person_uid=person_uid,
                    kind="call_reference_found",
                    source_provider="salesforce",
                    source_event_id=None,
                    data_class="call_recording_ref",
                    source_kind="salesforce_event",
                    source_external_id=event_id,
                    projection_ref_type=None,
                    projection_ref_id=None,
                    review_status="pending_review",
                    occurred_at=occurred_at,
                    summary=summary_for_event(
                        kind="call_reference_found",
                        source_provider="salesforce",
                        source_id=event_id,
                    ),
                    payload=_call_reference_payload(event_id, raw_event_id, reference),
                ),
            )
            existing_keys.add(dedupe_key)


# ---------------------------------------------------------- payload helpers


def _event_source_id(record: dict[str, Any]) -> str | None:
    value = record.get("Id")
    if isinstance(value, str | int) and str(value).strip():
        return str(value)
    return None


def _event_who_id(record: dict[str, Any]) -> str | None:
    value = record.get("WhoId")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _event_description(record: dict[str, Any]) -> str | None:
    value = record.get("Description")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _event_scheduled_at(record: dict[str, Any]) -> datetime | None:
    parsed = _parse_sf_datetime(record.get("StartDateTime"))
    if parsed is not None:
        return parsed
    activity_date = record.get("ActivityDate")
    if isinstance(activity_date, str) and activity_date.strip():
        return _parse_sf_datetime(f"{activity_date.strip()}T00:00:00Z")
    return None


def _event_duration(record: dict[str, Any]) -> int | None:
    start = _parse_sf_datetime(record.get("StartDateTime"))
    end = _parse_sf_datetime(record.get("EndDateTime"))
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds() / 60.0
    if delta <= 0:
        return None
    return int(delta)


def _call_reference_payload(
    event_id: str,
    raw_event_id: UUID,
    reference: CallReference,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_provider": "salesforce",
        "source_object_id": event_id,
        "raw_event_id": str(raw_event_id),
        "data_class": "call_recording_ref",
        "review_status": "pending_review",
        "provider": reference.provider,
        "kind": reference.kind,
    }
    if reference.url is not None:
        payload["url"] = reference.url
    if reference.external_id is not None:
        payload["external_id"] = reference.external_id
    return payload


def _call_reference_dedupe_key(reference: CallReference) -> tuple[str, str]:
    if reference.url is not None:
        return ("url", reference.url)
    if reference.external_id is not None:
        return ("external_id", reference.external_id)
    return ("provider_kind", f"{reference.provider}:{reference.kind}")


def _call_reference_dedupe_key_from_payload(payload: dict[str, object]) -> tuple[str, str]:
    url = payload.get("url")
    if isinstance(url, str) and url:
        return ("url", url)
    external_id = payload.get("external_id")
    if isinstance(external_id, str) and external_id:
        return ("external_id", external_id)
    provider = payload.get("provider")
    kind = payload.get("kind")
    return ("provider_kind", f"{provider}:{kind}")


def _map_status(record: dict[str, Any]) -> ConsultationStatus:
    """Best-effort temporal inference: standard SF Event has no Status field.

    - EndDateTime in the past → COMPLETED
    - StartDateTime in the past with no EndDateTime → COMPLETED (assume occurred)
    - Otherwise → SCHEDULED
    """
    now = datetime.now(UTC)
    end = _parse_sf_datetime(record.get("EndDateTime"))
    if end is not None and end < now:
        return ConsultationStatus.COMPLETED
    start = _parse_sf_datetime(record.get("StartDateTime"))
    if start is not None and start < now and end is None:
        return ConsultationStatus.COMPLETED
    return ConsultationStatus.SCHEDULED


def _map_kind(record: dict[str, Any]) -> ConsultationKind:
    raw = record.get("Type")
    if not isinstance(raw, str):
        return ConsultationKind.OTHER
    lower = raw.lower()
    if "initial" in lower or "consult" in lower or "intake" in lower:
        return ConsultationKind.INITIAL
    if "follow" in lower:
        return ConsultationKind.FOLLOW_UP
    if "treatment" in lower or "procedure" in lower:
        return ConsultationKind.TREATMENT
    return ConsultationKind.OTHER


def _parse_sf_datetime(value: object) -> datetime | None:
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
