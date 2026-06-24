"""Ops repository — strictly data access.

This repository is forbidden from importing anything from ``packages.phi``.
The codebase enforces this by code review and by CI lint (see ``ruff`` config).

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, case, cast, false, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, aggregate_order_by
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import (
    Account,
    Consultation,
    FollowupStatus,
    FollowupTask,
    Lead,
    Opportunity,
    PersonLocationProfile,
)

# SF Assigned_Center__c values arrive with non-breaking spaces (U+00A0) —
# 'El Dorado\xa0Hills' — so a plain-space needle never substring-matches.
_NBSP = " "


def _lead_assigned_center_predicate(needles: list[str]):
    """Soft-match Lead.extra->>'assigned_center' against any of ``needles``.

    Salesforce's ``Assigned_Center__c`` is free text (e.g.
    "Fusion Dental Implants - El Dorado Hills"); the dashboard's Location
    filter needs to map it back to the canonical ``tenant.location`` row.
    The endpoint resolves the chosen ``location_id`` to its short_name /
    name / city and passes those strings here; this predicate matches if
    any of them appears in the assigned_center text (case-insensitive,
    NBSP-normalized on both sides — ENG-398 found 6,306 EDH leads carrying
    U+00A0 instead of spaces). Approximate by design — future work pins a
    real ``ops.lead.location_id`` column at insert time via SF
    Assigned_Center normalization.
    """
    center = func.replace(
        func.lower(Lead.extra["assigned_center"].astext), _NBSP, " "
    )
    clauses = [
        center.like(f"%{n.lower().replace(_NBSP, ' ')}%") for n in needles if n
    ]
    if not clauses:
        return false()
    return or_(*clauses)


def _explorer_location_predicate(
    tenant_id: TenantId,
    location_match: list[str] | None,
    location_id: UUID | None,
):
    """Evidence-based location scope for the lead-source explorer (ENG-400).

    A lead belongs to a location when its ``assigned_center`` soft-matches
    the location's needles OR the person has a consultation booked at that
    location — bulk-imported SF leads carry stale centers while the
    patient's real life happens elsewhere. Returns ``None`` when no
    location filter is active. ``tenant_id`` is bound as a literal so the
    consultation subquery stays UNCORRELATED (a correlated variant
    re-executed per lead row and hung the 62k-row aggregates). The PM
    dashboard keeps the pure assigned_center predicate.
    """
    clauses = []
    if location_match:
        clauses.append(_lead_assigned_center_predicate(location_match))
    if location_id is not None:
        consult_persons = (
            select(Consultation.person_uid)
            .where(Consultation.location_id == location_id)
            .where(Consultation.tenant_id == tenant_id)
        )
        clauses.append(Lead.person_uid.in_(consult_persons))
    if not clauses:
        return None
    return or_(*clauses)


_PAID_SOURCE_TERMS = (
    "google",
    "meta",
    "facebook",
    "instagram",
    "ppc",
    "paid",
    "adwords",
    "paid search",
    "paid social",
)


def _paid_lead_source_predicate():
    """Best-effort paid-source classifier over CRM-safe lead metadata.

    This deliberately uses allowlisted marketing labels only. It does not read
    raw provider payloads and does not infer clinical or PHI-bearing facts.
    """
    candidates = (
        func.lower(func.coalesce(Lead.source, "")),
        func.lower(func.coalesce(Lead.extra["lead_source"].astext, "")),
        func.lower(func.coalesce(Lead.extra["utm_source"].astext, "")),
        func.lower(func.coalesce(Lead.extra["utm_medium"].astext, "")),
        func.lower(func.coalesce(Lead.extra["campaign"].astext, "")),
        func.lower(func.coalesce(Lead.extra["campaign_name"].astext, "")),
    )
    clauses = [
        candidate.like(f"%{term}%")
        for candidate in candidates
        for term in _PAID_SOURCE_TERMS
    ]
    return or_(*clauses)


def _lead_source_label():
    """Stable source label used by dashboard and analytics aggregates.

    ENG-382 "effective source": this clinic's SF org barely uses the
    standard ``LeadSource`` (83 of 62,483 leads) — the real attribution
    lives in ``Hubspot_Lead_Source__c`` (~17.7k) and ``utm_source__c``
    (~18.6k), mirrored into ``Lead.extra``. The coalesce chain prefers
    the explicit CRM source, then the HubSpot mirror, then the UTM
    source, so dashboards, the PM Source filter, and exact-match
    filtering all see the same label.
    """
    return func.coalesce(
        Lead.source,
        Lead.extra["lead_source"].astext,
        Lead.extra["hubspot_lead_source"].astext,
        Lead.extra["utm_source"].astext,
        "unknown",
    )


def _explorer_source_label():
    """Top hierarchy level for the lead-source explorer (ENG-391/ENG-393).

    Last-touch first: leads re-enter from a different resource over
    time, so the explorer attributes each lead to its most recent touch
    (`last_touch_source`, ENG-382), then the UTM source, then the CRM
    mirrors. `lower()` merges "Facebook" (CRM/HubSpot label) with
    "facebook" (utm_source) into one bucket.

    Deliberately NOT shared with the PM dashboard `_lead_source_label()`
    — that chain prefers the explicit CRM source and is case-preserving;
    its exact-match filter contract must not drift.
    """
    return func.lower(
        func.coalesce(
            Lead.extra["last_touch_source"].astext,
            Lead.extra["utm_source"].astext,
            Lead.extra["hubspot_lead_source"].astext,
            Lead.extra["lead_source"].astext,
            Lead.source,
            "unknown",
        )
    )


# Virtual channel aliases for the lead-source explorer (ENG-394). Maps a
# lowercased source label onto a canonical acquisition channel by substring
# match — "dental implants lead capturing form (fb pixel retargeted)" lands
# under "facebook". Dev-tool heuristic by design; a reviewed semantic-catalog
# mapping is the future home. Keep in sync with the Python mirror
# ``service._channel_of_source``.
_EXPLORER_CHANNEL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("facebook", ("facebook", "fb")),
    ("google", ("google", "adwords", "youtube")),
)


def _explorer_channel_label():
    """Virtual top hierarchy level for the lead-source explorer (ENG-394).

    CASE over the ENG-393 source label: known channel substrings collapse
    into the canonical channel; everything else stays its own channel, so
    no lead disappears from the tree.
    """
    source = _explorer_source_label()
    whens = [
        (or_(*[source.like(f"%{needle}%") for needle in needles]), channel)
        for channel, needles in _EXPLORER_CHANNEL_ALIASES
    ]
    return case(*whens, else_=source)


# Ad channels recognised by the lead-source resolver. A person whose lead
# resolves to one of these is "marketing" for the Full Funnel v2 audience
# toggle (ENG-481). Anything else (referral / direct / manual / CareStack
# patient with no lead) collapses to the fixed ``other`` channel.
_FUNNEL_AD_CHANNELS: tuple[str, ...] = ("google", "facebook")


def _funnel_channel_label():
    """Collapse the ENG-394 explorer channel onto google/facebook/other.

    The Full Funnel report (ENG-481) reports a fixed three-channel ladder.
    ``_explorer_channel_label`` already maps known ad substrings onto the
    canonical ``google`` / ``facebook`` channels and passes everything else
    through as its own label; this wrapper folds that passthrough tail into
    a single ``other`` bucket so no person disappears and the channel set is
    bounded. Reuses the one resolver — does not fork ``classifyLeadSource``.
    """
    channel = _explorer_channel_label()
    return case(
        (channel == "google", literal("google")),
        (channel == "facebook", literal("facebook")),
        else_=literal("other"),
    )


def _funnel_month_key(ts):
    """``YYYY-MM`` string for a timestamp column, in UTC.

    Each Full Funnel stage buckets on its own timestamp (lead provider
    created-at / consultation.scheduled_at / event.occurred_at) so a person
    can land in different months at different stages (ENG-481 §5).
    """
    return func.to_char(func.timezone("UTC", ts), "YYYY-MM")


def _lead_medium_label():
    """Second hierarchy level for the lead-source explorer (ENG-391/393).

    Last-touch medium wins over the lead's own utm_medium; rows without
    either collapse into the "unknown" bucket so every lead stays
    countable at every tree level.
    """
    return func.lower(
        func.coalesce(
            Lead.extra["last_touch_medium"].astext,
            Lead.extra["utm_medium"].astext,
            "unknown",
        )
    )


def _lead_campaign_label():
    """Third hierarchy level for the lead-source explorer (ENG-391/393).

    Last-touch campaign first, then the ENG-382 `utm_campaign` scalar,
    then the legacy `campaign` / `campaign_name` mirrors.
    """
    return func.lower(
        func.coalesce(
            Lead.extra["last_touch_campaign"].astext,
            Lead.extra["utm_campaign"].astext,
            Lead.extra["campaign"].astext,
            Lead.extra["campaign_name"].astext,
            "unknown",
        )
    )


def _lead_source_predicate(lead_source: str, match: str):
    """Dashboard lead-source filter predicate.

    ``contains`` keeps the historical operator-typed behaviour: ILIKE
    substring over ``Lead.source`` ("Website" matches "Website Form").
    ``exact`` compares against the same coalesced label the source
    aggregates group by, so a value picked from the source dropdown —
    including the ``unknown`` bucket for leads without any source —
    selects exactly the rows counted in that bucket.
    """
    if match == "exact":
        return _lead_source_label() == lead_source
    return Lead.source.ilike(f"%{lead_source}%")

# Provider-side creation timestamp for SF Lead rows. The SOQL pull captures
# Salesforce CreatedDate into Lead.extra['sf_created_at'] (ENG-255 SOQL
# extension); the dashboard filter walks that key cast to timestamptz so a
# 30-day window reflects "when SF created the lead" instead of "when we
# ingested it". Coalesce to Lead.created_at so leads pulled before the
# ENG-255 capture (older rows) still respect the filter.
_LEAD_PROVIDER_CREATED_AT = func.coalesce(
    cast(Lead.extra["sf_created_at"].astext, TIMESTAMP(timezone=True)),
    Lead.created_at,
)

# Provider-side creation timestamp for Consultation rows. Backfilled from
# ``ingest.raw_event.payload->>'createdOn'`` (CareStack) and ``CreatedDate``
# (Salesforce Event) by the d2e3f4a5b6c7 migration; written at insert time
# by the CS appointment / SF event ingest handlers going forward. Coalesce
# to Consultation.scheduled_at keeps the few rows without a backfilled
# value visible inside windows defined by their appointment date.
_CONSULTATION_PROVIDER_CREATED_AT = func.coalesce(
    Consultation.provider_created_at,
    Consultation.scheduled_at,
)


class OpsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Leads ---
    async def latest_lead_for(self, tenant_id: TenantId, person_uid: UUID) -> Lead | None:
        stmt = (
            for_tenant(select(Lead), tenant_id, Lead)
            .where(Lead.person_uid == person_uid)
            .order_by(Lead.created_at.desc(), Lead.id.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_lead_by_person(self, tenant_id: TenantId, person_uid: UUID) -> Lead | None:
        """Return the (single, Phase 1) Lead row for a person, or None.

        Phase 1 keeps a 1:1 (person_uid → Lead) mapping for simplicity. If
        multiple SF Leads ever map to one canonical person, future schema
        revs add an external-id column and this method specialises.
        """
        stmt = (
            for_tenant(select(Lead), tenant_id, Lead).where(Lead.person_uid == person_uid).limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_leads_for_persons(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> list[Lead]:
        """Return the (Phase 1) Lead rows for a list of persons.

        Phase 1 keeps a 1:1 ``person_uid → Lead`` mapping, so at most one row
        per person; the dashboard payments read model batches the lookup so a
        page of N payment rows requires one query, not N.
        """
        if not person_uids:
            return []
        stmt = (
            for_tenant(select(Lead), tenant_id, Lead)
            .where(Lead.person_uid.in_(person_uids))
            .order_by(Lead.person_uid.asc(), Lead.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_lead(self, tenant_id: TenantId, lead_id: UUID) -> Lead | None:
        """Return a tenant-scoped Lead by id."""
        stmt = for_tenant(select(Lead), tenant_id, Lead).where(Lead.id == lead_id).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_lead(self, lead: Lead) -> Lead:
        self._session.add(lead)
        await self._session.flush()
        return lead

    async def reassign_leads(
        self, tenant_id: TenantId, from_person_uid: UUID, to_person_uid: UUID
    ) -> int:
        """Re-point every Lead of ``from_person_uid`` at ``to_person_uid``.

        Data-only. Used after an identity merge collapses a duplicate person
        into a surviving canonical one (ENG-544 replay live pass): the merged
        person's leads must follow the survivor. ``person_uid`` is a plain
        indexed column with no unique constraint, so the bulk UPDATE never
        collides. Returns the number of leads moved.
        """
        result = await self._session.execute(
            update(Lead)
            .where(Lead.tenant_id == tenant_id)
            .where(Lead.person_uid == from_person_uid)
            .values(person_uid=to_person_uid)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def list_leads_with_extra_key(
        self, tenant_id: TenantId, key: str, limit: int
    ) -> list[Lead]:
        """List leads whose ``extra`` JSONB contains ``key``, newest first.

        Used to filter provider-origin leads (e.g. those with ``sf_lead_id``
        in ``extra``). The ``? text`` JSONB operator hits the GIN index on
        ``extra`` if one exists; otherwise it sequence-scans, which is fine
        at Phase 1 row counts.
        """
        stmt = (
            for_tenant(select(Lead), tenant_id, Lead)
            .where(Lead.extra.has_key(key))  # noqa: W601 — SQLAlchemy JSONB operator
            .order_by(Lead.created_at.desc(), Lead.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_lead_by_converted_opportunity_id(
        self, tenant_id: TenantId, opportunity_id: str
    ) -> Lead | None:
        """Lead whose SF conversion produced the given Opportunity.

        ENG-382 funnel glue: the lead pull stores
        ``extra['converted_opportunity_id']`` (SF ``ConvertedOpportunityId``),
        and the lead already knows its ``person_uid`` — so an Opportunity
        resolves to a person without account/contact links.
        """
        return await self._find_lead_by_extra_key(
            tenant_id, "converted_opportunity_id", opportunity_id
        )

    async def find_lead_by_converted_account_id(
        self, tenant_id: TenantId, account_id: str
    ) -> Lead | None:
        """Lead whose SF conversion produced the given Account (ENG-382)."""
        return await self._find_lead_by_extra_key(
            tenant_id, "converted_account_id", account_id
        )

    async def _find_lead_by_extra_key(
        self, tenant_id: TenantId, key: str, value: str
    ) -> Lead | None:
        stmt = (
            for_tenant(select(Lead), tenant_id, Lead)
            .where(Lead.extra[key].astext == value)
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

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
    ) -> list[Lead]:
        """List lead rows for PM dashboard drilldowns, newest first."""
        stmt = for_tenant(select(Lead), tenant_id, Lead)
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if lead_source is not None:
            stmt = stmt.where(_lead_source_predicate(lead_source, lead_source_match))
        if source_provider == "salesforce":
            stmt = stmt.where(Lead.extra.has_key("sf_lead_id"))  # noqa: W601
        elif source_provider is not None:
            stmt = stmt.where(false())
        stmt = stmt.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_lead_samples(self, tenant_id: TenantId, *, limit: int) -> list[Lead]:
        """Return bounded Lead rows for service-level masked samples."""
        stmt = (
            for_tenant(select(Lead), tenant_id, Lead)
            .order_by(Lead.created_at.desc(), Lead.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

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
        """Count lead rows for PM dashboard drilldowns."""
        stmt = for_tenant(select(func.count()).select_from(Lead), tenant_id, Lead)
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if lead_source is not None:
            stmt = stmt.where(_lead_source_predicate(lead_source, lead_source_match))
        if source_provider == "salesforce":
            stmt = stmt.where(Lead.extra.has_key("sf_lead_id"))  # noqa: W601
        elif source_provider is not None:
            stmt = stmt.where(false())
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_leads_by_status(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        lead_source: str | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
    ) -> dict[str, int]:
        """Aggregate Lead row counts grouped by ``status``.

        Returns a dict keyed by status string (matches
        :class:`LeadStatus` values). Missing statuses are NOT filled in
        here — the caller decides whether to project the zero buckets.
        """
        stmt = for_tenant(
            select(Lead.status, func.count()).select_from(Lead),
            tenant_id,
            Lead,
        )
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if lead_source is not None:
            # ILIKE substring — operator types "Website" and we match
            # "Website Form" too. Lead source values are vendor-defined free
            # text, so prefix/exact match would be too strict.
            stmt = stmt.where(Lead.source.ilike(f"%{lead_source}%"))
        if source_provider == "salesforce":
            stmt = stmt.where(Lead.extra.has_key("sf_lead_id"))  # noqa: W601
        elif source_provider is not None:
            stmt = stmt.where(false())
        if location_match:
            stmt = stmt.where(_lead_assigned_center_predicate(location_match))
        stmt = stmt.group_by(Lead.status)
        rows = (await self._session.execute(stmt)).all()
        return {str(status): int(count) for status, count in rows}

    async def count_leads_by_source(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, int]:
        """Aggregate Lead row counts grouped by source label."""
        source_label = _lead_source_label()
        stmt = for_tenant(
            select(source_label, func.count()).select_from(Lead),
            tenant_id,
            Lead,
        )
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if source_provider == "salesforce":
            stmt = stmt.where(Lead.extra.has_key("sf_lead_id"))  # noqa: W601
        elif source_provider is not None:
            stmt = stmt.where(false())
        if location_match:
            stmt = stmt.where(_lead_assigned_center_predicate(location_match))
        stmt = stmt.group_by(source_label).order_by(func.count().desc()).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        return {str(source): int(count) for source, count in rows}

    async def count_paid_leads_by_source(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        location_match: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, int]:
        """Aggregate paid-source Lead counts grouped by source label."""
        source_label = _lead_source_label()
        stmt = for_tenant(
            select(source_label, func.count()).select_from(Lead),
            tenant_id,
            Lead,
        ).where(_paid_lead_source_predicate())
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if source_provider == "salesforce":
            stmt = stmt.where(Lead.extra.has_key("sf_lead_id"))  # noqa: W601
        elif source_provider is not None:
            stmt = stmt.where(false())
        if location_match:
            stmt = stmt.where(_lead_assigned_center_predicate(location_match))
        stmt = stmt.group_by(source_label).order_by(func.count().desc()).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        return {str(source): int(count) for source, count in rows}

    async def aggregate_lead_read_model_quality(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        source_provider: str | None = None,
        lead_source: str | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, int]:
        """Return aggregate quality counters for lead-backed read models."""
        source_label = _lead_source_label()
        source_known = func.lower(func.trim(source_label)).notin_(("", "unknown"))
        mismatch_count: Any = literal(0)
        location_pred = None
        assigned_center_pred = None
        if location_match:
            assigned_center_pred = _lead_assigned_center_predicate(location_match)
            location_pred = _explorer_location_predicate(
                tenant_id,
                location_match,
                location_id,
            )
            if location_pred is not None:
                mismatch_count = func.count().filter(
                    location_pred & ~assigned_center_pred
                )
        elif location_id is not None:
            location_pred = _explorer_location_predicate(
                tenant_id,
                None,
                location_id,
            )
        stmt = for_tenant(
            select(
                func.count().label("total_lead_count"),
                func.count()
                .filter(Lead.person_uid.is_not(None))
                .label("identity_linked_lead_count"),
                func.count().filter(source_known).label("source_attributed_lead_count"),
                func.count().filter(~source_known).label("unmatched_lead_count"),
                mismatch_count.label("location_assigned_center_mismatch_count"),
            ).select_from(Lead),
            tenant_id,
            Lead,
        )
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if lead_source is not None:
            stmt = stmt.where(Lead.source.ilike(f"%{lead_source}%"))
        if source_provider == "salesforce":
            stmt = stmt.where(Lead.extra.has_key("sf_lead_id"))  # noqa: W601
        elif source_provider is not None:
            stmt = stmt.where(false())
        if location_pred is not None:
            stmt = stmt.where(location_pred)
        row = (await self._session.execute(stmt)).one()
        return {key: int(value or 0) for key, value in row._mapping.items()}

    async def count_lead_funnel_by_source_tree(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> list[tuple[str, str, str, int]]:
        """Lead counts grouped by (source, medium, campaign) labels.

        Feeds the ENG-391 lead-source explorer tree. The period filter
        walks the provider-side creation timestamp (same window the PM
        dashboard exposes); ``search`` is a case-insensitive substring
        match over any of the three node labels.
        """
        source_label = _explorer_source_label()
        medium_label = _lead_medium_label()
        campaign_label = _lead_campaign_label()
        stmt = for_tenant(
            select(source_label, medium_label, campaign_label, func.count()).select_from(Lead),
            tenant_id,
            Lead,
        )
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if search:
            needle = f"%{search}%"
            stmt = stmt.where(
                or_(
                    source_label.ilike(needle),
                    medium_label.ilike(needle),
                    campaign_label.ilike(needle),
                )
            )
        location_pred = _explorer_location_predicate(tenant_id, location_match, location_id)
        if location_pred is not None:
            stmt = stmt.where(location_pred)
        stmt = stmt.group_by(source_label, medium_label, campaign_label)
        rows = (await self._session.execute(stmt)).all()
        return [
            (str(source), str(medium), str(campaign), int(count))
            for source, medium, campaign, count in rows
        ]

    async def count_consultation_funnel_by_source_tree(
        self,
        tenant_id: TenantId,
        *,
        statuses: list[str],
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> list[tuple[str, str, str, str, int]]:
        """Consultation counts per (source, medium, campaign, status).

        Joins ``ops.consultation`` to ``ops.lead`` on the shared
        ``person_uid`` (Phase 1 keeps the mapping 1:1, so the join cannot
        fan out lead-side). The period/search filters mirror
        :meth:`count_lead_funnel_by_source_tree` — they scope the LEAD
        side, so each tree node counts the consultations of exactly the
        persons whose leads form that node.
        """
        source_label = _explorer_source_label()
        medium_label = _lead_medium_label()
        campaign_label = _lead_campaign_label()
        stmt = (
            select(
                source_label,
                medium_label,
                campaign_label,
                Consultation.status,
                func.count(),
            )
            .select_from(Consultation)
            .join(Lead, Lead.person_uid == Consultation.person_uid)
            .where(Consultation.status.in_(statuses))
        )
        stmt = for_tenant(stmt, tenant_id, Consultation)
        stmt = for_tenant(stmt, tenant_id, Lead)
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if search:
            needle = f"%{search}%"
            stmt = stmt.where(
                or_(
                    source_label.ilike(needle),
                    medium_label.ilike(needle),
                    campaign_label.ilike(needle),
                )
            )
        location_pred = _explorer_location_predicate(tenant_id, location_match, location_id)
        if location_pred is not None:
            stmt = stmt.where(location_pred)
        stmt = stmt.group_by(source_label, medium_label, campaign_label, Consultation.status)
        rows = (await self._session.execute(stmt)).all()
        return [
            (str(source), str(medium), str(campaign), str(status), int(count))
            for source, medium, campaign, status, count in rows
        ]

    async def map_persons_to_source_nodes(
        self,
        tenant_id: TenantId,
        *,
        person_uids: list[UUID],
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> list[tuple[str, str, str, UUID]]:
        """Map persons to their (source, medium, campaign) tree node.

        Used to attribute per-person collected cash to explorer nodes
        (ENG-391). DISTINCT keeps one row per (node, person) so an amount
        is never double-counted; filters mirror
        :meth:`count_lead_funnel_by_source_tree` so attribution follows
        exactly the leads that formed the node.
        """
        if not person_uids:
            return []
        source_label = _explorer_source_label()
        medium_label = _lead_medium_label()
        campaign_label = _lead_campaign_label()
        stmt = for_tenant(
            select(source_label, medium_label, campaign_label, Lead.person_uid)
            .select_from(Lead)
            .distinct(),
            tenant_id,
            Lead,
        ).where(Lead.person_uid.in_(person_uids))
        if created_from is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            stmt = stmt.where(_LEAD_PROVIDER_CREATED_AT < created_to)
        if search:
            needle = f"%{search}%"
            stmt = stmt.where(
                or_(
                    source_label.ilike(needle),
                    medium_label.ilike(needle),
                    campaign_label.ilike(needle),
                )
            )
        location_pred = _explorer_location_predicate(tenant_id, location_match, location_id)
        if location_pred is not None:
            stmt = stmt.where(location_pred)
        rows = (await self._session.execute(stmt)).all()
        return [
            (str(source), str(medium), str(campaign), person_uid)
            for source, medium, campaign, person_uid in rows
        ]

    # --- Full Funnel v2 (person-anchored) reads (ENG-481) ---
    async def full_funnel_lead_rows(
        self,
        tenant_id: TenantId,
        *,
        created_from: datetime,
        created_to: datetime,
    ) -> list[tuple[UUID, str, str]]:
        """``(person_uid, funnel_channel, YYYY-MM)`` for SF leads in window.

        The window walks the provider-side lead created-at
        (``extra.sf_created_at`` ?? ``created_at``); the month key buckets on
        the same timestamp. The channel is the collapsed google/facebook/other
        label from the single shared resolver. One row per
        ``(person_uid, channel, month)`` — the composition layer dedupes
        persons. A person with several leads can therefore contribute to
        several (channel, month) cells; that is intentional (last-touch leads
        re-enter over time), and distinct-person counting happens above.
        """
        channel = _funnel_channel_label()
        month = _funnel_month_key(_LEAD_PROVIDER_CREATED_AT)
        stmt = (
            for_tenant(
                select(Lead.person_uid, channel, month).select_from(Lead).distinct(),
                tenant_id,
                Lead,
            )
            .where(_LEAD_PROVIDER_CREATED_AT >= created_from)
            .where(_LEAD_PROVIDER_CREATED_AT < created_to)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(person_uid, str(ch), str(mon)) for person_uid, ch, mon in rows]

    async def full_funnel_person_channels(
        self, tenant_id: TenantId
    ) -> dict[UUID, str]:
        """Map every person with an SF lead to a single funnel channel.

        Used to (a) decide the marketing audience (a person is marketing iff
        their channel is an ad channel) and (b) attribute that person's
        consultations / revenue to a channel column. When a person's leads
        resolve to more than one channel, an ad channel wins over ``other``
        and ``facebook`` is preferred over ``google`` only for determinism;
        the audience test only cares whether *any* lead is an ad channel, so
        the precedence never changes the marketing⊆all invariant.

        Persons without any lead (CareStack-direct) are simply absent from the
        map; the composition layer treats them as ``other`` / non-marketing.
        """
        channel = _funnel_channel_label()
        stmt = for_tenant(
            select(Lead.person_uid, channel).select_from(Lead).distinct(),
            tenant_id,
            Lead,
        )
        rows = (await self._session.execute(stmt)).all()
        # Precedence: facebook > google > other, applied deterministically so
        # a multi-lead person resolves to one stable column.
        rank = {"facebook": 0, "google": 1, "other": 2}
        best: dict[UUID, str] = {}
        for person_uid, ch in rows:
            ch_s = str(ch)
            current = best.get(person_uid)
            if current is None or rank[ch_s] < rank[current]:
                best[person_uid] = ch_s
        return best

    async def full_funnel_consultation_rows(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime,
        scheduled_to: datetime,
    ) -> list[tuple[UUID, str, str, bool]]:
        """``(person_uid, status, YYYY-MM, is_past)`` for consultations in window.

        Anchored on ``ops.consultation`` directly (CareStack is the source of
        truth — NOT joined to ``ops.lead``), so CareStack-direct patients are
        counted. The window and month key both use ``scheduled_at`` (the
        booking/appointment time). Status is the raw consultation status; the
        composition layer maps ``completed`` → showed and ``no_show`` →
        no-show, excludes ``deleted``, and counts at the appointment level.

        ``is_past`` is ``scheduled_at < now()`` evaluated in SQL (ENG-481): a
        still-``scheduled`` appointment whose slot has already passed is a
        no-show (the patient never showed and the slot is gone), while a future
        ``scheduled`` appointment is genuinely pending. The composition layer
        applies that time-dependent rule.
        """
        month = _funnel_month_key(Consultation.scheduled_at)
        is_past = Consultation.scheduled_at < func.now()
        stmt = (
            for_tenant(
                select(
                    Consultation.person_uid,
                    Consultation.status,
                    month,
                    is_past,
                ),
                tenant_id,
                Consultation,
            )
            .where(Consultation.scheduled_at >= scheduled_from)
            .where(Consultation.scheduled_at < scheduled_to)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            (person_uid, str(status), str(mon), bool(past))
            for person_uid, status, mon, past in rows
        ]

    async def full_funnel_lead_person_uids(self, tenant_id: TenantId) -> list[UUID]:
        """DISTINCT person_uids that have ANY ``ops.lead`` row (ENG-481).

        All-time. The Full Funnel composition layer subtracts this set from the
        CareStack-direct universe so a person who is also an SF lead (SF-only or
        SF+CareStack linked) keeps the existing lead-date logic and is excluded
        from the earliest-activity CareStack-direct dating.
        """
        stmt = for_tenant(
            select(Lead.person_uid).select_from(Lead).distinct(),
            tenant_id,
            Lead,
        )
        rows = (await self._session.execute(stmt)).all()
        return [person_uid for (person_uid,) in rows]

    async def full_funnel_earliest_consultation_at_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, datetime]:
        """``person_uid → MIN(consultation.scheduled_at)`` for every person.

        One GROUP BY aggregate over ``ops.consultation`` (ENG-481), not N
        queries and no giant bound IN clause (the CareStack-direct universe is
        ~50k persons — well past asyncpg's parameter cap). The composition layer
        looks up only the CareStack-direct person_uids it cares about; persons
        with no consultation are simply absent from the map.
        """
        stmt = (
            for_tenant(
                select(
                    Consultation.person_uid,
                    func.min(Consultation.scheduled_at),
                ).select_from(Consultation),
                tenant_id,
                Consultation,
            ).group_by(Consultation.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {person_uid: earliest for person_uid, earliest in rows}

    async def analytics_lead_facts_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime, str | None]]:
        """``person_uid → (lead_date, source)`` for every lead-bearing person.

        For the analytics fact builder (ENG-506). ``lead_date`` is the
        person-anchored provider lead created-at (``extra.sf_created_at`` ??
        ``created_at``, ENG-481/ENG-255), taken as the earliest across a
        person's leads; ``source`` is the lead source (Phase 1 is 1:1
        person→lead, so ``min`` is deterministic and stable). One GROUP BY
        aggregate, no bound IN. Persons without a lead are absent.
        """
        stmt = for_tenant(
            select(
                Lead.person_uid,
                func.min(_LEAD_PROVIDER_CREATED_AT),
                func.min(Lead.source),
            ).select_from(Lead),
            tenant_id,
            Lead,
        ).group_by(Lead.person_uid)
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: (lead_date, source)
            for person_uid, lead_date, source in rows
            if person_uid is not None
        }

    async def analytics_consultation_facts_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[datetime | None, datetime | None, UUID | None]]:
        """``person_uid → (consult_scheduled_date, show_date, location_id)``.

        For the analytics fact builder (ENG-506), one GROUP BY aggregate over
        ``ops.consultation``:

        - ``consult_scheduled_date`` = ``MIN(scheduled_at)`` (any status).
        - ``show_date`` = ``MIN(scheduled_at)`` over ``completed`` rows only
          (``completed`` is the "showed" state).
        - ``location_id`` = the location of the earliest-scheduled consultation
          that carries one (``array_agg(location_id ORDER BY scheduled_at)``
          filtered to non-null, first element).

        Persons with no consultation are absent.
        """
        location_first = func.array_agg(
            aggregate_order_by(  # type: ignore[no-untyped-call]
                Consultation.location_id, Consultation.scheduled_at.asc()
            )
        ).filter(Consultation.location_id.isnot(None))
        stmt = for_tenant(
            select(
                Consultation.person_uid,
                func.min(Consultation.scheduled_at),
                func.min(Consultation.scheduled_at).filter(
                    Consultation.status == "completed"
                ),
                location_first[1],
            ).select_from(Consultation),
            tenant_id,
            Consultation,
        ).group_by(Consultation.person_uid)
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: (consult_scheduled, show, location_id)
            for person_uid, consult_scheduled, show, location_id in rows
            if person_uid is not None
        }

    async def analytics_lead_owner_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, str]:
        """``person_uid → SF Lead.OwnerId`` (the caller / Lead Owner, ENG-509).

        The owner of the person's EARLIEST lead (``extra->>'owner_id'``), so a
        person with several leads attributes deterministically to the first
        caller. One GROUP BY aggregate; persons whose lead carries no
        ``owner_id`` (pre-ENG-255 capture) are absent. SF user ids are NOT
        PII — they are opaque ``005…`` / ``00G…`` identifiers.
        """
        owner_expr = Lead.extra["owner_id"].astext
        owner_first = func.array_agg(
            aggregate_order_by(  # type: ignore[no-untyped-call]
                owner_expr, _LEAD_PROVIDER_CREATED_AT.asc()
            )
        ).filter(owner_expr.isnot(None))
        stmt = for_tenant(
            select(Lead.person_uid, owner_first[1]).select_from(Lead),
            tenant_id,
            Lead,
        ).group_by(Lead.person_uid)
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: owner_id
            for person_uid, owner_id in rows
            if person_uid is not None and owner_id
        }

    async def analytics_opportunity_owner_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, str]:
        """``person_uid → SF Opportunity.OwnerId`` (the coordinator / TC, ENG-509).

        The owner of the person's EARLIEST opportunity
        (``extra->>'owner_id'`` ordered by ``provider_created_at`` falling back
        to ``created_at``). Opportunities with no resolved ``person_uid`` or no
        ``owner_id`` are skipped. One GROUP BY aggregate.
        """
        owner_expr = Opportunity.extra["owner_id"].astext
        order_expr = func.coalesce(
            Opportunity.provider_created_at, Opportunity.created_at
        )
        owner_first = func.array_agg(
            aggregate_order_by(  # type: ignore[no-untyped-call]
                owner_expr, order_expr.asc()
            )
        ).filter(owner_expr.isnot(None))
        stmt = (
            for_tenant(
                select(Opportunity.person_uid, owner_first[1]).select_from(
                    Opportunity
                ),
                tenant_id,
                Opportunity,
            )
            .where(Opportunity.person_uid.isnot(None))
            .group_by(Opportunity.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: owner_id
            for person_uid, owner_id in rows
            if person_uid is not None and owner_id
        }

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
        priority_person_uids: list[UUID] | None = None,
        location_match: list[str] | None = None,
        location_id: UUID | None = None,
    ) -> tuple[int, list[Lead]]:
        """Paginated Lead rows behind one lead-source explorer node.

        ``channel``/``source``/``medium``/``campaign`` compare against the
        same label expressions the tree groups by, so a node's drill-down
        lists exactly the rows counted in that node (including the
        "unknown" buckets and ENG-394 virtual channel nodes).

        ``priority_person_uids`` (ENG-396 Collected sort): when set, rows
        whose ``person_uid`` appears in the list sort first, in list
        order (``array_position`` — the caller pre-sorts ids by cash
        descending), with everyone else following newest-first. The
        repository stays cash-agnostic; the interaction domain owns the
        amounts.
        """
        conditions: list[Any] = []
        if channel is not None:
            conditions.append(_explorer_channel_label() == channel)
        if source is not None:
            conditions.append(_explorer_source_label() == source)
        if medium is not None:
            conditions.append(_lead_medium_label() == medium)
        if campaign is not None:
            conditions.append(_lead_campaign_label() == campaign)
        if created_from is not None:
            conditions.append(_LEAD_PROVIDER_CREATED_AT >= created_from)
        if created_to is not None:
            conditions.append(_LEAD_PROVIDER_CREATED_AT < created_to)
        location_pred = _explorer_location_predicate(tenant_id, location_match, location_id)
        if location_pred is not None:
            conditions.append(location_pred)

        count_stmt = for_tenant(
            select(func.count()).select_from(Lead), tenant_id, Lead
        ).where(*conditions)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        order_by: list[Any] = []
        if priority_person_uids:
            order_by.append(
                func.array_position(
                    cast(literal(priority_person_uids), ARRAY(PG_UUID(as_uuid=True))),
                    Lead.person_uid,
                )
                .asc()
                .nulls_last()
            )
        order_by.extend([_LEAD_PROVIDER_CREATED_AT.desc(), Lead.id.desc()])

        page_stmt = (
            for_tenant(select(Lead), tenant_id, Lead)
            .where(*conditions)
            .order_by(*order_by)
            .limit(limit)
            .offset(offset)
        )
        leads = list((await self._session.execute(page_stmt)).scalars().all())
        return total, leads

    async def person_uids_for_source_node(
        self,
        tenant_id: TenantId,
        *,
        channel: str | None = None,
        source: str | None = None,
        medium: str | None = None,
        campaign: str | None = None,
    ) -> list[UUID]:
        """Distinct person_uids whose Lead belongs to one explorer node.

        Same label expressions as :meth:`list_leads_for_source_node`, but
        deliberately WITHOUT a lead-creation window: the PM Payments
        resource filter (ENG-408) scopes payments by *payment* date while
        attributing each payer to the source of their (possibly years-old)
        lead, so every lead under the node participates regardless of when
        it was created.
        """
        conditions: list[Any] = []
        if channel is not None:
            conditions.append(_explorer_channel_label() == channel)
        if source is not None:
            conditions.append(_explorer_source_label() == source)
        if medium is not None:
            conditions.append(_lead_medium_label() == medium)
        if campaign is not None:
            conditions.append(_lead_campaign_label() == campaign)
        stmt = for_tenant(
            select(Lead.person_uid).distinct(), tenant_id, Lead
        ).where(*conditions)
        return list((await self._session.execute(stmt)).scalars().all())

    async def profile_lead_field(
        self,
        tenant_id: TenantId,
        *,
        field: str,
        limit: int,
    ) -> dict[str, object]:
        """Aggregate-profile an allowlisted Lead field."""
        value_expr, null_predicate = _lead_profile_expression(field)
        return await self._profile_expression(
            tenant_id,
            model=Lead,
            value_expr=value_expr,
            null_predicate=null_predicate,
            limit=limit,
        )

    async def has_lead_for(self, tenant_id: TenantId, person_uids: list[UUID]) -> set[UUID]:
        """Return the subset of ``person_uids`` that have at least one Lead."""
        if not person_uids:
            return set()
        stmt = for_tenant(select(Lead.person_uid).distinct(), tenant_id, Lead).where(
            Lead.person_uid.in_(person_uids)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return set(rows)

    # --- Followups ---
    async def add_followup(self, task: FollowupTask) -> FollowupTask:
        self._session.add(task)
        await self._session.flush()
        return task

    async def open_followup_count(self, tenant_id: TenantId, person_uid: UUID) -> int:
        stmt = (
            for_tenant(
                select(func.count()).select_from(FollowupTask),
                tenant_id,
                FollowupTask,
            )
            .where(FollowupTask.person_uid == person_uid)
            .where(FollowupTask.status == FollowupStatus.OPEN)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def open_followup_count_for_tenant(self, tenant_id: TenantId) -> int:
        """Return open followup tasks across the tenant."""
        stmt = for_tenant(
            select(func.count()).select_from(FollowupTask),
            tenant_id,
            FollowupTask,
        ).where(FollowupTask.status == FollowupStatus.OPEN)
        return int((await self._session.execute(stmt)).scalar_one())

    async def overdue_followup_count_for_tenant(self, tenant_id: TenantId, now: datetime) -> int:
        """Return open followups whose due date has passed."""
        stmt = (
            for_tenant(
                select(func.count()).select_from(FollowupTask),
                tenant_id,
                FollowupTask,
            )
            .where(FollowupTask.status == FollowupStatus.OPEN)
            .where(FollowupTask.due_at.is_not(None))
            .where(FollowupTask.due_at < now)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def get_followup_task(self, tenant_id: TenantId, task_id: UUID) -> FollowupTask | None:
        """Return a tenant-scoped FollowupTask by id."""
        stmt = (
            for_tenant(select(FollowupTask), tenant_id, FollowupTask)
            .where(FollowupTask.id == task_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_followups(self, tenant_id: TenantId, person_uid: UUID) -> list[FollowupTask]:
        stmt = (
            for_tenant(select(FollowupTask), tenant_id, FollowupTask)
            .where(FollowupTask.person_uid == person_uid)
            .order_by(FollowupTask.due_at.asc().nullslast())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # --- Accounts ---
    async def find_account(
        self, tenant_id: TenantId, provider: str, source_id: str
    ) -> Account | None:
        stmt = (
            for_tenant(select(Account), tenant_id, Account)
            .where(Account.provider == provider)
            .where(Account.source_id == source_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_account(self, account: Account) -> Account:
        self._session.add(account)
        await self._session.flush()
        return account

    # --- Consultations ---
    async def find_consultation_by_source(
        self,
        tenant_id: TenantId,
        source_provider: str,
        source_instance: str,
        external_id: str,
    ) -> Consultation | None:
        """Idempotency lookup for the cron-driven puller.

        Returns the existing row for the natural key
        ``(tenant_id, source_provider, source_instance, external_id)`` so
        the service can decide between insert and update without racing the
        UNIQUE constraint.
        """
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .where(Consultation.source_provider == source_provider)
            .where(Consultation.source_instance == source_instance)
            .where(Consultation.external_id == external_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_consultation(self, consultation: Consultation) -> Consultation:
        self._session.add(consultation)
        await self._session.flush()
        return consultation

    async def get_consultation(
        self, tenant_id: TenantId, consultation_id: UUID
    ) -> Consultation | None:
        """Return a tenant-scoped Consultation by id."""
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .where(Consultation.id == consultation_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_consultations_for_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> list[Consultation]:
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .where(Consultation.person_uid == person_uid)
            .order_by(Consultation.scheduled_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_latest_consultations_for_persons(
        self,
        tenant_id: TenantId,
        person_uids: list[UUID],
        *,
        source_provider: str | None = None,
    ) -> list[Consultation]:
        """Return consultations for persons newest-first for dashboard projection.

        Tie-break rules when two consultations share a ``person_uid`` and a
        ``scheduled_at`` (the same slot booked twice in CareStack — e.g. an
        old cancelled record + a fresh scheduled one): prefer non-cancelled
        (so an active appointment surfaces, not its cancelled predecessor),
        then the newest ``provider_created_at`` (the operator-side booking
        time), then the largest ``id`` so the result is deterministic.
        """
        if not person_uids:
            return []
        status_priority = case(
            (Consultation.status == "cancelled", 1),
            else_=0,
        )
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .where(Consultation.person_uid.in_(person_uids))
            .order_by(
                Consultation.person_uid.asc(),
                Consultation.scheduled_at.desc(),
                status_priority.asc(),
                Consultation.provider_created_at.desc().nulls_last(),
                Consultation.id.desc(),
            )
        )
        if source_provider is not None:
            stmt = stmt.where(Consultation.source_provider == source_provider)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_consultations_for_tenant(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str | None = None,
        source_instance: str | None = None,
        limit: int = 200,
    ) -> list[Consultation]:
        stmt = for_tenant(select(Consultation), tenant_id, Consultation)
        if source_provider is not None:
            stmt = stmt.where(Consultation.source_provider == source_provider)
        if source_instance is not None:
            stmt = stmt.where(Consultation.source_instance == source_instance)
        stmt = stmt.order_by(Consultation.scheduled_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_confirmed_due_for_reminder(
        self,
        tenant_id: TenantId,
        *,
        after: datetime,
        until: datetime,
    ) -> list[Consultation]:
        """Confirmed consultations starting in ``(after, until]`` (ENG-486).

        Drives the T-15m reminder scan: ``source_status == 'Confirmed'`` (the
        verbatim CareStack status preserved by ENG-487 — the bucketed
        ``status`` collapses it) and a start strictly after ``after`` and at or
        before ``until``. Ordered soonest-first. At-most-once delivery is the
        caller's concern (the durable dedupe ledger keyed on consultation id).
        """
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .where(
                Consultation.source_status == "Confirmed",
                Consultation.scheduled_at > after,
                Consultation.scheduled_at <= until,
            )
            .order_by(Consultation.scheduled_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_consultation_samples(
        self,
        tenant_id: TenantId,
        *,
        limit: int,
    ) -> list[Consultation]:
        """Return bounded Consultation rows for service-level masked samples."""
        stmt = (
            for_tenant(select(Consultation), tenant_id, Consultation)
            .order_by(Consultation.scheduled_at.desc(), Consultation.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def lead_person_uids_in_month(
        self, tenant_id: TenantId, year_month: str
    ) -> set[UUID]:
        """Distinct persons whose lead's provider-side create month is ``year_month``.

        ``year_month`` is ``'YYYY-MM'``; the date is the SF CreatedDate (coalesced
        to ``created_at`` for pre-ENG-255 rows). Lets a month-windowed
        cross-domain view (the ENG-572 attribution tree by month) restrict to the
        persons whose lead was created that month, without attribution importing
        ``ops.Lead`` or a lead date.
        """
        # Pin the month bucket to UTC so it is deterministic regardless of the
        # session TimeZone (deployments run UTC today, but don't depend on it).
        month_bucket = func.to_char(
            _LEAD_PROVIDER_CREATED_AT.op("AT TIME ZONE")("UTC"), "YYYY-MM"
        )
        stmt = (
            for_tenant(select(Lead.person_uid), tenant_id, Lead)
            .where(month_bucket == year_month)
            .where(Lead.person_uid.is_not(None))
            .distinct()
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return {r for r in rows if r is not None}

    async def count_consultations_by_person_status(
        self, tenant_id: TenantId
    ) -> list[tuple[UUID, str, int]]:
        """Consultation counts per (person_uid, status).

        Feeds cross-domain funnel attribution (e.g. the ENG-450 attribution
        tree attributes each person's consults to their resolved chain node).
        Tenant-scoped, unwindowed — the caller maps persons to its own buckets.
        """
        stmt = (
            for_tenant(
                select(
                    Consultation.person_uid,
                    Consultation.status,
                    func.count(),
                ).select_from(Consultation),
                tenant_id,
                Consultation,
            )
            .group_by(Consultation.person_uid, Consultation.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(pid, str(status), int(count)) for pid, status, count in rows]

    async def count_consultations_by_status(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        source_provider: str | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, int]:
        """Aggregate Consultation row counts grouped by status."""
        stmt = for_tenant(
            select(Consultation.status, func.count()).select_from(Consultation),
            tenant_id,
            Consultation,
        )
        if scheduled_from is not None:
            stmt = stmt.where(_CONSULTATION_PROVIDER_CREATED_AT >= scheduled_from)
        if scheduled_to is not None:
            stmt = stmt.where(_CONSULTATION_PROVIDER_CREATED_AT < scheduled_to)
        if source_provider is not None:
            stmt = stmt.where(Consultation.source_provider == source_provider)
        if location_id is not None:
            stmt = stmt.where(Consultation.location_id == location_id)
        stmt = stmt.group_by(Consultation.status)
        rows = (await self._session.execute(stmt)).all()
        return {str(status): int(count) for status, count in rows}

    async def count_consultations_by_location(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        source_provider: str | None = None,
    ) -> dict[str | None, int]:
        """Aggregate Consultation row counts grouped by ``location_id``.

        Returned dict keys are the stringified UUID or ``None`` for rows
        without a location. Filters on ``provider_created_at`` (coalesced
        to ``scheduled_at``) so the count tracks the same window the
        dashboard date filter exposes.
        """
        stmt = for_tenant(
            select(Consultation.location_id, func.count()).select_from(Consultation),
            tenant_id,
            Consultation,
        )
        if scheduled_from is not None:
            stmt = stmt.where(_CONSULTATION_PROVIDER_CREATED_AT >= scheduled_from)
        if scheduled_to is not None:
            stmt = stmt.where(_CONSULTATION_PROVIDER_CREATED_AT < scheduled_to)
        if source_provider is not None:
            stmt = stmt.where(Consultation.source_provider == source_provider)
        stmt = stmt.group_by(Consultation.location_id)
        rows = (await self._session.execute(stmt)).all()
        return {
            (str(loc_id) if loc_id is not None else None): int(count)
            for loc_id, count in rows
        }

    async def count_consultations_by_source_provider(
        self,
        tenant_id: TenantId,
        *,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[str, int]:
        """Aggregate Consultation row counts grouped by provider."""
        stmt = for_tenant(
            select(Consultation.source_provider, func.count()).select_from(Consultation),
            tenant_id,
            Consultation,
        )
        if scheduled_from is not None:
            stmt = stmt.where(_CONSULTATION_PROVIDER_CREATED_AT >= scheduled_from)
        if scheduled_to is not None:
            stmt = stmt.where(_CONSULTATION_PROVIDER_CREATED_AT < scheduled_to)
        if location_id is not None:
            stmt = stmt.where(Consultation.location_id == location_id)
        stmt = stmt.group_by(Consultation.source_provider)
        rows = (await self._session.execute(stmt)).all()
        return {str(provider): int(count) for provider, count in rows}

    async def profile_consultation_field(
        self,
        tenant_id: TenantId,
        *,
        field: str,
        limit: int,
    ) -> dict[str, object]:
        """Aggregate-profile an allowlisted Consultation field."""
        value_expr, null_predicate = _consultation_profile_expression(field)
        return await self._profile_expression(
            tenant_id,
            model=Consultation,
            value_expr=value_expr,
            null_predicate=null_predicate,
            limit=limit,
        )

    # --- Person-location profiles ---
    async def find_person_location_profile(
        self, tenant_id: TenantId, person_uid: UUID, location_id: UUID
    ) -> PersonLocationProfile | None:
        stmt = (
            for_tenant(select(PersonLocationProfile), tenant_id, PersonLocationProfile)
            .where(PersonLocationProfile.person_uid == person_uid)
            .where(PersonLocationProfile.location_id == location_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_person_location_profile(
        self, profile: PersonLocationProfile
    ) -> PersonLocationProfile:
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def list_person_location_profiles_for_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> list[PersonLocationProfile]:
        stmt = (
            for_tenant(select(PersonLocationProfile), tenant_id, PersonLocationProfile)
            .where(PersonLocationProfile.person_uid == person_uid)
            .order_by(PersonLocationProfile.updated_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # --- Opportunities (ENG-414) ---

    async def find_opportunity_by_source(
        self,
        tenant_id: TenantId,
        source_provider: str,
        source_instance: str,
        external_id: str,
    ) -> Opportunity | None:
        """Idempotency lookup for the SF Opportunity puller (ENG-414).

        Returns the existing row for the natural key
        ``(tenant_id, source_provider, source_instance, external_id)`` so
        the service can decide between insert and update without racing
        the UNIQUE constraint.
        """
        stmt = (
            for_tenant(select(Opportunity), tenant_id, Opportunity)
            .where(Opportunity.source_provider == source_provider)
            .where(Opportunity.source_instance == source_instance)
            .where(Opportunity.external_id == external_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_opportunity(self, opportunity: Opportunity) -> Opportunity:
        self._session.add(opportunity)
        await self._session.flush()
        return opportunity

    async def list_opportunities_for_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> list[Opportunity]:
        # ENG-418 (D-W3-2): order by provider_created_at (coalesced to
        # created_at for pre-ENG-414 rows). The funnel-owner rule picks
        # the most-recent non-closed-lost Opportunity by provider_created_at,
        # not by close_date — close_date can be set far in the future on
        # an open Opportunity and would mis-order the funnel-owner lookup.
        anchor = func.coalesce(
            Opportunity.provider_created_at, Opportunity.created_at
        )
        stmt = (
            for_tenant(select(Opportunity), tenant_id, Opportunity)
            .where(Opportunity.person_uid == person_uid)
            .order_by(anchor.desc(), Opportunity.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_covering_opportunity(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        at_moment: datetime,
    ) -> Opportunity | None:
        """Return the Opportunity that "covers" ``at_moment`` for a person.

        Definition (ENG-417): the most recent SF Opportunity for this
        person whose ``provider_created_at`` is at or before ``at_moment``.
        That is the Opportunity that was already open when the consult
        happened, so its OwnerId is the Treatment Coordinator who owned
        the relationship at that moment.

        If no Opportunity precedes the moment (walk-in / pre-Opportunity
        consult), returns ``None`` and the consult attribution degrades
        to clinical-only.

        Coalesces ``provider_created_at`` to ``created_at`` so older
        Opportunities ingested before ENG-414 carried that column are
        still anchored to a comparable point in time.
        """
        anchor = func.coalesce(
            Opportunity.provider_created_at, Opportunity.created_at
        )
        stmt = (
            for_tenant(select(Opportunity), tenant_id, Opportunity)
            .where(Opportunity.person_uid == person_uid)
            .where(anchor <= at_moment)
            .order_by(anchor.desc(), Opportunity.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def sum_opportunity_amount_for_persons(
        self,
        tenant_id: TenantId,
        person_uids: list[UUID],
    ) -> dict[UUID, float]:
        """Return ``{person_uid: max(opportunity.amount)}`` for a batch.

        ENG-419 drop-off attribution uses this to weigh "lost" persons by
        the SF Opportunity.Amount we already have on file. ``max`` is
        chosen (vs sum) because a person typically carries one active
        Opportunity per cycle; summing across re-opens would double-count
        the same expected revenue. Persons with no row contribute zero.
        """
        if not person_uids:
            return {}
        stmt = (
            for_tenant(
                select(
                    Opportunity.person_uid,
                    func.max(Opportunity.amount).label("amount"),
                ).select_from(Opportunity),
                tenant_id,
                Opportunity,
            )
            .where(Opportunity.person_uid.in_(person_uids))
            .where(Opportunity.amount.is_not(None))
            .group_by(Opportunity.person_uid)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row.person_uid: float(row.amount) for row in rows}

    async def count_opportunity_outcomes_by_month(
        self,
        tenant_id: TenantId,
        *,
        close_from: datetime,
        close_to: datetime,
    ) -> list[tuple[str, int, int, int]]:
        """Per-month opportunity outcome counts keyed by ``close_date`` month.

        ENG-472 full-funnel report. Returns one tuple per calendar month
        (``"YYYY-MM"``) that has at least one opportunity with a
        ``close_date`` inside ``[close_from, close_to)``::

            (month, closed_count, won_count, carryover_count)

        - ``closed_count``  — opportunities whose ``extra->>'is_closed'`` is
          true and ``close_date`` falls in the month.
        - ``won_count``     — of those, ``extra->>'is_won'`` is true.
        - ``carryover_count`` — closed opportunities in the month whose
          covering consultation (``consultation.covering_opportunity_id``)
          was *scheduled* in a different calendar month — the funnel's
          "deals closed this month from an earlier consult" signal.

        The month bucket keys off ``close_date`` (the cash/decision moment)
        for every metric here; leads/consults bucket off their own dates in
        the caller. ``is_closed`` / ``is_won`` are JSON booleans on
        ``extra``; the ``->>'..' = 'true'`` text compare matches the
        Postgres JSONB boolean serialisation.
        """
        month = func.to_char(Opportunity.close_date, "YYYY-MM")
        is_closed = Opportunity.extra["is_closed"].astext == "true"
        is_won = Opportunity.extra["is_won"].astext == "true"

        # A scalar-correlated EXISTS that is true when the opportunity is
        # covered by a consultation scheduled in a month other than the
        # opportunity's close month — the carryover signal.
        consult_month = func.to_char(Consultation.scheduled_at, "YYYY-MM")
        carryover_pred = (
            select(literal(1))
            .where(
                Consultation.tenant_id == Opportunity.tenant_id,
                Consultation.covering_opportunity_id == Opportunity.id,
                consult_month != month,
            )
            .exists()
        )

        stmt = (
            for_tenant(
                select(
                    month.label("month"),
                    func.count().filter(is_closed).label("closed"),
                    func.count().filter(is_closed & is_won).label("won"),
                    func.count()
                    .filter(is_closed & carryover_pred)
                    .label("carryover"),
                ).select_from(Opportunity),
                tenant_id,
                Opportunity,
            )
            .where(Opportunity.close_date.is_not(None))
            .where(Opportunity.close_date >= close_from)
            .where(Opportunity.close_date < close_to)
            .group_by(month)
            .order_by(month)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            (row.month, int(row.closed), int(row.won), int(row.carryover))
            for row in rows
        ]

    async def summarize_sales_pipeline(
        self, tenant_id: TenantId
    ) -> tuple[int, int, int, float, float]:
        """Headline sales-pipeline aggregates for the Sales dashboard (ENG-473).

        Returns a single row::

            (active_opps, closed_opps, won_opps, pipeline_value, won_revenue)

        - ``active_opps``    — opportunities NOT marked ``extra.is_closed``.
        - ``closed_opps``    — opportunities marked ``extra.is_closed``.
        - ``won_opps``       — closed opportunities also marked ``extra.is_won``.
        - ``pipeline_value`` — Σ ``amount`` over active (not-closed) opps.
        - ``won_revenue``    — Σ ``amount`` over won opps.

        ``is_closed`` / ``is_won`` are JSONB booleans on ``extra``; the
        ``->>'..' = 'true'`` text compare matches the Postgres JSONB boolean
        serialisation. ``NULL`` amounts contribute 0 to the sums (``coalesce``).
        """
        is_closed = Opportunity.extra["is_closed"].astext == "true"
        is_won = Opportunity.extra["is_won"].astext == "true"
        amount = func.coalesce(Opportunity.amount, 0)
        stmt = for_tenant(
            select(
                func.count().filter(~is_closed).label("active_opps"),
                func.count().filter(is_closed).label("closed_opps"),
                func.count().filter(is_closed & is_won).label("won_opps"),
                func.coalesce(
                    func.sum(amount).filter(~is_closed), 0
                ).label("pipeline_value"),
                func.coalesce(
                    func.sum(amount).filter(is_closed & is_won), 0
                ).label("won_revenue"),
            ).select_from(Opportunity),
            tenant_id,
            Opportunity,
        )
        row = (await self._session.execute(stmt)).one()
        return (
            int(row.active_opps),
            int(row.closed_opps),
            int(row.won_opps),
            float(row.pipeline_value),
            float(row.won_revenue),
        )

    async def count_opportunities_by_stage(
        self, tenant_id: TenantId
    ) -> list[tuple[str, int, float]]:
        """Per-stage opportunity counts + value (Sales pipeline-by-stage tile).

        Groups by the raw free-form ``opportunity.stage`` string (no hardcoded
        ladder — the dashboard renders whatever stages exist). Returns one
        tuple per stage ``(stage, count, value)`` ordered by value descending.
        ``NULL`` stage collapses to the literal ``"(unknown)"`` bucket; ``NULL``
        amounts contribute 0 to the value sum.
        """
        stage = func.coalesce(Opportunity.stage, literal("(unknown)"))
        value = func.coalesce(func.sum(func.coalesce(Opportunity.amount, 0)), 0)
        stmt = (
            for_tenant(
                select(
                    stage.label("stage"),
                    func.count().label("cnt"),
                    value.label("value"),
                ).select_from(Opportunity),
                tenant_id,
                Opportunity,
            )
            .group_by(stage)
            .order_by(value.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row.stage, int(row.cnt), float(row.value)) for row in rows]

    async def aggregate_tc_leaderboard(
        self, tenant_id: TenantId
    ) -> list[tuple[str, int, int, int, float, float, list[UUID]]]:
        """Per-TC opportunity aggregates for the Sales TC leaderboard (ENG-473).

        Groups opportunities by ``extra->>'owner_name'`` (the only TC signal
        we have). Returns one tuple per owner::

            (tc, opps, won, lost, value, won_revenue, person_uids)

        - ``opps``        — total opportunities for the TC.
        - ``won``         — closed AND won (``is_closed`` & ``is_won``).
        - ``lost``        — closed AND NOT won.
        - ``value``       — Σ ``amount`` over all the TC's opportunities.
        - ``won_revenue`` — Σ ``amount`` over the won subset.
        - ``person_uids`` — distinct non-null ``person_uid`` behind the TC's
          opportunities, so the route can attribute Collected cash.

        Opportunities with no ``owner_name`` collapse to ``"(unassigned)"``.
        Close-rate and Collected are derived by the route, not here.
        """
        owner = func.coalesce(
            Opportunity.extra["owner_name"].astext, literal("(unassigned)")
        )
        is_closed = Opportunity.extra["is_closed"].astext == "true"
        is_won = Opportunity.extra["is_won"].astext == "true"
        amount = func.coalesce(Opportunity.amount, 0)
        stmt = (
            for_tenant(
                select(
                    owner.label("tc"),
                    func.count().label("opps"),
                    func.count().filter(is_closed & is_won).label("won"),
                    func.count().filter(is_closed & ~is_won).label("lost"),
                    func.coalesce(func.sum(amount), 0).label("value"),
                    func.coalesce(
                        func.sum(amount).filter(is_closed & is_won), 0
                    ).label("won_revenue"),
                    func.array_remove(
                        func.array_agg(func.distinct(Opportunity.person_uid)),
                        None,
                    ).label("person_uids"),
                ).select_from(Opportunity),
                tenant_id,
                Opportunity,
            )
            .group_by(owner)
            .order_by(func.coalesce(func.sum(amount), 0).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            (
                row.tc,
                int(row.opps),
                int(row.won),
                int(row.lost),
                float(row.value),
                float(row.won_revenue),
                list(row.person_uids or []),
            )
            for row in rows
        ]

    async def list_sales_consultations(
        self, tenant_id: TenantId, *, limit: int
    ) -> list[tuple[Consultation, Opportunity | None]]:
        """Recent consultations joined to their covering opportunity (ENG-473).

        LEFT-joins ``consultation`` → ``opportunity`` via
        ``covering_opportunity_id`` so the Sales consultations table can show
        TC / stage / opportunity value alongside each consultation. Ordered by
        ``scheduled_at`` descending and bounded by ``limit``. The opportunity
        is ``None`` when no covering opportunity is linked.
        """
        stmt = (
            for_tenant(
                select(Consultation, Opportunity).select_from(Consultation),
                tenant_id,
                Consultation,
            )
            .outerjoin(
                Opportunity,
                Consultation.covering_opportunity_id == Opportunity.id,
            )
            .order_by(Consultation.scheduled_at.desc(), Consultation.id.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def list_distinct_opportunity_owner_ids(
        self, tenant_id: TenantId
    ) -> list[str]:
        """Return distinct ``extra->>'owner_id'`` values for an
        Opportunity backfill pass.

        The backfill script reads this once, dedupes against SF Users /
        Groups, and bulk-jsonb_sets ``extra.owner_name`` for every row
        that references each owner id.
        """
        owner_expr = Opportunity.extra["owner_id"].astext
        stmt = (
            for_tenant(
                select(owner_expr).select_from(Opportunity),
                tenant_id,
                Opportunity,
            )
            .where(owner_expr.is_not(None))
            .distinct()
        )
        result = (await self._session.execute(stmt)).scalars().all()
        return [v for v in result if v]

    async def set_opportunity_owner_name(
        self, tenant_id: TenantId, owner_id: str, owner_name: str
    ) -> int:
        """Bulk ``jsonb_set`` of ``extra.owner_name`` for one owner_id.

        Returns the row count touched. Idempotent — only rows whose stored
        ``extra->>'owner_name'`` differs from ``owner_name`` are written,
        so repeated invocations are cheap.
        """
        from sqlalchemy import text as sql_text

        # Use raw SQL for the jsonb_set: SQLAlchemy's JSONB ORM updates
        # would require pulling each row first. The WHERE clause restricts
        # to the (tenant, owner_id) slice and the already-different rows
        # to keep the write idempotent.
        stmt = sql_text(
            """
            UPDATE ops.opportunity
            SET extra = jsonb_set(extra, '{owner_name}', to_jsonb(cast(:owner_name as text)), true),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND extra->>'owner_id' = :owner_id
              AND (extra->>'owner_name' IS DISTINCT FROM :owner_name)
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "tenant_id": tenant_id,
                "owner_id": owner_id,
                "owner_name": owner_name,
            },
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def _profile_expression(
        self,
        tenant_id: TenantId,
        *,
        model: type[Any],
        value_expr: Any,
        null_predicate: Any,
        limit: int,
    ) -> dict[str, object]:
        total_stmt = for_tenant(
            select(
                func.count().label("row_count"),
                func.count().filter(null_predicate).label("null_count"),
            ).select_from(model),
            tenant_id,
            model,
        )
        total_row = (await self._session.execute(total_stmt)).one()

        top_stmt = (
            for_tenant(
                select(value_expr.label("value"), func.count().label("count")).select_from(model),
                tenant_id,
                model,
            )
            .where(value_expr.is_not(None))
            .group_by(value_expr)
            .order_by(func.count().desc())
            .limit(limit)
        )
        top_rows = (await self._session.execute(top_stmt)).all()
        return {
            "row_count": int(total_row.row_count),
            "null_count": int(total_row.null_count),
            "top_values": [
                {"value": str(value), "count": int(count)}
                for value, count in top_rows
                if value is not None
            ],
        }


