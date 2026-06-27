"""AttributionService — public surface (ENG-447).

Block A ships the schema + a thin service: ensure/seed source nodes, read the
chain, upsert a resolved per-lead attribution, and CRUD mapping rules. The
waterfall resolver logic lands in ENG-448; manual enrichment in ENG-449.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import ValidationError
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId
from packages.identity.service import IdentityService
from packages.ingest.service import IngestService

from .models import (
    CLAIM_ORIGINS,
    LEVELS,
    METHODS,
    VENDOR_KINDS,
    LeadAttribution,
    MappingRule,
    SourceNode,
    Vendor,
    VendorClaim,
    VendorCost,
)
from .repository import AttributionRepository
from .schemas import (
    AttributionLeadItemOut,
    AttributionLeadListOut,
    AttributionTreeNodeOut,
    AttributionTreeOut,
    ClaimSuggestionOut,
    ClaimSuggestionsOut,
    LeadAttributionIn,
    LeadAttributionOut,
    LeadOverrideIn,
    MappingRuleIn,
    MappingRuleOut,
    SignatureValueOut,
    SourceNodeIn,
    SourceNodeOut,
    UnassignedSignaturesOut,
    VendorClaimIn,
    VendorClaimOut,
    VendorCostIn,
    VendorCostOut,
    VendorIn,
    VendorOut,
    VendorUpdateIn,
)
from .signals import _RAW_FIELDS, build_signals
from .waterfall import LeadSignals, Rule, _slugify, resolve

# Canonical signal fields the operator can bind a vendor on. The flat ones (in
# the SF payload at a top-level key) also power the unassigned-signature scan;
# ``created_by`` is bindable but nested, so it is excluded from the scan.
_FLAT_SIGNATURE_FIELDS: tuple[str, ...] = (
    "utm_source",
    "utm_campaign",
    "last_touch_source",
    "last_touch_campaign",
    "first_touch_campaign",
    "hubspot_lead_source",
    "lead_source",
)
_ALLOWED_CLAIM_FIELDS: frozenset[str] = frozenset({*_RAW_FIELDS, "created_by"})
_CLAIM_OPS: frozenset[str] = frozenset({"eq", "ilike", "prefix"})

# Generic words that would over-match if used as a vendor token (ENG-574).
_GENERIC_VENDOR_TOKENS: frozenset[str] = frozenset(
    {
        "the", "inc", "llc", "ltd", "media", "agency", "marketing", "ads",
        "digital", "house", "group", "team", "inhouse", "creatives", "studio",
        "solutions", "services", "company",
    }
)


def _tokenize(text: str) -> set[str]:
    """Lowercased alphanumeric word tokens (len ≥ 3) of ``text``."""
    tokens: set[str] = set()
    word: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            word.append(ch)
        elif word:
            tokens.add("".join(word))
            word = []
    if word:
        tokens.add("".join(word))
    return {t for t in tokens if len(t) >= 3}


def _vendor_tokens(name: str, slug: str) -> set[str]:
    """Distinctive word tokens from a vendor's name + slug, for matching against
    Unassigned signature values (ENG-574). Generic agency words are dropped so
    they don't over-match."""
    return {
        t for t in _tokenize(f"{name} {slug}") if t not in _GENERIC_VENDOR_TOKENS
    }


def _claim_value_matches(op: str, needle: str, value: str) -> bool:
    """Mirror the waterfall rule matcher for a claim's op/value vs a raw value."""
    v = value.strip().lower()
    n = needle.strip().lower()
    if op == "eq":
        return v == n
    if op == "prefix":
        return v.startswith(n)
    return n.strip("%") in v  # ilike (substring)

# Sentinel slug for a NULL level (a lead resolved to a channel but no learned
# vendor, etc.). Kept distinct from any real node slug so tree keys stay stable.
_NONE_SLUG = "__none__"
_NONE_LABEL = "(unassigned)"
# The chain levels the tree nests, outermost → innermost.
_TREE_LEVELS = ("vendor", "channel", "campaign")

# Controlled-vocabulary seed (ENG-447). Channels are the platform/medium axis;
# vendors are seeded with the in-house default — real agencies are added via
# mapping rules / manual enrichment (ENG-449) as they are discovered.
DEFAULT_CHANNELS: tuple[tuple[str, str], ...] = (
    ("facebook", "Facebook"),
    ("google", "Google"),
    ("tiktok", "TikTok"),
    ("instagram", "Instagram"),
    ("phone", "Phone / Call"),
    ("direct", "Direct"),
    ("manual", "Manual entry"),
    ("referral", "Referral"),
    ("organic", "Organic"),
    ("existing_patient", "Existing patient"),
)
DEFAULT_VENDORS: tuple[tuple[str, str], ...] = (
    ("in_house", "In-house"),
    ("unassigned", "Unassigned"),
)


class AttributionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AttributionRepository(session)
        # Read-only collaborators for ENG-448 resolution (signals + provenance).
        self._ingest = IngestService(session)
        self._identity = IdentityService(session)
        # Manual enrichment (rules + overrides) writes audit (packages/attribution
        # CLAUDE.md). Auto-resolution does not — it is derived, not a human edit.
        self._audit = AuditService(session)

    # --- source nodes ---

    async def ensure_node(
        self, tenant_id: TenantId, payload: SourceNodeIn
    ) -> SourceNodeOut:
        """Idempotently upsert a chain node by ``(level, slug)``."""
        if payload.level not in LEVELS:
            raise ValidationError(
                "unknown level",
                details={"level": payload.level, "allowed": list(LEVELS)},
            )
        existing = await self._repo.find_node(
            tenant_id, level=payload.level, slug=payload.slug
        )
        if existing is not None:
            # Keep the latest label/parent; nodes are controlled vocab.
            existing.label = payload.label
            if payload.parent_id is not None:
                existing.parent_id = payload.parent_id
            if payload.meta:
                existing.meta = {**existing.meta, **payload.meta}
            await self._session.flush()
            await self._ensure_vendor_entity(tenant_id, existing)
            return SourceNodeOut.model_validate(existing)
        node = SourceNode(
            tenant_id=tenant_id,
            level=payload.level,
            slug=payload.slug,
            label=payload.label,
            parent_id=payload.parent_id,
            active=True,
            meta=dict(payload.meta),
        )
        await self._repo.add_node(node)
        await self._ensure_vendor_entity(tenant_id, node)
        return SourceNodeOut.model_validate(node)

    async def _ensure_vendor_entity(
        self, tenant_id: TenantId, node: SourceNode
    ) -> None:
        """Mirror a vendor-level chain node into a configured ``Vendor`` (ENG-570).

        Every vendor node the resolver/rules produce gets a first-class vendor
        entity so the operator's settings list reflects reality. The
        ``unassigned``/``__none__`` buckets are the NULL sink, never a vendor.
        A manually-created vendor (no node yet) is back-linked here the moment
        its node first appears.
        """
        if node.level != "vendor" or node.slug in (_NONE_SLUG, "unassigned"):
            return
        vendor = await self._repo.find_vendor_by_slug(tenant_id, node.slug)
        if vendor is None:
            await self._repo.add_vendor(
                Vendor(
                    tenant_id=tenant_id,
                    slug=node.slug,
                    name=node.label,
                    kind="in_house" if node.slug == "in_house" else "agency",
                    active=True,
                    source_node_id=node.id,
                )
            )
        elif vendor.source_node_id is None:
            vendor.source_node_id = node.id
            await self._session.flush()

    async def list_nodes(
        self, tenant_id: TenantId, *, level: str | None = None
    ) -> list[SourceNodeOut]:
        rows = await self._repo.list_nodes(tenant_id, level=level)
        return [SourceNodeOut.model_validate(r) for r in rows]

    async def seed_default_nodes(self, tenant_id: TenantId) -> int:
        """Idempotently ensure the default channel + vendor vocabulary.

        Returns the number of nodes ensured. Safe to re-run.
        """
        count = 0
        for slug, label in DEFAULT_CHANNELS:
            await self.ensure_node(
                tenant_id, SourceNodeIn(level="channel", slug=slug, label=label)
            )
            count += 1
        for slug, label in DEFAULT_VENDORS:
            await self.ensure_node(
                tenant_id, SourceNodeIn(level="vendor", slug=slug, label=label)
            )
            count += 1
        return count

    # --- lead attribution ---

    async def upsert_lead_attribution(
        self, tenant_id: TenantId, payload: LeadAttributionIn
    ) -> LeadAttributionOut:
        if payload.method not in METHODS:
            raise ValidationError(
                "unknown method",
                details={"method": payload.method, "allowed": list(METHODS)},
            )
        existing = await self._repo.find_lead_attribution(
            tenant_id, payload.person_uid
        )
        now = datetime.now(UTC)
        if existing is not None:
            # A manual override is sticky — auto/rule re-resolution must not
            # clobber it (ENG-449).
            if existing.method == "manual" and payload.method != "manual":
                return LeadAttributionOut.model_validate(existing)
            for field in (
                "sf_lead_id",
                "vendor_id",
                "channel_id",
                "campaign_id",
                "ad_set_id",
                "ad_id",
                "form_id",
                "created_by_name",
                "method",
                "confidence",
                "source_signal",
            ):
                setattr(existing, field, getattr(payload, field))
            existing.resolved_at = now
            await self._session.flush()
            return LeadAttributionOut.model_validate(existing)
        row = LeadAttribution(
            tenant_id=tenant_id,
            person_uid=payload.person_uid,
            sf_lead_id=payload.sf_lead_id,
            vendor_id=payload.vendor_id,
            channel_id=payload.channel_id,
            campaign_id=payload.campaign_id,
            ad_set_id=payload.ad_set_id,
            ad_id=payload.ad_id,
            form_id=payload.form_id,
            created_by_name=payload.created_by_name,
            method=payload.method,
            confidence=payload.confidence,
            source_signal=payload.source_signal,
            resolved_at=now,
        )
        await self._repo.add_lead_attribution(row)
        return LeadAttributionOut.model_validate(row)

    async def get_lead_attribution(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> LeadAttributionOut | None:
        row = await self._repo.find_lead_attribution(tenant_id, person_uid)
        return LeadAttributionOut.model_validate(row) if row is not None else None

    async def analytics_attribution_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[UUID | None, str | None, UUID | None]]:
        """``person_uid → (campaign_id, campaign_name, vendor_id)`` for resolved leads.

        For the analytics fact builder (ENG-506). Present rows are resolved
        attributions; absent persons get NULL attribution in the fact. One scan,
        no bound IN.
        """
        return await self._repo.analytics_attribution_by_person(tenant_id)

    async def analytics_alloc_attribution_by_person(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[str | None, str | None, float | None]]:
        """``person_uid → (ad_slug, campaign_slug, confidence)`` for the ENG-512
        cost-per-lead allocator.

        The ad / campaign node slugs are what the fact builder bridges to the
        ``marketing`` ad / campaign spend rows; ``confidence`` flows into the
        ``marketing_cost_allocated`` provenance. One scan, no bound IN.
        """
        return await self._repo.analytics_alloc_attribution_by_person(tenant_id)

    # --- analytics: funnel by attribution chain level (ENG-450, Block D) ---

    async def _node_label_map(
        self, tenant_id: TenantId
    ) -> dict[UUID, tuple[str, str]]:
        """``node_id → (slug, label)`` for the whole tenant vocabulary."""
        return {
            n.id: (n.slug, n.label)
            for n in await self._repo.list_nodes(tenant_id)
        }

    async def _effective_fee(
        self, tenant_id: TenantId, vendor: Vendor, period: str
    ) -> float | None:
        """A vendor's fee for ``period`` ('YYYY-MM'): the flat monthly fee, or
        the per-month override row, or None if no fee is set (ENG-573)."""
        if vendor.flat_monthly_fee and vendor.monthly_fee is not None:
            return float(vendor.monthly_fee)
        cost = await self._repo.find_vendor_cost(tenant_id, vendor.id, period)
        return float(cost.amount) if cost is not None else None

    async def get_attribution_tree(
        self,
        tenant_id: TenantId,
        *,
        collected_by_person: dict[UUID, float] | None = None,
        consults_by_person: dict[UUID, tuple[int, int]] | None = None,
        person_filter: set[UUID] | None = None,
        period: str | None = None,
    ) -> AttributionTreeOut:
        """Lead→consult funnel counts sliced by the resolved chain (ENG-450).

        Tree levels: vendor → channel → campaign; a parent aggregates its
        children. Cash (interaction domain) and consult counts (ops domain) are
        passed in per-person by the route and attributed to each person's
        resolved node here — attribution never imports those domains' models.
        ``needs_review`` is reported separately as the explicit unresolved gap.

        ENG-572/ENG-573: ``person_filter`` windows the breakdown to a set of
        persons (the route resolves a month → persons via ops). ``period``
        ('YYYY-MM') enriches each vendor node with its colour, monthly cost, and
        cost-per-lead (cost ÷ that node's leads).
        """
        lead_rows = await self._repo.count_leads_by_chain(
            tenant_id, person_filter=person_filter
        )
        needs_review = await self._repo.count_needs_review(
            tenant_id, person_filter=person_filter
        )
        node_map = await self._node_label_map(tenant_id)
        labels: dict[tuple[str, str], str] = {}

        def seg(level: str, level_id: UUID | None) -> str:
            slug, label = (
                node_map.get(level_id, (_NONE_SLUG, _NONE_LABEL))
                if level_id is not None
                else (_NONE_SLUG, _NONE_LABEL)
            )
            labels[(level, slug)] = label
            return slug

        counts: dict[tuple[str, str, str], _AttrNodeCounts] = {}
        for vendor_id, channel_id, campaign_id, lead_count in lead_rows:
            key = (
                seg("vendor", vendor_id),
                seg("channel", channel_id),
                seg("campaign", campaign_id),
            )
            counts.setdefault(key, _AttrNodeCounts()).leads += lead_count

        persons = set(collected_by_person or {}) | set(consults_by_person or {})
        if persons:
            person_nodes = await self._repo.map_persons_to_chain(
                tenant_id, list(persons)
            )
            for vendor_id, channel_id, campaign_id, person_uid in person_nodes:
                key = (
                    seg("vendor", vendor_id),
                    seg("channel", channel_id),
                    seg("campaign", campaign_id),
                )
                node = counts.setdefault(key, _AttrNodeCounts())
                if collected_by_person:
                    node.collected_amount += collected_by_person.get(person_uid, 0.0)
                if consults_by_person:
                    scheduled, attended = consults_by_person.get(person_uid, (0, 0))
                    node.consults_scheduled += scheduled
                    node.consults_attended += attended

        nodes = _build_attribution_tree(counts, labels)

        # Enrich vendor-level nodes from the configured vendor entity (ENG-572):
        # colour always; monthly cost + cost-per-lead when a period is given.
        vendors_by_slug = {
            v.slug: v for v in await self._repo.list_vendors(tenant_id)
        }
        for vnode in nodes:  # top level == vendor; key == vendor slug
            vendor = vendors_by_slug.get(vnode.key)
            if vendor is None:
                continue
            vnode.color = vendor.color
            if period is not None:
                fee = await self._effective_fee(tenant_id, vendor, period)
                if fee is not None:
                    vnode.monthly_cost = round(fee, 2)
                    vnode.cost_per_lead = (
                        round(fee / vnode.leads, 2) if vnode.leads > 0 else None
                    )

        return AttributionTreeOut(
            total_leads=sum(n.leads for n in nodes),
            needs_review=needs_review,
            consults_scheduled=sum(n.consults_scheduled for n in nodes),
            consults_attended=sum(n.consults_attended for n in nodes),
            collected_amount=round(sum(n.collected_amount for n in nodes), 2),
            nodes=nodes,
        )

    async def list_leads_for_chain_node(
        self,
        tenant_id: TenantId,
        *,
        vendor: str | None = None,
        channel: str | None = None,
        campaign: str | None = None,
        limit: int = 50,
        offset: int = 0,
        collected_by_person: dict[UUID, float] | None = None,
        person_filter: set[UUID] | None = None,
    ) -> AttributionLeadListOut:
        """Paginated drill-down of the leads behind one attribution tree node.

        Each provided slug constrains that level (the ``__none__`` sentinel
        matches the NULL/unassigned bucket); at least one is required. Rows are
        enriched with identity (one batched lookup) and per-person cash.
        ``person_filter`` (ENG-572) windows the drill-down to the month's leads.
        """
        if vendor is None and channel is None and campaign is None:
            raise ValidationError(
                "at least one chain level is required for a drill-down",
                details={},
            )

        async def _slug_to_id(
            level: str, slug: str | None
        ) -> tuple[UUID | None, bool, bool]:
            """Return (node_id, is_part_of_path, resolved).

            ``resolved`` is False only when a real (non-sentinel) slug was given
            but matches no node — the caller then returns an empty set, rather
            than silently falling back to the NULL/unassigned bucket.
            """
            if slug is None:
                return None, False, True
            if slug == _NONE_SLUG:
                return None, True, True
            node = await self._repo.find_node(tenant_id, level=level, slug=slug)
            if node is None:
                return None, True, False
            return node.id, True, True

        vendor_id, match_vendor, ok_v = await _slug_to_id("vendor", vendor)
        channel_id, match_channel, ok_c = await _slug_to_id("channel", channel)
        campaign_id, match_campaign, ok_p = await _slug_to_id("campaign", campaign)

        # A provided slug that resolves to no node → no leads, not the NULL bucket.
        if not (ok_v and ok_c and ok_p):
            return AttributionLeadListOut(total=0, items=[])

        total, rows = await self._repo.list_lead_attributions_for_node(
            tenant_id,
            vendor_id=vendor_id,
            channel_id=channel_id,
            campaign_id=campaign_id,
            match_vendor=match_vendor,
            match_channel=match_channel,
            match_campaign=match_campaign,
            limit=limit,
            offset=offset,
            person_filter=person_filter,
        )

        node_map = await self._node_label_map(tenant_id)

        def label_of(level_id: UUID | None) -> str | None:
            if level_id is None:
                return None
            pair = node_map.get(level_id)
            return pair[1] if pair else None

        persons = await self._identity.list_by_ids(
            tenant_id, [row.person_uid for row in rows]
        )
        person_by_uid = {p.id: p for p in persons}
        cash = collected_by_person or {}

        items: list[AttributionLeadItemOut] = []
        for row in rows:
            person = person_by_uid.get(row.person_uid)
            display_name = person.display_name if person is not None else None
            # email / phone live on identity identifiers (eager-loaded by
            # list_by_ids) — same access the PM Leads / explorer rows use.
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
            items.append(
                AttributionLeadItemOut(
                    person_uid=row.person_uid,
                    sf_lead_id=row.sf_lead_id,
                    display_name=display_name,
                    email=email,
                    phone=phone,
                    vendor=label_of(row.vendor_id),
                    channel=label_of(row.channel_id),
                    campaign=label_of(row.campaign_id),
                    created_by_name=row.created_by_name,
                    method=row.method,
                    source_signal=row.source_signal,
                    confidence=(
                        float(row.confidence) if row.confidence is not None else None
                    ),
                    collected_amount=round(cash.get(row.person_uid, 0.0), 2),
                    resolved_at=row.resolved_at,
                )
            )

        return AttributionLeadListOut(total=total, items=items)

    # --- mapping rules ---

    async def create_rule(
        self, tenant_id: TenantId, payload: MappingRuleIn, *, principal: Principal
    ) -> MappingRuleOut:
        if payload.set_level not in LEVELS:
            raise ValidationError(
                "unknown set_level",
                details={"set_level": payload.set_level, "allowed": list(LEVELS)},
            )
        rule = MappingRule(
            tenant_id=tenant_id,
            priority=payload.priority,
            match_field=payload.match_field,
            match_op=payload.match_op,
            match_value=payload.match_value,
            set_level=payload.set_level,
            set_node_id=payload.set_node_id,
            active=payload.active,
        )
        await self._repo.add_rule(rule)
        await self._audit.record(
            principal=principal,
            action="attribution.rule.create",
            resource="attribution.mapping_rule",
            extra={
                "rule_id": str(rule.id),
                "match_field": rule.match_field,
                "set_level": rule.set_level,
            },
        )
        return MappingRuleOut.model_validate(rule)

    async def list_rules(
        self, tenant_id: TenantId, *, active_only: bool = True
    ) -> list[MappingRuleOut]:
        rows = await self._repo.list_rules(tenant_id, active_only=active_only)
        return [MappingRuleOut.model_validate(r) for r in rows]

    async def delete_rule(
        self, tenant_id: TenantId, rule_id: UUID, *, principal: Principal
    ) -> bool:
        rule = await self._repo.find_rule(tenant_id, rule_id)
        if rule is None:
            return False
        await self._repo.delete_rule(rule)
        await self._audit.record(
            principal=principal,
            action="attribution.rule.delete",
            resource="attribution.mapping_rule",
            extra={"rule_id": str(rule_id)},
        )
        return True

    # --- vendors (ENG-570) ---

    async def list_vendors(
        self, tenant_id: TenantId, *, active_only: bool = False
    ) -> list[VendorOut]:
        rows = await self._repo.list_vendors(tenant_id, active_only=active_only)
        return [VendorOut.model_validate(r) for r in rows]

    async def create_vendor(
        self, tenant_id: TenantId, payload: VendorIn, *, principal: Principal
    ) -> VendorOut:
        if payload.kind not in VENDOR_KINDS:
            raise ValidationError(
                "unknown vendor kind",
                details={"kind": payload.kind, "allowed": list(VENDOR_KINDS)},
            )
        slug = _slugify(payload.slug or payload.name)
        if await self._repo.find_vendor_by_slug(tenant_id, slug) is not None:
            raise ValidationError(
                "vendor slug already exists", details={"slug": slug}
            )
        # Link an existing vendor-level node with the same slug, if one was
        # already learned from traffic; otherwise the link fills in later via
        # _ensure_vendor_entity when the node first appears.
        node = await self._repo.find_node(tenant_id, level="vendor", slug=slug)
        vendor = Vendor(
            tenant_id=tenant_id,
            slug=slug,
            name=payload.name,
            kind=payload.kind,
            active=payload.active,
            color=payload.color,
            notes=payload.notes,
            monthly_fee=(
                Decimal(str(payload.monthly_fee))
                if payload.monthly_fee is not None
                else None
            ),
            flat_monthly_fee=payload.flat_monthly_fee,
            fee_currency=payload.fee_currency,
            source_node_id=node.id if node is not None else None,
        )
        await self._repo.add_vendor(vendor)
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.create",
            resource="attribution.vendor",
            extra={"vendor_id": str(vendor.id), "slug": slug, "kind": vendor.kind},
        )
        return VendorOut.model_validate(vendor)

    async def update_vendor(
        self,
        tenant_id: TenantId,
        vendor_id: UUID,
        payload: VendorUpdateIn,
        *,
        principal: Principal,
    ) -> VendorOut | None:
        vendor = await self._repo.find_vendor(tenant_id, vendor_id)
        if vendor is None:
            return None
        if payload.kind is not None:
            if payload.kind not in VENDOR_KINDS:
                raise ValidationError(
                    "unknown vendor kind",
                    details={"kind": payload.kind, "allowed": list(VENDOR_KINDS)},
                )
            vendor.kind = payload.kind
        if payload.name is not None:
            vendor.name = payload.name
        if payload.color is not None:
            vendor.color = payload.color
        if payload.notes is not None:
            vendor.notes = payload.notes
        if payload.active is not None:
            vendor.active = payload.active
        if payload.monthly_fee is not None:
            vendor.monthly_fee = Decimal(str(payload.monthly_fee))
        if payload.flat_monthly_fee is not None:
            vendor.flat_monthly_fee = payload.flat_monthly_fee
        if payload.fee_currency is not None:
            vendor.fee_currency = payload.fee_currency
        await self._session.flush()
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.update",
            resource="attribution.vendor",
            extra={"vendor_id": str(vendor.id)},
        )
        return VendorOut.model_validate(vendor)

    async def deactivate_vendor(
        self, tenant_id: TenantId, vendor_id: UUID, *, principal: Principal
    ) -> bool:
        vendor = await self._repo.find_vendor(tenant_id, vendor_id)
        if vendor is None:
            return False
        vendor.active = False
        await self._session.flush()
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.deactivate",
            resource="attribution.vendor",
            extra={"vendor_id": str(vendor.id)},
        )
        return True

    # --- vendor monthly costs (ENG-573) ---

    async def list_vendor_costs(
        self, tenant_id: TenantId, vendor_id: UUID
    ) -> list[VendorCostOut]:
        rows = await self._repo.list_vendor_costs(tenant_id, vendor_id)
        return [VendorCostOut.model_validate(r) for r in rows]

    async def set_vendor_cost(
        self,
        tenant_id: TenantId,
        vendor_id: UUID,
        payload: VendorCostIn,
        *,
        principal: Principal,
    ) -> VendorCostOut | None:
        """Upsert a vendor's fee for one month. Returns None if the vendor is gone."""
        if await self._repo.find_vendor(tenant_id, vendor_id) is None:
            return None
        existing = await self._repo.find_vendor_cost(
            tenant_id, vendor_id, payload.period_month
        )
        if existing is not None:
            existing.amount = Decimal(str(payload.amount))
            existing.note = payload.note
            await self._session.flush()
            cost = existing
        else:
            cost = VendorCost(
                tenant_id=tenant_id,
                vendor_id=vendor_id,
                period_month=payload.period_month,
                amount=Decimal(str(payload.amount)),
                note=payload.note,
            )
            await self._repo.add_vendor_cost(cost)
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.cost.set",
            resource="attribution.vendor_cost",
            extra={"vendor_id": str(vendor_id), "period_month": payload.period_month},
        )
        return VendorCostOut.model_validate(cost)

    async def delete_vendor_cost(
        self,
        tenant_id: TenantId,
        vendor_id: UUID,
        period_month: str,
        *,
        principal: Principal,
    ) -> bool:
        cost = await self._repo.find_vendor_cost(tenant_id, vendor_id, period_month)
        if cost is None:
            return False
        await self._repo.delete_vendor_cost(cost)
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.cost.delete",
            resource="attribution.vendor_cost",
            extra={"vendor_id": str(vendor_id), "period_month": period_month},
        )
        return True

    # --- vendor claims + unassigned signatures (ENG-571) ---

    async def list_vendor_claims(
        self, tenant_id: TenantId, *, vendor_id: UUID | None = None
    ) -> list[VendorClaimOut]:
        rows = await self._repo.list_vendor_claims(tenant_id, vendor_id=vendor_id)
        return [VendorClaimOut.model_validate(r) for r in rows]

    async def create_vendor_claim(
        self,
        tenant_id: TenantId,
        vendor_id: UUID,
        payload: VendorClaimIn,
        *,
        principal: Principal,
        reresolve: bool = True,
    ) -> VendorClaimOut | None:
        """Bind matching traffic to a vendor; re-resolve the matching leads.

        Returns None if the vendor does not exist.
        """
        if payload.match_field not in _ALLOWED_CLAIM_FIELDS:
            raise ValidationError(
                "unknown match_field",
                details={
                    "match_field": payload.match_field,
                    "allowed": sorted(_ALLOWED_CLAIM_FIELDS),
                },
            )
        if payload.match_op not in _CLAIM_OPS:
            raise ValidationError(
                "unknown match_op",
                details={"match_op": payload.match_op, "allowed": sorted(_CLAIM_OPS)},
            )
        if payload.origin not in CLAIM_ORIGINS:
            raise ValidationError(
                "unknown origin",
                details={"origin": payload.origin, "allowed": sorted(CLAIM_ORIGINS)},
            )
        if await self._repo.find_vendor(tenant_id, vendor_id) is None:
            return None
        claim = VendorClaim(
            tenant_id=tenant_id,
            vendor_id=vendor_id,
            priority=payload.priority,
            match_field=payload.match_field,
            match_op=payload.match_op,
            match_value=payload.match_value,
            active=True,
            origin=payload.origin,
        )
        await self._repo.add_vendor_claim(claim)
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.claim.create",
            resource="attribution.vendor_claim",
            extra={
                "vendor_id": str(vendor_id),
                "match_field": claim.match_field,
                "match_op": claim.match_op,
            },
        )
        if reresolve:
            await self._reresolve_for_claim(tenant_id, claim)
        return VendorClaimOut.model_validate(claim)

    async def delete_vendor_claim(
        self, tenant_id: TenantId, claim_id: UUID, *, principal: Principal
    ) -> bool:
        claim = await self._repo.find_vendor_claim(tenant_id, claim_id)
        if claim is None:
            return False
        await self._repo.delete_vendor_claim(claim)
        await self._audit.record(
            principal=principal,
            action="attribution.vendor.claim.delete",
            resource="attribution.vendor_claim",
            extra={"claim_id": str(claim_id)},
        )
        return True

    async def unassigned_signatures(
        self, tenant_id: TenantId, *, lead_limit: int = 2000
    ) -> UnassignedSignaturesOut:
        """Distinct traffic-signature values behind the Unassigned leads.

        Reads the captured SF lead payloads (via the ingest service) of the
        no-vendor leads and aggregates each flat signature field's distinct
        values with a lead count — the "pick from a list" source for binding.
        Capped at ``lead_limit`` (reported, never silently truncated).
        """
        leads = await self._repo.list_unassigned_leads(tenant_id, limit=lead_limit)
        total = await self._repo.count_unassigned_leads(tenant_id)
        sf_ids = [sid for _pid, sid in leads]
        counts: dict[tuple[str, str], int] = {}
        # NOTE: latest_payload_values returns the lexically-MAX captured value per
        # field, not the value off the newest payload (which is what the
        # authoritative resolver reads). Identical for the stable utm/source
        # fields used here; a per-newest-payload ingest helper is a follow-up if
        # a signal ever changes between captures. Same caveat in
        # _reresolve_for_claim's matcher below.
        for field in _FLAT_SIGNATURE_FIELDS:
            sf_field = _RAW_FIELDS[field]
            values = await self._ingest.latest_payload_values(
                tenant_id,
                event_type="lead.pull",
                external_ids=sf_ids,
                payload_key=sf_field,
            )
            for value in values.values():
                v = value.strip()
                if v:
                    counts[(field, v)] = counts.get((field, v), 0) + 1
        items = [
            SignatureValueOut(match_field=f, value=v, lead_count=c)
            for (f, v), c in counts.items()
        ]
        items.sort(key=lambda i: (i.lead_count, i.match_field, i.value), reverse=True)
        return UnassignedSignaturesOut(
            items=items, scanned=len(leads), capped=total > len(leads)
        )

    async def suggest_claims_for_vendor(
        self, tenant_id: TenantId, vendor_id: UUID, *, lead_limit: int = 2000
    ) -> ClaimSuggestionsOut | None:
        """Agent-propose bindings for a vendor (ENG-574).

        Heuristic suggester: matches each Unassigned signature value against the
        vendor's distinctive name/slug tokens and proposes the ones that hit,
        with a rationale. The operator accepts a suggestion → a claim with
        ``origin='agent'``. Returns None if the vendor does not exist. (A future
        upgrade can swap the heuristic for an LLM suggester behind the same
        contract.)
        """
        vendor = await self._repo.find_vendor(tenant_id, vendor_id)
        if vendor is None:
            return None
        tokens = _vendor_tokens(vendor.name, vendor.slug)
        sigs = await self.unassigned_signatures(tenant_id, lead_limit=lead_limit)
        # Belt-and-suspenders dedup against this vendor's existing claims. (The
        # signatures already come only from vendor_id-NULL leads, so a claimed
        # signature can't reappear; this is NOT a cross-vendor guard and needs
        # none — competing claims aren't possible from an Unassigned-only feed.)
        already = {
            (c.match_field, c.match_value)
            for c in await self._repo.list_vendor_claims(
                tenant_id, vendor_id=vendor_id
            )
        }
        items: list[ClaimSuggestionOut] = []
        if tokens:
            for sig in sigs.items:
                if (sig.match_field, sig.value) in already:
                    continue
                # Match on whole WORD tokens (not raw substring) so a token like
                # "art" hits "fb_art" but not "smart" — avoids partial-word
                # false positives.
                value_tokens = _tokenize(sig.value)
                hit = next((t for t in tokens if t in value_tokens), None)
                if hit is not None:
                    items.append(
                        ClaimSuggestionOut(
                            match_field=sig.match_field,
                            value=sig.value,
                            lead_count=sig.lead_count,
                            rationale=(
                                f'value mentions "{hit}" — matches vendor '
                                f"{vendor.name}"
                            ),
                        )
                    )
        items.sort(key=lambda i: i.lead_count, reverse=True)
        return ClaimSuggestionsOut(
            items=items, scanned=sigs.scanned, capped=sigs.capped
        )

    async def _reresolve_for_claim(
        self, tenant_id: TenantId, claim: VendorClaim, *, lead_limit: int = 5000
    ) -> int:
        """Re-resolve the Unassigned leads a new claim now matches.

        Best-effort and immediate. A ``created_by`` claim has no flat
        ``_RAW_FIELDS`` mapping (it is nested in the payload), so ``sf_field`` is
        None and this rebinds nothing now — the claim still takes effect on the
        next full resolver pass (``resolve_attribution.py``).
        """
        sf_field = _RAW_FIELDS.get(claim.match_field)
        leads = await self._repo.list_unassigned_leads(tenant_id, limit=lead_limit)
        by_sid = {sid: pid for pid, sid in leads}
        if sf_field is None or not by_sid:
            return 0
        values = await self._ingest.latest_payload_values(
            tenant_id,
            event_type="lead.pull",
            external_ids=list(by_sid),
            payload_key=sf_field,
        )
        matched = [
            by_sid[sid]
            for sid, value in values.items()
            if sid in by_sid
            and _claim_value_matches(claim.match_op, claim.match_value, value)
        ]
        if matched:
            await self.resolve_many(tenant_id, matched)
        return len(matched)

    # --- manual enrichment (ENG-449) ---

    async def set_override(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        payload: LeadOverrideIn,
        *,
        principal: Principal,
    ) -> LeadAttributionOut:
        """Staff manual override of a lead's chain. method=manual (sticky).

        Levels present in ``payload`` are set; omitted levels keep their current
        value on the existing row.
        """
        from .schemas import SourceRef

        existing = await self._repo.find_lead_attribution(tenant_id, person_uid)

        async def _level_id(
            level: str, ref: SourceRef | None, current: UUID | None
        ) -> UUID | None:
            if ref is None:
                return current
            node = await self.ensure_node(
                tenant_id, SourceNodeIn(level=level, slug=ref.slug, label=ref.label)
            )
            return node.id

        attribution = LeadAttributionIn(
            person_uid=person_uid,
            sf_lead_id=existing.sf_lead_id if existing else None,
            vendor_id=await _level_id(
                "vendor", payload.vendor, existing.vendor_id if existing else None
            ),
            channel_id=await _level_id(
                "channel", payload.channel, existing.channel_id if existing else None
            ),
            campaign_id=await _level_id(
                "campaign",
                payload.campaign,
                existing.campaign_id if existing else None,
            ),
            ad_set_id=await _level_id(
                "ad_set", payload.ad_set, existing.ad_set_id if existing else None
            ),
            ad_id=await _level_id(
                "ad", payload.ad, existing.ad_id if existing else None
            ),
            form_id=await _level_id(
                "form", payload.form, existing.form_id if existing else None
            ),
            created_by_name=payload.created_by_name
            or (existing.created_by_name if existing else None),
            method="manual",
            confidence=1.0,
            source_signal="manual",
        )
        out = await self.upsert_lead_attribution(tenant_id, attribution)
        await self._audit.record(
            principal=principal,
            action="attribution.lead.override",
            resource="attribution.lead_attribution",
            person_uid=PersonUID(person_uid),
            extra={
                "levels": [
                    level
                    for level, ref in (
                        ("vendor", payload.vendor),
                        ("channel", payload.channel),
                        ("campaign", payload.campaign),
                        ("ad_set", payload.ad_set),
                        ("ad", payload.ad),
                        ("form", payload.form),
                    )
                    if ref is not None
                ],
            },
        )
        return out

    async def resolve_many(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> dict[str, int]:
        """Re-resolve a batch of leads. Idempotent; manual overrides stay put."""
        counts = {"resolved": 0, "skipped": 0}
        for person_uid in person_uids:
            out = await self.resolve_person(tenant_id, person_uid)
            counts["resolved" if out is not None else "skipped"] += 1
        return counts

    # --- resolution (ENG-448) ---

    async def load_rules(self, tenant_id: TenantId) -> list[Rule]:
        """Load active mapping rules as waterfall :class:`Rule` objects."""
        rows = await self._repo.list_rules(tenant_id, active_only=True)
        nodes = {n.id: n for n in await self._repo.list_nodes(tenant_id)}
        out: list[Rule] = []
        for row in rows:
            node = nodes.get(row.set_node_id)
            if node is None:
                continue
            out.append(
                Rule(
                    match_field=row.match_field,
                    match_op=row.match_op,
                    match_value=row.match_value,
                    set_level=row.set_level,
                    set_slug=node.slug,
                    set_label=node.label,
                    priority=row.priority,
                )
            )
        # Vendor claims (ENG-571) resolve as vendor-level rules keyed to a
        # configured vendor entity (by its slug/name) rather than a raw node.
        vendors = {
            v.id: v
            for v in await self._repo.list_vendors(tenant_id, active_only=True)
        }
        for claim in await self._repo.list_vendor_claims(
            tenant_id, active_only=True
        ):
            vendor = vendors.get(claim.vendor_id)
            if vendor is None:
                continue
            out.append(
                Rule(
                    match_field=claim.match_field,
                    match_op=claim.match_op,
                    match_value=claim.match_value,
                    set_level="vendor",
                    set_slug=vendor.slug,
                    set_label=vendor.name,
                    priority=claim.priority,
                )
            )
        return out

    async def resolve_and_store(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
        signals: LeadSignals,
        *,
        rules: list[Rule] | None = None,
        sf_lead_id: str | None = None,
    ) -> LeadAttributionOut:
        """Run the waterfall on ``signals``, ensure chain nodes, persist."""
        chain = resolve(signals, rules or [])

        async def _node_id(level: str, pair: tuple[str, str] | None) -> UUID | None:
            if pair is None:
                return None
            node = await self.ensure_node(
                tenant_id, SourceNodeIn(level=level, slug=pair[0], label=pair[1])
            )
            return node.id

        payload = LeadAttributionIn(
            person_uid=person_uid,
            sf_lead_id=sf_lead_id,
            vendor_id=await _node_id("vendor", chain.vendor),
            channel_id=await _node_id("channel", chain.channel),
            campaign_id=await _node_id("campaign", chain.campaign),
            ad_set_id=await _node_id("ad_set", chain.ad_set),
            ad_id=await _node_id("ad", chain.ad),
            form_id=await _node_id("form", chain.form),
            created_by_name=chain.created_by_name,
            method=chain.method,
            confidence=chain.confidence,
            source_signal=chain.source_signal,
        )
        return await self.upsert_lead_attribution(tenant_id, payload)

    async def resolve_person(
        self, tenant_id: TenantId, person_uid: UUID
    ) -> LeadAttributionOut | None:
        """Resolve one person's attribution from captured evidence.

        Reads the person's source links (for the SF lead id and the
        reactivation check — CareStack patient seen before the SF lead) and the
        latest captured SF lead payload, builds signals, applies mapping rules,
        and persists. Returns ``None`` if the person has no SF lead.
        """
        links_by_person = await self._identity.source_links_for_persons(
            tenant_id, [person_uid]
        )
        links = links_by_person.get(person_uid, [])
        sf_lead = next(
            (
                link
                for link in links
                if link.source_system == "salesforce"
                and link.source_kind == "lead"
                and link.source_id
            ),
            None,
        )
        if sf_lead is None:
            return None
        carestack = [
            link
            for link in links
            if link.source_system == "carestack" and link.source_kind == "patient"
        ]
        has_earlier_cs = any(
            link.first_seen_at
            and sf_lead.first_seen_at
            and link.first_seen_at < sf_lead.first_seen_at
            for link in carestack
        )
        payload = await self._ingest.latest_payload(
            tenant_id, event_type="lead.pull", external_id=str(sf_lead.source_id)
        )
        if payload is None:
            return None
        signals = build_signals(payload, has_earlier_carestack=has_earlier_cs)
        rules = await self.load_rules(tenant_id)
        return await self.resolve_and_store(
            tenant_id,
            person_uid,
            signals,
            rules=rules,
            sf_lead_id=str(sf_lead.source_id),
        )


# --- attribution tree assembly (ENG-450, Block D) ---


@dataclass
class _AttrNodeCounts:
    """Mutable per-node accumulator while assembling the attribution tree."""

    leads: int = 0
    consults_scheduled: int = 0
    consults_attended: int = 0
    collected_amount: float = 0.0


def _build_attribution_tree(
    counts: dict[tuple[str, str, str], _AttrNodeCounts],
    labels: dict[tuple[str, str], str],
) -> list[AttributionTreeNodeOut]:
    """Roll (vendor, channel, campaign) slug leaves up into a sorted tree.

    Sibling order is leads-descending at every level so the heaviest resolved
    sources surface first. The slash-joined slug ``key`` is the stable
    drill-down handle the frontend passes back.
    """
    nested: dict[str, dict[str, dict[str, _AttrNodeCounts]]] = {}
    for (vendor, channel, campaign), node_counts in counts.items():
        nested.setdefault(vendor, {}).setdefault(channel, {})[campaign] = node_counts

    def _label(level: str, slug: str) -> str:
        return labels.get((level, slug), slug)

    def _node(
        key: str,
        label: str,
        level: str,
        children: list[AttributionTreeNodeOut],
        leaf: _AttrNodeCounts | None = None,
    ) -> AttributionTreeNodeOut:
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
        return AttributionTreeNodeOut(
            key=key,
            label=label,
            level=level,
            leads=leads,
            consults_scheduled=scheduled,
            consults_attended=attended,
            collected_amount=round(collected, 2),
            children=children,
        )

    vendors: list[AttributionTreeNodeOut] = []
    for vendor, channels_map in nested.items():
        channel_nodes: list[AttributionTreeNodeOut] = []
        for channel, campaigns in channels_map.items():
            campaign_nodes = [
                _node(
                    f"{vendor}/{channel}/{campaign}",
                    _label("campaign", campaign),
                    "campaign",
                    [],
                    leaf=leaf,
                )
                for campaign, leaf in campaigns.items()
            ]
            campaign_nodes.sort(key=lambda n: n.leads, reverse=True)
            channel_nodes.append(
                _node(
                    f"{vendor}/{channel}",
                    _label("channel", channel),
                    "channel",
                    campaign_nodes,
                )
            )
        channel_nodes.sort(key=lambda n: n.leads, reverse=True)
        vendors.append(
            _node(vendor, _label("vendor", vendor), "vendor", channel_nodes)
        )
    vendors.sort(key=lambda n: n.leads, reverse=True)
    return vendors
