"""Resolve a :class:`ChatProvider` for a tenant + provider kind.

Block C (ENG-436) shipped the dispatcher and this resolver hook; Block B
(ENG-435) wires the concrete adapters. Today the only supported kind is
``mattermost``: the resolver reads the tenant's decrypted credential via
:class:`IntegrationCredentialService` and constructs a
:class:`MattermostAdapter`.

Error handling is deliberately loud — the dispatcher
(``apps.worker.jobs.notification_dispatch``) catches any exception out of
this function and marks the outbox row ``failed``:

- a missing credential surfaces as ``NoCredentialError`` (from the
  credential service);
- an unknown ``provider_kind`` raises ``UnknownChatProviderError``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import PlatformError
from packages.core.types import TenantId
from packages.tenant.credential_service import IntegrationCredentialService

from .base import ChatProvider
from .mattermost import MattermostAdapter

# Provider kinds this resolver can build an adapter for. Kept narrow on
# purpose — adding a provider is an explicit code change here plus a new
# adapter module.
SUPPORTED_PROVIDER_KINDS = ("mattermost",)


class UnknownChatProviderError(PlatformError):
    """Raised when ``provider_kind`` has no chat adapter wired."""

    code = "unknown_chat_provider"
    http_status = 400


class InvalidChatCredentialError(PlatformError):
    """Raised when a stored chat credential is missing required fields."""

    code = "invalid_chat_credential"
    http_status = 422


async def resolve_chat_provider(
    tenant_id: TenantId,
    provider_kind: str,
    session: AsyncSession,
) -> ChatProvider:
    """Return a chat provider for the given tenant + ``provider_kind``.

    Raises:
        UnknownChatProviderError: ``provider_kind`` has no adapter.
        NoCredentialError: no active credential for the tenant.
        InvalidChatCredentialError: the credential payload is malformed.
    """
    if provider_kind != "mattermost":
        raise UnknownChatProviderError(
            "no chat adapter for provider_kind",
            details={
                "provider_kind": provider_kind,
                "supported": list(SUPPORTED_PROVIDER_KINDS),
            },
        )

    credentials = IntegrationCredentialService(session)
    # ``read_for`` raises ``NoCredentialError`` when no active row exists;
    # the dispatcher catches it and fails the row. Bot tokens are stored
    # under the ``api_key`` credential kind.
    payload = await credentials.read_for(tenant_id, "mattermost", "api_key")

    base_url = payload.get("base_url")
    bot_token = payload.get("bot_token")
    if not isinstance(base_url, str) or not base_url:
        raise InvalidChatCredentialError(
            "mattermost credential missing base_url",
            details={"tenant_id": str(tenant_id)},
        )
    if not isinstance(bot_token, str) or not bot_token:
        raise InvalidChatCredentialError(
            "mattermost credential missing bot_token",
            details={"tenant_id": str(tenant_id)},
        )

    # ENG-458: optional workspace default team a bare channel name resolves
    # against (the bot lives in several teams; "first team" is ambiguous).
    # Per-tenant config carried in the credential payload — no new env var.
    default_team_raw = payload.get("default_team")
    default_team = default_team_raw if isinstance(default_team_raw, str) and default_team_raw else None

    # ENG-564: optional system-admin personal access token enabling the staff
    # "Messenger" directory tab to list ALL teams on the server (the bot token
    # only sees its own memberships). Additive JSONB field — payloads without
    # it keep working. When present it must be a non-empty string (mirrors the
    # bot_token validation); never logged.
    admin_token_raw = payload.get("admin_token")
    if admin_token_raw is not None and not (
        isinstance(admin_token_raw, str) and admin_token_raw
    ):
        raise InvalidChatCredentialError(
            "mattermost credential has invalid admin_token",
            details={"tenant_id": str(tenant_id)},
        )
    admin_token = admin_token_raw if isinstance(admin_token_raw, str) else None

    return MattermostAdapter(
        base_url=base_url,
        bot_token=bot_token,
        default_team=default_team,
        admin_token=admin_token,
    )


__all__ = [
    "resolve_chat_provider",
    "SUPPORTED_PROVIDER_KINDS",
    "UnknownChatProviderError",
    "InvalidChatCredentialError",
]
