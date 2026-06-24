"""Unit tests for ``resolve_chat_provider`` (ENG-435, Block B).

The resolver maps ``provider_kind == "mattermost"`` onto a
:class:`MattermostAdapter` built from the tenant's decrypted credential.
These tests monkeypatch ``IntegrationCredentialService.read_for`` so no
database is touched — credential decryption is covered by the tenant
suite.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from packages.core.types import TenantId
from packages.integrations.chat import resolver as resolver_mod
from packages.integrations.chat.mattermost import MattermostAdapter
from packages.integrations.chat.resolver import (
    InvalidChatCredentialError,
    UnknownChatProviderError,
    resolve_chat_provider,
)
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)


class _DummySession:
    """Stand-in for AsyncSession; the resolver never queries through it."""


def _tenant() -> TenantId:
    return TenantId(uuid.uuid4())


async def test_resolves_mattermost_adapter_from_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, tenant_id, provider_kind, credential_kind=None):  # noqa: ANN001
        assert provider_kind == "mattermost"
        assert credential_kind == "api_key"
        return {"base_url": "https://chat.example.com", "bot_token": "tok"}

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    provider = await resolve_chat_provider(
        _tenant(), "mattermost", _DummySession()
    )

    assert isinstance(provider, MattermostAdapter)
    assert provider._base_url == "https://chat.example.com"  # noqa: SLF001
    assert provider._bot_token == "tok"  # noqa: SLF001


async def test_unknown_provider_kind_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(UnknownChatProviderError):
        await resolve_chat_provider(_tenant(), "slack", _DummySession())


async def test_missing_credential_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        raise NoCredentialError("none")

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    with pytest.raises(NoCredentialError):
        await resolve_chat_provider(_tenant(), "mattermost", _DummySession())


async def test_missing_base_url_raises_invalid_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        return {"bot_token": "tok"}

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    with pytest.raises(InvalidChatCredentialError):
        await resolve_chat_provider(_tenant(), "mattermost", _DummySession())


async def test_missing_bot_token_raises_invalid_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        return {"base_url": "https://chat.example.com"}

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    with pytest.raises(InvalidChatCredentialError):
        await resolve_chat_provider(_tenant(), "mattermost", _DummySession())


async def test_admin_token_passed_through_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        return {
            "base_url": "https://chat.example.com",
            "bot_token": "tok",
            "admin_token": "admin-pat",
        }

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    provider = await resolve_chat_provider(
        _tenant(), "mattermost", _DummySession()
    )

    assert isinstance(provider, MattermostAdapter)
    assert provider._admin_token == "admin-pat"  # noqa: SLF001


async def test_admin_token_absent_keeps_legacy_payload_working(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        return {"base_url": "https://chat.example.com", "bot_token": "tok"}

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    provider = await resolve_chat_provider(
        _tenant(), "mattermost", _DummySession()
    )

    assert isinstance(provider, MattermostAdapter)
    assert provider._admin_token is None  # noqa: SLF001


async def test_invalid_admin_token_raises_invalid_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        return {
            "base_url": "https://chat.example.com",
            "bot_token": "tok",
            "admin_token": "",  # present but empty → invalid
        }

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    with pytest.raises(InvalidChatCredentialError):
        await resolve_chat_provider(_tenant(), "mattermost", _DummySession())


async def test_non_string_admin_token_raises_invalid_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _read_for(self, *a: Any, **kw: Any):  # noqa: ANN401
        return {
            "base_url": "https://chat.example.com",
            "bot_token": "tok",
            "admin_token": 12345,  # wrong type → invalid
        }

    monkeypatch.setattr(IntegrationCredentialService, "read_for", _read_for)

    with pytest.raises(InvalidChatCredentialError):
        await resolve_chat_provider(_tenant(), "mattermost", _DummySession())


def test_supported_kinds_constant() -> None:
    assert "mattermost" in resolver_mod.SUPPORTED_PROVIDER_KINDS
