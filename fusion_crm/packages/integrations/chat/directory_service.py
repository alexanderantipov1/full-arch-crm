"""Read-only Mattermost directory service (ENG-564).

Backs the staff "Messenger" settings tab: list the teams on the corporate
Mattermost server and, per team, its channels. This is a *mirror* — no writes,
no provisioning. The doctor-mapping card stays under the ``settings`` tab and
keeps its own router/service (``provider_messenger_mappings`` / ``ActorService``).

Lives in ``integrations.chat`` deliberately: ``actor`` / ``ops`` must not import
``integrations`` (matrix in ``packages/CLAUDE.md``), and the only dependency
here is the chat provider resolver + adapter, both inside this subpackage.

Failure mapping (the API middleware turns these into the JSON envelope):

* resolver raises (no credential / invalid credential / unknown kind) → it
  propagates unchanged (``NoCredentialError`` 404, ``InvalidChatCredentialError``
  422, ``UnknownChatProviderError`` 400);
* adapter returns ``None`` (token rejected, server unreachable / timeout) →
  ``IntegrationError`` (``integration_error``, HTTP 502). No token, no payload
  ever enters the message or details;
* adapter returns ``[]`` (genuinely empty) → ``[]`` (HTTP 200).
"""

from __future__ import annotations

from typing import Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import IntegrationError
from packages.core.types import TenantId

from .directory_schemas import MessengerChannelOut, MessengerTeamOut
from .resolver import resolve_chat_provider


class MessengerDirectoryProvider(Protocol):
    """The slice of a chat adapter the directory needs (``MattermostAdapter``)."""

    async def list_teams(self) -> list[dict[str, object]] | None: ...

    async def list_channels(
        self, team_id: str
    ) -> list[dict[str, object]] | None: ...

    def team_url(self, team_name: str) -> str: ...


class MessengerDirectoryService:
    """List Mattermost teams + channels for the staff directory tab.

    Resolves the tenant's Mattermost adapter via ``resolve_chat_provider`` per
    call (matching the worker dispatcher). A provider may be injected for tests.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        provider: MessengerDirectoryProvider | None = None,
    ) -> None:
        self._session = session
        self._provider = provider

    async def list_teams(self, tenant_id: TenantId) -> list[MessengerTeamOut]:
        provider = await self._resolve(tenant_id)
        teams = await provider.list_teams()
        if teams is None:
            raise _unavailable(tenant_id)
        return [
            MessengerTeamOut(
                id=_field(team, "id"),
                name=_field(team, "name"),
                display_name=_field(team, "display_name"),
                url=provider.team_url(_field(team, "name")),
            )
            for team in teams
        ]

    async def list_channels(
        self, tenant_id: TenantId, team_id: str
    ) -> list[MessengerChannelOut]:
        provider = await self._resolve(tenant_id)
        channels = await provider.list_channels(team_id)
        if channels is None:
            raise _unavailable(tenant_id)
        return [
            MessengerChannelOut(
                id=_field(channel, "id"),
                name=_field(channel, "name"),
                display_name=_field(channel, "display_name"),
                type=_field(channel, "type"),
                purpose=_field(channel, "purpose"),
            )
            for channel in channels
        ]

    async def _resolve(self, tenant_id: TenantId) -> MessengerDirectoryProvider:
        if self._provider is not None:
            return self._provider
        provider = await resolve_chat_provider(
            tenant_id, "mattermost", self._session
        )
        # ``resolve_chat_provider`` only builds ``MattermostAdapter`` for the
        # ``mattermost`` kind, which implements the directory methods.
        return cast(MessengerDirectoryProvider, provider)


def _field(obj: dict[str, object], key: str) -> str:
    """Return a string field from a raw MM dict, or ``""`` when absent/non-str."""
    value = obj.get(key)
    return value if isinstance(value, str) else ""


def _unavailable(tenant_id: TenantId) -> IntegrationError:
    """Build the token-free 502 for a rejected/unreachable Mattermost server."""
    return IntegrationError(
        "Mattermost directory unavailable",
        details={"tenant_id": str(tenant_id)},
    )


__all__ = ["MessengerDirectoryService", "MessengerDirectoryProvider"]
