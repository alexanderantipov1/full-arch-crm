"""Lead source attribution API (ENG-449).

Thin DTO → service wiring for the manual-enrichment surface: source-node and
mapping-rule management, per-lead manual override, and single-lead resolution.
No business logic here — see ``packages.attribution.service``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from packages.attribution.schemas import (
    AttributionLeadListOut,
    AttributionTreeOut,
    ClaimSuggestionsOut,
    LeadAttributionOut,
    LeadOverrideIn,
    MappingRuleIn,
    MappingRuleOut,
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
from packages.attribution.service import AttributionService
from packages.core.security import Principal
from packages.interaction.service import InteractionService
from packages.ops.service import OpsService

from ..dependencies import (
    get_attribution_service,
    get_interaction_service,
    get_ops_service,
    get_principal_with_tenant,
)

router = APIRouter(prefix="/attribution", tags=["attribution"])

_Principal = Annotated[Principal, Depends(get_principal_with_tenant)]
_Service = Annotated[AttributionService, Depends(get_attribution_service)]
_Ops = Annotated[OpsService, Depends(get_ops_service)]
_Interaction = Annotated[InteractionService, Depends(get_interaction_service)]


# --- source nodes (controlled vocabulary) ---


@router.get("/nodes", response_model=list[SourceNodeOut])
async def list_nodes(
    principal: _Principal,
    service: _Service,
    level: Annotated[str | None, Query()] = None,
) -> list[SourceNodeOut]:
    return await service.list_nodes(principal.require_tenant(), level=level)


@router.post("/nodes", response_model=SourceNodeOut)
async def create_node(
    payload: SourceNodeIn, principal: _Principal, service: _Service
) -> SourceNodeOut:
    return await service.ensure_node(principal.require_tenant(), payload)


# --- vendors (ENG-570) ---


@router.get("/vendors", response_model=list[VendorOut])
async def list_vendors(
    principal: _Principal,
    service: _Service,
    active_only: Annotated[bool, Query()] = False,
) -> list[VendorOut]:
    return await service.list_vendors(
        principal.require_tenant(), active_only=active_only
    )


@router.post("/vendors", response_model=VendorOut)
async def create_vendor(
    payload: VendorIn, principal: _Principal, service: _Service
) -> VendorOut:
    return await service.create_vendor(
        principal.require_tenant(), payload, principal=principal
    )


@router.patch("/vendors/{vendor_id}", response_model=VendorOut | None)
async def update_vendor(
    vendor_id: UUID,
    payload: VendorUpdateIn,
    principal: _Principal,
    service: _Service,
) -> VendorOut | None:
    return await service.update_vendor(
        principal.require_tenant(), vendor_id, payload, principal=principal
    )


@router.delete("/vendors/{vendor_id}")
async def deactivate_vendor(
    vendor_id: UUID, principal: _Principal, service: _Service
) -> dict[str, bool]:
    deactivated = await service.deactivate_vendor(
        principal.require_tenant(), vendor_id, principal=principal
    )
    return {"deactivated": deactivated}


# --- vendor monthly costs (ENG-573) ---


@router.get("/vendors/{vendor_id}/costs", response_model=list[VendorCostOut])
async def list_vendor_costs(
    vendor_id: UUID, principal: _Principal, service: _Service
) -> list[VendorCostOut]:
    return await service.list_vendor_costs(principal.require_tenant(), vendor_id)


@router.put("/vendors/{vendor_id}/costs", response_model=VendorCostOut | None)
async def set_vendor_cost(
    vendor_id: UUID,
    payload: VendorCostIn,
    principal: _Principal,
    service: _Service,
) -> VendorCostOut | None:
    return await service.set_vendor_cost(
        principal.require_tenant(), vendor_id, payload, principal=principal
    )


@router.delete("/vendors/{vendor_id}/costs/{period_month}")
async def delete_vendor_cost(
    vendor_id: UUID,
    period_month: str,
    principal: _Principal,
    service: _Service,
) -> dict[str, bool]:
    deleted = await service.delete_vendor_cost(
        principal.require_tenant(), vendor_id, period_month, principal=principal
    )
    return {"deleted": deleted}


# --- vendor claims + unassigned signatures (ENG-571) ---


@router.get(
    "/vendors/{vendor_id}/claims", response_model=list[VendorClaimOut]
)
async def list_vendor_claims(
    vendor_id: UUID, principal: _Principal, service: _Service
) -> list[VendorClaimOut]:
    return await service.list_vendor_claims(
        principal.require_tenant(), vendor_id=vendor_id
    )


@router.post("/vendors/{vendor_id}/claims", response_model=VendorClaimOut | None)
async def create_vendor_claim(
    vendor_id: UUID,
    payload: VendorClaimIn,
    principal: _Principal,
    service: _Service,
) -> VendorClaimOut | None:
    return await service.create_vendor_claim(
        principal.require_tenant(), vendor_id, payload, principal=principal
    )


@router.delete("/vendors/{vendor_id}/claims/{claim_id}")
async def delete_vendor_claim(
    vendor_id: UUID,
    claim_id: UUID,
    principal: _Principal,
    service: _Service,
) -> dict[str, bool]:
    deleted = await service.delete_vendor_claim(
        principal.require_tenant(), claim_id, principal=principal
    )
    return {"deleted": deleted}


@router.get(
    "/vendors/{vendor_id}/claim-suggestions", response_model=ClaimSuggestionsOut | None
)
async def vendor_claim_suggestions(
    vendor_id: UUID,
    principal: _Principal,
    service: _Service,
    lead_limit: Annotated[int, Query(ge=1, le=10000)] = 2000,
) -> ClaimSuggestionsOut | None:
    """Agent-proposed bindings for a vendor: Unassigned signatures whose value
    matches the vendor's name/slug tokens (ENG-574). Accept → claim origin=agent."""
    return await service.suggest_claims_for_vendor(
        principal.require_tenant(), vendor_id, lead_limit=lead_limit
    )


