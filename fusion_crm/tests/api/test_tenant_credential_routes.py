"""HTTP-level tests for tenant credential admin routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db, get_principal_with_tenant, get_tenant_service
from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import tenant as tenant_router
from packages.agent_runtime.schemas import AgentRuntimeConnectionCheckOut
from packages.core.exceptions import PlatformError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.tenant.credential_service import NoCredentialError


def _principal(tenant_id: uuid.UUID) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="ops@example.com",
        tenant_id=TenantId(tenant_id),
        roles=frozenset({Role.ADMIN}),
    )


def _credential_body(
    *,
    credential_id: uuid.UUID,
    tenant_id: uuid.UUID,
    provider_kind: str = "google_workspace",
) -> dict[str, Any]:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "id": str(credential_id),
        "tenant_id": str(tenant_id),
        "provider_kind": provider_kind,
        "credential_kind": "oauth_token",
        "display_name": "Main mailbox",
        "status": "active",
        "expires_at": None,
        "last_refreshed_at": None,
        "mailbox_email": "ops@example.com",
        "location_id": None,
        "is_default": True,
        "tags": ["marketing"],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "payload": {"ciphertext": "must-not-leak"},
    }


def _build_app(
    *,
    tenant_id: uuid.UUID,
    db_session: Any,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(tenant_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_principal_with_tenant] = lambda: _principal(tenant_id)
    return app


def test_update_credential_returns_metadata_only(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_update_metadata(self, credential_id_arg, **kwargs):
        captured["credential_id"] = credential_id_arg
        captured.update(kwargs)
        return _credential_body(credential_id=credential_id, tenant_id=tenant_id)

    monkeypatch.setattr(
        tenant_router.IntegrationCredentialService,
        "update_metadata",
        _fake_update_metadata,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.put(
        f"/tenant/credentials/{credential_id}",
        json={
            "display_name": "Main mailbox",
            "tags": ["marketing"],
            "is_default": True,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(credential_id)
    assert body["display_name"] == "Main mailbox"
    assert "payload" not in body
    assert captured["credential_id"] == credential_id
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["payload"].display_name == "Main mailbox"


def test_upsert_bootstrap_credential_returns_metadata_only(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_upsert_bootstrap_credentials(self, tenant_id_arg, payload, **kwargs):
        captured["tenant_id"] = tenant_id_arg
        captured["payload"] = payload
        captured.update(kwargs)
        return _credential_body(
            credential_id=credential_id,
            tenant_id=tenant_id,
            provider_kind="salesforce",
        ) | {
            "credential_kind": "api_key",
            "mailbox_email": None,
            "is_default": False,
        }

    monkeypatch.setattr(
        tenant_router.IntegrationCredentialService,
        "upsert_bootstrap_credentials",
        _fake_upsert_bootstrap_credentials,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/tenant/credentials",
        json={
            "provider_kind": "salesforce",
            "client_id": "sf-client-id",
            "client_secret": "sf-client-secret",
            "callback_url": "https://fusioncrm.app/api/integrations/salesforce/callback",
            "domain": "login.salesforce.com",
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_kind"] == "salesforce"
    assert body["credential_kind"] == "api_key"
    assert "payload" not in body
    assert "sf-client-secret" not in res.text
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["payload"].client_secret == "sf-client-secret"


def test_upsert_openai_credential_returns_metadata_only(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_upsert_bootstrap_credentials(self, tenant_id_arg, payload, **kwargs):
        captured["tenant_id"] = tenant_id_arg
        captured["payload"] = payload
        captured.update(kwargs)
        return _credential_body(
            credential_id=credential_id,
            tenant_id=tenant_id,
            provider_kind="openai",
        ) | {
            "credential_kind": "api_key",
            "display_name": "OpenAI primary",
            "mailbox_email": None,
            "is_default": True,
        }

    monkeypatch.setattr(
        tenant_router.IntegrationCredentialService,
        "upsert_bootstrap_credentials",
        _fake_upsert_bootstrap_credentials,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/tenant/credentials",
        json={
            "provider_kind": "openai",
            "credential_kind": "api_key",
            "display_name": "OpenAI primary",
            "api_key": "sk-test-openai-secret",
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_kind"] == "openai"
    assert body["credential_kind"] == "api_key"
    assert "payload" not in body
    assert "sk-test-openai-secret" not in res.text
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["payload"].api_key == "sk-test-openai-secret"


def test_openai_connection_check_returns_safe_metadata(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_test_openai_connection(self, principal):
        captured["tenant_id"] = principal.require_tenant()
        captured["principal_email"] = principal.email
        return AgentRuntimeConnectionCheckOut(
            ok=True,
            model="gpt-4.1-mini",
            last_agent="Fusion OpenAI Health Check",
            output="ok",
        )

    monkeypatch.setattr(
        tenant_router.AgentRuntimeService,
        "test_openai_connection",
        _fake_test_openai_connection,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post("/tenant/credentials/openai/test")

    assert res.status_code == 200
    body = res.json()
    assert body == {
        "ok": True,
        "runtime": "agent_runtime",
        "provider_kind": "openai",
        "credential_kind": "api_key",
        "model": "gpt-4.1-mini",
        "last_agent": "Fusion OpenAI Health Check",
        "output": "ok",
    }
    assert "sk-" not in res.text
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["principal_email"] == "ops@example.com"
    assert captured["tenant_id"] == TenantId(tenant_id)


def test_upsert_bootstrap_credential_rejects_wrong_kind() -> None:
    tenant_id = uuid.uuid4()
    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.post(
        "/tenant/credentials",
        json={
            "provider_kind": "salesforce",
            "credential_kind": "password_grant",
            "client_id": "sf-client-id",
            "client_secret": "sf-client-secret",
            "callback_url": "https://fusioncrm.app/api/integrations/salesforce/callback",
        },
    )

    assert res.status_code == 422


def test_upsert_bootstrap_credential_rejects_cross_provider_fields() -> None:
    tenant_id = uuid.uuid4()
    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))

    sf_res = client.post(
        "/tenant/credentials",
        json={
            "provider_kind": "salesforce",
            "credential_kind": "api_key",
            "client_id": "sf-client-id",
            "client_secret": "sf-client-secret",
            "callback_url": "https://fusioncrm.app/api/integrations/salesforce/callback",
            "vendor_key": "carestack-only",
        },
    )
    cs_res = client.post(
        "/tenant/credentials",
        json={
            "provider_kind": "carestack",
            "credential_kind": "password_grant",
            "client_id": "cs-client-id",
            "client_secret": "cs-client-secret",
            "vendor_key": "vendor",
            "account_key": "account-key",
            "account_id": "account-id",
            "idp_base_url": "https://identity.carestack.com",
            "api_base_url": "https://api.carestack.com",
            "callback_url": "https://fusioncrm.app/api/integrations/salesforce/callback",
        },
    )

    assert sf_res.status_code == 422
    assert cs_res.status_code == 422


def test_update_credential_not_found_uses_platform_error(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()

    async def _fake_update_metadata(self, credential_id_arg, **kwargs):
        raise NoCredentialError("credential not found")

    monkeypatch.setattr(
        tenant_router.IntegrationCredentialService,
        "update_metadata",
        _fake_update_metadata,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.put(
        f"/tenant/credentials/{credential_id}",
        json={"display_name": "Main mailbox"},
    )

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_list_credentials_filters_and_returns_metadata_only(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    async def _fake_list_for_tenant(self, tenant_id_arg, provider_kind=None, **kwargs):
        captured["tenant_id"] = tenant_id_arg
        captured["provider_kind"] = provider_kind
        captured.update(kwargs)
        return [
            _credential_body(
                credential_id=credential_id,
                tenant_id=tenant_id,
                provider_kind="salesforce",
            )
        ]

    monkeypatch.setattr(
        tenant_router.IntegrationCredentialService,
        "list_for_tenant",
        _fake_list_for_tenant,
    )

    client = TestClient(_build_app(tenant_id=tenant_id, db_session=MagicMock()))
    res = client.get(
        "/tenant/credentials",
        params={"provider_kind": "salesforce", "include_revoked": "true"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body[0]["provider_kind"] == "salesforce"
    assert "payload" not in body[0]
    assert captured == {
        "tenant_id": TenantId(tenant_id),
        "provider_kind": "salesforce",
        "include_revoked": True,
    }


def test_upsert_setting_uses_path_key() -> None:
    tenant_id = uuid.uuid4()
    captured: dict[str, Any] = {}
    now = datetime(2026, 1, 1, tzinfo=UTC)

    class FakeTenantService:
        async def upsert_setting(self, tenant_id_arg, payload, *, principal):
            captured["tenant_id"] = tenant_id_arg
            captured["key"] = payload.key
            captured["value"] = payload.value
            captured["principal"] = principal
            return SimpleNamespace(
                tenant_id=tenant_id_arg,
                key=payload.key,
                value=payload.value,
                updated_at=now,
            )

    app = _build_app(tenant_id=tenant_id, db_session=MagicMock())
    app.dependency_overrides[get_tenant_service] = lambda: FakeTenantService()
    client = TestClient(app)

    res = client.put(
        "/tenant/settings/provider_link_bases",
        json={
            "value": {
                "salesforce_lightning_base_url": "https://fusiondentalimplants.lightning.force.com",
                "carestack_app_base_url": "https://antipov.carestack.com",
            }
        },
    )

    assert res.status_code == 200
    assert res.json() == {
        "tenant_id": str(tenant_id),
        "key": "provider_link_bases",
        "value": {
            "salesforce_lightning_base_url": "https://fusiondentalimplants.lightning.force.com",
            "carestack_app_base_url": "https://antipov.carestack.com",
        },
        "updated_at": now.isoformat().replace("+00:00", "Z"),
    }
    assert captured["tenant_id"] == TenantId(tenant_id)
    assert captured["key"] == "provider_link_bases"
    assert captured["value"] == {
        "salesforce_lightning_base_url": "https://fusiondentalimplants.lightning.force.com",
        "carestack_app_base_url": "https://antipov.carestack.com",
    }
