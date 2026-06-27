"""Provider → Mattermost username mapping routes (ENG-546, Step 2b).

The staff Messenger-settings card maps each CareStack provider (doctor) to a
Mattermost username so the T-15m consult-reminder can @mention them (ENG-543).
This is the API behind that card; it replaces the interim operator script
``infra/scripts/set_provider_mattermost.py``.

Handlers stay thin (apps/api invariant #5): path/body → service → DTO. All
logic — actor resolution, the additive-attach purge that keeps exactly one
``mattermost_username`` per doctor, tenant scoping — lives in
:class:`packages.actor.service.ActorService`. Domain failures raise
``PlatformError`` subclasses (``NotFoundError`` / ``ValidationError``); the
middleware translates them to the JSON envelope (no raw ``HTTPException``).

Like every other endpoint today these run under the platform-wide ANONYMOUS
auth stub — the documented single-user posture (root ``CLAUDE.md`` "Data
visibility & access posture"): no per-endpoint authn/authz this phase, on any
environment, with one trusted operator. Endpoint authz arrives later as the
uniform access-control layer.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_actor_service, get_principal_with_tenant
from packages.actor.schemas import (
    ProviderMessengerMappingListOut,
    ProviderMessengerMappingOut,
    SetProviderMessengerUsernameIn,
)
from packages.actor.service import ActorService
from packages.core.security import Principal
from packages.core.types import TenantId

router = APIRouter(
    prefix="/actor/provider-messenger-mappings",
    tags=["provider-messenger-mappings"],
)

ActorServiceDep = Annotated[ActorService, Depends(get_actor_service)]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.get("", response_model=ProviderMessengerMappingListOut)
async def list_provider_messenger_mappings(
    svc: ActorServiceDep,
    principal: PrincipalDep,
) -> ProviderMessengerMappingListOut:
    tenant_id: TenantId = principal.require_tenant()
    items = await svc.list_provider_messenger_mappings(tenant_id)
    return ProviderMessengerMappingListOut(items=items)


@router.put(
    "/{carestack_provider_id}",
    response_model=ProviderMessengerMappingOut,
)
async def set_provider_messenger_username(
    carestack_provider_id: str,
    body: SetProviderMessengerUsernameIn,
    svc: ActorServiceDep,
    principal: PrincipalDep,
) -> ProviderMessengerMappingOut:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.set_provider_messenger_username(
        tenant_id, carestack_provider_id, body.mattermost_username
    )