@router.get("/unassigned-signatures", response_model=UnassignedSignaturesOut)
async def unassigned_signatures(
    principal: _Principal,
    service: _Service,
    lead_limit: Annotated[int, Query(ge=1, le=10000)] = 2000,
) -> UnassignedSignaturesOut:
    """Distinct traffic signatures behind the Unassigned (no-vendor) leads —
    the source list for binding traffic to a vendor (ENG-571)."""
    return await service.unassigned_signatures(
        principal.require_tenant(), lead_limit=lead_limit
    )


# --- mapping rules ---


@router.get("/rules", response_model=list[MappingRuleOut])
async def list_rules(
    principal: _Principal,
    service: _Service,
    active_only: Annotated[bool, Query()] = True,
) -> list[MappingRuleOut]:
    return await service.list_rules(
        principal.require_tenant(), active_only=active_only
    )


@router.post("/rules", response_model=MappingRuleOut)
async def create_rule(
    payload: MappingRuleIn, principal: _Principal, service: _Service
) -> MappingRuleOut:
    return await service.create_rule(
        principal.require_tenant(), payload, principal=principal
    )


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: UUID, principal: _Principal, service: _Service
) -> dict[str, bool]:
    deleted = await service.delete_rule(
        principal.require_tenant(), rule_id, principal=principal
    )
    return {"deleted": deleted}


# --- per-lead attribution ---


@router.get("/leads/{person_uid}", response_model=LeadAttributionOut | None)
async def get_lead_attribution(
    person_uid: UUID, principal: _Principal, service: _Service
) -> LeadAttributionOut | None:
    return await service.get_lead_attribution(principal.require_tenant(), person_uid)


@router.post("/leads/{person_uid}/override", response_model=LeadAttributionOut)
async def override_lead_attribution(
    person_uid: UUID,
    payload: LeadOverrideIn,
    principal: _Principal,
    service: _Service,
) -> LeadAttributionOut:
    return await service.set_override(
        principal.require_tenant(), person_uid, payload, principal=principal
    )


@router.post("/leads/{person_uid}/resolve", response_model=LeadAttributionOut | None)
async def resolve_lead_attribution(
    person_uid: UUID, principal: _Principal, service: _Service
) -> LeadAttributionOut | None:
    return await service.resolve_person(principal.require_tenant(), person_uid)


# --- analytics: funnel by attribution chain level (ENG-450, Block D) ---


@router.get("/analytics/tree", response_model=AttributionTreeOut)
async def attribution_tree(
    principal: _Principal,
    service: _Service,
    ops: _Ops,
    interaction: _Interaction,
    period: Annotated[
        str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    ] = None,
) -> AttributionTreeOut:
    """Hierarchical lead→consult funnel sliced by the resolved chain (ENG-450).

    Replaces the dashboard "unknown" bucket with the resolved vendor → channel
    → campaign breakdown and surfaces the ``needs_review`` gap explicitly. The
    route wires cross-domain inputs (collected cash from interaction, consult
    counts from ops); the attribution service attributes them to nodes.

    ``period`` ('YYYY-MM', ENG-572/ENG-573) windows the breakdown to that
    month's leads (persons resolved by ops) and turns on per-vendor cost/CPL.
    """
    tenant_id = principal.require_tenant()
    collected = await interaction.collected_by_person(tenant_id)
    consults = await ops.consult_counts_by_person(tenant_id)
    person_filter: set[UUID] | None = None
    if period is not None:
        person_filter = await ops.lead_person_uids_in_month(tenant_id, period)
        collected = {p: v for p, v in collected.items() if p in person_filter}
        consults = {p: v for p, v in consults.items() if p in person_filter}
    return await service.get_attribution_tree(
        tenant_id,
        collected_by_person=collected,
        consults_by_person=consults,
        person_filter=person_filter,
        period=period,
    )


@router.get("/analytics/leads", response_model=AttributionLeadListOut)
async def attribution_node_leads(
    principal: _Principal,
    service: _Service,
    interaction: _Interaction,
    ops: _Ops,
    vendor: Annotated[str | None, Query(max_length=160)] = None,
    channel: Annotated[str | None, Query(max_length=160)] = None,
    campaign: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    period: Annotated[
        str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    ] = None,
) -> AttributionLeadListOut:
    """Drill-down lead list behind one attribution tree node (ENG-450).

    At least one of ``vendor``/``channel``/``campaign`` slugs is required
    (service-validated). The ``__none__`` sentinel slug matches the
    NULL/unassigned bucket at that level. ``period`` ('YYYY-MM') windows to the
    month's leads (ENG-572).
    """
    tenant_id = principal.require_tenant()
    collected = await interaction.collected_by_person(tenant_id)
    person_filter: set[UUID] | None = None
    if period is not None:
        person_filter = await ops.lead_person_uids_in_month(tenant_id, period)
        collected = {p: v for p, v in collected.items() if p in person_filter}
    return await service.list_leads_for_chain_node(
        tenant_id,
        vendor=vendor,
        channel=channel,
        campaign=campaign,
        limit=limit,
        offset=offset,
        collected_by_person=collected,
        person_filter=person_filter,
    )
