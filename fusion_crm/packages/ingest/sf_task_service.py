"""Salesforce Task ingest pipeline (ENG-240).

Pulls standard ``Task`` rows via SOQL, captures each row verbatim into
``ingest.raw_event``, resolves ``WhoId`` to a canonical ``person_uid`` via
``identity.source_link``, then emits workflow-ready interaction events and
optional ``ops.followup_task`` projections.

PHI safety:
- ``Description`` is captured only in ``ingest.raw_event``.
- ``Subject`` is used only for deterministic call-like classification. It is
  not copied into summaries, event payloads, or follow-up task text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.call_reference import CallReference, detect_call_references
from packages.ingest.responsibility_resolver import (
    FunnelResponsibilityResolver,
    ProviderOwnerHint,
)
from packages.ingest.schemas import RawEventIn, SchemaDiffOut, SfTaskImportOut
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.models import Event
from packages.interaction.schemas import EventIn, ResponsibilityAssignmentIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.schemas import FollowupTaskIn
from packages.ops.service import OpsService

logger = logging.getLogger(__name__)


class SfTaskClientProtocol(Protocol):
    """Minimum Salesforce client surface used by the Task ingest service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


# Static fallback projection (ENG-427); normal pulls use the dynamic projection.
_SF_TASK_COLUMNS = (
    "Id, Subject, Status, Priority, ActivityDate, CreatedDate, "
    "LastModifiedDate, WhoId, WhatId, OwnerId, Type, CallType, "
    "CallDurationInSeconds, CallObject, CallDisposition, Description"
)
_SF_TASK_EVENT_TYPE = "salesforce.task.upsert"
# Ascending order is load-bearing for the watermark cursor (ENG-381):
# oldest pending changes are captured first so the watermark never
# advances past changes that were cut off by ``limit``.
_SF_TASK_SOQL = (
    "SELECT {projection} FROM Task "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {limit}"
)
_SF_TASK_SOQL_BACKFILL = (
    "SELECT {projection} FROM Task "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {batch}"
)
_SF_TASK_BACKFILL_MAX_BATCH = 2000

_OPEN_STATUSES = frozenset(
    {
        "open",
        "not started",
        "in progress",
        "waiting",
        "deferred",
        "new",
        "pending",
    }
)
_CALL_SUBJECT_PREFIXES = (
    "call",
    "voicemail",
    "inbound call",
    "outbound call",
    "sofia ai call",
)
_CALL_RECORDING_LINE_RE = re.compile(
    r"(?im)^\s*Call Recording:\s*(https?://\S+)\s*$"
)
_DESCRIPTION_FIELD_RE = re.compile(r"(?im)^\s*(Agent|Outcome|Duration):\s*(.+?)\s*$")

TaskLane = Literal["action", "historical", "call"]


@dataclass(frozen=True)
class TaskClassification:
    """Deterministic lane assignment for a Salesforce Task row."""

    lane: TaskLane | None
    direction: str | None = None


