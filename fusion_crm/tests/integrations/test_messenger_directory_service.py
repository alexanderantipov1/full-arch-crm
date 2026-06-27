"""Unit tests for ``MessengerDirectoryService`` (ENG-564).

The service maps raw Mattermost API dicts → DTOs and translates the adapter's
no-raise ``None`` (token rejected / server unreachable) into a clean
``IntegrationError`` (502). A genuinely empty list stays ``[]`` (200). Resolver
failures (missing / invalid credential) propagate unchanged.

A fake provider is injected so no DB and no HTTP are touched.
"""

from __future__ import annotations

import uuid

import pytest

from packages.core.exceptions import IntegrationError
from packages.core.types import TenantId
from packages.integrations.chat import directory_service as ds_mod
from packages.integrations.chat.directory_service import MessengerDirectoryService
from packages.tenant.credential_service import NoCredentialError

_TENANT = TenantId(uuid.uuid4())
_ADMIN_TOKEN = "admin-pat-secret"


class _FakeProvider:
    """Stands in for ``MattermostAdapter`` directory methods."""

    def __init__(
        self,
        *,
        teams: list[dict[str, object]] | None = None,
        channels: list[dict[str, object]] | None = None,
    ) -> None:
        self._teams = teams
        self._channels = channels

    async def list_teams(self) -> list[dict[str, object]] | None:
        return self._teams

    async def list_channels(self, team_id: str) -> list[dict[str, object]] | None:
        return self._channels

    def team_url(self, team_name: str) -> str:
        return f"https://chat.example.com/{team_name}"


class _DummySession:
    """Stand-in for AsyncSession; the service never queries through it here."""


async def test_list_teams_maps_dicts_to_dtos() -> None:
    provider = _FakeProvider(
        teams=[
            {"id": "t1", "name": "marketing", "display_name": "Marketing"},
            {"id": "t2", "name": "ops", "display_name": "Operations"},
        ]
    )
    svc = MessengerDirectoryService(_DummySession(), provider=provider)

    teams = await svc.list_teams(_TENANT)

    assert [t.id for t in teams] == ["t1", "t2"]
    assert teams[0].name == "marketing"
    assert teams[0].display_name == "Marketing"
    assert teams[0].url == "https://chat.example.com/marketing"


async def test_list_teams_empty_returns_empty_list() -> None:
    svc = MessengerDirectoryService(_DummySession(), provider=_FakeProvider(teams=[]))
    assert await svc.list_teams(_TENANT) == []


async def test_list_teams_none_raises_integration_error_without_token() -> None:
    svc = MessengerDirectoryService(_DummySession(), provider=_FakeProvider(teams=None))

    with pytest.raises(IntegrationError) as excinfo:
        await svc.list_teams(_TENANT)

    err = excinfo.value
    assert err.code == "integration_error"
    assert err.http_status == 502
    # No token / payload ever leaks into the surfaced error.
    assert _ADMIN_TOKEN not in err.message
    assert _ADMIN_TOKEN not in str(err.details)
    assert err.details == {"tenant_id": str(_TENANT)}


async def test_list_channels_maps_type_and_purpose() -> None:
    provider = _FakeProvider(
        channels=[
            {
                "id": "c1",
                "name": "leads",
                "display_name": "Leads",
                "type": "O",
                "purpose": "incoming leads",
            },
            {
                "id": "c2",
                "name": "secret",
                "display_name": "Secret",
                "type": "P",
                "purpose": "",
            },
        ]
    )
    svc = MessengerDirectoryService(_DummySession(), provider=provider)

    channels = await svc.list_channels(_TENANT, "t1")

    assert [c.id for c in channels] == ["c1", "c2"]
    assert channels[0].type == "O"
    assert channels[0].purpose == "incoming leads"
    assert channels[1].type == "P"


async def test_list_channels_none_raises_integration_error() -> None:
    svc = MessengerDirectoryService(
        _DummySession(), provider=_FakeProvider(channels=None)
    )
    with pytest.raises(IntegrationError):
        await svc.list_channels(_TENANT, "t1")


async def test_resolver_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _raise(*a: object, **kw: object) -> object:
        raise NoCredentialError("no mattermost credential")

    monkeypatch.setattr(ds_mod, "resolve_chat_provider", _raise)

    # No injected provider → the service resolves and the resolver error bubbles.
    svc = MessengerDirectoryService(_DummySession())
    with pytest.raises(NoCredentialError):
        await svc.list_teams(_TENANT)
