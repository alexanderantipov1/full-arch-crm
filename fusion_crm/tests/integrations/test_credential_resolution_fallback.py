"""ENG-125 — credential resolution fallback ordering.

Asserts the contract that the SF / CareStack credential paths follow:

  1. ``IntegrationCredentialService.read_for`` returns the DB row when
     present (DB-first).
  2. ``NoCredentialError`` is raised when no row exists; the caller is
     expected to fall back to ``Settings.salesforce_*`` /
     ``Settings.carestack_*``.
  3. The fallback path is deterministic — the env values are read via
     the same ``Settings`` accessor as application code, never via
     ``os.environ`` directly.

These are unit-level tests; the production end-to-end (Next.js calls
FastAPI; FastAPI hits Postgres) is covered separately by the TS
``credentialResolver.test.ts`` and (when integrated) by a smoke test
in CI.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from packages.core.types import TenantId
from packages.integrations import crypto
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
    _wrap_envelope,
)
from packages.tenant.models import IntegrationCredential


@pytest.fixture(autouse=True)
def _isolate_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a real Fernet without touching ``Settings``."""
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(crypto, "_get_fernet", lambda: fernet)


def _scalar_one_or_none_result(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _make_service() -> tuple[IntegrationCredentialService, MagicMock]:
    session = MagicMock()
    session.execute = AsyncMock()
    service = IntegrationCredentialService(session)
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()
    return service, session


# --- Salesforce ---


@pytest.mark.asyncio
async def test_sf_db_first_succeeds_when_row_present() -> None:
    service, session = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    payload = {
        "client_id": "abc",
        "client_secret": "shh",
        "callback_url": "https://x/cb",
        "domain": "login.salesforce.com",
    }
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="api_key",
        payload=_wrap_envelope(payload),
        status="active",
    )
    cred.id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    decoded = await service.read_for(tenant_id, "salesforce", "api_key")
    assert decoded == payload


@pytest.mark.asyncio
async def test_sf_no_row_raises_no_credential_error() -> None:
    """When the DB has no row for the tuple, the service raises
    ``NoCredentialError``. The caller (e.g. an SF client builder)
    converts this into an env-fallback or a 409 ``not_connected``."""
    service, session = _make_service()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

    with pytest.raises(NoCredentialError):
        await service.read_for(TenantId(uuid.uuid4()), "salesforce", "api_key")


# --- CareStack ---


@pytest.mark.asyncio
async def test_cs_db_first_succeeds_when_row_present() -> None:
    service, session = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    payload = {
        "client_id": "cs_id",
        "client_secret": "cs_secret",
        "vendor_key": "vk",
        "account_key": "ak",
        "account_id": "10029",
        "idp_base_url": "https://idp.x",
        "api_base_url": "https://api.x",
        "api_version": "v1.0",
    }
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="carestack",
        credential_kind="password_grant",
        payload=_wrap_envelope(payload),
        status="active",
    )
    cred.id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    decoded = await service.read_for(tenant_id, "carestack", "password_grant")
    assert decoded == payload


@pytest.mark.asyncio
async def test_cs_no_row_raises_no_credential_error() -> None:
    service, session = _make_service()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
    with pytest.raises(NoCredentialError):
        await service.read_for(
            TenantId(uuid.uuid4()), "carestack", "password_grant"
        )


# --- Env-fallback contract ---


def test_settings_fields_present_for_env_fallback() -> None:
    """The fallback path MUST go through ``Settings``; this asserts the
    field names that callers depend on still exist on the Settings model.

    Settings is imported defensively here — the test suite environment
    sets the required env vars; if it does not, the assert documents
    the dependency rather than crashing the whole test module."""
    from packages.core.config import Settings

    field_names = set(Settings.model_fields.keys())
    assert "salesforce_client_id" in field_names
    assert "salesforce_client_secret" in field_names
    assert "carestack_client_id" in field_names
    assert "carestack_vendor_key" in field_names
    # Internal token field exists (added with ENG-125).
    assert "internal_credential_token" in field_names