def _lead_profile_expression(field: str) -> tuple[Any, Any]:
    if field == "lead_source":
        value = _lead_source_label()
        return value, Lead.source.is_(None) & Lead.extra["lead_source"].astext.is_(None)
    if field == "source_provider":
        value = case(
            (Lead.extra.has_key("sf_lead_id"), "salesforce"),  # noqa: W601
            else_="unknown",
        )
        return value, false()
    if field == "campaign":
        value = func.coalesce(
            Lead.extra["campaign"].astext,
            Lead.extra["campaign_name"].astext,
        )
        return (
            value,
            Lead.extra["campaign"].astext.is_(None)
            & Lead.extra["campaign_name"].astext.is_(None),
        )
    if field == "owner_id":
        value = func.coalesce(
            Lead.extra["owner_id"].astext,
            Lead.extra["owner_name"].astext,
        )
        return (
            value,
            Lead.extra["owner_id"].astext.is_(None)
            & Lead.extra["owner_name"].astext.is_(None),
        )
    if field == "lead_status":
        return cast(Lead.status, String), Lead.status.is_(None)
    if field == "created_at":
        value = cast(func.date_trunc("day", _LEAD_PROVIDER_CREATED_AT), String)
        return value, _LEAD_PROVIDER_CREATED_AT.is_(None)
    if field in {
        "assigned_center",
        "business_unit",
        "consultation_scheduled_at",
        "last_touch_source",
        "last_touch_medium",
        "last_touch_campaign",
    }:
        value = Lead.extra[field].astext
        return value, Lead.extra[field].astext.is_(None)
    if field == "location_id":
        value = Lead.extra["assigned_center"].astext
        return value, Lead.extra["assigned_center"].astext.is_(None)
    raise ValueError(f"unsupported lead profile field: {field}")


def _consultation_profile_expression(field: str) -> tuple[Any, Any]:
    if field == "consultation_status":
        return cast(Consultation.status, String), Consultation.status.is_(None)
    if field == "source_provider":
        return Consultation.source_provider, Consultation.source_provider.is_(None)
    if field == "scheduled_at":
        value = cast(func.date_trunc("day", _CONSULTATION_PROVIDER_CREATED_AT), String)
        return value, _CONSULTATION_PROVIDER_CREATED_AT.is_(None)
    if field == "location_id":
        return cast(Consultation.location_id, String), Consultation.location_id.is_(None)
    raise ValueError(f"unsupported consultation profile field: {field}")
