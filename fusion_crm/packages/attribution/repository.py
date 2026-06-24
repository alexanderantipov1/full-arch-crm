"""Attribution repository — data access only (ENG-447)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import (
    LeadAttribution,
    MappingRule,
    SourceNode,
    Vendor,
    VendorClaim,
    VendorCost,
)

# Leads the resolver could not place — the explicit gap, surfaced as a headline
# count and kept OUT of the resolved tree so the breakdown stays clean.
_NEEDS_REVIEW = "needs_review"


class AttributionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- source_node ---

    async def find_node(
        self, tenant_id: TenantId, *, level: str, slug: str
    ) -> SourceNode | None:
        stmt = (
            for_tenant(select(SourceNode), tenant_id, SourceNode)
            .where(SourceNode.level == level)
            .where(SourceNode.slug == slug)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_node(self, node: SourceNode) -> SourceNode:
        self._session.add(node)
        await self._session.flush()
        return node

    async def list_nodes(
        self, tenant_id: TenantId, *, level: str | None = None
    ) -> list[SourceNode]:
        stmt = for_tenant(select(SourceNode), tenant_id, SourceNode).order_by(
            SourceNode.level.asc(), SourceNode.slug.asc()
        )
        if level is not None:
            stmt = stmt.where(SourceNode.level == level)
        return list((await self._session.execute(stmt)).scalars().all())

    # --- lead_attribution ---

    async def find_lead_attribution(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> LeadAttribution | None:
        stmt = for_tenant(
            select(LeadAttribution), tenant_id, LeadAttribution
        ).where(LeadAttribution.person_uid == person_uid)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_lead_attribution(
        self, row: LeadAttribution
    ) -> LeadAttribution:
        self._session.add(row)
        await self._session.flush()
        return row

    # --- mapping_rule ---

    async def list_rules(
        self, tenant_id: TenantId, *, active_only: bool = True
    ) -> list[MappingRule]:
        stmt = for_tenant(select(MappingRule), tenant_id, MappingRule).order_by(
            MappingRule.priority.asc()
        )
        if active_only:
            stmt = stmt.where(MappingRule.active.is_(True))
        return list((await self._session.execute(stmt)).scalars().all())

    async def add_rule(self, rule: MappingRule) -> MappingRule:
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def find_rule(
        self, tenant_id: TenantId, rule_id: UUID
    ) -> MappingRule | None:
        stmt = for_tenant(select(MappingRule), tenant_id, MappingRule).where(
            MappingRule.id == rule_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def delete_rule(self, rule: MappingRule) -> None:
        await self._session.delete(rule)
        await self._session.flush()

    # --- vendor (ENG-570) ---

    async def list_vendors(
        self, tenant_id: TenantId, *, active_only: bool = False
    ) -> list[Vendor]:
        stmt = for_tenant(select(Vendor), tenant_id, Vendor).order_by(
            Vendor.active.desc(), Vendor.name.asc()
        )
        if active_only:
            stmt = stmt.where(Vendor.active.is_(True))
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_vendor(
        self, tenant_id: TenantId, vendor_id: UUID
    ) -> Vendor | None:
        stmt = for_tenant(select(Vendor), tenant_id, Vendor).where(
            Vendor.id == vendor_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_vendor_by_slug(
        self, tenant_id: TenantId, slug: str
    ) -> Vendor | None:
        stmt = for_tenant(select(Vendor), tenant_id, Vendor).where(
            Vendor.slug == slug
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_vendor(self, vendor: Vendor) -> Vendor:
        self._session.add(vendor)
        await self._session.flush()
        return vendor

    # --- vendor_cost (ENG-573) ---

    async def list_vendor_costs(
        self, tenant_id: TenantId, vendor_id: UUID
    ) -> list[VendorCost]:
        stmt = (
            for_tenant(select(VendorCost), tenant_id, VendorCost)
            .where(VendorCost.vendor_id == vendor_id)
            .order_by(VendorCost.period_month.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_vendor_cost(
        self, tenant_id: TenantId, vendor_id: UUID, period_month: str
    ) -> VendorCost | None:
        stmt = (
            for_tenant(select(VendorCost), tenant_id, VendorCost)
            .where(VendorCost.vendor_id == vendor_id)
            .where(VendorCost.period_month == period_month)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_vendor_cost(self, cost: VendorCost) -> VendorCost:
        self._session.add(cost)
        await self._session.flush()
        return cost

    async def delete_vendor_cost(self, cost: VendorCost) -> None:
        await self._session.delete(cost)
        await self._session.flush()

    # --- vendor_claim + unassigned leads (ENG-571) ---

    async def list_vendor_claims(
        self,
        tenant_id: TenantId,
        *,
        vendor_id: UUID | None = None,
        active_only: bool = False,
    ) -> list[VendorClaim]:
        stmt = for_tenant(select(VendorClaim), tenant_id, VendorClaim).order_by(
            VendorClaim.priority.asc()
        )
        if vendor_id is not None:
            stmt = stmt.where(VendorClaim.vendor_id == vendor_id)
        if active_only:
            stmt = stmt.where(VendorClaim.active.is_(True))
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_vendor_claim(
        self, tenant_id: TenantId, claim_id: UUID
    ) -> VendorClaim | None:
        stmt = for_tenant(select(VendorClaim), tenant_id, VendorClaim).where(
            VendorClaim.id == claim_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_vendor_claim(self, claim: VendorClaim) -> VendorClaim:
        self._session.add(claim)
        await self._session.flush()
        return claim

    async def delete_vendor_claim(self, claim: VendorClaim) -> None:
        await self._session.delete(claim)
        await self._session.flush()

    async def list_unassigned_leads(
        self, tenant_id: TenantId, *, limit: int
    ) -> list[tuple[UUID, str]]:
        """`(person_uid, sf_lead_id)` for resolved leads with no vendor yet.

        Unassigned = the resolver placed a channel but no vendor (``vendor_id``
        NULL), excluding the ``needs_review`` gap and rows without an SF lead id
        (no payload to read a signature from). Newest first; capped by ``limit``.
        """
        stmt = (
            self._resolved_only(
                for_tenant(
                    select(LeadAttribution.person_uid, LeadAttribution.sf_lead_id),
                    tenant_id,
                    LeadAttribution,
                )
            )
            .where(LeadAttribution.vendor_id.is_(None))
            .where(LeadAttribution.sf_lead_id.is_not(None))
            .order_by(LeadAttribution.resolved_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(pid, sid) for pid, sid in rows]

    async def count_unassigned_leads(self, tenant_id: TenantId) -> int:
        stmt = (
            self._resolved_only(
                for_tenant(
                    select(func.count()).select_from(LeadAttribution),
                    tenant_id,
                    LeadAttribution,
                )
            )
            .where(LeadAttribution.vendor_id.is_(None))
            .where(LeadAttribution.sf_lead_id.is_not(None))
        )
        return int((await self._session.execute(stmt)).scalar_one())

    # --- analytics: funnel by attribution chain level (ENG-450, Block D) ---

    @staticmethod
    def _resolved_only(stmt):  # type: ignore[no-untyped-def]
        """Exclude leads the resolver could not place (the needs_review gap)."""
        return stmt.where(
            or_(
                LeadAttribution.source_signal.is_(None),
                LeadAttribution.source_signal != _NEEDS_REVIEW,
            )
        )

    async def count_leads_by_chain(
        self, tenant_id: TenantId, *, person_filter: set[UUID] | None = None
    ) -> list[tuple[UUID | None, UUID | None, UUID | None, int]]:
        """Lead counts grouped by (vendor_id, channel_id, campaign_id).

        One row per distinct chain path; NULL ids are real buckets (a lead
        with a channel but no learned vendor groups under NULL vendor). Excludes
        needs_review leads — those are the explicit gap, counted separately.
        Labels are resolved by the service from the node vocabulary, so this
        query stays a single GROUP BY with no self-joins. ``person_filter``
        (ENG-572) restricts to a set of persons — the month-windowed subset.
        """
        base = self._resolved_only(
            for_tenant(
                select(
                    LeadAttribution.vendor_id,
                    LeadAttribution.channel_id,
                    LeadAttribution.campaign_id,
                    func.count(),
                ).select_from(LeadAttribution),
                tenant_id,
                LeadAttribution,
            )
        )
        if person_filter is not None:
            # Bounded by one month of leads for one clinic (low-thousands today).
            # If monthly volume ever reaches 5 figures, switch this IN to a
            # VALUES/temp-table join or a person sub-select (pre-scale follow-up).
            base = base.where(LeadAttribution.person_uid.in_(person_filter))
        stmt = base.group_by(
            LeadAttribution.vendor_id,
            LeadAttribution.channel_id,
            LeadAttribution.campaign_id,
        )
        rows = (await self._session.execute(stmt)).all()
        return [(v, c, cp, int(n)) for v, c, cp, n in rows]

    async def analytics_attribution_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[UUID | None, str | None, UUID | None]]:
        """``person_uid → (campaign_id, campaign_name, vendor_id)`` for resolved leads.

        For the analytics fact builder (ENG-506). Every stored ``lead_attribution``
        row is a resolved chain (``method ∈ {auto, rule, manual}``); the builder
        treats present rows as resolved and absent persons as NULL attribution.
        ``campaign_name`` is the campaign node's ``label`` via a LEFT JOIN on
        ``source_node`` (NULL when the lead has no campaign-level node). No bound
        IN — one scan over the tenant's attributions.
        """
        campaign_node = aliased(SourceNode)
        stmt = for_tenant(
            select(
                LeadAttribution.person_uid,
                LeadAttribution.campaign_id,
                campaign_node.label,
                LeadAttribution.vendor_id,
            )
            .select_from(LeadAttribution)
            .outerjoin(
                campaign_node, campaign_node.id == LeadAttribution.campaign_id
            ),
            tenant_id,
            LeadAttribution,
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: (campaign_id, campaign_name, vendor_id)
            for person_uid, campaign_id, campaign_name, vendor_id in rows
            if person_uid is not None
        }

    async def analytics_alloc_attribution_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[str | None, str | None, float | None]]:
        """``person_uid → (ad_slug, campaign_slug, confidence)`` for cost-per-lead.

        For the ENG-512 allocator: the resolved ad-level and campaign-level node
        slugs (LEFT JOINs on ``source_node``) plus the attribution confidence.
        The slugs are what the fact builder bridges to the ``marketing`` ad /
        campaign spend rows. One scan, no bound IN.
        """
        ad_node = aliased(SourceNode)
        campaign_node = aliased(SourceNode)
        stmt = for_tenant(
            select(
                LeadAttribution.person_uid,
                ad_node.slug,
                campaign_node.slug,
                LeadAttribution.confidence,
            )
            .select_from(LeadAttribution)
            .outerjoin(ad_node, ad_node.id == LeadAttribution.ad_id)
            .outerjoin(campaign_node, campaign_node.id == LeadAttribution.campaign_id),
            tenant_id,
            LeadAttribution,
        )
        rows = (await self._session.execute(stmt)).all()
        return {
            person_uid: (
                ad_slug,
                campaign_slug,
                float(confidence) if confidence is not None else None,
            )
            for person_uid, ad_slug, campaign_slug, confidence in rows
            if person_uid is not None
        }

    async def count_needs_review(
        self, tenant_id: TenantId, *, person_filter: set[UUID] | None = None
    ) -> int:
        """Count leads the resolver left as needs_review (the gap to close)."""
        stmt = for_tenant(
            select(func.count()).select_from(LeadAttribution),
            tenant_id,
            LeadAttribution,
        ).where(LeadAttribution.source_signal == _NEEDS_REVIEW)
        if person_filter is not None:
            stmt = stmt.where(LeadAttribution.person_uid.in_(person_filter))
        return int((await self._session.execute(stmt)).scalar_one())

    async def map_persons_to_chain(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> list[tuple[UUID | None, UUID | None, UUID | None, UUID]]:
        """Map each person to their (vendor_id, channel_id, campaign_id) path.

        Used to attribute per-person cash / consult counts (computed by other
        domains and passed in by the route) onto the resolved tree nodes —
        mirrors the lead-source explorer's cross-domain discipline.
        """
        if not person_uids:
            return []
        stmt = self._resolved_only(
            for_tenant(
                select(
                    LeadAttribution.vendor_id,
                    LeadAttribution.channel_id,
                    LeadAttribution.campaign_id,
                    LeadAttribution.person_uid,
                ).select_from(LeadAttribution),
                tenant_id,
                LeadAttribution,
            ).where(LeadAttribution.person_uid.in_(person_uids))
        )
        rows = (await self._session.execute(stmt)).all()
        return [(v, c, cp, pid) for v, c, cp, pid in rows]

    async def list_lead_attributions_for_node(
        self,
        tenant_id: TenantId,
        *,
        vendor_id: UUID | None,
        channel_id: UUID | None,
        campaign_id: UUID | None,
        match_vendor: bool,
        match_channel: bool,
        match_campaign: bool,
        limit: int = 50,
        offset: int = 0,
        person_filter: set[UUID] | None = None,
    ) -> tuple[int, list[LeadAttribution]]:
        """Paginated ``lead_attribution`` rows behind one tree node.

        Each ``match_*`` flag says whether that level is part of the node path;
        when set, the row's level id must equal the given id (``None`` matches
        the NULL bucket). Unflagged levels are unconstrained. This lists exactly
        the rows counted in the node, including the NULL ("unassigned") buckets.
        ``person_filter`` (ENG-572) windows to the month's persons.
        """
        conditions = []
        if match_vendor:
            conditions.append(LeadAttribution.vendor_id == vendor_id)
        if match_channel:
            conditions.append(LeadAttribution.channel_id == channel_id)
        if match_campaign:
            conditions.append(LeadAttribution.campaign_id == campaign_id)
        if person_filter is not None:
            conditions.append(LeadAttribution.person_uid.in_(person_filter))

        base = self._resolved_only(
            for_tenant(select(LeadAttribution), tenant_id, LeadAttribution)
        ).where(*conditions)

        count_stmt = self._resolved_only(
            for_tenant(
                select(func.count()).select_from(LeadAttribution),
                tenant_id,
                LeadAttribution,
            )
        ).where(*conditions)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        page_stmt = (
            base.order_by(
                LeadAttribution.resolved_at.desc(), LeadAttribution.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
        rows = list((await self._session.execute(page_stmt)).scalars().all())
        return total, rows
