"""Semantic catalog proposal review routes.

ENG-315 defines the HTTP contract for replacing browser-local catalog review
drafts with service-owned API calls. Handlers stay thin: tenant/principal
wiring, service call, response DTO.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from apps.api.dependencies import (
    get_analytics_catalog_review_service,
    get_principal_with_tenant,
)
from packages.analytics.schemas import (
    CatalogDraftPatchIn,
    CatalogDraftPatchOut,
    CatalogProposalCreateIn,
    CatalogProposalHistoryOut,
    CatalogProposalImpactPreviewOut,
    CatalogProposalListOut,
    CatalogProposalOut,
    CatalogProposalReviewIn,
    CatalogProposalReviewOut,
    CatalogProposalStatus,
    CatalogProposalUpdateIn,
    CatalogVersionHistoryOut,
)
from packages.analytics.service import AnalyticsCatalogReviewService
from packages.core.security import Principal
from packages.core.types import TenantId

router = APIRouter(prefix="/semantic/catalog", tags=["semantic-catalog"])

CatalogReviewServiceDep = Annotated[
    AnalyticsCatalogReviewService,
    Depends(get_analytics_catalog_review_service),
]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.get("/proposals", response_model=CatalogProposalListOut)
async def list_catalog_proposals(
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
    status_filter: CatalogProposalStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> CatalogProposalListOut:
    tenant_id: TenantId = principal.require_tenant()
    items = await svc.list_proposals(tenant_id, status=status_filter, limit=limit)
    return CatalogProposalListOut(items=items)


@router.post(
    "/proposals",
    response_model=CatalogProposalOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_proposal(
    payload: CatalogProposalCreateIn,
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
) -> CatalogProposalOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.create_proposal(tenant_id, payload, principal)


@router.patch("/proposals/{proposal_id}", response_model=CatalogProposalOut)
async def update_catalog_proposal(
    proposal_id: UUID,
    payload: CatalogProposalUpdateIn,
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
) -> CatalogProposalOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.update_proposal(tenant_id, proposal_id, payload, principal)


@router.get(
    "/proposals/{proposal_id}/impact-preview",
    response_model=CatalogProposalImpactPreviewOut,
)
async def preview_catalog_proposal_impact(
    proposal_id: UUID,
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
) -> CatalogProposalImpactPreviewOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.preview_impact(tenant_id, proposal_id)


@router.get(
    "/proposals/{proposal_id}/history",
    response_model=CatalogProposalHistoryOut,
)
async def get_catalog_proposal_history(
    proposal_id: UUID,
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> CatalogProposalHistoryOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.proposal_review_history(tenant_id, proposal_id, limit=limit)


@router.post(
    "/proposals/{proposal_id}/review",
    response_model=CatalogProposalReviewOut,
)
async def review_catalog_proposal(
    proposal_id: UUID,
    payload: CatalogProposalReviewIn,
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
) -> CatalogProposalReviewOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.review_proposal(tenant_id, proposal_id, payload, principal)


@router.get("/versions", response_model=CatalogVersionHistoryOut)
async def get_catalog_version_history(
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
    term: str = Query(min_length=1, max_length=256),
    limit: int = Query(default=100, ge=1, le=500),
) -> CatalogVersionHistoryOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.term_version_history(tenant_id, term, limit=limit)


@router.post("/draft-patch", response_model=CatalogDraftPatchOut)
async def create_catalog_draft_patch(
    payload: CatalogDraftPatchIn,
    svc: CatalogReviewServiceDep,
    principal: PrincipalDep,
) -> CatalogDraftPatchOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.draft_catalog_patch(tenant_id, payload)
