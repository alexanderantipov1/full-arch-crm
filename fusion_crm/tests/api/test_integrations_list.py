from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.routers.integrations_list import list_integrations
from packages.core.types import TenantId
from packages.tenant.schemas import IntegrationCredentialOut

_TENANT_ID = TenantId(uuid.uuid4())


def _fake_db() -> MagicMock:
    """Create a mock AsyncSession whose execute() returns an awaitable result."""
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    return db


def _credential(
    *,
    provider_kind: str,
    credential_kind: str,
    status: str,
    display_name: str | None = None,
) -> IntegrationCredentialOut:
    now = datetime(2026, 5, 22, tzinfo=UTC)
    return IntegrationCredentialOut.model_validate(
        {
            "id": uuid.uuid4(),
            "tenant_id": _TENANT_ID,
            "provider_kind": provider_kind,
            "credential_kind": credential_kind,
            "display_name": display_name,
            "status": status,
            "expires_at": None,
            "last_refreshed_at": None,
            "mailbox_email": None,
            "location_id": None,
            "is_default": False,
            "tags": [],
            "created_at": now,
            "updated_at": now,
        }
    )


@pytest.mark.asyncio
async def test_list_integrations_surfaces_expired_salesforce_as_needs_reconnect() -> None:
    principal = MagicMock()
    principal.require_tenant.return_value = _TENANT_ID
    cred_svc = MagicMock()

    async def _list_for_tenant(
        _tenant_id: TenantId, *, provider_kind: str
    ) -> list[IntegrationCredentialOut]:
        if provider_kind == "salesforce":
            return [
                _credential(
                    provider_kind="salesforce",
                    credential_kind="oauth_token",
                    status="expired",
                    display_name="Salesforce production",
                )
            ]
        return []

    cred_svc.list_for_tenant = AsyncMock(side_effect=_list_for_tenant)

    with patch(
        "apps.api.routers.integrations_list.IntegrationCredentialService",
        return_value=cred_svc,
    ):
        result = await list_integrations(principal, _fake_db())

    salesforce = next(i for i in result.items if i.provider == "salesforce")
    assert salesforce.status == "needs_reconnect"
    assert salesforce.display_name == "Salesforce production"
    assert salesforce.error_message is not None


@pytest.mark.asyncio
async def test_list_integrations_prefers_active_over_expired() -> None:
    principal = MagicMock()
    principal.require_tenant.return_value = _TENANT_ID
    cred_svc = MagicMock()
    cred_svc.list_for_tenant = AsyncMock(
        side_effect=[
            [
                _credential(
                    provider_kind="salesforce",
                    credential_kind="oauth_token",
                    status="expired",
                    display_name="Old Salesforce",
                ),
                _credential(
                    provider_kind="salesforce",
                    credential_kind="oauth_token",
                    status="active",
                    display_name="Salesforce production",
                ),
            ],
            [],
        ]
    )

    with patch(
        "apps.api.routers.integrations_list.IntegrationCredentialService",
        return_value=cred_svc,
    ):
        result = await list_integrations(principal, _fake_db())

    salesforce = next(i for i in result.items if i.provider == "salesforce")
    assert salesforce.status == "connected"
    assert salesforce.display_name == "Salesforce production"
