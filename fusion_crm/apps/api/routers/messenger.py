"""Messenger directory routes (ENG-564).

Read-only mirror of the corporate Mattermost server for the staff "Messenger"
settings tab: list teams, and per-team channels. The doctor → Mattermost
username mapping is a separate concern under
``/actor/provider-messenger-mappings`` (ENG-546) and is unaffected.

Handlers stay thin (apps/api invariant #5): path/query → service → DTO. All
logic (provider resolution, credential validation, MM pagination, error
mapping) lives in
:class:`packages.integrations.chat.directory_service.MessengerDirectoryService`.
Domain failures raise ``PlatformError`` subclasses (``NoCredentialError`` 404,
``InvalidChatCredentialError`` 422, ``IntegrationError`` 502); the middleware
translates them to the JSON envelope (no raw ``HTTPException``). No Mattermost
token ever appears in a response, log, or error.

Runs under the platform-wide ANONYMOUS auth stub — the documented single-user
posture (root ``CLAUDE.md`` "Data visibility & access posture").
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.dependencies import (
    get_messenger_directory_service,
    get_principal_with_tenant,
)
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations.chat.directory_schemas import (
    MessengerChannelOut,
    MessengerTeamOut,
)
from packages.integrations.chat.directory_service import (
    MessengerDirectoryService,
)

router = APIRouter(prefix="/messenger", tags=["messenger"])

MessengerDirectoryServiceDep = Annotated[
    MessengerDirectoryService, Depends(get_messenger_directory_service)
]
PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


@router.get("/teams", response_model=list[MessengerTeamOut])
async def list_messenger_teams(
    svc: MessengerDirectoryServiceDep,
    principal: PrincipalDep,
) -> list[MessengerTeamOut]:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.list_teams(tenant_id)


@router.get(
    "/teams/{team_id}/channels",
    response_model=list[MessengerChannelOut],
)
async def list_messenger_channels(
    team_id: str,
    svc: MessengerDirectoryServiceDep,
    principal: PrincipalDep,
) -> list[MessengerChannelOut]:
    tenant_id: TenantId = principal.require_tenant()
    return await svc.list_channels(tenant_id, team_id)
