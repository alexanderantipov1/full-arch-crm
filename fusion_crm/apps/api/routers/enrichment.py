"""Enrichment annotation routes (ENG-439, Block F).

The staff-UI write path for *our own* fields layered over canonical entities.
Handlers stay thin (invariant #5): DTO/query → service → response DTO. All
logic — validation, audit, tenant scoping — lives in
:class:`packages.enrichment.service.EnrichmentService`.

Staff endpoints (not public): they depend on the tenant-aware principal.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from apps.api.dependencies import (
    get_enrichment_service,
    get_principal_with_tenant,
)
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.enrichment.schemas import (
    AnnotationIn,
    AnnotationListOut,
    AnnotationOut,
)
from packages.enrichment.service import EnrichmentService

router = APIRouter(prefix="/enrichment", tags=["enrichment"])

EnrichmentServiceDep = Annotated[EnrichmentService, Depends(get_enrichment_service)]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.post(
    "/annotations",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    body: AnnotationIn,
    svc: EnrichmentServiceDep,
    principal: PrincipalDep,
) -> AnnotationOut:
    tenant_id: TenantId = principal.require_tenant()
    annotation = await svc.add_annotation(tenant_id, body, principal=principal)
    return AnnotationOut.model_validate(annotation)


@router.get("/annotations", response_model=AnnotationListOut)
async def list_annotations(
    svc: EnrichmentServiceDep,
    principal: PrincipalDep,
    subject_type: str = Query(min_length=1, max_length=64),
    subject_id: UUID = Query(),
) -> AnnotationListOut:
    tenant_id: TenantId = principal.require_tenant()
    rows = await svc.list_for_subject(tenant_id, subject_type, subject_id)
    return AnnotationListOut(items=[AnnotationOut.model_validate(row) for row in rows])
