"""PHI HTTP routes — every endpoint here is gated by ``PhiService`` auth + audit."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from apps.api.dependencies import get_phi_service, get_principal_with_tenant
from packages.core.security import Principal
from packages.core.types import PersonUID
from packages.phi.schemas import PatientProfileIn, PatientProfileOut, PhiPersonSnapshot
from packages.phi.service import PhiService

router = APIRouter(prefix="/phi", tags=["phi"])

PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.get("/persons/{person_uid}/snapshot", response_model=PhiPersonSnapshot)
async def phi_snapshot(
    person_uid: UUID,
    principal: PrincipalDep,
    reason: str = "api.phi.snapshot",
    svc: PhiService = Depends(get_phi_service),
) -> PhiPersonSnapshot:
    return await svc.snapshot(
        principal.require_tenant(), PersonUID(person_uid), reason=reason
    )


@router.put(
    "/persons/{person_uid}/profile",
    response_model=PatientProfileOut,
    status_code=status.HTTP_200_OK,
)
async def upsert_profile(
    person_uid: UUID,
    payload: PatientProfileIn,
    principal: PrincipalDep,
    svc: PhiService = Depends(get_phi_service),
) -> PatientProfileOut:
    if payload.person_uid != person_uid:
        # Path/body must agree; refuse silent rewrite.
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="path person_uid != body person_uid")
    profile = await svc.upsert_profile(principal.require_tenant(), payload)
    return PatientProfileOut.model_validate(profile)
