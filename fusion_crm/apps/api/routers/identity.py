"""Identity HTTP routes — thin pass-through to ``IdentityService``.

NO business logic in this file. If you reach for ``if`` or a database query
inside a handler, push it down into the service.

Every route resolves ``tenant_id`` from ``Principal.tenant_id`` via the
``get_principal_with_tenant`` dependency (ENG-128) and forwards it to the
service.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.dependencies import get_identity_service, get_principal_with_tenant
from packages.core.security import Principal
from packages.core.types import PersonUID
from packages.identity.schemas import PersonIn, PersonOut, ResolveQuery
from packages.identity.service import IdentityService

router = APIRouter(prefix="/identity", tags=["identity"])

PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.post("/persons", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(
    payload: PersonIn,
    principal: PrincipalDep,
    svc: IdentityService = Depends(get_identity_service),
) -> PersonOut:
    person = await svc.create_person(principal.require_tenant(), payload)
    return PersonOut.model_validate(person)


@router.get("/persons/{person_uid}", response_model=PersonOut)
async def get_person(
    person_uid: UUID,
    principal: PrincipalDep,
    svc: IdentityService = Depends(get_identity_service),
) -> PersonOut:
    person = await svc.get_person(principal.require_tenant(), PersonUID(person_uid))
    return PersonOut.model_validate(person)


@router.post("/persons/resolve", response_model=PersonOut)
async def resolve_person(
    query: ResolveQuery,
    principal: PrincipalDep,
    svc: IdentityService = Depends(get_identity_service),
) -> PersonOut:
    if bool(query.phone) == bool(query.email):
        raise HTTPException(status_code=400, detail="provide exactly one of phone, email")
    tenant_id = principal.require_tenant()
    person = (
        await svc.resolve_by_phone(tenant_id, query.phone)  # type: ignore[arg-type]
        if query.phone
        else await svc.resolve_by_email(tenant_id, query.email)  # type: ignore[arg-type]
    )
    if person is None:
        raise HTTPException(status_code=404, detail="person not found")
    return PersonOut.model_validate(person)
