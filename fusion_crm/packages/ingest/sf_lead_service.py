"""W1 slice-1 — manual Salesforce Lead pull pipeline.

Orchestrates the per-record flow of the W1 worker (ENG-6) for the slice-1
manual-button trigger (ENG-100 / ENG-185):

1. ``IngestService.capture`` — verbatim raw_event row, BEFORE any mapping
2. ``IngestService.capture_normalized_person_hint`` — provider-neutral hint
3. ``IdentityService.resolve_or_create_from_hint`` — explicit match policy
4. ``OpsService.upsert_lead`` — idempotent ops.lead upsert by person_uid

The same service is reused by slice 2 (cron polling) and slice 3 (CDC
streaming) — only the trigger surface changes.

Every public method takes ``tenant_id: TenantId`` (ENG-128). The route
populates it from ``Principal.tenant_id``; the worker triggers populate
it from ``Settings.tenant_default_slug`` resolution.

## Cross-domain mediation

Per ``packages/CLAUDE.md`` matrix, ``ingest`` cannot import ``integrations``.
The Salesforce HTTP client is therefore consumed via the ``SfClientProtocol``
duck-type defined here; the wiring layer (``apps/api/dependencies.py``)
constructs a real ``packages.integrations.salesforce.SfClient`` and passes it
in. This is the standard Ports & Adapters pattern.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import get_logger
from packages.core.types import PersonUID, TenantId
from packages.identity.schemas import MatchHintIn
from packages.identity.service import IdentityService
from packages.ingest.responsibility_resolver import (
    FunnelResponsibilityResolver,
    ProviderOwnerHint,
)
from packages.ingest.schemas import (
    NormalizedPersonHintIn,
    RawEventIn,
    SchemaDiffOut,
    SfLeadOut,
)
from packages.ingest.service import IngestService
from packages.ingest.sf_schema_sync import SfSchemaSync
from packages.ingest.sync_window import resume_modified_since
from packages.interaction.schemas import EventIn, ResponsibilityAssignmentIn
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.service import OpsService, UpsertLeadResult

# Scheduled-pull projection. Adds ENG-255 dashboard-dimension fields:
# Assigned_Center__c (clinic), Business_Unit__c (BU), Preferred_Language__c,
# UTM trio (utm_source/medium/campaign), OwnerId + Owner.Name (relationship),
# Consultation_Scheduled__c. The two custom-source/campaign mirrors
# (Hubspot_Lead_Source__c, Record_Source_Detail__c) ride along so the
# dashboard's Source/Campaign filters do not need a second SF round trip.
#
# ENG-382 adds the funnel glue + full attribution:
# - Conversion fields (IsConverted, ConvertedDate, Converted*Id) stitch
#   Lead -> Contact/Account/Opportunity so opportunities can be linked
#   to the lead's person and the agent layer can read the whole journey.
# - The attribution set (first/last touch, click ids, landing page,
#   placement, ad network, remaining utm_*) carries the marketing
#   provenance that the standard LeadSource almost never holds (83 of
#   62,483 leads vs ~18k with utm_source).
_SF_LEAD_PROJECTION = (
    "Id, FirstName, LastName, Email, Phone, Company, "
    "LeadSource, Status, CreatedDate, LastModifiedDate, "
    "Assigned_Center__c, Business_Unit__c, "
    "utm_source__c, utm_medium__c, utm_campaign__c, "
    "OwnerId, Owner.Name, "
    # ENG-430 attribution: who created/last-touched the lead. CreatedById /
    # LastModifiedById are captured dynamically; the *.Name relationship
    # expansions are preserved here so the lead's creator (staff = manual /
    # phone entry) is human-readable without a separate User ingest.
    "CreatedBy.Name, LastModifiedBy.Name, "
    "Consultation_Scheduled__c, "
    "Hubspot_Lead_Source__c, Record_Source_Detail__c, "
    "IsConverted, ConvertedDate, ConvertedContactId, "
    "ConvertedAccountId, ConvertedOpportunityId, "
    "utm_content__c, utm_term__c, utm_adgroup__c, utm_creative__c, "
    "utm_location__c, utm_id__c, "
    "first_touch_source__c, first_touch_medium__c, "
    "first_touch_campaign__c, first_touch_date__c, "
    "last_touch_source__c, last_touch_medium__c, "
    "last_touch_campaign__c, last_touch_date__c, "
    "gclid__c, fbclid__c, landing_page__c, placement__c, "
    "referral_source__c, ad_network__c"
)

# SF API name -> Lead.extra key for the ENG-382 conversion + attribution
# scalars. Shared by the upsert provider_metadata and the DTO extra view
# so the two shapes cannot drift.
_LEAD_FUNNEL_EXTRA_FIELDS: dict[str, str] = {
    "IsConverted": "is_converted",
    "ConvertedDate": "converted_at",
    "ConvertedContactId": "converted_contact_id",
    "ConvertedAccountId": "converted_account_id",
    "ConvertedOpportunityId": "converted_opportunity_id",
    "utm_content__c": "utm_content",
    "utm_term__c": "utm_term",
    "utm_adgroup__c": "utm_adgroup",
    "utm_creative__c": "utm_creative",
    "utm_location__c": "utm_location",
    "utm_id__c": "utm_id",
    "first_touch_source__c": "first_touch_source",
    "first_touch_medium__c": "first_touch_medium",
    "first_touch_campaign__c": "first_touch_campaign",
    "first_touch_date__c": "first_touch_date",
    "last_touch_source__c": "last_touch_source",
    "last_touch_medium__c": "last_touch_medium",
    "last_touch_campaign__c": "last_touch_campaign",
    "last_touch_date__c": "last_touch_date",
    "gclid__c": "gclid",
    "fbclid__c": "fbclid",
    "landing_page__c": "landing_page",
    "placement__c": "placement",
    "referral_source__c": "referral_source",
    "ad_network__c": "ad_network",
}


def _funnel_extra(record: dict[str, Any]) -> dict[str, Any]:
    """Project the ENG-382 conversion + attribution scalars from a record.

    ``IsConverted=False`` is kept (a real lifecycle state); other keys
    are included as-is — the ops upsert merge skips ``None`` values for
    existing rows, so absent provider data never erases stored extra.
    """
    return {
        extra_key: record.get(api_name)
        for api_name, extra_key in _LEAD_FUNNEL_EXTRA_FIELDS.items()
    }
_SF_LEAD_EVENT_TYPE = "lead.pull"
# ENG-427: the SOQL projection is now built dynamically (full-fidelity) and
# interpolated as ``{projection}`` at call time. ``_SF_LEAD_PROJECTION`` above
# remains the static fallback used when a live describe and the schema registry
# are both unavailable, so a pull never breaks.
_SF_SOQL_RECENT = (
    "SELECT {projection} FROM Lead ORDER BY CreatedDate DESC LIMIT {limit}"
)

# Scheduled-sync SOQL (ENG-381): modified-since watermark cursor instead
# of "newest created". Catches status/source changes on OLD leads, which
# the CreatedDate ordering never re-visited. Ascending order is
# load-bearing: oldest pending changes first, so the watermark never
# advances past changes cut off by {limit}.
_SF_SOQL_SYNC = (
    "SELECT {projection} FROM Lead WHERE LastModifiedDate >= {since} "
    "ORDER BY LastModifiedDate ASC LIMIT {limit}"
)

# Backfill SOQL — sorted ASC by CreatedDate so the cursor advances forward
# from the caller-supplied since-timestamp. Each page is bounded by
# {batch} (SOQL hard cap is 2000); the caller advances the since cursor
# using the last record's CreatedDate to fetch the next page.
_SF_SOQL_BACKFILL = (
    "SELECT {projection} FROM Lead WHERE CreatedDate >= {since} "
    "ORDER BY CreatedDate ASC LIMIT {batch}"
)


_SF_BACKFILL_MAX_BATCH = 2000
log = get_logger("ingest.sf_lead")


class SfClientProtocol(Protocol):
    """Minimum SF client surface used by this service.

    The real implementation lives in ``packages.integrations.salesforce`` and
    matches by duck-typing — we do not import it here to respect the
    ingest → integrations cross-package import rule.
    """

    async def soql(self, query: str) -> dict[str, Any]: ...

    # ENG-427 full-fidelity capture — describe + Tooling field list.
    async def describe(self, resource: str) -> dict[str, Any]: ...

    async def describe_tooling_fields(
        self, resource: str
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class SfLeadNotifySignal:
    """NON-PII signal that a genuinely-new lead was created (ENG-456).

    Emitted by ``pull_recent_for_sync`` ONLY (never the backfill path) so a
    worker boundary can fan a ``lead.created`` chat notification. Carries no
    name / email / phone value — only:

    * ``person_uid`` — opaque global UUID, drives the de-identified template;
    * ``sf_lead_id`` — the stable SF Lead Id, used as the notification
      ``dedupe_key`` so a re-pull of the same lead is a guaranteed no-op;
    * ``source_created_at`` — the SF ``CreatedDate`` (tz-aware UTC) feeding the
      historical cutoff guard; ``None`` if SF returned no parseable date;
    * ``has_phone`` — a NON-PII boolean (never the number) for the phone-less
      field-control rule. ``None`` when the SF record carries no ``Phone`` key
      at all (presence UNKNOWN), so the missing-phone rule does not fire on
      uncertainty — mirrors the API-route contract.
    * ``source`` — the lead-source label (a categorical enum, not free text).
    """

    person_uid: UUID
    sf_lead_id: str
    source_created_at: datetime | None
    has_phone: bool | None
    source: str | None


@dataclass(frozen=True)
class SfLeadPullSummary:
    imported: list[SfLeadOut]
    skipped_count: int
    queried_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    # ENG-456: NON-PII signals for genuinely-NEW leads in THIS pull. Populated
    # ONLY by ``pull_recent_for_sync`` (the scheduled-pull boundary); the
    # backfill path (``pull_all_since``) leaves this empty by construction, so
    # a full historical backfill emits ZERO chat notifications.
    notify_signals: tuple[SfLeadNotifySignal, ...] = ()

    @property
    def imported_count(self) -> int:
        return len(self.imported)

    def model_dump(self) -> dict[str, int]:
        return {
            "imported_count": self.imported_count,
            "unchanged_count": self.unchanged_count,
            "skipped_count": self.skipped_count,
            "queried_count": self.queried_count,
        }


class SfLeadIngestService:
    """Pull SF Leads, capture raw, dedupe person, upsert ops.lead."""

    def __init__(
        self,
        session: AsyncSession,
        sf_client: SfClientProtocol,
        responsibility_resolver: FunnelResponsibilityResolver | None = None,
    ) -> None:
        self._session = session
        self._sf = sf_client
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        self._ops = OpsService(session)
        self._interaction = InteractionService(session)
        # ENG-416: optional so legacy callers (older tests, manual pulls
        # without an ActorService wired in) still work — the event is
        # then emitted with zero responsibility rows and the backfill
        # script seeds them on the next pass.
        self._responsibility = responsibility_resolver

    # --- Full-fidelity schema (ENG-427) ---

    def _schema(self) -> SfSchemaSync:
        return SfSchemaSync(
            self._ingest,
            self._sf,
            object_name="Lead",
            static_projection=_SF_LEAD_PROJECTION,
        )

    async def sync_schema(
        self, tenant_id: TenantId
    ) -> tuple[SchemaDiffOut, list[str]]:
        """Refresh the Lead schema registry from SF describe + Tooling.

        Returns ``(SchemaDiffOut, fls_gap)``. The FLS gap — fields on the object
        the integration user cannot read — is logged as the admin's remediation
        list. Called out-of-band by the Block C refresh job, not per pull.
        """
        return await self._schema().sync(tenant_id)

    async def _projection(self, tenant_id: TenantId) -> str:
        """SOQL field list for a Lead pull: registry, then describe, then static."""
        return await self._schema().projection(tenant_id)

    async def pull_recent(
        self, tenant_id: TenantId, limit: int = 5
    ) -> list[SfLeadOut]:
        """Fetch the N most recent SF Leads by CreatedDate, persist, return DTOs.

        Idempotent: a re-pull observing the same SF Lead Ids hits the existing
        ``source_link`` rows, reuses the same ``person_uid``, and the
        ``upsert_lead`` change-detection prevents duplicate ops.lead rows.
        """
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")

        soql = _SF_SOQL_RECENT.format(
            projection=await self._projection(tenant_id), limit=limit
        )
        result = await self._sf.soql(soql)
        records: list[dict[str, Any]] = result.get("records", [])

        out: list[SfLeadOut] = []
        for record in records:
            out.append(await self._capture_lead(tenant_id, record))
        return out

    async def pull_recent_for_sync(
        self, tenant_id: TenantId, limit: int = 50, *, days: int = 7
    ) -> SfLeadPullSummary:
        """Scheduled pull variant that isolates per-record failures.

        Manual API pulls remain strict via ``pull_recent``. The scheduler uses
        this method so one malformed or conflicting lead records a partial
        sync instead of aborting the whole provider batch.

        ENG-381: resumes from the highest captured ``LastModifiedDate``
        (``days`` is the first-run fallback window) and skips rows whose
        provider stamp did not move since the last capture. This also
        means status/source edits on OLD leads are now picked up — the
        previous "newest created" query never re-visited them.
        """
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")

        watermark = await self._ingest.max_payload_watermark(
            tenant_id,
            event_type=_SF_LEAD_EVENT_TYPE,
            watermark_key="LastModifiedDate",
        )
        since_dt = resume_modified_since(
            watermark, default_since=datetime.now(UTC) - timedelta(days=days)
        )
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        soql = _SF_SOQL_SYNC.format(
            projection=await self._projection(tenant_id), since=since, limit=limit
        )
        result = await self._sf.soql(soql)
        records: list[dict[str, Any]] = result.get("records", []) or []

        # Capture change-guard: skip rows whose LastModifiedDate is
        # already captured (healthy overlap re-reads).
        candidate_ids = [
            str(record["Id"]) for record in records if record.get("Id")
        ]
        captured_stamps = await self._ingest.latest_payload_values(
            tenant_id,
            event_type=_SF_LEAD_EVENT_TYPE,
            external_ids=candidate_ids,
            payload_key="LastModifiedDate",
        )

        out: list[SfLeadOut] = []
        # ENG-456: NON-PII signals for genuinely-new leads, fanned out as
        # ``lead.created`` chat notifications by the worker boundary.
        notify_signals: list[SfLeadNotifySignal] = []
        unchanged_count = 0
        skipped_count = 0
        for record in records:
            sf_id = str(record.get("Id", ""))
            stamp = record.get("LastModifiedDate")
            if (
                sf_id
                and isinstance(stamp, str)
                and captured_stamps.get(sf_id) == stamp
            ):
                unchanged_count += 1
                continue
            try:
                # A per-record sink, so a record that fails inside the nested
                # savepoint does NOT leave a half-claimed notification signal:
                # we only extend the shared list AFTER the savepoint commits.
                record_signals: list[SfLeadNotifySignal] = []
                async with self._session.begin_nested():
                    out.append(
                        await self._capture_lead(
                            tenant_id, record, notify_sink=record_signals
                        )
                    )
                notify_signals.extend(record_signals)
            except Exception as exc:  # noqa: BLE001 - sync must continue per record.
                skipped_count += 1
                log.warning(
                    "sf_lead.sync.record_skipped",
                    tenant_id=str(tenant_id),
                    sf_lead_id=sf_id or None,
                    error_type=type(exc).__name__,
                )

        return SfLeadPullSummary(
            imported=out,
            unchanged_count=unchanged_count,
            skipped_count=skipped_count,
            queried_count=len(records),
            notify_signals=tuple(notify_signals),
        )

    async def pull_all_since(
        self,
        tenant_id: TenantId,
        since: datetime,
        *,
        batch_size: int = 500,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> int:
        """Full backfill of SF Leads created on or after ``since``.

        Walks the Lead history forward in batches of ``batch_size`` (max 2000
        per SOQL response), advancing the cursor to the last record's
        CreatedDate + 1 millisecond each page. Returns the total count
        captured. Re-runs are idempotent at every level since ENG-381:
        rows whose ``LastModifiedDate`` is already captured are skipped
        entirely, so a repeated backfill fills holes without duplicating
        ``ingest.raw_event`` rows. (Rows captured before LastModifiedDate
        joined the projection re-capture once, then dedupe.)

        ``commit`` is the caller's unit-of-work flush, invoked after every
        page (ENG-326 pattern; documented exception to "services never
        commit" for streaming backfills). Without it a full-history run is
        ONE multi-minute transaction — long enough to deadlock against the
        scheduled tick writing the same tables, losing the whole run (seen
        live 2026-06-10). ``None`` keeps the legacy caller-owned
        transaction for small windows.

        Designed for one-shot operator-triggered loading and NOT wired into
        the scheduled job. Sync-run journaling is intentionally absent in
        this revision; ENG-239 retrofits real `integrations.sync_run` rows.
        """
        if batch_size < 1 or batch_size > _SF_BACKFILL_MAX_BATCH:
            raise ValueError(
                f"batch_size must be between 1 and {_SF_BACKFILL_MAX_BATCH}"
            )

        cursor = since if since.tzinfo is not None else since.replace(tzinfo=UTC)
        total = 0
        while True:
            cursor_str = cursor.strftime("%Y-%m-%dT%H:%M:%SZ")
            soql = _SF_SOQL_BACKFILL.format(
                projection=await self._projection(tenant_id),
                since=cursor_str,
                batch=batch_size,
            )
            result = await self._sf.soql(soql)
            records: list[dict[str, Any]] = result.get("records", []) or []
            if not records:
                break
            candidate_ids = [
                str(record["Id"]) for record in records if record.get("Id")
            ]
            captured_stamps = await self._ingest.latest_payload_values(
                tenant_id,
                event_type=_SF_LEAD_EVENT_TYPE,
                external_ids=candidate_ids,
                payload_key="LastModifiedDate",
            )
            last_created_at: datetime | None = None
            for record in records:
                sf_id = str(record.get("Id", ""))
                stamp = record.get("LastModifiedDate")
                parsed = _parse_sf_iso(record.get("CreatedDate"))
                if parsed is not None and (
                    last_created_at is None or parsed > last_created_at
                ):
                    last_created_at = parsed
                if (
                    sf_id
                    and isinstance(stamp, str)
                    and captured_stamps.get(sf_id) == stamp
                ):
                    continue
                await self._capture_lead(tenant_id, record)
                total += 1
            if commit is not None:
                await commit()
            if len(records) < batch_size:
                break
            if last_created_at is None:
                # Defensive: provider returned rows without a CreatedDate.
                # Advancing by 1 ms from the previous cursor avoids an
                # infinite loop; some rows may re-process (idempotent).
                cursor = cursor + timedelta(milliseconds=1)
            else:
                cursor = last_created_at + timedelta(milliseconds=1)
        return total

    async def _capture_lead(
        self,
        tenant_id: TenantId,
        record: dict[str, Any],
        *,
        notify_sink: list[SfLeadNotifySignal] | None = None,
    ) -> SfLeadOut:
        """Per-record capture + identity + ops upsert, shared by recent + backfill.

        When ``notify_sink`` is provided AND the upsert CREATED the lead, a
        NON-PII :class:`SfLeadNotifySignal` is appended for the worker boundary
        to fan out as a ``lead.created`` chat notification (ENG-456). The sink
        is left untouched for updates / no-op re-pulls, and is ``None`` on the
        manual-pull and backfill paths so those never notify.
        """
        sf_id = str(record["Id"])

        # 1. Capture verbatim BEFORE mapping (forensic trail).
        raw_event = await self._ingest.capture(
            tenant_id,
            RawEventIn(
                source="salesforce",
                event_type=_SF_LEAD_EVENT_TYPE,
                external_id=sf_id,
                received_at=datetime.now(UTC),
                payload=record,
            ),
        )

        hint = await self._ingest.capture_normalized_person_hint(
            tenant_id,
            NormalizedPersonHintIn(
                raw_event_id=raw_event.id,
                source_system="salesforce",
                source_kind="lead",
                source_id=sf_id,
                observed_at=datetime.now(UTC),
                given_name=record.get("FirstName"),
                family_name=record.get("LastName"),
                display_name=_join_name(
                    record.get("FirstName"), record.get("LastName")
                ),
                email=record.get("Email"),
                phone=record.get("Phone"),
            ),
        )

        # 2. Resolve person through the explicit ENG-185 match policy.
        person, is_reactivation = await self._resolve_person_from_hint(
            tenant_id, hint
        )

        # 3. Upsert ops.lead, carrying provider metadata in `extra`.
        upsert = await self._ops.upsert_lead(
            tenant_id,
            person_uid=person.id,
            raw=record,
            provider_metadata={
                "sf_lead_id": sf_id,
                "is_reactivation": is_reactivation,
                "sf_created_at": record.get("CreatedDate"),
                "company": record.get("Company"),
                # ENG-255 dashboard-dimension fields. None when the SF org
                # has not populated the field — downstream readers must
                # handle missing values.
                "assigned_center": record.get("Assigned_Center__c"),
                "business_unit": record.get("Business_Unit__c"),
                "utm_source": record.get("utm_source__c"),
                "utm_medium": record.get("utm_medium__c"),
                "utm_campaign": record.get("utm_campaign__c"),
                "owner_id": record.get("OwnerId"),
                # ENG-408: human-facing owner for dashboard columns. SOQL
                # relationship field — arrives as {"Owner": {"Name": ...}};
                # None-valued keys are skipped by the upsert merge, so the
                # next re-pull/backfill enriches existing rows in place.
                "owner_name": _owner_name(record),
                "consultation_scheduled_at": record.get("Consultation_Scheduled__c"),
                "hubspot_lead_source": record.get("Hubspot_Lead_Source__c"),
                "record_source_detail": record.get("Record_Source_Detail__c"),
                # ENG-382 funnel glue + attribution scalars.
                **_funnel_extra(record),
            },
        )

        await self._emit_lead_event(
            tenant_id,
            person_uid=person.id,
            raw_event_id=raw_event.id,
            sf_id=sf_id,
            record=record,
            upsert=upsert,
        )

        # ENG-456: collect a NON-PII signal ONLY for genuinely-NEW leads, so the
        # worker boundary can fan a ``lead.created`` chat notification. Updates
        # and no-op re-pulls (``was_created=False``) never enter the sink.
        if notify_sink is not None and upsert.was_created:
            notify_sink.append(
                SfLeadNotifySignal(
                    person_uid=person.id,
                    sf_lead_id=sf_id,
                    source_created_at=_parse_sf_iso(record.get("CreatedDate")),
                    has_phone=_has_phone_hint(record),
                    source=record.get("LeadSource"),
                )
            )

        return _to_dto_from_record(
            lead=upsert.lead,
            person=person,
            record=record,
            is_reactivation=is_reactivation,
        )

    async def list_recent(
        self, tenant_id: TenantId, limit: int = 5
    ) -> list[SfLeadOut]:
        """Read locally-persisted SF leads (last N by created_at, desc)."""
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")

        leads = await self._ops.list_recent_sf_leads(tenant_id, limit)
        out: list[SfLeadOut] = []
        for lead in leads:
            person = await self._identity.get_person(
                tenant_id, PersonUID(lead.person_uid)
            )
            email = next((i.value for i in person.identifiers if i.kind == "email"), None)
            phone = next((i.value for i in person.identifiers if i.kind == "phone"), None)
            extra = lead.extra or {}
            out.append(
                SfLeadOut(
                    id=lead.id,
                    person_uid=lead.person_uid,
                    sf_lead_id=str(extra.get("sf_lead_id", "")),
                    display_name=person.display_name,
                    email=email,
                    phone=phone,
                    company=extra.get("company"),
                    lead_source=extra.get("lead_source"),
                    lead_status=extra.get("lead_status"),
                    is_reactivation=bool(extra.get("is_reactivation", False)),
                    sf_created_at=extra.get("sf_created_at"),
                    created_at=lead.created_at,
                )
            )
        return out

    # --- private ---

    async def _resolve_person_from_hint(
        self, tenant_id: TenantId, hint: Any
    ) -> tuple[Any, bool]:
        """Return ``(person, is_reactivation)`` from the ENG-185 policy result."""
        if hint.source_id is None:
            raise ValueError("normalized person hint source_id is required")

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
        person = await self._identity.get_person(tenant_id, PersonUID(result.person_uid))
        return person, result.was_existing_person_match

    async def _emit_lead_event(
        self,
        tenant_id: TenantId,
        *,
        person_uid: UUID,
        raw_event_id: UUID,
        sf_id: str,
        record: dict[str, Any],
        upsert: UpsertLeadResult,
    ) -> None:
        """Emit the workflow-ready timeline event for a changed SF Lead."""
        kind: Literal["lead_created", "lead_updated"]
        if upsert.was_created:
            kind = "lead_created"
        elif upsert.was_changed:
            kind = "lead_updated"
        else:
            return

        occurred_at = _lead_event_occurred_at(kind, record)
        # ENG-416: pre-consult event, so the resolver attributes the
        # operational owner to Lead.OwnerId (read off the just-upserted
        # Lead.extra). When the SF Lead has no OwnerId yet, the resolver
        # returns an empty assignment list and the event lands without
        # responsibility rows — the backfill seeds them later.
        responsibilities = await self._resolve_responsibilities(
            tenant_id,
            event_kind=kind,
            person_uid=person_uid,
            occurred_at=occurred_at,
            explicit_owner_id=_owner_id_from_record(record),
        )

        await self._interaction.create_event(
            tenant_id,
            EventIn(
                person_uid=person_uid,
                kind=kind,
                source_provider="salesforce",
                source_event_id=raw_event_id,
                data_class="operational",
                source_kind="salesforce_lead",
                source_external_id=sf_id,
                projection_ref_type="ops_lead",
                projection_ref_id=upsert.lead.id,
                review_status="auto",
                occurred_at=occurred_at,
                summary=summary_for_event(
                    kind=kind,
                    source_provider="salesforce",
                    source_id=sf_id,
                ),
                payload=_lead_event_payload(record),
                responsibilities=responsibilities,
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
        """Run the funnel-responsibility resolver, tolerating missing wiring."""
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


def _join_name(first: str | None, last: str | None) -> str | None:
    parts = [p for p in (first, last) if p]
    return " ".join(parts) if parts else None


def _parse_sf_iso(value: object) -> datetime | None:
    """Parse an ISO 8601 timestamp from a Salesforce SOQL response.

    Accepts both the raw ``Z``-suffixed form SF returns
    (``2026-05-23T21:14:39.930+0000``) and a Python-native datetime.
    Returns ``None`` for any unparseable input.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.replace("Z", "+00:00")
    # SF emits "+0000" without the colon; Python's fromisoformat handles
    # "+00:00" but not "+0000" before 3.11. We are on 3.12, but be defensive.
    if len(candidate) >= 5 and candidate[-5] in ("+", "-") and candidate[-3] != ":":
        candidate = candidate[:-2] + ":" + candidate[-2:]
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _lead_event_occurred_at(kind: str, record: dict[str, Any]) -> datetime:
    keys = (
        ("CreatedDate", "LastModifiedDate")
        if kind == "lead_created"
        else ("LastModifiedDate", "CreatedDate")
    )
    for key in keys:
        parsed = _parse_sf_iso(record.get(key))
        if parsed is not None:
            return parsed
    return datetime.now(UTC)


def _owner_id_from_record(record: dict[str, Any]) -> str | None:
    """Extract the SF Lead OwnerId from a SOQL record.

    Used to override the staged Lead-owner lookup so a Lead pull that
    sees a freshly-changed OwnerId attributes the new event to the new
    owner immediately, without waiting for a second pull to land the
    updated ``Lead.extra['owner_id']``.
    """
    value = record.get("OwnerId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _lead_event_payload(record: dict[str, Any]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in ("Status", "LeadSource", "Id", "CreatedDate", "LastModifiedDate"):
        if key not in record:
            continue
        value = _json_event_value(record[key])
        if value is not None:
            out[key] = value
    return out


def _json_event_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str | int | float | bool):
        return value
    return None


def _has_phone_hint(record: dict[str, Any]) -> bool | None:
    """Return a NON-PII phone-presence boolean for the notification context.

    Mirrors the API-route contract (``apps/api/routers/ops.py``): emit a
    BOOLEAN (never the number) ONLY when a ``Phone`` key is actually present in
    the SF record. When NO ``Phone`` key exists the presence is UNKNOWN — we
    return ``None`` so the phone-less field-control rule (``has_phone == false``)
    does NOT fire on uncertainty; it fires only when ``Phone`` is
    present-but-empty.
    """
    if "Phone" not in record:
        return None
    return bool(record.get("Phone"))


def _owner_name(record: dict[str, Any]) -> str | None:
    """Extract ``Owner.Name`` from the SOQL relationship sub-object.

    SF renders relationship fields as a nested dict (``{"Owner":
    {"Name": "Jane Doe", ...}}``) and ``None`` when the lookup is empty.
    """
    owner = record.get("Owner")
    if isinstance(owner, dict):
        name = owner.get("Name")
        return str(name) if name else None
    return None


def _extra_view(
    record: dict[str, Any], sf_id: str, is_reactivation: bool
) -> dict[str, Any]:
    """Build the same ``Lead.extra`` shape the upsert produces, for the DTO."""
    return {
        "sf_lead_id": sf_id,
        "is_reactivation": is_reactivation,
        "sf_created_at": record.get("CreatedDate"),
        "company": record.get("Company"),
        "lead_source": record.get("LeadSource"),
        "lead_status": record.get("Status"),
        # ENG-255 dashboard dimensions — mirror provider_metadata.
        "assigned_center": record.get("Assigned_Center__c"),
        "business_unit": record.get("Business_Unit__c"),
        "utm_source": record.get("utm_source__c"),
        "utm_medium": record.get("utm_medium__c"),
        "utm_campaign": record.get("utm_campaign__c"),
        "owner_id": record.get("OwnerId"),
        "owner_name": _owner_name(record),
        "consultation_scheduled_at": record.get("Consultation_Scheduled__c"),
        "hubspot_lead_source": record.get("Hubspot_Lead_Source__c"),
        "record_source_detail": record.get("Record_Source_Detail__c"),
        # ENG-382 funnel glue + attribution scalars.
        **_funnel_extra(record),
    }


def _to_dto_from_record(
    lead: Any,
    person: Any,
    record: dict[str, Any],
    is_reactivation: bool,
) -> SfLeadOut:
    """Build SfLeadOut using email/phone from the verbatim SF record.

    Avoids ``person.identifiers`` lazy-load (which fails outside an awaited
    context in async SQLAlchemy). The SF record already carries the values
    we just persisted as identifiers, so this is information-equivalent.
    """
    sf_id = str(record["Id"])
    return SfLeadOut(
        id=lead.id,
        person_uid=person.id,
        sf_lead_id=sf_id,
        display_name=person.display_name,
        email=record.get("Email"),
        phone=record.get("Phone"),
        company=record.get("Company"),
        lead_source=record.get("LeadSource"),
        lead_status=record.get("Status"),
        is_reactivation=is_reactivation,
        sf_created_at=record.get("CreatedDate"),
        created_at=lead.created_at if lead.created_at is not None else datetime.now(UTC),
    )


def _to_dto(lead: Any, person: Any, lead_extra: dict[str, Any]) -> SfLeadOut:
    """Build SfLeadOut from a freshly upserted Lead + Person.

    The Lead row was inserted/updated in the same UoW — we don't reload it
    from the DB; we materialise the DTO from what we know. ``lead.id`` and
    ``lead.created_at`` come from the persisted row; everything else from
    the verbatim record + person identifiers.
    """
    email = next((i.value for i in person.identifiers if i.kind == "email"), None)
    phone = next((i.value for i in person.identifiers if i.kind == "phone"), None)
    return SfLeadOut(
        id=lead.id,
        person_uid=person.id,
        sf_lead_id=str(lead_extra.get("sf_lead_id", "")),
        display_name=person.display_name,
        email=email,
        phone=phone,
        company=lead_extra.get("company"),
        lead_source=lead_extra.get("lead_source"),
        lead_status=lead_extra.get("lead_status"),
        is_reactivation=bool(lead_extra.get("is_reactivation", False)),
        sf_created_at=lead_extra.get("sf_created_at"),
        created_at=lead.created_at if lead.created_at is not None else datetime.now(UTC),
    )
