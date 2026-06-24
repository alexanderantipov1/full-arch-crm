"""Salesforce OpportunityHistory ingest service (ENG-382).

OpportunityHistory rows are the pipeline-movement segments of the SF
funnel: Salesforce appends one row per stage/forecast change on an
Opportunity. Capturing them gives the agent layer the journey
("New → Consult Scheduled → Surgery Completed"), not just the current
stage snapshot the Opportunity pull stores.

History rows are immutable — there is no LastModifiedDate; the
watermark cursor runs on ``CreatedDate`` and the capture change-guard
makes every re-read of a captured row a no-op by definition.

Each captured row emits one ``opportunity_stage_changed`` timeline
event when the opportunity resolves to a person (converted-lead glue
first, account source link as fallback). Summaries are no-PII; the
event payload carries the stage name + opportunity id only — no
amounts (same rule as opportunity summaries).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.identity.repository import IdentityRepository
from packages.ingest.schemas import (
    RawEventIn,
    SchemaDiffOut,
    SfOpportunityHistoryImportOut,
)
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.service import OpsService

logger = logging.getLogger(__name__)


class SfOpportunityHistoryClientProtocol(Protocol):
    """Minimum Salesforce client surface used by this service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


_SF_OPPORTUNITY_HISTORY_EVENT_TYPE = "salesforce.opportunity_history.upsert"
# Static fallback projection (ENG-427); normal pulls use the dynamic projection.
_SF_OPPORTUNITY_HISTORY_COLUMNS = (
    "Id, OpportunityId, StageName, Amount, CloseDate, Probability, "
    "CreatedDate, CreatedById"
)
# Ascending order is load-bearing for the watermark cursor (ENG-381).
_SF_OPPORTUNITY_HISTORY_SOQL = (
    "SELECT {projection} FROM OpportunityHistory "
    "WHERE CreatedDate >= {since} "
    "ORDER BY CreatedDate ASC "
    "LIMIT {limit}"
)


class SfOpportunityHistoryIngestService:
    """Pull stage history, capture raw, emit stage-change timeline events."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfOpportunityHistoryClientProtocol,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._interaction = InteractionService(session)
        self._ops = OpsService(session)

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="OpportunityHistory",
            static_projection=_SF_OPPORTUNITY_HISTORY_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_history(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 200,
    ) -> SfOpportunityHistoryImportOut:
        """Pull history rows created since the watermark (``days`` fallback)."""
        if days < 1 or days > 365:
            raise ValidationError(
                "days must be between 1 and 365", details={"days": days}
            )
        if limit < 1 or limit > 500:
            raise ValidationError(
                "limit must be between 1 and 500", details={"limit": limit}
            )

        watermark = await self._ingest.max_payload_watermark(
            tenant_id,
            event_type=_SF_OPPORTUNITY_HISTORY_EVENT_TYPE,
            watermark_key="CreatedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        body = await self._sf.soql(
            _SF_OPPORTUNITY_HISTORY_SOQL.format(
                projection=await self._projection(tenant_id),
                since=since,
                limit=limit,
            )
        )
        records: list[dict[str, Any]] = body.get("records", []) or []

        candidate_ids = [
            row_id
            for record in records
            if (row_id := _record_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_OPPORTUNITY_HISTORY_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="CreatedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            row_id = _record_id(record)
            opportunity_id = _string_field(record, "OpportunityId")
            if row_id is None or opportunity_id is None:
                skipped_count += 1
                continue
            stamp = record.get("CreatedDate")
            if isinstance(stamp, str) and captured_stamps.get(row_id) == stamp:
                unchanged_count += 1
                continue
            await self._capture_history_row(
                tenant_id, record, row_id, opportunity_id
            )
            imported_count += 1

        return SfOpportunityHistoryImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
        )

    async def _capture_history_row(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        row_id: str,
        opportunity_id: str,
    ) -> None:
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_OPPORTUNITY_HISTORY_EVENT_TYPE,
                external_id=row_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        person_uid = await self._resolve_person(tenant_id, opportunity_id)
        if person_uid is None:
            logger.info(
                "salesforce.opportunity_history.no_person_link",
                extra={
                    "history_id": row_id,
                    "opp_id": opportunity_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return

        stage = _string_field(record, "StageName") or "unknown"
        occurred_at = _parse_sf_iso(record.get("CreatedDate")) or datetime.now(UTC)
        await self._interaction.create_event_idempotent(
            tenant_id,
            EventIn(
                person_uid=person_uid,
                kind="opportunity_stage_changed",
                source_provider="salesforce",
                source_event_id=raw_event.id,
                data_class="operational",
                source_kind="salesforce_opportunity_history",
                source_external_id=row_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary_for_event(
                    kind="opportunity_stage_changed",
                    source_provider="salesforce",
                    source_id=opportunity_id,
                ),
                # Structured no-PII payload: stage + ids only, no amounts.
                payload={
                    "sf_opportunity_id": opportunity_id,
                    "stage": stage,
                },
            ),
        )

    async def _resolve_person(
        self, tenant_id: TenantId, opportunity_id: str
    ) -> UUID | None:
        """Converted-lead glue first, account source link as fallback.

        History rows carry no AccountId, so the fallback reads it from
        the latest captured payload of the opportunity itself.
        """
        person_uid = await self._ops.find_lead_person_by_converted_opportunity(
            tenant_id, opportunity_id
        )
        if person_uid is not None:
            return person_uid

        opportunity = await self._ingest.latest_payload(
            tenant_id,
            event_type="salesforce.opportunity.upsert",
            external_id=opportunity_id,
        )
        account_id = (
            opportunity.get("AccountId") if opportunity is not None else None
        )
        if not isinstance(account_id, str) or not account_id:
            return None
        link = await self._identity_repo.find_source_link(
            tenant_id,
            source_system="salesforce",
            source_instance="salesforce-main",
            source_kind="account",
            source_id=account_id,
        )
        return link.person_uid if link is not None else None


def _record_id(record: dict[str, Any]) -> str | None:
    raw = record.get("Id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _string_field(record: dict[str, Any], key: str) -> str | None:
    raw = record.get(key)
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


def _parse_sf_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
