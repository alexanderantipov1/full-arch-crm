"""Outreach HTTP routes — templates, campaigns, suppressions.

Phase 1 surface for the operator settings UI (ENG-135). The full
enqueue + send pipeline (ENG-132) is invoked by the worker, not from
HTTP; the tracking pixel + one-click unsubscribe endpoints live in
``apps/api/routers/outreach_tracking.py``.

Per ``apps/api/CLAUDE.md`` this router is a thin pass-through — every
list method delegates to the matching service.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from apps.api.dependencies import (
    get_campaign_service,
    get_principal_with_tenant,
    get_suppression_service,
    get_template_service,
)
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.outreach.schemas import (
    CampaignOut,
    SuppressionOut,
    TemplateOut,
)
from packages.outreach.service import (
    CampaignService,
    SuppressionService,
    TemplateService,
)

router = APIRouter(prefix="/outreach", tags=["outreach"])

TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
CampaignServiceDep = Annotated[CampaignService, Depends(get_campaign_service)]
SuppressionServiceDep = Annotated[
    SuppressionService, Depends(get_suppression_service)
]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


class TemplateListResponse(BaseModel):
    """Mirrors Zod ``TemplateListSchema`` on the frontend."""

    model_config = ConfigDict(from_attributes=True)
    items: list[TemplateOut]


class CampaignListResponse(BaseModel):
    """Mirrors Zod ``CampaignListSchema`` on the frontend."""

    model_config = ConfigDict(from_attributes=True)
    items: list[CampaignOut]


class SuppressionListResponse(BaseModel):
    """Mirrors Zod ``SuppressionListSchema`` on the frontend."""

    model_config = ConfigDict(from_attributes=True)
    items: list[SuppressionOut]


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    svc: TemplateServiceDep,
    principal: PrincipalDep,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> TemplateListResponse:
    tenant_id: TenantId = principal.require_tenant()
    rows = await svc.list_templates(tenant_id, status=status, limit=limit)
    return TemplateListResponse(
        items=[TemplateOut.model_validate(r) for r in rows],
    )


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(
    svc: CampaignServiceDep,
    principal: PrincipalDep,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> CampaignListResponse:
    tenant_id: TenantId = principal.require_tenant()
    rows = await svc.list_campaigns(tenant_id, status=status, limit=limit)
    return CampaignListResponse(
        items=[CampaignOut.model_validate(r) for r in rows],
    )


@router.get("/suppressions", response_model=SuppressionListResponse)
async def list_suppressions(
    svc: SuppressionServiceDep,
    principal: PrincipalDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SuppressionListResponse:
    tenant_id: TenantId = principal.require_tenant()
    rows = await svc.list_for_tenant(tenant_id, limit=limit, offset=offset)
    return SuppressionListResponse(items=list(rows))
