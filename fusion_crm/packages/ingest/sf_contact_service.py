"""Salesforce Contact ingest service (ENG-382).

Contacts are the post-conversion identity segment of the SF funnel:
``Lead → (convert) → Contact + Account + Opportunity``. Capturing them
closes the identity gap between the marketing lead and the rest of the
CRM record — Tasks, Cases, and Opportunities reference people via
ContactId/AccountId, not the original LeadId.

Pipeline per record (ENG-185 cutover pattern):

1. Capture the verbatim row into ``ingest.raw_event`` (watermark +
   capture change-guard per ENG-381 — the service is born
   idempotent).
2. Capture one ``normalized_person_hint``.
3. Resolve the person through the identity match policy
   (``resolve_or_create_from_hint``) — converted leads share
   email/phone with their contact, so Tier 0/1 reuses the lead's
   person instead of minting a duplicate.
4. Emit a ``contact_created`` timeline event once per contact.

PHI safety: contact rows are CRM demographics (name/email/phone) —
allowed in raw (ingest carve-out rules) and in identity identifiers;
timeline summaries carry only the action verb + provider + contact id.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import PersonUID, TenantId
from packages.identity.schemas import MatchHintIn
from packages.identity.service import IdentityService
from packages.ingest.schemas import (
    NormalizedPersonHintIn,
    RawEventIn,
    SchemaDiffOut,
    SfContactImportOut,
)
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn
from packages.interaction.service import InteractionService, summary_for_event

logger = logging.getLogger(__name__)


class SfContactClientProtocol(Protocol):
    """Minimum Salesforce client surface used by the Contact ingest service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


_SF_CONTACT_EVENT_TYPE = "salesforce.contact.upsert"
# Static fallback projection (ENG-427) — used only when a live describe and the
# schema registry are both unavailable. Normal pulls use the dynamic projection.
_SF_CONTACT_COLUMNS = (
    "Id, FirstName, LastName, Email, Phone, MobilePhone, AccountId, "
    "OwnerId, CreatedDate, LastModifiedDate"
)
# Ascending order is load-bearing for the watermark cursor (ENG-381).
_SF_CONTACT_SOQL = (
    "SELECT {projection} FROM Contact "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {limit}"
)


class SfContactIngestService:
    """Pull SF Contacts, capture raw, resolve person, emit timeline events."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfContactClientProtocol,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        self._interaction = InteractionService(session)

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Contact",
            static_projection=_SF_CONTACT_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_contacts(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 200,
    ) -> SfContactImportOut:
        """Pull Contacts modified since the watermark (``days`` fallback)."""
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
            event_type=_SF_CONTACT_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        body = await self._sf.soql(
            _SF_CONTACT_SOQL.format(
                projection=await self._projection(tenant_id),
                since=since,
                limit=limit,
            )
        )
        records: list[dict[str, Any]] = body.get("records", []) or []

        candidate_ids = [
            contact_id
            for record in records
            if (contact_id := _record_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_CONTACT_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            contact_id = _record_id(record)
            if contact_id is None:
                skipped_count += 1
                continue
            stamp = record.get("LastModifiedDate")
            if isinstance(stamp, str) and captured_stamps.get(contact_id) == stamp:
                unchanged_count += 1
                continue
            await self._capture_contact(tenant_id, record, contact_id)
            imported_count += 1

        return SfContactImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
        )

    async def _capture_contact(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        contact_id: str,
    ) -> None:
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_CONTACT_EVENT_TYPE,
                external_id=contact_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        hint = await self._ingest.capture_normalized_person_hint(
            tenant_id,
            NormalizedPersonHintIn(
                raw_event_id=raw_event.id,
                source_system="salesforce",
                source_kind="contact",
                source_id=contact_id,
                observed_at=datetime.now(UTC),
                given_name=record.get("FirstName"),
                family_name=record.get("LastName"),
                display_name=_join_name(
                    record.get("FirstName"), record.get("LastName")
                ),
                email=record.get("Email"),
                phone=record.get("Phone") or record.get("MobilePhone"),
            ),
        )

        result = await self._identity.resolve_or_create_from_hint(
            tenant_id,
            MatchHintIn(
                hint_id=hint.id,
                source_system=hint.source_system,
                source_kind=hint.source_kind,
                source_id=hint.source_id,
                given_name=hint.given_name,
                family_name=hint.family_name,
                display_name=hint.display_name,
                email_normalized=hint.email_normalized,
                phone_normalized=hint.phone_normalized,
                quality_flags=hint.quality_flags,
                meta=hint.meta,
            ),
        )
        person = await self._identity.get_person(
            tenant_id, PersonUID(result.person_uid)
        )

        await self._create_event_once(
            tenant_id,
            person_uid=person.id,
            contact_id=contact_id,
            raw_event_id=raw_event.id,
            occurred_at=_parse_sf_iso(record.get("CreatedDate"))
            or datetime.now(UTC),
        )

    async def _create_event_once(
        self,
        tenant_id: TenantId,
        *,
        person_uid: Any,
        contact_id: str,
        raw_event_id: Any,
        occurred_at: datetime,
    ) -> None:
        result = await self._interaction.create_event_idempotent(
            tenant_id,
            EventIn(
                person_uid=person_uid,
                kind="contact_created",
                source_provider="salesforce",
                source_event_id=raw_event_id,
                data_class="operational",
                source_kind="salesforce_contact",
                source_external_id=contact_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary_for_event(
                    kind="contact_created",
                    source_provider="salesforce",
                    source_id=contact_id,
                ),
                payload={"sf_contact_id": contact_id},
            ),
        )
        if not result.was_created:
            logger.debug(
                "salesforce.contact.event_dedup",
                extra={"contact_id": contact_id, "tenant_id": str(tenant_id)},
            )


def _record_id(record: dict[str, Any]) -> str | None:
    raw = record.get("Id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _join_name(first: object, last: object) -> str | None:
    parts = [str(part).strip() for part in (first, last) if part]
    joined = " ".join(part for part in parts if part)
    return joined or None


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