class SfTaskIngestService:
    """Pull SF Tasks, capture raw, emit events and follow-up projections."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfTaskClientProtocol,
        responsibility_resolver: FunnelResponsibilityResolver | None = None,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._ops = OpsService(session)
        self._interaction = InteractionService(session)
        # ENG-416: optional resolver. Call/task events are pre-consult,
        # so the operational owner is normally Lead.OwnerId — BUT for
        # call events the SF ``Task.OwnerId`` is the per-touch
        # attribution surface (Sofia AI vs human agent) and overrides
        # the staged Lead owner for that single event.
        self._responsibility = responsibility_resolver

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Task",
            static_projection=_SF_TASK_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_tasks(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 100,
    ) -> SfTaskImportOut:
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
            event_type=_SF_TASK_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        query = build_recent_tasks_soql(
            projection=await self._projection(tenant_id), since=since, limit=limit
        )
        body = await self._sf.soql(query)
        records: list[dict[str, Any]] = body.get("records", []) or []
        return await self._import_records(tenant_id, records)

    async def reproject_tasks_from_raw(
        self,
        tenant_id: TenantId,
        *,
        since: datetime,
    ) -> SfTaskImportOut:
        """Re-project already-captured SF Tasks into interaction events (ENG-462).

        Closes the import-before-link race: a task first seen before its
        ``WhoId`` lead/contact was linked is skipped and stranded — the
        ``_import_records`` LastModifiedDate change-guard then blocks any
        retry once the link appears. This reads the latest raw payload per
        task since ``since`` (no Salesforce round-trip) and re-runs the
        emit path. Idempotent: already-projected tasks dedup to no-ops via
        ``InteractionService.create_event``; only now-linkable orphans
        actually add events.

        ``imported_count`` counts tasks with a resolved person (emitted or
        already-present); ``skipped_count`` counts still-unlinked or
        unsupported rows. Verify net new events against the DB, not this
        counter.
        """
        rows = await self._ingest.list_latest_by_type_since(
            tenant_id, event_type=_SF_TASK_EVENT_TYPE, since=since
        )
        imported = 0
        skipped = 0
        for raw_event_id, record in rows:
            task_id = _task_source_id(record)
            who_id = _task_who_id(record)
            if task_id is None or who_id is None:
                skipped += 1
                continue
            emitted = await self._emit_task_events(
                tenant_id,
                record=record,
                task_id=task_id,
                who_id=who_id,
                raw_event_id=raw_event_id,
            )
            if emitted:
                imported += 1
            else:
                skipped += 1
        return SfTaskImportOut(
            imported_count=imported,
            unchanged_count=0,
            skipped_count=skipped,
            queried_count=len(rows),
        )

    async def import_all_since(
        self,
        tenant_id: TenantId,
        since: datetime,
        *,
        batch_size: int = 500,
    ) -> SfTaskImportOut:
        """Full backfill of SF Tasks modified on or after ``since``."""
        if batch_size < 1 or batch_size > _SF_TASK_BACKFILL_MAX_BATCH:
            raise ValidationError(
                f"batch_size must be between 1 and {_SF_TASK_BACKFILL_MAX_BATCH}",
                details={"batch_size": batch_size},
            )

        cursor = since if since.tzinfo is not None else since.replace(tzinfo=UTC)
        imported_total = 0
        unchanged_total = 0
        skipped_total = 0
        queried_total = 0
        projection = await self._projection(tenant_id)
        while True:
            cursor_str = cursor.strftime("%Y-%m-%dT%H:%M:%SZ")
            query = _SF_TASK_SOQL_BACKFILL.format(
                projection=projection, since=cursor_str, batch=batch_size
            )
            body = await self._sf.soql(query)
            records: list[dict[str, Any]] = body.get("records", []) or []
            queried_total += len(records)
            if not records:
                break

            result = await self._import_records(tenant_id, records)
            imported_total += result.imported_count
            unchanged_total += result.unchanged_count
            skipped_total += result.skipped_count

            last_modified: datetime | None = None
            for record in records:
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

        return SfTaskImportOut(
            imported_count=imported_total,
            unchanged_count=unchanged_total,
            skipped_count=skipped_total,
            queried_count=queried_total,
        )

    async def _import_records(
        self,
        tenant_id: TenantId,
        records: list[dict[str, Any]],
    ) -> SfTaskImportOut:
        # Capture change-guard (ENG-381): rows whose LastModifiedDate is
        # already captured are healthy overlap re-reads — skip them
        # before any raw write or downstream processing.
        candidate_ids = [
            task_id
            for record in records
            if (task_id := _task_source_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_TASK_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            task_id = _task_source_id(record)
            who_id = _task_who_id(record)
            if task_id is None or who_id is None:
                skipped_count += 1
                continue

            stamp = record.get("LastModifiedDate")
            if isinstance(stamp, str) and captured_stamps.get(task_id) == stamp:
                unchanged_count += 1
                continue

            imported = await self._capture_task(tenant_id, record, task_id, who_id)
            if imported:
                imported_count += 1
            else:
                skipped_count += 1

        return SfTaskImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
        )

    async def _capture_task(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        task_id: str,
        who_id: str,
    ) -> bool:
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_TASK_EVENT_TYPE,
                external_id=task_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )
        return await self._emit_task_events(
            tenant_id,
            record=record,
            task_id=task_id,
            who_id=who_id,
            raw_event_id=raw_event.id,
        )

    async def _emit_task_events(
        self,
        tenant_id: TenantId,
        *,
        record: dict[str, Any],
        task_id: str,
        who_id: str,
        raw_event_id: UUID,
    ) -> bool:
        """Project one SF Task into interaction events + follow-ups.

        Split out of :meth:`_capture_task` (ENG-462) so reconciliation can
        re-run the projection from an already-captured ``raw_event`` —
        bypassing the ``_import_records`` LastModifiedDate change-guard that
        otherwise permanently strands tasks first seen before their
        ``WhoId`` was linked. Idempotent: all emits go through
        ``InteractionService.create_event`` (partial-UNIQUE dedup), so a
        task already projected is a no-op.
        """
        person_uid = await self._resolve_who(tenant_id, who_id)
        if person_uid is None:
            logger.warning(
                "salesforce.task.skipped: WhoId not yet linked",
                extra={
                    "task_id": task_id,
                    "who_id": who_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return False

        classification = classify_task(record)
        if classification.lane is None:
            logger.info(
                "salesforce.task.skipped: unsupported status",
                extra={
                    "task_id": task_id,
                    "status": record.get("Status"),
                    "tenant_id": str(tenant_id),
                },
            )
            return False

        owner_id = _task_owner_id(record)
        if classification.lane == "action":
            await self._handle_action_task(
                tenant_id, record, task_id, person_uid, raw_event_id, owner_id
            )
        elif classification.lane == "historical":
            await self._create_event_once(
                tenant_id,
                kind="task_completed",
                person_uid=person_uid,
                task_id=task_id,
                raw_event_id=raw_event_id,
                occurred_at=_task_occurred_at(record),
                data_class="operational",
                review_status="auto",
                payload=_source_payload(task_id, raw_event_id),
                responsibilities=await self._resolve_responsibilities(
                    tenant_id,
                    event_kind="task_completed",
                    person_uid=person_uid,
                    occurred_at=_task_occurred_at(record),
                    explicit_owner_id=owner_id,
                ),
            )
        else:
            await self._handle_call_task(
                tenant_id,
                record,
                task_id,
                person_uid,
                raw_event_id,
                classification,
                owner_id,
            )
        return True

    async def _handle_action_task(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        task_id: str,
        person_uid: UUID,
        raw_event_id: UUID,
        owner_id: str | None,
    ) -> None:
        existing = await self._find_existing_task_event(
            tenant_id, task_id, "task_created"
        )
        if existing is not None:
            return

        followup = await self._ops.create_followup(
            tenant_id,
            FollowupTaskIn(
                person_uid=person_uid,
                title="Salesforce follow-up task",
                description=None,
                due_at=_task_due_at(record),
                assigned_to=None,
            ),
        )
        await self._create_event_once(
            tenant_id,
            kind="task_created",
            person_uid=person_uid,
            task_id=task_id,
            raw_event_id=raw_event_id,
            occurred_at=_task_created_at(record),
            data_class="operational",
            review_status="auto",
            projection_ref_type="ops_followup_task",
            projection_ref_id=followup.id,
            payload={
                **_source_payload(task_id, raw_event_id),
                "projection_ref_type": "ops_followup_task",
                "projection_ref_id": str(followup.id),
            },
            responsibilities=await self._resolve_responsibilities(
                tenant_id,
                event_kind="task_created",
                person_uid=person_uid,
                occurred_at=_task_created_at(record),
                explicit_owner_id=owner_id,
            ),
        )

    async def _handle_call_task(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        task_id: str,
        person_uid: UUID,
        raw_event_id: UUID,
        classification: TaskClassification,
        owner_id: str | None,
    ) -> None:
        occurred_at = _task_occurred_at(record)
        # Call events use the Task's OWN OwnerId as the operational
        # attribution — preserves the Sofia AI vs human-agent split that
        # downstream agent-performance metrics depend on.
        call_responsibilities = await self._resolve_responsibilities(
            tenant_id,
            event_kind="call_logged",
            person_uid=person_uid,
            occurred_at=occurred_at,
            explicit_owner_id=owner_id,
        )
        await self._create_event_once(
            tenant_id,
            kind="call_logged",
            person_uid=person_uid,
            task_id=task_id,
            raw_event_id=raw_event_id,
            occurred_at=occurred_at,
            data_class="operational",
            review_status="auto",
            payload=_call_logged_payload(record, task_id, raw_event_id, classification),
            responsibilities=call_responsibilities,
        )

        references = _extract_call_references(record)
        if not references:
            return
        reference = references[0]
        await self._create_event_once(
            tenant_id,
            kind="call_reference_found",
            person_uid=person_uid,
            task_id=task_id,
            raw_event_id=raw_event_id,
            occurred_at=occurred_at,
            data_class="call_recording_ref",
            review_status="pending_review",
            attach_raw_event=False,
            payload=_call_reference_payload(task_id, raw_event_id, reference),
            # Same owner as the call_logged sibling — they describe the
            # same touch from two angles.
            responsibilities=call_responsibilities,
        )

    async def _create_event_once(
        self,
        tenant_id: TenantId,
        *,
        kind: Literal[
            "task_created",
            "task_completed",
            "call_logged",
            "call_reference_found",
        ],
        person_uid: UUID,
        task_id: str,
        raw_event_id: UUID,
        occurred_at: datetime,
        data_class: Literal["operational", "call_recording_ref"],
        review_status: Literal["auto", "pending_review"],
        payload: dict[str, object],
        projection_ref_type: Literal["ops_followup_task"] | None = None,
        projection_ref_id: UUID | None = None,
        attach_raw_event: bool = True,
        responsibilities: list[ResponsibilityAssignmentIn] | None = None,
    ) -> Event:
        existing = await self._find_existing_task_event(tenant_id, task_id, kind)
        if existing is not None:
            return existing

        return await self._interaction.create_event(
            tenant_id,
            EventIn(
                person_uid=person_uid,
                kind=kind,
                source_provider="salesforce",
                source_event_id=raw_event_id if attach_raw_event else None,
                data_class=data_class,
                source_kind="salesforce_task",
                source_external_id=task_id,
                projection_ref_type=projection_ref_type,
                projection_ref_id=projection_ref_id,
                review_status=review_status,
                occurred_at=occurred_at,
                summary=summary_for_event(
                    kind=kind,
                    source_provider="salesforce",
                    source_id=task_id,
                ),
                payload=payload,
                responsibilities=responsibilities or [],
            ),
        )

    async def _resolve_responsibilities(
        self,
        tenant_id: TenantId,
        *,
        event_kind: str,
        person_uid: UUID,
        occurred_at: datetime,
        explicit_owner_id: str | None,
    ) -> list[ResponsibilityAssignmentIn]:
        if self._responsibility is None:
            return []
        explicit = (
            ProviderOwnerHint(
                source_provider="salesforce",
                source_instance="salesforce-main",
                external_id=explicit_owner_id,
            )
            if explicit_owner_id is not None
            else None
        )
        resolved = await self._responsibility.resolve(
            tenant_id,
            event_kind=event_kind,
            person_uid=person_uid,
            occurred_at=occurred_at,
            explicit_owner=explicit,
        )
        return resolved.assignments

    async def _find_existing_task_event(
        self,
        tenant_id: TenantId,
        task_id: str,
        kind: str,
    ) -> Event | None:
        return await self._interaction.find_provider_event_by_external_id(
            tenant_id,
            source_provider="salesforce",
            source_kind="salesforce_task",
            source_external_id=task_id,
            kind=kind,
        )

    async def _resolve_who(self, tenant_id: TenantId, who_id: str) -> UUID | None:
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


# ---------------------------------------------------------- payload helpers


def build_recent_tasks_soql(
    *, since: datetime, limit: int, projection: str = _SF_TASK_COLUMNS
) -> str:
    """Build the bounded recent Task query used by tests and the service.

    ``projection`` defaults to the static fallback so existing callers/tests
    keep working; the service passes the dynamic full-fidelity projection
    (ENG-427).
    """
    since_value = since if since.tzinfo is not None else since.replace(tzinfo=UTC)
    return _SF_TASK_SOQL.format(
        projection=projection,
        since=since_value.strftime("%Y-%m-%dT%H:%M:%SZ"),
        limit=limit,
    )


def classify_task(record: dict[str, Any]) -> TaskClassification:
    """Assign a Salesforce Task to exactly one workflow lane."""
    call_type = _stripped(record.get("CallType"))
    subject = _stripped(record.get("Subject"))
    if call_type is not None or _is_call_subject(subject):
        return TaskClassification(lane="call", direction=_call_direction(call_type, subject))

    status = (_stripped(record.get("Status")) or "").lower()
    if status in _OPEN_STATUSES:
        return TaskClassification(lane="action")
    if status == "completed":
        return TaskClassification(lane="historical")
    return TaskClassification(lane=None)


def _task_source_id(record: dict[str, Any]) -> str | None:
    value = record.get("Id")
    if isinstance(value, str | int) and str(value).strip():
        return str(value).strip()
    return None


def _task_who_id(record: dict[str, Any]) -> str | None:
    value = record.get("WhoId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _task_owner_id(record: dict[str, Any]) -> str | None:
    """Extract the SF Task.OwnerId for per-touch responsibility attribution.

    SF Task.OwnerId carries the user who recorded the activity — for
    call-classified tasks this distinguishes Sofia AI from a human
    agent. Returns ``None`` when SF did not supply an owner id, in
    which case the resolver falls back to the staged Lead.OwnerId.
    """
    value = record.get("OwnerId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _task_created_at(record: dict[str, Any]) -> datetime:
    return (
        _parse_sf_datetime(record.get("CreatedDate"))
        or _parse_sf_datetime(record.get("LastModifiedDate"))
        or datetime.now(UTC)
    )


def _task_occurred_at(record: dict[str, Any]) -> datetime:
    return (
        _parse_sf_datetime(record.get("LastModifiedDate"))
        or _parse_sf_date(record.get("ActivityDate"))
        or _parse_sf_datetime(record.get("CreatedDate"))
        or datetime.now(UTC)
    )


def _task_due_at(record: dict[str, Any]) -> datetime | None:
    return _parse_sf_date(record.get("ActivityDate"))


def _parse_sf_datetime(value: object) -> datetime | None:
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
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed_date = date.fromisoformat(value.strip())
    except ValueError:
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=UTC)


def _stripped(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _is_call_subject(subject: str | None) -> bool:
    if subject is None:
        return False
    lower = subject.lower()
    return any(lower.startswith(prefix) for prefix in _CALL_SUBJECT_PREFIXES)


def _call_direction(call_type: str | None, subject: str | None) -> str | None:
    candidates = [value.lower() for value in (call_type, subject) if value]
    for value in candidates:
        if "inbound" in value:
            return "inbound"
        if "outbound" in value:
            return "outbound"
    return None


def _call_duration(record: dict[str, Any]) -> int | None:
    value = record.get("CallDurationInSeconds")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    parsed = _description_metadata(record).get("duration_seconds")
    if isinstance(parsed, int):
        return parsed
    return None


def _source_payload(task_id: str, raw_event_id: UUID) -> dict[str, object]:
    return {
        "source_provider": "salesforce",
        "source_object_id": task_id,
        "raw_event_id": str(raw_event_id),
    }


def _call_logged_payload(
    record: dict[str, Any],
    task_id: str,
    raw_event_id: UUID,
    classification: TaskClassification,
) -> dict[str, object]:
    payload = _source_payload(task_id, raw_event_id)
    duration = _call_duration(record)
    disposition = _stripped(record.get("CallDisposition"))
    metadata = _description_metadata(record)
    if duration is not None:
        payload["call_duration_seconds"] = duration
    if disposition is not None:
        payload["call_disposition"] = disposition
    if classification.direction is not None:
        payload["direction"] = classification.direction
    for source_key, payload_key in (
        ("agent", "agent"),
        ("outcome", "call_outcome"),
        ("duration_label", "duration_label"),
    ):
        value = metadata.get(source_key)
        if isinstance(value, str):
            payload[payload_key] = value
    return payload


def _call_reference_payload(
    task_id: str,
    raw_event_id: UUID,
    reference: CallReference,
) -> dict[str, object]:
    payload = {
        **_source_payload(task_id, raw_event_id),
        "data_class": "call_recording_ref",
        "review_status": "pending_review",
        "provider": reference.provider,
        "kind": reference.kind,
    }
    if reference.url is not None:
        payload["url"] = reference.url
        payload["reference_url"] = reference.url
    if reference.external_id is not None:
        payload["external_id"] = reference.external_id
        payload["provider_id"] = reference.external_id
    return payload


def _extract_call_references(record: dict[str, Any]) -> list[CallReference]:
    call_object = _stripped(record.get("CallObject"))
    references: list[CallReference] = []
    if call_object is not None:
        references.extend(
            detect_call_references(None, allowlisted_keys={"CallObject": call_object})
        )
    description_url = _call_recording_url_from_description(record.get("Description"))
    if description_url is not None:
        references.extend(
            detect_call_references(
                None,
                allowlisted_keys={"CallRecording": description_url},
            )
        )
    return references


def _call_recording_url_from_description(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = _CALL_RECORDING_LINE_RE.search(value)
    if match is None:
        return None
    return match.group(1).rstrip(".,")


def _description_metadata(record: dict[str, Any]) -> dict[str, object]:
    description = record.get("Description")
    if not isinstance(description, str) or not description.strip():
        return {}
    out: dict[str, object] = {}
    for match in _DESCRIPTION_FIELD_RE.finditer(description):
        key = match.group(1).lower()
        value = match.group(2).strip()
        if not value:
            continue
        if key == "agent":
            out["agent"] = value
        elif key == "outcome":
            out["outcome"] = value
        elif key == "duration":
            out["duration_label"] = value
            seconds = _duration_label_seconds(value)
            if seconds is not None:
                out["duration_seconds"] = seconds
    return out


def _duration_label_seconds(value: str) -> int | None:
    match = re.fullmatch(r"(?i)\s*(\d+)\s*(sec|secs|second|seconds|min|mins|minute|minutes)\s*", value)
    if match is None:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("min"):
        return amount * 60
    return amount
