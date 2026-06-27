"""Salesforce Opportunity ingest service with identity linking and timeline events.

Pulls standard ``Opportunity`` rows via SOQL, captures each row verbatim
into ``ingest.raw_event``, attempts best-effort person resolution via
``AccountId`` (and fallback to lead/contact source links), then emits
workflow-ready interaction events.

PHI safety:
- Opportunity records are CRM/sales objects. They do not contain
  clinical content by default. The verbatim payload is stored in
  ``ingest.raw_event`` (PHI-carrier schema); reads are gated.
- Timeline summaries use Opportunity Name + Stage only. No amounts
  or other financial details in summaries.
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
from packages.ingest.responsibility_resolver import (
    FunnelResponsibilityResolver,
    ProviderOwnerHint,
)
from packages.ingest.schemas import (
    RawEventIn,
    SchemaDiffOut,
    SfOpportunityImportOut,
)
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.models import Event
from packages.interaction.schemas import EventIn, ResponsibilityAssignmentIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.schemas import OpportunityIn
from packages.ops.service import OpsService

logger = logging.getLogger(__name__)

# Source-instance slug used for SF Opportunity rows in
# ``ops.opportunity`` (mirrors ``salesforce-main`` already used by
# ``identity.source_link`` and ``ops.consultation`` for SF Events).
_SF_OPPORTUNITY_SOURCE_INSTANCE = "salesforce-main"


class SfOpportunityClientProtocol(Protocol):
    """Minimum Salesforce client surface used by the Opportunity ingest service."""

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


_SF_OPPORTUNITY_EVENT_TYPE = "salesforce.opportunity.upsert"
# ENG-382: the attribution custom fields ride along into the verbatim
# raw payload — opportunities carry the clinic's real marketing
# provenance (utm_*, first/last touch, ad network), which the standard
# LeadSource almost never holds. Raw-only for now; safe projections are
# read from raw when surfaces need them.
_SF_OPPORTUNITY_COLUMNS = (
    "Id, Name, StageName, Amount, CloseDate, AccountId, OwnerId, Owner.Name, "
    "CreatedDate, LastModifiedDate, Type, LeadSource, Probability, "
    "IsClosed, IsWon, "
    "utm_source__c, utm_medium__c, utm_campaign__c, utm_content__c, "
    "utm_term__c, utm_adgroup__c, utm_creative__c, utm_location__c, "
    "utm_id__c, "
    "first_touch_source__c, first_touch_medium__c, "
    "first_touch_campaign__c, first_touch_date__c, "
    "last_touch_source__c, last_touch_medium__c, "
    "last_touch_campaign__c, last_touch_date__c, "
    "gclid__c, fbclid__c, landing_page__c, placement__c, "
    "referral_source__c, ad_network__c"
)
# Ascending order is load-bearing for the watermark cursor (ENG-381):
# the run captures the OLDEST pending changes first, the watermark
# advances to the newest captured stamp, and the next run resumes from
# there. With DESC + LIMIT a burst larger than ``limit`` would advance
# the watermark past changes that were never captured.
# ENG-427: projection built dynamically; _SF_OPPORTUNITY_COLUMNS above is the
# static fallback (it carries the Owner.Name relationship field, preserved by
# the dynamic projection).
_SF_OPPORTUNITY_SOQL = (
    "SELECT {projection} FROM Opportunity "
    "WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC "
    "LIMIT {limit}"
)


class SfOpportunityIngestService:
    """Pull SF Opportunities, capture raw, resolve person, emit timeline events."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfOpportunityClientProtocol,
        responsibility_resolver: FunnelResponsibilityResolver | None = None,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity_repo = IdentityRepository(session)
        self._interaction = InteractionService(session)
        self._ops = OpsService(session)
        # ENG-416: optional resolver — same rationale as
        # ``SfLeadIngestService``. The opportunity_* events are
        # consult-onward, so they attribute via the covering Opportunity
        # owner. When the resolver is wired in, the OWN opportunity
        # we are emitting also passes through ``resolve_actor_from_source``
        # via its OwnerId on the SOQL record (taken as the explicit
        # hint so the resolver doesn't have to round-trip back through
        # ``find_covering_opportunity`` for the same row we just upserted).
        self._responsibility = responsibility_resolver

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Opportunity",
            static_projection=_SF_OPPORTUNITY_COLUMNS,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        return await self._schema().projection(tenant_id)

    async def import_recent_opportunities(
        self,
        tenant_id: TenantId,
        *,
        days: int = 7,
        limit: int = 200,
    ) -> SfOpportunityImportOut:
        """Pull Opportunities modified within the last ``days`` days."""
        if days < 1 or days > 365:
            raise ValidationError(
                "days must be between 1 and 365", details={"days": days}
            )
        if limit < 1 or limit > 500:
            raise ValidationError(
                "limit must be between 1 and 500", details={"limit": limit}
            )

        # Resume from the highest captured LastModifiedDate (ENG-381) so
        # repeated ticks stop re-reading the whole fixed window; ``days``
        # is the first-run fallback.
        watermark = await self._ingest.max_payload_watermark(
            tenant_id,
            event_type=_SF_OPPORTUNITY_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        query = _SF_OPPORTUNITY_SOQL.format(
            projection=await self._projection(tenant_id), since=since, limit=limit
        )
        body = await self._sf.soql(query)
        records: list[dict[str, Any]] = body.get("records", []) or []

        # Capture change-guard: rows whose provider stamp matches the
        # latest captured one are healthy overlap re-reads, not new
        # evidence — skip the raw write entirely.
        candidate_ids = [
            opp_id for record in records if (opp_id := _record_id(record)) is not None
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_OPPORTUNITY_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        imported_count = 0
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            opp_id = _record_id(record)
            if opp_id is None:
                skipped_count += 1
                continue

            stamp = record.get("LastModifiedDate")
            if isinstance(stamp, str) and captured_stamps.get(opp_id) == stamp:
                unchanged_count += 1
                continue

            await self._capture_opportunity(tenant_id, record, opp_id)
            # Opportunities without person link are still valid imports.
            imported_count += 1

        return SfOpportunityImportOut(
            imported_count=imported_count,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
        )

    async def _capture_opportunity(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        opp_id: str,
    ) -> None:
        """Capture raw event, project into ops.opportunity, attempt person
        resolution + timeline event.

        The ``ops.opportunity`` projection runs even when ``person_uid``
        does not resolve — the funnel-responsibility layer (ENG-413) needs
        to see the SF Opportunity OwnerId / Owner.Name even on rows whose
        AccountId is not yet linked.
        """
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_OPPORTUNITY_EVENT_TYPE,
                external_id=opp_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        account_id = _account_id(record)
        person_uid = await self._resolve_person(tenant_id, account_id)

        # ENG-414: project into ops.opportunity regardless of person link.
        await self._ops.upsert_opportunity(
            tenant_id,
            OpportunityIn(
                person_uid=person_uid,
                source_provider="salesforce",
                source_instance=_SF_OPPORTUNITY_SOURCE_INSTANCE,
                external_id=opp_id,
                name=_stripped(record.get("Name")),
                stage=_stripped(record.get("StageName")),
                amount=_safe_float(record.get("Amount")),
                close_date=_parse_sf_date(record.get("CloseDate")),
                provider_created_at=_parse_sf_datetime(record.get("CreatedDate")),
                raw_event_id=raw_event.id,
                extra=_opportunity_extra(record),
            ),
        )

        if person_uid is None:
            # ENG-382 funnel glue: the converting lead stores
            # extra['converted_opportunity_id'] and already knows its
            # person — the primary resolution path for this clinic's SF,
            # where account source links do not exist yet.
            person_uid = await self._ops.find_lead_person_by_converted_opportunity(
                tenant_id, opp_id
            )
        if person_uid is None:
            logger.info(
                "salesforce.opportunity.no_person_link",
                extra={
                    "opp_id": opp_id,
                    "account_id": account_id,
                    "tenant_id": str(tenant_id),
                },
            )
            return

        kind = _opportunity_event_kind(record)
        occurred_at = _opportunity_occurred_at(record, kind)
        # ENG-416: this opportunity IS the covering Opportunity for its
        # own event — attribute the operational owner directly from the
        # SF record's OwnerId rather than re-running the covering-window
        # lookup, which would race the upsert we just performed.
        explicit_owner_id = _stripped(record.get("OwnerId"))
        responsibilities = await self._resolve_responsibilities(
            tenant_id,
            event_kind=kind,
            person_uid=person_uid,
            occurred_at=occurred_at,
            explicit_owner_id=explicit_owner_id,
        )

        await self._create_event_once(
            tenant_id,
            kind=kind,
            person_uid=person_uid,
            opp_id=opp_id,
            raw_event_id=raw_event.id,
            occurred_at=occurred_at,
            payload=_source_payload(opp_id, raw_event.id, record),
            responsibilities=responsibilities,
        )

    async def _create_event_once(
        self,
        tenant_id: TenantId,
        *,
        kind: Literal["opportunity_created", "opportunity_won", "opportunity_lost"],
        person_uid: UUID,
        opp_id: str,
        raw_event_id: UUID,
        occurred_at: datetime,
        payload: dict[str, object],
        responsibilities: list[ResponsibilityAssignmentIn] | None = None,
    ) -> Event:
        """Idempotent timeline event creation for an Opportunity."""
        existing = await self._interaction.find_provider_event_by_external_id(
            tenant_id,
            source_provider="salesforce",
            source_kind="salesforce_opportunity",
            source_external_id=opp_id,
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
                source_kind="salesforce_opportunity",
                source_external_id=opp_id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary_for_event(
                    kind=kind,
                    source_provider="salesforce",
                    source_id=opp_id,
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
                source_instance=_SF_OPPORTUNITY_SOURCE_INSTANCE,
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

    async def _resolve_person(
        self, tenant_id: TenantId, account_id: str | None
    ) -> UUID | None:
        """Best-effort person resolution for an Opportunity.

        Opportunities are company-level objects that link to Accounts,
        not directly to Leads/Contacts. Resolution strategy:

        1. If ``AccountId`` is present, check source_link for
           ``source_kind="account"`` (future-proofing for when account
           source links exist).
        2. Fall back to ``source_kind="lead"`` and ``source_kind="contact"``
           with the AccountId -- some dental clinic SFs link opportunities
           via converted leads that share the account id.
        3. If no AccountId or no link found, return None (valid -- not all
           opportunities can be linked to a single person).
        """
        if account_id is None:
            return None

        # Try account, lead, contact source kinds with the AccountId.
        for source_kind in ("account", "lead", "contact"):
            link = await self._identity_repo.find_source_link(
                tenant_id,
                source_system="salesforce",
                source_instance="salesforce-main",
                source_kind=source_kind,
                source_id=account_id,
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


def _account_id(record: dict[str, Any]) -> str | None:
    """Extract the AccountId from an Opportunity record."""
    value = record.get("AccountId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _opportunity_event_kind(
    record: dict[str, Any],
) -> Literal["opportunity_created", "opportunity_won", "opportunity_lost"]:
    """Determine event kind based on IsClosed and IsWon flags."""
    is_closed = record.get("IsClosed")
    is_won = record.get("IsWon")

    closed = is_closed is True or (
        isinstance(is_closed, str) and is_closed.lower() == "true"
    )
    won = is_won is True or (isinstance(is_won, str) and is_won.lower() == "true")

    if closed and won:
        return "opportunity_won"
    if closed and not won:
        return "opportunity_lost"
    return "opportunity_created"


def _opportunity_occurred_at(
    record: dict[str, Any],
    kind: Literal["opportunity_created", "opportunity_won", "opportunity_lost"],
) -> datetime:
    """Determine the occurred_at timestamp for an Opportunity event.

    For closed opportunities (won/lost), prefer CloseDate. For open
    opportunities, prefer CreatedDate.
    """
    if kind in ("opportunity_won", "opportunity_lost"):
        close_date = _parse_sf_date(record.get("CloseDate"))
        if close_date is not None:
            return close_date
    created = _parse_sf_datetime(record.get("CreatedDate"))
    if created is not None:
        return created
    modified = _parse_sf_datetime(record.get("LastModifiedDate"))
    if modified is not None:
        return modified
    return datetime.now(UTC)


def _source_payload(
    opp_id: str,
    raw_event_id: UUID,
    record: dict[str, Any],
) -> dict[str, object]:
    """Build a no-PII event payload for an Opportunity.

    Name excluded — may contain patient name or clinical context.
    Only structured stage/source/type fields are safe.
    """
    payload: dict[str, object] = {
        "source_provider": "salesforce",
        "source_object_id": opp_id,
        "raw_event_id": str(raw_event_id),
    }
    stage = _stripped(record.get("StageName"))
    if stage is not None:
        payload["opportunity_stage"] = stage
    lead_source = _stripped(record.get("LeadSource"))
    if lead_source is not None:
        payload["lead_source"] = lead_source
    opp_type = _stripped(record.get("Type"))
    if opp_type is not None:
        payload["opportunity_type"] = opp_type
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


def _safe_float(value: object) -> float | None:
    """Cast Salesforce numeric values to float, returning None on bad input.

    SF emits ``Amount`` as a number, but the SOQL JSON shape can be
    string-typed for currency formatting in some orgs; defensive parse.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # ``bool`` is a subclass of ``int`` but is never an Amount.
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _owner_name_from_record(record: dict[str, Any]) -> str | None:
    """Extract Owner.Name from the SOQL ``Owner`` relation projection.

    SOQL returns ``"Owner": {"attributes": {...}, "Name": "..."}`` for the
    ``Owner.Name`` field in the projection. SF Users (``005…``) carry the
    user's full name; SF Groups (``00G…``) carry the group / queue name.
    """
    owner = record.get("Owner")
    if isinstance(owner, dict):
        value = owner.get("Name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _opportunity_extra(record: dict[str, Any]) -> dict[str, object]:
    """Build the ``extra`` JSONB blob for ``ops.opportunity.upsert_opportunity``.

    Mirrors the ``ops.Lead.extra`` shape: owner_id / owner_name plus the
    structured stage / type / lead_source / probability / is_closed /
    is_won fields the dashboard already reads from Lead.
    """
    extra: dict[str, object] = {}
    sf_id = _stripped(record.get("Id"))
    if sf_id is not None:
        extra["sf_opportunity_id"] = sf_id
    owner_id = _stripped(record.get("OwnerId"))
    if owner_id is not None:
        extra["owner_id"] = owner_id
    owner_name = _owner_name_from_record(record)
    if owner_name is not None:
        extra["owner_name"] = owner_name
    stage = _stripped(record.get("StageName"))
    if stage is not None:
        extra["opportunity_stage"] = stage
    opp_type = _stripped(record.get("Type"))
    if opp_type is not None:
        extra["opportunity_type"] = opp_type
    lead_source = _stripped(record.get("LeadSource"))
    if lead_source is not None:
        extra["lead_source"] = lead_source
    account_id = _account_id(record)
    if account_id is not None:
        extra["account_id"] = account_id
    sf_created = _stripped(record.get("CreatedDate"))
    if sf_created is not None:
        extra["sf_created_at"] = sf_created
    probability = record.get("Probability")
    if isinstance(probability, int | float):
        extra["probability"] = float(probability)
    is_closed = record.get("IsClosed")
    if isinstance(is_closed, bool):
        extra["is_closed"] = is_closed
    is_won = record.get("IsWon")
    if isinstance(is_won, bool):
        extra["is_won"] = is_won
    return extra


def _parse_sf_date(value: object) -> datetime | None:
    """Parse a Salesforce date-only string into a midnight UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed_date = date.fromisoformat(value.strip())
    except ValueError:
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=UTC)
