"""Team-aware channel resolution (ENG-458).

The notifier bot belongs to several teams, each owning a same-named channel
(e.g. #scheduls). ``resolve_channel_id`` therefore accepts a 26-char id
(passthrough), a ``team/channel`` pair, or a bare name resolved against a
configured default team (or the bot's first team as the legacy fallback).

External HTTP is stubbed via ``respx``; no real Mattermost traffic.
"""

from __future__ import annotations

import httpx
import respx

from packages.integrations.chat.mattermost import MattermostAdapter

_BASE_URL = "https://chat.example.com"
_TOKEN = "bot-token-secret"


@respx.mock
async def test_resolves_team_qualified_channel() -> None:
    team_id = "team0eldorado000000000000a"
    chan_id = "chan0scheduls000000000000a"
    rx_team = respx.get(f"{_BASE_URL}/api/v4/teams/name/el-dorado").mock(
        return_value=httpx.Response(200, json={"id": team_id})
    )
    rx_chan = respx.get(
        f"{_BASE_URL}/api/v4/teams/{team_id}/channels/name/scheduls"
    ).mock(return_value=httpx.Response(200, json={"id": chan_id}))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("el-dorado/scheduls")

    assert resolved == chan_id
    assert rx_team.called and rx_chan.called


@respx.mock
async def test_bare_name_uses_default_team() -> None:
    team_id = "team0fusion00000000000000a"
    chan_id = "chan0leads000000000000000a"
    respx.get(f"{_BASE_URL}/api/v4/teams/name/fusion").mock(
        return_value=httpx.Response(200, json={"id": team_id})
    )
    respx.get(
        f"{_BASE_URL}/api/v4/teams/{team_id}/channels/name/leads"
    ).mock(return_value=httpx.Response(200, json={"id": chan_id}))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(
            _BASE_URL, _TOKEN, client=http, default_team="fusion"
        )
        resolved = await adapter.resolve_channel_id("leads")

    assert resolved == chan_id


@respx.mock
async def test_bare_name_without_default_falls_back_to_first_team() -> None:
    team_id = "team0first0000000000000000"
    chan_id = "chan0leads000000000000000a"
    rx_me = respx.get(f"{_BASE_URL}/api/v4/users/me/teams").mock(
        return_value=httpx.Response(200, json=[{"id": team_id}])
    )
    respx.get(
        f"{_BASE_URL}/api/v4/teams/{team_id}/channels/name/leads"
    ).mock(return_value=httpx.Response(200, json={"id": chan_id}))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("leads")

    assert resolved == chan_id
    assert rx_me.called


async def test_existing_id_is_passed_through_without_api_call() -> None:
    # A 26-char id needs no resolution — and no HTTP client traffic.
    already_id = "abcdefghijklmnopqrstuvwxyz"  # 26 chars
    assert len(already_id) == 26

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        # No respx mock registered: if this made an HTTP call it would raise.
        resolved = await adapter.resolve_channel_id(already_id)

    assert resolved == already_id


@respx.mock
async def test_unresolvable_team_returns_none() -> None:
    respx.get(f"{_BASE_URL}/api/v4/teams/name/ghost").mock(
        return_value=httpx.Response(404, json={"message": "team not found"})
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("ghost/scheduls")

    assert resolved is None
