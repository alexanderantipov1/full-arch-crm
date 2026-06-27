"""Scheduled Salesforce OAuth token keepalive.

The runtime Salesforce client already refreshes reactively when an API call
returns 401. This worker job refreshes proactively on a quiet cadence so an
idle tenant's connection does not sit on a stale access token until the next
operator action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from packages.core.exceptions import PlatformError
from packages.core.logging import get_logger
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.integrations.salesforce import SfClient
from packages.integrations.salesforce.exceptions import SfNotConnectedError
from packages.integrations.salesforce.tokens import SfTokens
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)
from packages.tenant.service import TenantService

from .ingest_scheduled import _scheduler_principal

log = get_logger("worker.salesforce_token_keepalive")


async def refresh_salesforce_token_for_tenant(
    _ctx: dict[str, Any], tenant_id_str: str
) -> dict[str, Any]:
    """Refresh one tenant's Salesforce OAuth token.

    Missing credentials are skipped. A Salesforce ``invalid_grant`` marks the
    active OAuth credential expired so the UI can show a reconnect-required
    state instead of repeatedly attempting to use a dead refresh token.
    """
    tenant_id = TenantId(UUID(tenant_id_str))
    async with async_session() as session:
        cred_svc = IntegrationCredentialService(session)
        try:
            oauth_payload = await cred_svc.read_for(
                tenant_id, "salesforce", "oauth_token"
            )
        except NoCredentialError:
            log.info(
                "salesforce_token_keepalive.no_credential",
                tenant_id=tenant_id_str,
            )
            return {"skipped": "no_credential"}

        try:
            api_key_payload: dict[str, object] | None = await cred_svc.read_for(
                tenant_id, "salesforce", "api_key"
            )
        except (NoCredentialError, PlatformError):
            api_key_payload = None

        principal = _scheduler_principal(tenant_id)

        async def _persist(tokens: SfTokens) -> None:
            new_payload: dict[str, object] = {
                "access_token": tokens.access_token,
                "instance_url": tokens.instance_url,
            }
            if tokens.refresh_token:
                new_payload["refresh_token"] = tokens.refresh_token
            if tokens.issued_at:
                new_payload["issued_at"] = tokens.issued_at
            await cred_svc.upsert(
                tenant_id,
                "salesforce",
                "oauth_token",
                new_payload,
                principal=principal,
                display_name="Salesforce OAuth tokens (refreshed by keepalive)",
                last_refreshed_at=datetime.now(UTC),
            )

        sf_client = SfClient.from_credential(
            oauth_payload,
            on_refresh=_persist,
            api_key_payload=api_key_payload,
        )
        try:
            await sf_client.refresh_access_token()
        except SfNotConnectedError as exc:
            if exc.details.get("action") == "reconnect":
                expired_count = await cred_svc.expire_active_for(
                    tenant_id,
                    "salesforce",
                    "oauth_token",
                    principal=principal,
                )
                log.info(
                    "salesforce_token_keepalive.needs_reconnect",
                    tenant_id=tenant_id_str,
                    expired_count=expired_count,
                    reason=str(exc.details.get("sf_error", "")),
                )
                return {
                    "skipped": "needs_reconnect",
                    "expired_count": expired_count,
                }
            log.warning(
                "salesforce_token_keepalive.refresh_failed",
                tenant_id=tenant_id_str,
                error=exc.message,
                details=exc.details,
            )
            return {"failed": "refresh_failed"}
        except Exception as exc:  # noqa: BLE001 - transient provider/network failure
            log.warning(
                "salesforce_token_keepalive.transient_failed",
                tenant_id=tenant_id_str,
                error=str(exc),
            )
            return {"failed": "transient_failed"}
        finally:
            await sf_client.close()

    log.info("salesforce_token_keepalive.refreshed", tenant_id=tenant_id_str)
    return {"refreshed": True}


async def refresh_salesforce_tokens(ctx: dict[str, Any]) -> dict[str, int]:
    """Cron entry: refresh active Salesforce OAuth tokens for every tenant."""
    _ = ctx
    summary = {
        "tenants": 0,
        "refreshed": 0,
        "skipped": 0,
        "needs_reconnect": 0,
        "failed": 0,
    }

    async with async_session() as session:
        tenant_rows = await TenantService(session).list_tenants()
        tenant_ids = [str(t.id) for t in tenant_rows]

    if not tenant_ids:
        log.info("salesforce_token_keepalive.no_tenants")
        return summary

    for tenant_id_str in tenant_ids:
        summary["tenants"] += 1
        try:
            result = await refresh_salesforce_token_for_tenant({}, tenant_id_str)
        except Exception as exc:  # noqa: BLE001 - one tenant must not poison the tick
            log.error(
                "salesforce_token_keepalive.error",
                tenant_id=tenant_id_str,
                error=str(exc),
            )
            summary["failed"] += 1
            continue

        if result.get("refreshed"):
            summary["refreshed"] += 1
        elif result.get("skipped") == "needs_reconnect":
            summary["needs_reconnect"] += 1
        elif result.get("skipped"):
            summary["skipped"] += 1
        else:
            summary["failed"] += 1

    log.info("salesforce_token_keepalive.tick", summary=summary)
    return summary
