"""OpsService — orchestrates ops repositories and produces PHI-safe snapshots.

The service depends on ``IdentityService`` only for the public display name —
NEVER on PhiService or PhiRepository.

Every public method takes ``tenant_id: TenantId`` as the first positional
argument after ``self`` (ENG-128) and forwards it into the repository.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import PersonUID, TenantId
from packages.identity.service import IdentityService
from packages.tenant.service import LocationService

from .models import (
    ACCOUNT_PROVIDERS,
    CONSULTATION_PROVIDERS,
    OPPORTUNITY_PROVIDERS,
    Account,
    Consultation,
    ConsultationStatus,
    FollowupTask,
    Lead,
    LeadStatus,
    Opportunity,
    PersonLocationProfile,
    RelationshipKind,
    RelationshipStatus,
)
from .repository import OpsRepository
from .schemas import (
    AnalyticsBucketOut,
    ConsultationFollowupOut,
    ConsultationIn,
    ConsultationOut,
    ConsultationUpsertResult,
    ConversionFunnelOut,
    FieldValueBucketOut,
    FollowupTaskIn,
    LeadIn,
    LeadOut,
    LeadSourceLeadItemOut,
    LeadSourceLeadListOut,
    LeadSourceNodeOut,
    LeadSourceProfileOut,
    LeadSourceTreeOut,
    OpportunityIn,
    OpportunityMonthOutcomeOut,
    OpportunityOut,
    OpportunityUpsertResult,
    OpsFieldProfileOut,
    OpsPersonSnapshot,
    PaidLeadsOut,
    PersonLocationProfileOut,
    SalesConsultationRowOut,
    SalesPipelineSummaryOut,
    SalesStageRowOut,
    SalesTcRowOut,
)


@dataclass(frozen=True, slots=True)
class CurrentFunnelOwner:
    """Per-person current funnel-stage owner (ENG-418).

    ``stage`` discriminates between the pre-consult Lead-owner state and
    the post-Opportunity TC state so the chain header can label the
    hand-off explicitly.

    ``external_id`` is the SF UserId / GroupId stored on the Lead /
    Opportunity. The API route resolves it to an ``actor.actor`` via
    :meth:`packages.actor.service.ActorService.resolve_actor_from_source`
    and appends the display name to the API DTO.
    """

    stage: str
    source_provider: str
    external_id: str
    owner_name: str | None
    opportunity_id: UUID | None


def _opportunity_stage(stage: str | None) -> str:
    """Map a free-form SF Opportunity stage to a canonical label.

    SF Opportunity.StageName is free text; the only canonical bucket we
    care about for ownership is whether it is closed-lost (so the chain
    header can move on to the next Opportunity / Lead owner). Everything
    else is treated as "open".
    """
    if stage is None:
        return "open"
    lowered = stage.strip().lower()
    if "lost" in lowered:
        return "closed_lost"
    if "won" in lowered:
        return "closed_won"
    return "open"


@dataclass(frozen=True)
class UpsertLeadResult:
    """Output of :meth:`OpsService.upsert_lead`.

    Workers (W1 Salesforce-pull) use this to decide whether to emit an
    interaction event:

    - ``was_created=True``  → emit ``lead_created``
    - ``was_changed=True``  → emit ``lead_updated`` if NOT was_created
    - both False            → no-op re-pull, suppress event emission

    ``was_changed`` is true whenever the row was inserted OR a watched field
    (``Status``, ``LeadSource``) actually differed from what we had on file.
    """

    lead: Lead
    was_created: bool
    was_changed: bool


# Watched fields for upsert_lead change-detection. Adding a field here
# widens the change-emission contract — coordinate with workers.
_LEAD_CHANGE_KEYS = ("lead_status", "lead_source")
_PIPELINE_EXCLUDE_STATUSES = frozenset({LeadStatus.LOST.value})
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")
_PAID_SOURCE_CLASSIFICATION_TERMS = [
    "google",
    "meta",
    "facebook",
    "instagram",
    "ppc",
    "paid",
    "adwords",
    "paid search",
    "paid social",
]

# Marketing-safe Lead.extra keys surfaced by the lead-source explorer
# drill-down (ENG-391). Mirrors the ENG-255/ENG-382 SOQL capture set;
# anything outside this allowlist (and free-text ``notes``) stays out of
# the explorer payload by construction.
_LEAD_ATTRIBUTION_EXTRA_KEYS = frozenset(
    {
        "lead_source",
        "lead_status",
        "sf_lead_id",
        "sf_created_at",
        "company",
        "assigned_center",
        "business_unit",
        "owner_id",
        "consultation_scheduled_at",
        "hubspot_lead_source",
        "record_source_detail",
        "is_reactivation",
        "is_converted",
        "converted_at",
        "converted_contact_id",
        "converted_account_id",
        "converted_opportunity_id",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "utm_adgroup",
        "utm_creative",
        "utm_location",
        "utm_id",
        "first_touch_source",
        "first_touch_medium",
        "first_touch_campaign",
        "first_touch_date",
        "last_touch_source",
        "last_touch_medium",
        "last_touch_campaign",
        "last_touch_date",
        "gclid",
        "fbclid",
        "landing_page",
        "placement",
        "referral_source",
        "ad_network",
        "campaign",
        "campaign_name",
    }
)

_UNKNOWN_BUCKET = "unknown"

# Python mirror of ``repository._EXPLORER_CHANNEL_ALIASES`` (ENG-394).
# Substring containment over the lowercased source label — MUST stay in
# sync with the SQL CASE in ``_explorer_channel_label``.
_EXPLORER_CHANNEL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("facebook", ("facebook", "fb")),
    ("google", ("google", "adwords", "youtube")),
)


_NBSP_CHAR = "\u00a0"


def _center_matches(center: object, needles: list[str]) -> bool:
    """Python mirror of ``repository._lead_assigned_center_predicate``."""
    if not isinstance(center, str) or not center:
        return False
    normalized = center.lower().replace(_NBSP_CHAR, " ")
    return any(
        needle and needle.lower().replace(_NBSP_CHAR, " ") in normalized
        for needle in needles
    )


# ENG-560 location-tab classifier. A person lands in exactly one clinic tab.
# The four tab keys are the operator-fixed contract shared with the frontend
# (ENG-561); ``galleria`` is the default bucket, ``fusion``/``cosmo`` are
# reachable only via a consultation.
LocationTab = Literal["galleria", "fusion", "el_dorado", "cosmo"]

# tenant.location.short_name → tab. Resolved by short_name (never hardcoded
# location UUIDs) so a re-imported location keeps its tab.
_TAB_BY_LOCATION_SHORT_NAME: dict[str, LocationTab] = {
    "GALLERIA": "galleria",
    "FUSION-ROS": "fusion",
    "FUSION-EDH": "el_dorado",
    "COSMO": "cosmo",
}

_DEFAULT_LOCATION_TAB: LocationTab = "galleria"

# Rule-2 assigned_center needle. Only El Dorado Hills escapes the default
# bucket; Roseville / Galleria OMS / empty / NULL all fall to ``galleria``.
_EL_DORADO_ASSIGNED_CENTER_NEEDLES = ["El Dorado Hills"]


def _assigned_center_tab(center: object) -> LocationTab:
    """Rule-2 fallback: SF ``Assigned_Center__c`` → location tab.

    "El Dorado Hills" (including the U+00A0 NBSP variant SF emits) →
    ``el_dorado``; every other value — Roseville, Galleria OMS, empty,
    NULL — falls to the ``galleria`` default catch-all (ENG-560).
    """
    if _center_matches(center, _EL_DORADO_ASSIGNED_CENTER_NEEDLES):
        return "el_dorado"
    return _DEFAULT_LOCATION_TAB


def _channel_of_source(source_label: str) -> str:
    """Map a source label onto its virtual channel (ENG-394)."""
    lowered = source_label.lower()
    for channel, needles in _EXPLORER_CHANNEL_ALIASES:
        if any(needle in lowered for needle in needles):
            return channel
    return source_label


def _parse_provider_iso_or_none(value: object) -> datetime | None:
    """Parse a provider ISO timestamp (SF ``CreatedDate``) defensively."""
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    # SF emits "+0000" zone offsets which fromisoformat rejects before 3.11
    # normalization; insert the colon when the offset lacks one.
    if len(candidate) >= 5 and candidate[-5] in "+-" and candidate[-3] != ":":
        candidate = f"{candidate[:-2]}:{candidate[-2:]}"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


@dataclass
class _FunnelNodeCounts:
    """Mutable accumulator for one lead-source tree node."""

    leads: int = 0
    consults_scheduled: int = 0
    consults_attended: int = 0
    collected_amount: float = 0.0


@dataclass(frozen=True)
class FunnelLeadRow:
    """One ``(person_uid, channel, month)`` lead cell (Full Funnel v2)."""

    person_uid: UUID
    channel: str
    month: str


@dataclass(frozen=True)
class FunnelConsultationRow:
    """One consultation cell (Full Funnel v2).

    ``is_past`` is ``scheduled_at < now()`` (ENG-481): the composition layer
    reads a still-``scheduled`` past appointment as a no-show and a future one
    as pending.
    """

    person_uid: UUID
    status: str
    month: str
    is_past: bool


class OpsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OpsRepository(session)
        self._identity = IdentityService(session)

    async def snapshot(self, tenant_id: TenantId, person_uid: PersonUID) -> OpsPersonSnapshot:
        """Produce a PHI-free snapshot suitable for staff and AI agents."""
        person = await self._identity.get_person(tenant_id, person_uid)
        latest = await self._repo.latest_lead_for(tenant_id, person_uid)
        open_count = await self._repo.open_followup_count(tenant_id, person_uid)

        return OpsPersonSnapshot(
            person_uid=PersonUID(person.id),
            display_name=person.display_name,
            open_followups=open_count,
            last_lead_status=latest.status if latest else None,
        )

    async def create_followup(self, tenant_id: TenantId, payload: FollowupTaskIn) -> FollowupTask:
        # Validate that the referenced person exists. Fail loud if not.
        await self._identity.get_person(tenant_id, PersonUID(payload.person_uid))

        task = FollowupTask(
            tenant_id=tenant_id,
            person_uid=payload.person_uid,
            title=payload.title,
            description=payload.description,
            due_at=payload.due_at,
            assigned_to=payload.assigned_to,
        )
        await self._repo.add_followup(task)
        return task

    async def create_lead(self, tenant_id: TenantId, payload: LeadIn) -> Lead:
        await self._identity.get_person(tenant_id, PersonUID(payload.person_uid))
        lead = Lead(
            tenant_id=tenant_id,
            person_uid=payload.person_uid,
            source=payload.source,
            notes=payload.notes,
            extra=payload.extra,
        )
        await self._repo.add_lead(lead)
        return lead

    async def reassign_leads(
        self,
        tenant_id: TenantId,
        from_person_uid: PersonUID,
        to_person_uid: PersonUID,
    ) -> int:
        """Move every Lead from a merged person onto the surviving person.

        Called by the ENG-544 replay job's LIVE pass AFTER IdentityService has
        recorded the merge: a duplicate person being collapsed into a canonical
        one must not strand its ``ops.lead`` rows. Idempotent — re-running after
        the survivor already owns the leads simply moves zero rows. Returns the
        number of leads moved.
        """
        return await self._repo.reassign_leads(
            tenant_id, from_person_uid, to_person_uid
        )

    async def list_followups(
        self, tenant_id: TenantId, person_uid: PersonUID
    ) -> list[FollowupTask]:
        # Existence check
        await self._identity.get_person(tenant_id, person_uid)
        return await self._repo.list_followups(tenant_id, person_uid)

    # Defensive: raise from one place if a caller asks for a person we don't know.
    async def _require_person(self, tenant_id: TenantId, person_uid: PersonUID) -> None:
        if (await self._identity.get_person(tenant_id, person_uid)) is None:
            raise NotFoundError("person not found", details={"person_uid": str(person_uid)})

    # --- D3 (ENG-4) additions: Account + upsert_lead change-detection ---

    async def record_account(
        self,
        tenant_id: TenantId,
        *,
        provider: str,
        source_id: str,
        name: str,
        raw: dict[str, Any] | None = None,
    ) -> Account:
        """Idempotent account upsert keyed by ``(provider, source_id)``.

        Returns the existing row when called twice with the same key; only
        ``name`` and ``raw`` are refreshed on the second call (so a renamed
        SF Account flows through). The W1 Salesforce worker calls this
        for every Lead's parent Account.

        ``provider`` must be in :data:`packages.ops.models.ACCOUNT_PROVIDERS`;
        the DB CHECK enforces it as a safety net.
        """
        if provider not in ACCOUNT_PROVIDERS:
            raise ValidationError(
                "unknown provider",
                details={"provider": provider, "allowed": list(ACCOUNT_PROVIDERS)},
            )
        if not source_id:
            raise ValidationError("source_id must be a non-empty string")
        if not name:
            raise ValidationError("name must be a non-empty string")

        existing = await self._repo.find_account(tenant_id, provider, source_id)
        if existing is not None:
            # Refresh display fields if they drifted.
            if existing.name != name:
                existing.name = name
            if raw is not None:
                existing.raw = dict(raw)
            return existing

        account = Account(
            tenant_id=tenant_id,
            provider=provider,
            source_id=source_id,
            name=name,
            raw=dict(raw or {}),
        )
        return await self._repo.add_account(account)

    async def upsert_lead(
        self,
        tenant_id: TenantId,
        *,
        person_uid: UUID,
        raw: dict[str, Any],
        provider_metadata: dict[str, Any] | None = None,
    ) -> UpsertLeadResult:
        """Insert a Lead for a person, or detect changes on re-pull.

        Phase 1 contract:
          * Keyed by ``person_uid`` — one Lead row per person. (When a
            person legitimately has multiple Leads in SF, that's a future
            schema rev; today we collapse them.)
          * ``raw`` is the full provider record (e.g. SF Lead row). The
            change-detection looks at two derived fields stored under
            ``Lead.extra``: ``lead_status`` (mirrors SF ``Status``) and
            ``lead_source`` (mirrors SF ``LeadSource``).
          * ``provider_metadata`` (optional) — a dict merged into
            ``Lead.extra`` ON CREATION ONLY. Existing rows keep whatever
            metadata was stored on first observation; subsequent re-pulls
            refresh only the watched ``lead_status`` / ``lead_source`` keys.
            Use this to carry provider-specific identifiers (``sf_lead_id``,
            ``is_reactivation``, …) without growing the schema.
          * Returns :class:`UpsertLeadResult` — workers use ``was_created``
            and ``was_changed`` to decide on ``interaction.event`` emission
            (see plan §3 W1 pipeline).

        We do NOT store the full ``raw`` row on the Lead — it lives in
        ``ingest.raw_event`` already. Duplicating it here would double the
        write volume and confuse the source of truth.
        """
        new_status = raw.get("Status")
        new_source = raw.get("LeadSource")

        existing = await self._repo.find_lead_by_person(tenant_id, person_uid)
        if existing is None:
            extra: dict[str, Any] = {"lead_status": new_status, "lead_source": new_source}
            if provider_metadata:
                # provider_metadata wins over the watched defaults if it sets
                # the same keys; that lets a provider override mirroring if
                # its raw shape differs from SF.
                extra = {**extra, **provider_metadata}
            lead = Lead(
                tenant_id=tenant_id,
                person_uid=person_uid,
                source=new_source,
                extra=extra,
            )
            await self._repo.add_lead(lead)
            return UpsertLeadResult(lead=lead, was_created=True, was_changed=True)

        old_status = existing.extra.get("lead_status")
        old_source = existing.extra.get("lead_source")

        # Merge any incoming provider_metadata keys that are missing on the
        # existing row. Backfills land here once the projection grows new
        # columns (ENG-255 added assigned_center, business_unit, UTM, …);
        # without this merge a re-pull silently throws away the enrichment.
        # Watched fields (lead_status, lead_source) are tracked separately
        # below; never overwrite a populated extra key from None.
        extra_patch: dict[str, Any] = {}
        if provider_metadata:
            for key, value in provider_metadata.items():
                if value is None:
                    continue
                if key in {"lead_status", "lead_source"}:
                    continue
                if existing.extra.get(key) != value:
                    extra_patch[key] = value

        if (
            new_status == old_status
            and new_source == old_source
            and not extra_patch
        ):
            # No-op re-pull: don't dirty the row, don't emit an event.
            return UpsertLeadResult(lead=existing, was_created=False, was_changed=False)

        existing.extra = {
            **existing.extra,
            **extra_patch,
            "lead_status": new_status,
            "lead_source": new_source,
        }
        if new_source != old_source:
            existing.source = new_source
        was_status_or_source_change = (
            new_status != old_status or new_source != old_source
        )
        return UpsertLeadResult(
            lead=existing,
            was_created=False,
            was_changed=was_status_or_source_change,
        )

    async def find_lead_person_by_converted_opportunity(
        self, tenant_id: TenantId, opportunity_id: str
    ) -> UUID | None:
        """Person behind the lead that converted into this Opportunity.

        ENG-382: backs Opportunity → person resolution in the ingest
        layer. Returns ``None`` when no lead recorded the conversion id
        (pre-ENG-382 rows until their next re-import, or opportunities
        created without lead conversion).
        """
        lead = await self._repo.find_lead_by_converted_opportunity_id(
            tenant_id, opportunity_id
        )
        return lead.person_uid if lead is not None else None

    async def find_lead_person_by_converted_account(
        self, tenant_id: TenantId, account_id: str
    ) -> UUID | None:
        """Person behind the lead that converted into this Account (ENG-382)."""
        lead = await self._repo.find_lead_by_converted_account_id(
            tenant_id, account_id
        )
        return lead.person_uid if lead is not None else None

    async def get_lead_status_counts(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        lead_source: str | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
    ) -> dict[str, int]:
        """Return Lead counts per :class:`LeadStatus` for the dashboard.

        Buckets that have no rows are projected as ``0`` so the caller can
        always render every status without a ``KeyError``.
        """
        from .models import LeadStatus

        raw = await self._repo.count_leads_by_status(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            lead_source=lead_source,
            source_provider=source_provider,
            location_match=location_match,
        )
        return {str(s): int(raw.get(str(s), 0)) for s in LeadStatus}

    async def get_lead_source_counts(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, int]:
        """Return top Lead source buckets for dashboard breakdowns."""
        return await self._repo.count_leads_by_source(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            source_provider=source_provider,
            location_match=location_match,
            limit=limit,
        )

    async def get_lead_source_profile(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
        limit: int = 10,
    ) -> LeadSourceProfileOut:
        """Return the approved lead-source profile analytics query."""
        buckets = await self.get_lead_source_counts(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            source_provider=source_provider,
            location_match=location_match,
            limit=limit,
        )
        return LeadSourceProfileOut(
            total_leads=sum(buckets.values()),
            sources=_analytics_buckets(buckets),
        )

    async def get_conversion_funnel_analytics(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        lead_source: str | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> ConversionFunnelOut:
        """Return the approved lead-to-consultation funnel analytics query."""
        lead_counts = await self.get_lead_status_counts(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_match=location_match,
        )
        consultation_counts = await self.get_consultation_status_counts(
            tenant_id,
            scheduled_from=created_from,
            scheduled_to=created_to,
            source_provider=source_provider,
            location_id=location_id,
        )
        pipeline_total = sum(
            count
            for status, count in lead_counts.items()
            if status not in _PIPELINE_EXCLUDE_STATUSES
        )
        return ConversionFunnelOut(
            lead_status=_analytics_buckets(lead_counts),
            consultation_status=_analytics_buckets(consultation_counts),
            pipeline_total=pipeline_total,
            consultations_total=sum(consultation_counts.values()),
            completed_consultations=consultation_counts.get(
                str(ConsultationStatus.COMPLETED),
                0,
            ),
        )

    async def get_paid_leads_analytics(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
        limit: int = 10,
    ) -> PaidLeadsOut:
        """Return the approved paid-source lead analytics query.

        V1 uses CRM-safe source and campaign labels only. It intentionally
        avoids raw provider payloads and does not infer patient or clinical
        facts.
        """
        buckets = await self._repo.count_paid_leads_by_source(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            source_provider=source_provider,
            location_match=location_match,
            limit=limit,
        )
        return PaidLeadsOut(
            total_paid_leads=sum(buckets.values()),
            sources=_analytics_buckets(buckets),
            classification_terms=_PAID_SOURCE_CLASSIFICATION_TERMS,
        )

    async def get_lead_read_model_quality_evidence(
        self,
        tenant_id: TenantId,
        *,
        read_model_id: str,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        lead_source: str | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, object]:
        """Return aggregate quality evidence for lead-backed manager read models."""
        raw = await self._repo.aggregate_lead_read_model_quality(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            source_provider=source_provider,
            lead_source=lead_source,
            location_match=location_match,
            location_id=location_id,
        )
        total = int(raw.get("total_lead_count", 0))
        linked = int(raw.get("identity_linked_lead_count", 0))
        attributed = int(raw.get("source_attributed_lead_count", 0))
        unmatched = int(raw.get("unmatched_lead_count", 0))
        mismatch = int(raw.get("location_assigned_center_mismatch_count", 0))
        refs = ["lead.person_uid", "lead.lead_source", "lead.campaign"]
        if location_match:
            refs.append("lead.assigned_center")
        if location_id is not None:
            refs.append("consultation.location_id")
        caveats: list[str] = []
        blockers: list[str] = []
        identity_coverage = _coverage_ratio(linked, total)
        source_coverage = _coverage_ratio(attributed, total)
        if total > 0 and linked < total:
            blockers.append(
                "Lead read-model identity linkage coverage is incomplete; manager answer generation is blocked."
            )
        if unmatched > 0:
            caveats.append(
                f"{unmatched} lead aggregate rows lack approved source attribution for read model {read_model_id}."
            )
        if mismatch > 0:
            caveats.append(
                f"{mismatch} lead aggregate rows have assigned-center evidence that conflicts with consultation-location evidence."
            )
        metrics = [
            _quality_ratio_metric(
                "identity_linkage_coverage",
                "Identity linkage coverage",
                identity_coverage,
                numerator=linked,
                denominator=total,
                evidence_ref="lead.person_uid",
                status="blocked" if total > 0 and linked < total else "ok",
            ),
            _quality_ratio_metric(
                "source_attribution_coverage",
                "Source attribution coverage",
                source_coverage,
                numerator=attributed,
                denominator=total,
                evidence_ref="lead.lead_source",
                status="caveat" if unmatched > 0 else "ok",
            ),
            _quality_count_metric(
                "unmatched_lead_count",
                "Unmatched lead count",
                unmatched,
                evidence_ref="lead.lead_source",
                status="caveat" if unmatched > 0 else "ok",
            ),
        ]
        if location_match:
            metrics.append(
                _quality_count_metric(
                    "location_assigned_center_mismatch_count",
                    "Location assigned-center mismatch count",
                    mismatch,
                    evidence_ref="location_mismatch.aggregate",
                    status="caveat" if mismatch > 0 else "ok",
                ),
            )
        return {
            "refs": refs,
            "metrics": metrics,
            "caveats": caveats,
            "blockers": blockers,
        }

    async def consult_counts_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[int, int]]:
        """Net (scheduled, attended) consultation counts per person.

        ``attended`` is COMPLETED; ``scheduled`` is the SCHEDULED status. Lets
        another domain (e.g. ENG-450 attribution) attribute a person's funnel
        progress to its own buckets without importing ``ops.Consultation``.
        """
        rows = await self._repo.count_consultations_by_person_status(tenant_id)
        out: dict[UUID, tuple[int, int]] = {}
        for person_uid, status, count in rows:
            scheduled, attended = out.get(person_uid, (0, 0))
            if status == ConsultationStatus.SCHEDULED.value:
                scheduled += count
            elif status == ConsultationStatus.COMPLETED.value:
                attended += count
            out[person_uid] = (scheduled, attended)
        return out

    async def lead_person_uids_in_month(
        self, tenant_id: TenantId, year_month: str
    ) -> set[UUID]:
        """Persons whose lead was created in ``year_month`` ('YYYY-MM').

        For month-windowed cross-domain views (the ENG-572 attribution tree by
        month): the route passes this set to the attribution service so the
        breakdown reflects only that month's leads.
        """
        return await self._repo.lead_person_uids_in_month(tenant_id, year_month)

    async def get_lead_source_tree(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        collected_by_person: dict[UUID, float] | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> LeadSourceTreeOut:
        """Hierarchical per-source funnel counts for the DEV explorer (ENG-391).

        Tree levels: effective source → utm_medium → utm_campaign. Each
        node carries lead counts plus the SCHEDULED / COMPLETED
        consultation counts of the persons behind those leads; parents
        aggregate their children.

        ``collected_by_person`` (net Collected cash per person, computed by
        the interaction domain and passed in by the route — ops never
        imports interaction) attributes revenue to the node owning each
        person's lead.
        """
        lead_rows = await self._repo.count_lead_funnel_by_source_tree(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            search=search,
            location_match=location_match,
            location_id=location_id,
        )
        consult_rows = await self._repo.count_consultation_funnel_by_source_tree(
            tenant_id,
            statuses=[
                ConsultationStatus.SCHEDULED.value,
                ConsultationStatus.COMPLETED.value,
            ],
            created_from=created_from,
            created_to=created_to,
            search=search,
            location_match=location_match,
            location_id=location_id,
        )

        counts: dict[tuple[str, str, str], _FunnelNodeCounts] = {}
        for source, medium, campaign, lead_count in lead_rows:
            counts.setdefault((source, medium, campaign), _FunnelNodeCounts()).leads += lead_count
        for source, medium, campaign, status, consult_count in consult_rows:
            node = counts.setdefault((source, medium, campaign), _FunnelNodeCounts())
            if status == ConsultationStatus.SCHEDULED.value:
                node.consults_scheduled += consult_count
            elif status == ConsultationStatus.COMPLETED.value:
                node.consults_attended += consult_count

        if collected_by_person:
            person_nodes = await self._repo.map_persons_to_source_nodes(
                tenant_id,
                person_uids=list(collected_by_person),
                created_from=created_from,
                created_to=created_to,
                search=search,
                location_match=location_match,
                location_id=location_id,
            )
            for source, medium, campaign, person_uid in person_nodes:
                node = counts.setdefault((source, medium, campaign), _FunnelNodeCounts())
                node.collected_amount += collected_by_person.get(person_uid, 0.0)

        sources = _build_lead_source_tree(counts)
        return LeadSourceTreeOut(
            total_leads=sum(node.leads for node in sources),
            consults_scheduled=sum(node.consults_scheduled for node in sources),
            consults_attended=sum(node.consults_attended for node in sources),
            collected_amount=round(sum(node.collected_amount for node in sources), 2),
            sources=sources,
        )

    async def get_opportunity_outcomes_by_month(
        self,
        tenant_id: TenantId,
        *,
        close_from: datetime,
        close_to: datetime,
    ) -> list[OpportunityMonthOutcomeOut]:
        """Per-month opportunity outcomes for the full-funnel report (ENG-472).

        One row per ``close_date`` calendar month in ``[close_from,
        close_to)`` carrying closed / won / carryover counts. The full-funnel
        route stitches these month-keyed outcomes onto the per-channel
        lead/consult/revenue rows produced by :meth:`get_lead_source_tree`.
        """
        rows = await self._repo.count_opportunity_outcomes_by_month(
            tenant_id,
            close_from=close_from,
            close_to=close_to,
        )
        return [
            OpportunityMonthOutcomeOut(
                month=month, closed=closed, won=won, carryover=carryover
            )
            for month, closed, won, carryover in rows
        ]

    async def full_funnel_lead_rows(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime,
        created_to: datetime,
    ) -> list[FunnelLeadRow]:
        """Person-anchored SF-lead rows for the Full Funnel report (ENG-481).

        Returns ``(person_uid, channel, month)`` triples (channel collapsed to
        google/facebook/other by the single shared resolver, month bucketed on
        the provider lead created-at). The analytics composition layer dedupes
        persons per stage and per (channel, month) cell.
        """
        rows = await self._repo.full_funnel_lead_rows(
            tenant_id, created_from=created_from, created_to=created_to
        )
        return [FunnelLeadRow(person_uid=p, channel=c, month=m) for p, c, m in rows]

    async def full_funnel_person_channels(
        self, tenant_id: TenantId
    ) -> dict[UUID, str]:
        """Map each lead-bearing person to one funnel channel (ENG-481).

        Drives the marketing audience (a person is marketing iff their channel
        is an ad channel) and attributes consultations / revenue to a channel
        column. Persons without a lead are absent (treated as ``other`` /
        non-marketing by the composition layer).
        """
        return await self._repo.full_funnel_person_channels(tenant_id)

    async def full_funnel_consultation_rows(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime,
        scheduled_to: datetime,
    ) -> list[FunnelConsultationRow]:
        """Person-anchored consultation rows for the Full Funnel report (ENG-481).

        Returns ``(person_uid, status, month, is_past)`` rows anchored on
        ``ops.consultation`` directly (CareStack truth, not joined to leads),
        windowed and month-bucketed on ``scheduled_at``. ``is_past`` flags an
        appointment whose ``scheduled_at`` has already passed so the
        composition layer can resolve a still-``scheduled`` past slot as a
        no-show.
        """
        rows = await self._repo.full_funnel_consultation_rows(
            tenant_id, scheduled_from=scheduled_from, scheduled_to=scheduled_to
        )
        return [
            FunnelConsultationRow(person_uid=p, status=s, month=m, is_past=past)
            for p, s, m, past in rows
        ]

    async def full_funnel_lead_person_uids(self, tenant_id: TenantId) -> set[UUID]:
        """Set of person_uids that have ANY ``ops.lead`` row (ENG-481).

        The Full Funnel composition layer subtracts this set from the
        CareStack-direct universe: a person who is also an SF lead keeps the
        existing lead-date logic and never enters the earliest-activity dating.
        """
        return set(await self._repo.full_funnel_lead_person_uids(tenant_id))

    async def full_funnel_earliest_consultation_at_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, datetime]:
        """``person_uid → MIN(consultation.scheduled_at)`` for every person.

        One GROUP BY aggregate (ENG-481), used to date CareStack-direct persons
        by their earliest real activity. Persons with no consultation are absent.
        """
        return await self._repo.full_funnel_earliest_consultation_at_by_person(
            tenant_id
        )

    async def analytics_lead_facts_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime, str | None]]:
        """``person_uid → (lead_date, source)`` for the analytics fact builder.

        Person-anchored lead created-at (ENG-481/ENG-255) + lead source, one
        GROUP BY aggregate. Persons without a lead are absent (the builder dates
        them as CareStack-direct). See ENG-506.
        """
        return await self._repo.analytics_lead_facts_by_person(tenant_id)

    async def analytics_consultation_facts_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime | None, datetime | None, UUID | None]]:
        """``person_uid → (consult_scheduled_date, show_date, location_id)``.

        For the analytics fact builder (ENG-506): earliest scheduled consult,
        earliest completed ("showed") consult, and the earliest consultation's
        location. Persons with no consultation are absent.
        """
        return await self._repo.analytics_consultation_facts_by_person(tenant_id)

    async def analytics_lead_owner_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, str]:
        """``person_uid → SF Lead.OwnerId`` for the analytics fact builder.

        The caller / Lead Owner SF user id (``extra->>'owner_id'``) of the
        person's earliest lead. The builder resolves it to an ``actor.actor``
        (``caller_id``). Persons without a captured owner_id are absent
        (NULL caller, method=unresolved). See ENG-509.
        """
        return await self._repo.analytics_lead_owner_by_person(tenant_id)

    async def analytics_opportunity_owner_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, str]:
        """``person_uid → SF Opportunity.OwnerId`` for the analytics fact builder.

        The coordinator / Treatment-Coordinator SF user id
        (``extra->>'owner_id'``) of the person's earliest opportunity. The
        builder resolves it to an ``actor.actor`` (``coordinator_id``). Persons
        without an opportunity owner are absent. See ENG-509.
        """
        return await self._repo.analytics_opportunity_owner_by_person(tenant_id)

    async def get_sales_pipeline_summary(
        self, tenant_id: TenantId
    ) -> SalesPipelineSummaryOut:
        """Headline sales-pipeline counts for the Sales dashboard (ENG-473).

        Reads the ``extra.is_closed`` / ``extra.is_won`` JSON booleans (NOT the
        free-form ``stage`` string). The route turns these into KPIs (close
        rate, total Collected via interaction) — ops never imports interaction.
        """
        (
            active_opps,
            closed_opps,
            won_opps,
            pipeline_value,
            won_revenue,
        ) = await self._repo.summarize_sales_pipeline(tenant_id)
        return SalesPipelineSummaryOut(
            active_opps=active_opps,
            closed_opps=closed_opps,
            won_opps=won_opps,
            pipeline_value=round(pipeline_value, 2),
            won_revenue=round(won_revenue, 2),
        )

    async def get_pipeline_by_stage(
        self, tenant_id: TenantId
    ) -> list[SalesStageRowOut]:
        """Opportunities grouped by raw ``stage`` string (Sales dashboard).

        Dynamic grouping — no hardcoded stage ladder; the dashboard renders
        whatever stage strings exist. Ordered by value descending.
        """
        rows = await self._repo.count_opportunities_by_stage(tenant_id)
        return [
            SalesStageRowOut(stage=stage, count=count, value=round(value, 2))
            for stage, count, value in rows
        ]

    async def get_tc_leaderboard(
        self, tenant_id: TenantId
    ) -> list[SalesTcRowOut]:
        """Per-TC opportunity aggregates grouped by ``extra.owner_name``.

        Carries ``person_uids`` per TC so the route can attribute net Collected
        cash via ``InteractionService.collected_by_person`` (ops never imports
        interaction). Close-rate and Collected are derived by the route.
        """
        rows = await self._repo.aggregate_tc_leaderboard(tenant_id)
        return [
            SalesTcRowOut(
                tc=tc,
                opps=opps,
                won=won,
                lost=lost,
                value=round(value, 2),
                won_revenue=round(won_revenue, 2),
                person_uids=person_uids,
            )
            for tc, opps, won, lost, value, won_revenue, person_uids in rows
        ]

    async def list_sales_consultations(
        self, tenant_id: TenantId, *, limit: int = 200
    ) -> list[SalesConsultationRowOut]:
        """Recent consultations joined to their covering opportunity (ENG-473).

        Carries ``person_uid`` so the route can attach the patient identity
        display name and Collected cash. TC / stage / opportunity value /
        close date are ``None`` when no covering opportunity is linked.
        """
        rows = await self._repo.list_sales_consultations(tenant_id, limit=limit)
        out: list[SalesConsultationRowOut] = []
        for consultation, opportunity in rows:
            extra = (opportunity.extra or {}) if opportunity else {}
            out.append(
                SalesConsultationRowOut(
                    consultation_id=consultation.id,
                    person_uid=consultation.person_uid,
                    status=consultation.status,
                    scheduled_at=consultation.scheduled_at,
                    tc=extra.get("owner_name") if opportunity else None,
                    stage=opportunity.stage if opportunity else None,
                    opp_value=(
                        float(opportunity.amount)
                        if opportunity and opportunity.amount is not None
                        else None
                    ),
                    close_date=opportunity.close_date if opportunity else None,
                )
            )
        return out

    async def list_leads_for_source_node(
        self,
        tenant_id: TenantId,
        *,
        channel: str | None = None,
        source: str | None = None,
        medium: str | None = None,
        campaign: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
        collected_by_person: dict[UUID, float] | None = None,
        sort: str = "created",
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> LeadSourceLeadListOut:
        """Paginated drill-down lead list for one explorer node.

        ``collected_by_person`` (interaction-domain net Collected per
        person, passed in by the route; ENG-396) annotates each row with
        the person's cash so the list answers "who actually paid" inline.
        ``sort="collected"`` (ENG-396) floats paying persons to the top (cash
        descending, then newest-first for everyone else).
        """
        if channel is None and source is None:
            raise ValidationError(
                "channel or source is required for a lead-source drill-down",
                details={},
            )
        if sort not in ("created", "collected"):
            raise ValidationError(
                "unsupported lead-source sort", details={"sort": sort}
            )
        priority_person_uids: list[UUID] | None = None
        if sort == "collected" and collected_by_person:
            priority_person_uids = [
                person_uid
                for person_uid, amount in sorted(
                    collected_by_person.items(), key=lambda kv: kv[1], reverse=True
                )
                if amount > 0
            ]
        total, leads = await self._repo.list_leads_for_source_node(
            tenant_id,
            channel=channel,
            source=source,
            medium=medium,
            campaign=campaign,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
            priority_person_uids=priority_person_uids,
            location_match=location_match,
            location_id=location_id,
        )
        # One batched identity lookup per page (ENG-395) — never N+1.
        persons = await self._identity.list_by_ids(
            tenant_id, [lead.person_uid for lead in leads]
        )
        person_by_uid = {person.id: person for person in persons}
        cash = collected_by_person or {}
        # ENG-400: rows that entered the location scope only via consultation
        # evidence (stale assigned_center pointing elsewhere) get flagged so
        # the UI can mark them red.
        location_filter_active = bool(location_match) or location_id is not None
        needles = location_match or []
        return LeadSourceLeadListOut(
            total=total,
            items=[
                _lead_source_lead_item(
                    lead,
                    person_by_uid.get(lead.person_uid),
                    collected_amount=round(cash.get(lead.person_uid, 0.0), 2),
                    location_mismatch=(
                        location_filter_active
                        and not _center_matches(
                            (lead.extra or {}).get("assigned_center"), needles
                        )
                    ),
                )
                for lead in leads
            ],
        )

    async def person_uids_for_lead_source_node(
        self,
        tenant_id: TenantId,
        *,
        channel: str | None = None,
        source: str | None = None,
        medium: str | None = None,
        campaign: str | None = None,
    ) -> list[UUID]:
        """Distinct person_uids behind one lead-source explorer node (ENG-408).

        Powers the PM Payments resource filter: the route resolves the
        selected node to its persons here, then scopes interaction-domain
        payment queries by ``person_uid`` — ops never imports interaction
        and vice versa. No lead-creation window on purpose: the payment
        date is the filter axis, the lead may be arbitrarily old.
        """
        if channel is None and source is None:
            raise ValidationError(
                "channel or source is required for a lead-source node filter",
                details={},
            )
        return await self._repo.person_uids_for_source_node(
            tenant_id,
            channel=channel,
            source=source,
            medium=medium,
            campaign=campaign,
        )

    async def get_lead_field_profile(
        self,
        tenant_id: TenantId,
        *,
        field: str,
        limit: int = 50,
    ) -> OpsFieldProfileOut:
        """Return an aggregate-only profile for an allowlisted Lead field."""
        if field not in {
            "lead_source",
            "source_provider",
            "campaign",
            "owner_id",
            "lead_status",
            "created_at",
            "location_id",
        }:
            raise ValidationError("unsupported lead field profile", details={"field": field})
        raw = await self._repo.profile_lead_field(tenant_id, field=field, limit=limit)
        return _field_profile_from_raw(raw)

    async def get_lead_masked_samples(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
    ) -> list[dict[str, object]]:
        """Return bounded, masked Lead samples for Data Intelligence tooling."""
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be between 1 and 100", details={"limit": limit})
        rows = await self._repo.list_lead_samples(tenant_id, limit=limit)
        return [_lead_masked_sample(row) for row in rows]

    async def has_lead_for(self, tenant_id: TenantId, person_uids: list[UUID]) -> set[UUID]:
        """Return the subset of ``person_uids`` that have at least one Lead."""
        return await self._repo.has_lead_for(tenant_id, person_uids)

    async def list_recent_sf_leads(self, tenant_id: TenantId, limit: int = 5) -> list[Lead]:
        """List the most recently ingested Salesforce-origin leads.

        Filters to leads whose ``extra`` JSONB contains a ``sf_lead_id`` key,
        ordered by ``created_at DESC``. Used by the slice-1 manual-pull UI to
        render the local cache view.
        """
        return await self._repo.list_leads_with_extra_key(tenant_id, "sf_lead_id", limit)

    async def list_leads_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        status: str | None = None,
        lead_source: str | None = None,
        lead_source_match: str = "contains",
        source_provider: str | None = None,
        limit: int = 200,
    ) -> list[LeadOut]:
        """Return dashboard lead rows as safe DTOs."""
        rows = await self._repo.list_leads_for_dashboard(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            status=status,
            lead_source=lead_source,
            lead_source_match=lead_source_match,
            source_provider=source_provider,
            limit=limit,
        )
        return [LeadOut.model_validate(row) for row in rows]

    async def count_leads_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        status: str | None = None,
        lead_source: str | None = None,
        lead_source_match: str = "contains",
        source_provider: str | None = None,
    ) -> int:
        """Return a count for dashboard lead rows."""
        return await self._repo.count_leads_for_dashboard(
            tenant_id,
            created_from=created_from,
            created_to=created_to,
            status=status,
            lead_source=lead_source,
            lead_source_match=lead_source_match,
            source_provider=source_provider,
        )

    # ------------------------------------------------------------ Consultations

    async def upsert_consultation_from_hint(
        self, tenant_id: TenantId, payload: ConsultationIn
    ) -> ConsultationUpsertResult:
        """Idempotent upsert of a consultation row from a normalized hint.

        Called by the CareStack / Salesforce pullers (ENG-218 / ENG-219) once
        per pulled row, AFTER ``IdentityService.resolve_or_create_from_hint``
        has resolved the ``person_uid`` for the same natural key.

        Idempotency key is ``(tenant_id, source_provider, source_instance,
        external_id)`` — repeated pulls return ``was_created=False`` if the
        row already exists. ``was_changed`` is true whenever a watched field
        differs (status, scheduled_at, duration_minutes, consultation_kind,
        location_id, provider_clinician_name).
        """
        if payload.source_provider not in CONSULTATION_PROVIDERS:
            raise ValidationError(
                "unknown consultation provider",
                details={
                    "source_provider": payload.source_provider,
                    "allowed": list(CONSULTATION_PROVIDERS),
                },
            )
        # Validate the person exists in this tenant before linking a
        # consultation to them — prevents orphan consultations if the
        # puller calls us with a stale person_uid.
        person = await self._identity.get_person(tenant_id, PersonUID(payload.person_uid))
        if person is None:
            raise NotFoundError(
                "person not found for consultation upsert",
                details={"person_uid": str(payload.person_uid)},
            )

        existing = await self._repo.find_consultation_by_source(
            tenant_id=tenant_id,
            source_provider=payload.source_provider,
            source_instance=payload.source_instance,
            external_id=payload.external_id,
        )
        if existing is None:
            row = Consultation(
                tenant_id=tenant_id,
                person_uid=payload.person_uid,
                source_provider=payload.source_provider,
                source_instance=payload.source_instance,
                external_id=payload.external_id,
                scheduled_at=payload.scheduled_at,
                provider_created_at=payload.provider_created_at,
                duration_minutes=payload.duration_minutes,
                status=payload.status,
                consultation_kind=payload.consultation_kind,
                location_id=payload.location_id,
                provider_clinician_name=payload.provider_clinician_name,
                provider_carestack_id=payload.provider_carestack_id,
                source_status=payload.source_status,
                raw_event_id=payload.raw_event_id,
                # ENG-417 covering_opportunity_id is intentionally NOT set
                # here — the link is computed AFTER the row exists by the
                # ingest emitter (so the resolver can attribute the
                # operational owner) and persisted via
                # ``attach_consultation_to_opportunity``. Setting it on
                # initial upsert would require a covering-Opportunity
                # lookup inside the upsert path, which would push the
                # cross-row coupling into a function that today only
                # touches the consultation row.
            )
            await self._repo.add_consultation(row)
            # Populate server-default columns (created_at, updated_at) before
            # Pydantic accesses them via from_attributes — otherwise the
            # implicit lazy SELECT raises MissingGreenlet under async sessions
            # with expire_on_commit=False.
            await self._session.refresh(row)
            # Snapshot the DTO BEFORE the location-profile upsert. Adding a
            # PersonLocationProfile triggers an autoflush, which expires
            # ``updated_at`` on the Consultation row (it has onupdate=func.now);
            # a later model_validate then fires a lazy refresh and the
            # MissingGreenlet error returns. Snapshotting now avoids the
            # second round trip and the lazy-load.
            snapshot = ConsultationOut.model_validate(row)
            await self._upsert_person_location_profile_from_consultation(tenant_id, row)
            return ConsultationUpsertResult(
                consultation=snapshot,
                was_created=True,
                was_changed=True,
                was_status_change=False,
                was_scheduled_at_change=False,
            )

        # Existing row — compare watched fields and mutate in place if any
        # changed. ``person_uid`` is intentionally NOT updated here — a
        # consultation's owner is fixed at creation; if a provider re-keys
        # the record to a new person, that is an identity merge concern
        # handled by ``IdentityService``.
        status_before = existing.status
        scheduled_at_before = existing.scheduled_at
        watched_before = (
            status_before,
            scheduled_at_before,
            existing.duration_minutes,
            existing.consultation_kind,
            existing.location_id,
            existing.provider_clinician_name,
            existing.provider_carestack_id,
            existing.source_status,
        )
        existing.status = payload.status
        existing.scheduled_at = payload.scheduled_at
        existing.duration_minutes = payload.duration_minutes
        existing.consultation_kind = payload.consultation_kind
        existing.location_id = payload.location_id
        existing.provider_clinician_name = payload.provider_clinician_name
        existing.provider_carestack_id = payload.provider_carestack_id
        existing.source_status = payload.source_status
        watched_after = (
            existing.status,
            existing.scheduled_at,
            existing.duration_minutes,
            existing.consultation_kind,
            existing.location_id,
            existing.provider_clinician_name,
            existing.provider_carestack_id,
            existing.source_status,
        )
        was_changed = watched_before != watched_after
        was_status_change = status_before != existing.status
        was_scheduled_at_change = scheduled_at_before != existing.scheduled_at
        # Snapshot the DTO BEFORE the location-profile upsert — the autoflush
        # the profile insert triggers expires Consultation.updated_at (due to
        # onupdate=func.now), and a subsequent model_validate would raise
        # MissingGreenlet on the lazy refresh. Same pattern as the
        # was_created branch above.
        snapshot = ConsultationOut.model_validate(existing)
        await self._upsert_person_location_profile_from_consultation(tenant_id, existing)
        return ConsultationUpsertResult(
            consultation=snapshot,
            was_created=False,
            was_changed=was_changed,
            was_status_change=was_status_change,
            was_scheduled_at_change=was_scheduled_at_change,
        )

    async def list_consultations_for_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> list[ConsultationOut]:
        rows = await self._repo.list_consultations_for_person(tenant_id, person_uid)
        return [ConsultationOut.model_validate(r) for r in rows]

    async def get_operational_timeline_projection(
        self,
        tenant_id: TenantId,
        projection_ref_type: str,
        projection_ref_id: UUID,
    ) -> dict[str, object] | None:
        """Return the allowlist-candidate ops snapshot for a timeline ref.

        This method deliberately returns only CRM-safe operational fields.
        ``InteractionService`` applies its own final allowlist before exposing
        the API DTO.
        """
        if projection_ref_type == "ops_lead":
            lead = await self._repo.get_lead(tenant_id, projection_ref_id)
            if lead is None:
                return None
            return {"status": str(lead.status)}

        if projection_ref_type == "ops_consultation":
            consultation = await self._repo.get_consultation(tenant_id, projection_ref_id)
            if consultation is None:
                return None
            return {
                "status": str(consultation.status),
                "scheduled_at": consultation.scheduled_at,
            }

        if projection_ref_type == "ops_followup_task":
            task = await self._repo.get_followup_task(tenant_id, projection_ref_id)
            if task is None:
                return None
            return {"status": str(task.status), "due_at": task.due_at}

        return None

    async def get_lead_for_person(self, tenant_id: TenantId, person_uid: UUID) -> LeadOut | None:
        """Return the (single, Phase 1) Lead for a person as a DTO, or None.

        Used by the staff person-detail read surface to render the
        Lead-status / Lead-source header. Phase 1 keeps a 1:1 mapping.
        """
        row = await self._repo.find_lead_by_person(tenant_id, person_uid)
        return LeadOut.model_validate(row) if row is not None else None

    async def latest_leads_for_persons(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> dict[UUID, LeadOut]:
        """Return the (Phase 1) Lead per person for dashboard rows.

        Phase 1 keeps a 1:1 ``person_uid → Lead`` mapping; the repository
        orders newest-first per person so the first row wins if more than
        one ever exists.
        """
        rows = await self._repo.list_leads_for_persons(tenant_id, person_uids)
        out: dict[UUID, LeadOut] = {}
        for row in rows:
            if row.person_uid not in out:
                out[row.person_uid] = LeadOut.model_validate(row)
        return out

    async def list_consultations_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str | None = None,
        source_instance: str | None = None,
        limit: int = 200,
    ) -> list[ConsultationOut]:
        rows = await self._repo.list_consultations_for_tenant(
            tenant_id,
            source_provider=source_provider,
            source_instance=source_instance,
            limit=limit,
        )
        return [ConsultationOut.model_validate(r) for r in rows]

    async def list_confirmed_due_for_reminder(
        self,
        tenant_id: TenantId,
        *,
        after: datetime,
        until: datetime,
    ) -> list[ConsultationOut]:
        """Confirmed consultations starting in ``(after, until]`` (ENG-486)."""
        rows = await self._repo.list_confirmed_due_for_reminder(
            tenant_id, after=after, until=until
        )
        return [ConsultationOut.model_validate(r) for r in rows]

    async def latest_consultations_for_persons(
        self,
        tenant_id: TenantId,
        person_uids: list[UUID],
        *,
        source_provider: str | None = None,
    ) -> dict[UUID, ConsultationOut]:
        """Return latest consultation per person for dashboard rows."""
        rows = await self._repo.list_latest_consultations_for_persons(
            tenant_id,
            person_uids,
            source_provider=source_provider,
        )
        out: dict[UUID, ConsultationOut] = {}
        for row in rows:
            if row.person_uid not in out:
                out[row.person_uid] = ConsultationOut.model_validate(row)
        return out

    async def _location_tab_by_id(self, tenant_id: TenantId) -> dict[UUID, LocationTab]:
        """Map this tenant's location ids → ENG-560 tab via ``short_name``.

        Only the four recognised short_names participate; any other location
        is absent from the map so a consultation there does not decide a tab.
        """
        locations = await LocationService(self._session).list_locations(tenant_id)
        return {
            loc.id: _TAB_BY_LOCATION_SHORT_NAME[loc.short_name]
            for loc in locations
            if loc.short_name in _TAB_BY_LOCATION_SHORT_NAME
        }

    async def classify_location_tabs(
        self,
        tenant_id: TenantId,
        person_uids: list[UUID],
        *,
        latest_consultations: dict[UUID, ConsultationOut] | None = None,
    ) -> dict[UUID, LocationTab]:
        """Bucket each person into exactly one clinic location tab (ENG-560).

        Operator-fixed precedence (do not "improve"):

        1. A person with ≥1 consultation is decided by their LATEST
           consultation (newest ``scheduled_at`` — see
           :meth:`latest_consultations_for_persons`): its ``location_id``
           resolves through ``tenant.location.short_name`` (GALLERIA→galleria,
           FUSION-ROS→fusion, FUSION-EDH→el_dorado, COSMO→cosmo).
        2. Otherwise the SF ``Assigned_Center__c``
           (``ops.lead.extra->>'assigned_center'``, NBSP-normalized):
           "El Dorado Hills"→el_dorado; everything else (Roseville /
           Galleria OMS / empty / NULL / anything else) → ``galleria``.

        ``fusion`` and ``cosmo`` are reachable only via rule 1; ``galleria`` is
        the default bucket; buckets are mutually exclusive. A consultation
        whose ``location_id`` is null or maps to no recognised short_name does
        not decide a tab — the person falls through to rule 2 so every person
        still lands in exactly one bucket.

        ``latest_consultations`` may be passed in by callers that already
        resolved it (the ``/pm/leads`` handler) to avoid a second query.
        """
        if not person_uids:
            return {}
        if latest_consultations is None:
            latest_consultations = await self.latest_consultations_for_persons(
                tenant_id, person_uids
            )
        tab_by_location_id = await self._location_tab_by_id(tenant_id)
        leads = await self.latest_leads_for_persons(tenant_id, person_uids)
        tabs: dict[UUID, LocationTab] = {}
        for person_uid in person_uids:
            consult = latest_consultations.get(person_uid)
            if consult is not None and consult.location_id is not None:
                tab = tab_by_location_id.get(consult.location_id)
                if tab is not None:
                    tabs[person_uid] = tab
                    continue
            lead = leads.get(person_uid)
            center = lead.extra.get("assigned_center") if lead is not None else None
            tabs[person_uid] = _assigned_center_tab(center)
        return tabs

    async def get_consultation_status_counts(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, int]:
        """Return Consultation counts per status for dashboard read models."""
        raw = await self._repo.count_consultations_by_status(
            tenant_id,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            source_provider=source_provider,
            location_id=location_id,
        )
        return {str(s): int(raw.get(str(s), 0)) for s in ConsultationStatus}

    async def get_consultation_source_counts(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, int]:
        """Return Consultation counts grouped by source provider."""
        return await self._repo.count_consultations_by_source_provider(
            tenant_id,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            location_id=location_id,
        )

    async def get_consultation_location_counts(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        source_provider: str | None = None,
    ) -> dict[str | None, int]:
        """Return Consultation counts grouped by location_id (UUID string)."""
        return await self._repo.count_consultations_by_location(
            tenant_id,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            source_provider=source_provider,
        )

    async def get_open_followup_count(self, tenant_id: TenantId) -> int:
        """Return tenant-wide open followup count."""
        return await self._repo.open_followup_count_for_tenant(tenant_id)

    async def get_overdue_followup_count(self, tenant_id: TenantId, now: datetime) -> int:
        """Return tenant-wide overdue followup count."""
        return await self._repo.overdue_followup_count_for_tenant(tenant_id, now)

    async def get_consultation_followup_analytics(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
        now: datetime,
    ) -> ConsultationFollowupOut:
        """Return the approved consultation follow-up workload query."""
        consultation_counts = await self.get_consultation_status_counts(
            tenant_id,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            source_provider=source_provider,
            location_id=location_id,
        )
        return ConsultationFollowupOut(
            consultation_status=_analytics_buckets(consultation_counts),
            open_followups=await self.get_open_followup_count(tenant_id),
            overdue_followups=await self.get_overdue_followup_count(tenant_id, now),
        )

    async def get_consultation_field_profile(
        self,
        tenant_id: TenantId,
        *,
        field: str,
        limit: int = 50,
    ) -> OpsFieldProfileOut:
        """Return an aggregate-only profile for an allowlisted Consultation field."""
        if field not in {
            "consultation_status",
            "source_provider",
            "scheduled_at",
            "location_id",
        }:
            raise ValidationError(
                "unsupported consultation field profile",
                details={"field": field},
            )
        raw = await self._repo.profile_consultation_field(tenant_id, field=field, limit=limit)
        return _field_profile_from_raw(raw)

    async def get_consultation_masked_samples(
        self,
        tenant_id: TenantId,
        *,
        limit: int = 25,
    ) -> list[dict[str, object]]:
        """Return bounded, masked Consultation samples for Data Intelligence tooling."""
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be between 1 and 100", details={"limit": limit})
        rows = await self._repo.list_consultation_samples(tenant_id, limit=limit)
        return [_consultation_masked_sample(row) for row in rows]

    # ------------------------------------------------------------ Opportunities (ENG-414)

    async def upsert_opportunity(
        self, tenant_id: TenantId, payload: OpportunityIn
    ) -> OpportunityUpsertResult:
        """Idempotent upsert of an SF Opportunity row.

        Called by ``SfOpportunityIngestService`` once per pulled
        Opportunity row, AFTER the raw event is captured.

        Idempotency key is ``(tenant_id, source_provider, source_instance,
        external_id)`` — repeated pulls return ``was_created=False`` if
        the row already exists. ``was_changed`` is true whenever a
        watched field differs (``stage``, ``amount``, ``close_date``,
        ``extra.owner_id``, ``extra.owner_name``).

        ``person_uid`` may be ``None`` when the AccountId fallback fails
        on the first pull; later pulls can backfill it via the same
        upsert call.
        """
        if payload.source_provider not in OPPORTUNITY_PROVIDERS:
            raise ValidationError(
                "unknown opportunity provider",
                details={
                    "source_provider": payload.source_provider,
                    "allowed": list(OPPORTUNITY_PROVIDERS),
                },
            )

        # Optional person existence check — skip when the puller hasn't
        # linked the row yet (Account → person fallback may miss).
        if payload.person_uid is not None:
            person = await self._identity.get_person(
                tenant_id, PersonUID(payload.person_uid)
            )
            if person is None:
                raise NotFoundError(
                    "person not found for opportunity upsert",
                    details={"person_uid": str(payload.person_uid)},
                )

        existing = await self._repo.find_opportunity_by_source(
            tenant_id=tenant_id,
            source_provider=payload.source_provider,
            source_instance=payload.source_instance,
            external_id=payload.external_id,
        )

        new_owner_id = _extra_str(payload.extra, "owner_id")

        if existing is None:
            row = Opportunity(
                tenant_id=tenant_id,
                person_uid=payload.person_uid,
                source_provider=payload.source_provider,
                source_instance=payload.source_instance,
                external_id=payload.external_id,
                name=payload.name,
                stage=payload.stage,
                amount=payload.amount,
                close_date=payload.close_date,
                provider_created_at=payload.provider_created_at,
                raw_event_id=payload.raw_event_id,
                extra=dict(payload.extra),
            )
            await self._repo.add_opportunity(row)
            await self._session.refresh(row)
            return OpportunityUpsertResult(
                opportunity=OpportunityOut.model_validate(row),
                was_created=True,
                was_changed=True,
                was_owner_change=new_owner_id is not None,
                was_stage_change=payload.stage is not None,
            )

        # Watched-field comparison BEFORE mutation.
        old_stage = existing.stage
        old_amount = existing.amount
        old_close_date = existing.close_date
        old_owner_id = _extra_str(existing.extra or {}, "owner_id")
        old_owner_name = _extra_str(existing.extra or {}, "owner_name")

        # ``person_uid`` is backfilled if it was previously NULL.
        # Reassignment (non-NULL → different non-NULL) is treated as an
        # identity-domain merge concern; do not silently re-key.
        if existing.person_uid is None and payload.person_uid is not None:
            existing.person_uid = payload.person_uid

        if payload.name is not None and payload.name != existing.name:
            existing.name = payload.name
        if payload.stage is not None and payload.stage != existing.stage:
            existing.stage = payload.stage
        if payload.amount is not None and payload.amount != existing.amount:
            existing.amount = payload.amount
        if payload.close_date is not None and payload.close_date != existing.close_date:
            existing.close_date = payload.close_date
        if (
            payload.provider_created_at is not None
            and payload.provider_created_at != existing.provider_created_at
        ):
            existing.provider_created_at = payload.provider_created_at
        if payload.raw_event_id is not None:
            existing.raw_event_id = payload.raw_event_id

        # Merge ``extra`` keys — never overwrite an existing key with None.
        merged_extra = dict(existing.extra or {})
        for key, value in payload.extra.items():
            if value is None:
                continue
            merged_extra[key] = value
        existing.extra = merged_extra

        new_owner_id_post = _extra_str(existing.extra, "owner_id")
        new_owner_name_post = _extra_str(existing.extra, "owner_name")

        was_owner_change = (
            old_owner_id != new_owner_id_post
            or old_owner_name != new_owner_name_post
        )
        was_stage_change = old_stage != existing.stage
        was_changed = (
            was_stage_change
            or old_amount != existing.amount
            or old_close_date != existing.close_date
            or was_owner_change
        )

        return OpportunityUpsertResult(
            opportunity=OpportunityOut.model_validate(existing),
            was_created=False,
            was_changed=was_changed,
            was_owner_change=was_owner_change,
            was_stage_change=was_stage_change,
        )

    async def list_opportunities_for_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> list[OpportunityOut]:
        rows = await self._repo.list_opportunities_for_person(tenant_id, person_uid)
        return [OpportunityOut.model_validate(r) for r in rows]

    async def find_covering_opportunity(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        at_moment: datetime,
    ) -> OpportunityOut | None:
        """Return the Opportunity that covers ``at_moment`` for the person.

        See :meth:`OpsRepository.find_covering_opportunity` for the
        selection contract. Returns the DTO (NOT the ORM row) so callers
        in ingest do not pull session-attached models across the
        repo/service boundary.
        """
        row = await self._repo.find_covering_opportunity(
            tenant_id, person_uid, at_moment
        )
        return OpportunityOut.model_validate(row) if row is not None else None

    async def attach_consultation_to_opportunity(
        self,
        tenant_id: TenantId,
        consultation_id: UUID,
        opportunity_id: UUID | None,
    ) -> ConsultationOut | None:
        """Set/clear ``Consultation.covering_opportunity_id`` (ENG-417).

        Idempotent: returns the refreshed DTO when the link changed,
        ``None`` when the consultation was not found, and the existing
        DTO unchanged when the value matched. Walk-ins call this with
        ``opportunity_id=None`` to leave the column NULL — equivalent to
        skipping the call, but explicit for the backfill script.
        """
        existing = await self._repo.get_consultation(tenant_id, consultation_id)
        if existing is None:
            return None
        if existing.covering_opportunity_id == opportunity_id:
            return ConsultationOut.model_validate(existing)
        existing.covering_opportunity_id = opportunity_id
        await self._session.flush()
        await self._session.refresh(existing)
        return ConsultationOut.model_validate(existing)

    async def get_current_funnel_owner(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> CurrentFunnelOwner | None:
        """Return the person's current operational funnel owner (ENG-418).

        Rule (managers-confirmed): Lead owner until an Opportunity exists
        that is not closed-lost; once one exists, the most recently
        created non-closed-lost Opportunity owner takes over.

        Returns a :class:`CurrentFunnelOwner` envelope so the caller can
        identify which stage the person is at (``stage="lead"`` vs
        ``"opportunity"``), and the route layer can append the actor
        display name from ``ActorService``. ``None`` means we have no
        owner information (no Lead row + no Opportunity row).
        """
        opportunities = await self._repo.list_opportunities_for_person(
            tenant_id, person_uid
        )
        # Newest-not-lost first (list_opportunities orders newest first by
        # close_date desc + created_at desc).
        active_opp = next(
            (
                opp
                for opp in opportunities
                if _opportunity_stage(opp.stage) != "closed_lost"
            ),
            None,
        )
        if active_opp is not None:
            owner_id = _extra_str(active_opp.extra or {}, "owner_id")
            owner_name = _extra_str(active_opp.extra or {}, "owner_name")
            if owner_id is not None:
                return CurrentFunnelOwner(
                    stage="opportunity",
                    source_provider="salesforce",
                    external_id=owner_id,
                    owner_name=owner_name,
                    opportunity_id=active_opp.id,
                )
        # Fall through to the Lead owner.
        lead = await self._repo.find_lead_by_person(tenant_id, person_uid)
        if lead is None:
            return None
        extra = lead.extra or {}
        owner_id = _extra_str(extra, "owner_id")
        if owner_id is None:
            return None
        owner_name = _extra_str(extra, "owner_name")
        return CurrentFunnelOwner(
            stage="lead",
            source_provider="salesforce",
            external_id=owner_id,
            owner_name=owner_name,
            opportunity_id=None,
        )

    async def get_lead_owner_id(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> str | None:
        """Return the SF Lead.OwnerId stored in ``Lead.extra['owner_id']``.

        Used by the funnel-responsibility resolver to attribute
        pre-consult events to the call-center agent (Lead owner) and as
        the fallback when a consult has no covering Opportunity.

        ``None`` means we have no Lead record for the person yet OR the
        Lead pull predates the ENG-255 owner_id capture (in which case
        the backfill seeds the column).
        """
        lead = await self._repo.find_lead_by_person(tenant_id, person_uid)
        if lead is None:
            return None
        extra = lead.extra or {}
        owner_id = extra.get("owner_id")
        if isinstance(owner_id, str) and owner_id.strip():
            return owner_id.strip()
        return None

    async def get_opportunity_owner_id(
        self, opportunity: OpportunityOut
    ) -> str | None:
        """Return the SF Opportunity.OwnerId from the DTO's ``extra``.

        Thin helper kept here (rather than on the DTO) so callers don't
        sprinkle ``extra.get("owner_id")`` reads across ingest code; if
        the storage shape ever moves to a typed column this signature
        stays stable.
        """
        owner_id = opportunity.extra.get("owner_id")
        if isinstance(owner_id, str) and owner_id.strip():
            return owner_id.strip()
        return None

    async def sum_opportunity_amount_for_persons(
        self,
        tenant_id: TenantId,
        person_uids: list[UUID],
    ) -> dict[UUID, float]:
        """Batch lookup of ``max(Opportunity.amount)`` per person (ENG-419).

        Used by the funnel drop-off endpoint to attach the $ basis for
        people who never closed (Opportunity.Amount is the only signal
        we have for expected, never-closed revenue). See decision-log
        D-W3-3 for the basis policy.
        """
        return await self._repo.sum_opportunity_amount_for_persons(
            tenant_id, person_uids
        )

    async def list_distinct_opportunity_owner_ids(
        self, tenant_id: TenantId
    ) -> list[str]:
        """Used by the opportunity-owner-name backfill script."""
        return await self._repo.list_distinct_opportunity_owner_ids(tenant_id)

    async def set_opportunity_owner_name(
        self, tenant_id: TenantId, *, owner_id: str, owner_name: str
    ) -> int:
        """Used by the opportunity-owner-name backfill script.

        Returns the row count touched. Idempotent — only differing rows
        are updated.
        """
        if not owner_id:
            raise ValidationError("owner_id required")
        if not owner_name:
            raise ValidationError("owner_name required")
        return await self._repo.set_opportunity_owner_name(
            tenant_id, owner_id, owner_name
        )

    async def list_person_location_profiles_for_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> list[PersonLocationProfileOut]:
        rows = await self._repo.list_person_location_profiles_for_person(tenant_id, person_uid)
        return [PersonLocationProfileOut.model_validate(r) for r in rows]

    async def _upsert_person_location_profile_from_consultation(
        self, tenant_id: TenantId, consultation: Consultation
    ) -> None:
        """Project consultation evidence into the per-location relationship.

        No ``location_id`` means no clinic context, so we skip rather than
        creating an ambiguous location profile. Scheduled/no-show/cancelled
        evidence can create or update a prospect profile. Only completed
        consultation evidence promotes the relationship to patient.
        """
        if consultation.location_id is None:
            return

        relationship_status = _relationship_status_from_consultation(consultation.status)
        promotes_patient = consultation.status == ConsultationStatus.COMPLETED

        existing = await self._repo.find_person_location_profile(
            tenant_id,
            consultation.person_uid,
            consultation.location_id,
        )
        if existing is None:
            profile = PersonLocationProfile(
                tenant_id=tenant_id,
                person_uid=consultation.person_uid,
                location_id=consultation.location_id,
                relationship_kind=(
                    RelationshipKind.PATIENT if promotes_patient else RelationshipKind.PROSPECT
                ),
                relationship_status=relationship_status,
                last_evidence_provider=consultation.source_provider,
                last_evidence_source_instance=consultation.source_instance,
                last_evidence_external_id=consultation.external_id,
                last_evidence_at=consultation.scheduled_at,
                last_consultation_id=consultation.id,
                last_raw_event_id=consultation.raw_event_id,
            )
            await self._repo.add_person_location_profile(profile)
            return

        if promotes_patient:
            existing.relationship_kind = RelationshipKind.PATIENT
        existing.relationship_status = relationship_status
        existing.last_evidence_provider = consultation.source_provider
        existing.last_evidence_source_instance = consultation.source_instance
        existing.last_evidence_external_id = consultation.external_id
        existing.last_evidence_at = consultation.scheduled_at
        existing.last_consultation_id = consultation.id
        existing.last_raw_event_id = consultation.raw_event_id


def _relationship_status_from_consultation(
    status: ConsultationStatus,
) -> RelationshipStatus:
    if status == ConsultationStatus.COMPLETED:
        return RelationshipStatus.CONSULT_COMPLETED
    if status in {ConsultationStatus.CANCELLED}:
        return RelationshipStatus.CANCELLED
    if status == ConsultationStatus.NO_SHOW:
        return RelationshipStatus.NO_SHOW
    return RelationshipStatus.CONSULT_SCHEDULED


def _build_lead_source_tree(
    counts: dict[tuple[str, str, str], _FunnelNodeCounts],
) -> list[LeadSourceNodeOut]:
    """Roll (source, medium, campaign) leaf counts up into a sorted tree.

    ENG-394: a virtual **channel** level tops the tree — source labels
    that mention a known channel (fb pixel forms, adwords, …) group under
    that channel; unmapped labels are their own channel. Sibling order is
    leads-descending at every level so the heaviest resources surface
    first; the "unknown" bucket competes on equal footing rather than
    being pinned.
    """
    nested: dict[str, dict[str, dict[str, dict[str, _FunnelNodeCounts]]]] = {}
    for (source, medium, campaign), node_counts in counts.items():
        channel = _channel_of_source(source)
        nested.setdefault(channel, {}).setdefault(source, {}).setdefault(medium, {})[
            campaign
        ] = node_counts

    def _node(key: str, label: str, level: str, children: list[LeadSourceNodeOut],
              leaf: _FunnelNodeCounts | None = None) -> LeadSourceNodeOut:
        if leaf is not None:
            leads, scheduled, attended, collected = (
                leaf.leads,
                leaf.consults_scheduled,
                leaf.consults_attended,
                leaf.collected_amount,
            )
        else:
            leads = sum(c.leads for c in children)
            scheduled = sum(c.consults_scheduled for c in children)
            attended = sum(c.consults_attended for c in children)
            collected = sum(c.collected_amount for c in children)
        return LeadSourceNodeOut(
            key=key,
            label=label,
            level=level,
            leads=leads,
            consults_scheduled=scheduled,
            consults_attended=attended,
            collected_amount=round(collected, 2),
            children=children,
        )

    channels: list[LeadSourceNodeOut] = []
    for channel, sources_map in nested.items():
        source_nodes: list[LeadSourceNodeOut] = []
        for source, mediums in sources_map.items():
            medium_nodes: list[LeadSourceNodeOut] = []
            for medium, campaigns in mediums.items():
                campaign_nodes = [
                    _node(
                        f"{channel}/{source}/{medium}/{campaign}",
                        campaign,
                        "campaign",
                        [],
                        leaf=leaf,
                    )
                    for campaign, leaf in campaigns.items()
                ]
                campaign_nodes.sort(key=lambda n: n.leads, reverse=True)
                medium_nodes.append(
                    _node(f"{channel}/{source}/{medium}", medium, "medium", campaign_nodes)
                )
            medium_nodes.sort(key=lambda n: n.leads, reverse=True)
            source_nodes.append(_node(f"{channel}/{source}", source, "source", medium_nodes))
        source_nodes.sort(key=lambda n: n.leads, reverse=True)
        channels.append(_node(channel, channel, "channel", source_nodes))
    channels.sort(key=lambda n: n.leads, reverse=True)
    return channels


def explorer_source_label_for_lead(lead: Any) -> str:
    """Explorer source label (lowercased, last-touch first) for one Lead.

    Python mirror of ``repository._explorer_source_label`` — MUST keep the
    same coalesce order so a row labelled here visibly belongs to the
    explorer node that counted it. Accepts any Lead-shaped object exposing
    ``extra`` / ``source`` (ORM row, ``LeadOut``); used by the PM Payments
    Source column (ENG-408) and the explorer drill-down items.
    """
    extra = getattr(lead, "extra", None) or {}
    label = (
        extra.get("last_touch_source")
        or extra.get("utm_source")
        or extra.get("hubspot_lead_source")
        or extra.get("lead_source")
        or getattr(lead, "source", None)
        or _UNKNOWN_BUCKET
    )
    return str(label).lower()


def owner_label_for_lead(lead: Any) -> str | None:
    """Human-facing SF Lead owner for dashboard rows (ENG-408).

    Prefers the ``Owner.Name`` mirror (captured from the ENG-408 SF
    projection onward; older rows backfill on the next lead re-pull),
    falling back to the raw ``OwnerId`` so the column is never silently
    empty when ownership is known.
    """
    extra = getattr(lead, "extra", None) or {}
    owner = extra.get("owner_name") or extra.get("owner_id")
    return str(owner) if owner else None


def _lead_source_lead_item(
    lead: Lead,
    person: Any = None,
    *,
    collected_amount: float = 0.0,
    location_mismatch: bool = False,
) -> LeadSourceLeadItemOut:
    """Project one Lead row into the explorer drill-down DTO.

    The Python coalesce chains MUST mirror the SQL label expressions in
    ``repository._explorer_source_label`` / ``_lead_medium_label`` /
    ``_lead_campaign_label`` (last-touch first, lowercased — ENG-393) so
    the listed rows visibly belong to the node the user clicked.
    """
    extra = lead.extra or {}
    medium = extra.get("last_touch_medium") or extra.get("utm_medium")
    campaign = (
        extra.get("last_touch_campaign")
        or extra.get("utm_campaign")
        or extra.get("campaign")
        or extra.get("campaign_name")
    )
    attribution = {
        key: value
        for key, value in extra.items()
        if key in _LEAD_ATTRIBUTION_EXTRA_KEYS and value is not None
    }
    display_name = person.display_name if person is not None else None
    email = (
        next((i.value for i in person.identifiers if i.kind == "email"), None)
        if person is not None
        else None
    )
    phone = (
        next((i.value for i in person.identifiers if i.kind == "phone"), None)
        if person is not None
        else None
    )
    return LeadSourceLeadItemOut(
        id=lead.id,
        person_uid=lead.person_uid,
        display_name=display_name,
        email=email,
        phone=phone,
        collected_amount=collected_amount,
        assigned_center=extra.get("assigned_center"),
        location_mismatch=location_mismatch,
        status=LeadStatus(lead.status),
        source_label=explorer_source_label_for_lead(lead),
        utm_medium=str(medium).lower() if medium else None,
        utm_campaign=str(campaign).lower() if campaign else None,
        created_at=lead.created_at,
        provider_created_at=_parse_provider_iso_or_none(extra.get("sf_created_at"))
        or lead.created_at,
        attribution=attribution,
    )


def _analytics_buckets(raw: dict[str, int]) -> list[AnalyticsBucketOut]:
    """Convert aggregate maps into stable API/tool bucket DTOs."""
    return [
        AnalyticsBucketOut(
            key=key,
            label=key.replace("_", " ").title(),
            count=int(count),
        )
        for key, count in raw.items()
    ]


def _coverage_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)


def _quality_ratio_metric(
    metric_id: str,
    label: str,
    value: float,
    *,
    numerator: int,
    denominator: int,
    evidence_ref: str,
    status: str,
) -> dict[str, object]:
    return {
        "id": metric_id,
        "label": label,
        "value": value,
        "unit": "ratio",
        "numerator": numerator,
        "denominator": denominator,
        "status": status,
        "evidence_ref": evidence_ref,
    }


def _quality_count_metric(
    metric_id: str,
    label: str,
    value: int,
    *,
    evidence_ref: str,
    status: str,
) -> dict[str, object]:
    return {
        "id": metric_id,
        "label": label,
        "value": value,
        "unit": "count",
        "status": status,
        "evidence_ref": evidence_ref,
    }


def _field_profile_from_raw(raw: dict[str, object]) -> OpsFieldProfileOut:
    top_values = raw.get("top_values")
    if not isinstance(top_values, list):
        top_values = []
    return OpsFieldProfileOut(
        row_count=_raw_int(raw.get("row_count")),
        null_count=_raw_int(raw.get("null_count")),
        top_values=[
            FieldValueBucketOut(
                value=str(item.get("value")),
                count=_raw_int(item.get("count")),
            )
            for item in top_values
            if isinstance(item, dict)
        ],
    )


def _extra_str(extra: dict[str, object], key: str) -> str | None:
    """Return ``extra[key]`` as a stripped string, or ``None`` if absent/empty."""
    value = extra.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _raw_int(value: object) -> int:
    return int(str(value or 0))


def _lead_masked_sample(row: Lead) -> dict[str, object]:
    campaign = row.extra.get("campaign") or row.extra.get("campaign_name")
    owner = row.extra.get("owner_id") or row.extra.get("owner_name")
    return {
        "person_uid_masked": _mask_identifier(row.person_uid),
        "lead_source": _redact_sample_text(row.source or row.extra.get("lead_source")),
        "source_provider": "salesforce" if row.extra.get("sf_lead_id") else "unknown",
        "campaign": _redact_sample_text(campaign),
        "owner_id_masked": _mask_optional_identifier(owner),
        "lead_status": str(row.status),
        "created_at": row.created_at.isoformat(),
        "location_evidence": _redact_sample_text(row.extra.get("assigned_center")),
    }


def _consultation_masked_sample(row: Consultation) -> dict[str, object]:
    return {
        "person_uid_masked": _mask_identifier(row.person_uid),
        "consultation_status": str(row.status),
        "scheduled_at": row.scheduled_at.isoformat(),
        "source_provider": row.source_provider,
        "source_external_id_masked": _mask_identifier(row.external_id),
        "location_id": str(row.location_id) if row.location_id is not None else None,
    }


def _mask_optional_identifier(value: object) -> str | None:
    if value is None:
        return None
    return _mask_identifier(value)


def _mask_identifier(value: object) -> str:
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def _redact_sample_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = _EMAIL_RE.sub("[redacted]", text)
    return _PHONE_RE.sub("[redacted]", text)
