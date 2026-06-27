"""Unit tests for the Mattermost chat adapter (ENG-435, Block B).

External calls are stubbed via ``respx``; no real Mattermost traffic is
generated. A live post against a running Mattermost server with a real
bot token is an operator step (ENG-434 bring-up) and is NOT covered here.

Covered:

1. ``post`` success: 201 + ``{"id": "postid"}`` → ok=True, id carried;
   Authorization bearer header + channel_id/message body asserted.
2. ``post`` failure: non-2xx → ok=False, error populated, no raise.
3. ``post`` transport error → ok=False, error populated, no raise.
4. ``blocks`` / ``extra`` map into ``props.attachments``.
5. ``PROVIDER_KINDS`` includes ``mattermost``.
"""

from __future__ import annotations

import json

import httpx
import respx

from packages.integrations.chat.base import ChatMessage
from packages.integrations.chat.mattermost import MattermostAdapter

_BASE_URL = "https://chat.example.com"
_POSTS_URL = f"{_BASE_URL}/api/v4/posts"
_TOKEN = "bot-token-secret"


@respx.mock
async def test_post_success_returns_provider_message_id() -> None:
    route = respx.post(_POSTS_URL).mock(
        return_value=httpx.Response(201, json={"id": "postid"})
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        result = await adapter.post(
            ChatMessage(channel="chan-1", text="hello world")
        )

    assert result.ok is True
    assert result.provider_message_id == "postid"
    assert result.error is None

    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {_TOKEN}"

    body = json.loads(request.content)
    assert body["channel_id"] == "chan-1"
    assert body["message"] == "hello world"


@respx.mock
async def test_post_non_2xx_returns_not_ok_without_raising() -> None:
    respx.post(_POSTS_URL).mock(
        return_value=httpx.Response(
            403, json={"message": "channel not found", "id": "store.sql_channel"}
        )
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        result = await adapter.post(ChatMessage(channel="missing", text="hi"))

    assert result.ok is False
    assert result.provider_message_id is None
    assert result.error is not None
    assert "403" in result.error
    assert "channel not found" in result.error
    # The bot token must never leak into the error string.
    assert _TOKEN not in result.error


@respx.mock
async def test_post_transport_error_returns_not_ok() -> None:
    respx.post(_POSTS_URL).mock(side_effect=httpx.ConnectError("boom"))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        result = await adapter.post(ChatMessage(channel="chan-1", text="hi"))

    assert result.ok is False
    assert result.error is not None
    assert "transport error" in result.error
    assert _TOKEN not in result.error


@respx.mock
async def test_blocks_and_extra_map_to_props_attachments() -> None:
    route = respx.post(_POSTS_URL).mock(
        return_value=httpx.Response(201, json={"id": "p1"})
    )

    attachments = [{"text": "card body", "color": "#36a64f"}]
    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        result = await adapter.post(
            ChatMessage(
                channel="chan-1",
                text="see attachment",
                blocks=attachments,
                extra={"from_webhook": "true"},
            )
        )

    assert result.ok is True

    body = json.loads(route.calls.last.request.content)
    assert body["props"]["attachments"] == attachments
    # Non-attachment extras pass through as props.
    assert body["props"]["from_webhook"] == "true"


@respx.mock
async def test_extra_attachments_used_when_no_blocks() -> None:
    route = respx.post(_POSTS_URL).mock(
        return_value=httpx.Response(201, json={"id": "p2"})
    )

    attachments = [{"text": "from extra"}]
    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        await adapter.post(
            ChatMessage(
                channel="chan-1",
                text="x",
                extra={"attachments": attachments},
            )
        )


    body = json.loads(route.calls.last.request.content)
    assert body["props"]["attachments"] == attachments


@respx.mock
async def test_base_url_trailing_slash_normalised() -> None:
    route = respx.post(_POSTS_URL).mock(
        return_value=httpx.Response(201, json={"id": "p3"})
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(f"{_BASE_URL}/", _TOKEN, client=http)
        await adapter.post(ChatMessage(channel="c", text="t"))

    assert route.called
    assert str(route.calls.last.request.url) == _POSTS_URL


def test_provider_kinds_includes_mattermost() -> None:
    from packages.tenant.models import PROVIDER_KINDS

    assert "mattermost" in PROVIDER_KINDS


def test_adapter_creates_own_client_when_not_injected() -> None:
    adapter = MattermostAdapter(_BASE_URL, _TOKEN)
    # Self-owned client should be a live AsyncClient instance.
    assert isinstance(adapter._client, httpx.AsyncClient)  # noqa: SLF001


# --- resolve_channel_id (ENG-458, Block D) --------------------------------

_TEAMS_URL = f"{_BASE_URL}/api/v4/users/me/teams"
_MM_CHANNEL_ID = "abcdefghijklmnopqrstuvwxyz"  # 26-char id shape


async def test_resolve_channel_id_passes_through_existing_id() -> None:
    """A 26-char id is returned unchanged with no HTTP round-trip."""
    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id(_MM_CHANNEL_ID)
    assert resolved == _MM_CHANNEL_ID


@respx.mock
async def test_resolve_channel_id_resolves_name_to_id() -> None:
    respx.get(_TEAMS_URL).mock(
        return_value=httpx.Response(200, json=[{"id": "team-123"}])
    )
    chan_url = f"{_BASE_URL}/api/v4/teams/team-123/channels/name/leads"
    route = respx.get(chan_url).mock(
        return_value=httpx.Response(200, json={"id": _MM_CHANNEL_ID, "name": "leads"})
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("leads")

    assert resolved == _MM_CHANNEL_ID
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {_TOKEN}"


@respx.mock
async def test_resolve_channel_id_returns_none_on_unknown_name() -> None:
    respx.get(_TEAMS_URL).mock(
        return_value=httpx.Response(200, json=[{"id": "team-123"}])
    )
    respx.get(
        f"{_BASE_URL}/api/v4/teams/team-123/channels/name/missing"
    ).mock(return_value=httpx.Response(404, json={"message": "channel not found"}))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("missing")

    assert resolved is None


@respx.mock
async def test_resolve_channel_id_returns_none_when_no_team() -> None:
    respx.get(_TEAMS_URL).mock(return_value=httpx.Response(200, json=[]))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("leads")

    assert resolved is None


@respx.mock
async def test_resolve_channel_id_returns_none_on_transport_error() -> None:
    respx.get(_TEAMS_URL).mock(side_effect=httpx.ConnectError("boom"))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        resolved = await adapter.resolve_channel_id("leads")

    assert resolved is None


# --- Directory: list_teams / list_channels / team_url (ENG-564) -----------

_ADMIN_TOKEN = "admin-pat-secret"
_ALL_TEAMS_URL = f"{_BASE_URL}/api/v4/teams"


def _team(i: int, *, delete_at: int = 0) -> dict[str, object]:
    return {
        "id": f"team-{i}",
        "name": f"team{i}",
        "display_name": f"Team {i}",
        "delete_at": delete_at,
    }


@respx.mock
async def test_list_teams_admin_path_paginates_and_accumulates() -> None:
    """admin_token → GET /api/v4/teams paged until a short page; all accumulated."""
    page0 = [_team(i) for i in range(200)]  # full page → fetch another
    page1 = [_team(200), _team(201)]  # short page → stop
    route0 = respx.get(_ALL_TEAMS_URL, params={"page": "0", "per_page": "200"}).mock(
        return_value=httpx.Response(200, json=page0)
    )
    route1 = respx.get(_ALL_TEAMS_URL, params={"page": "1", "per_page": "200"}).mock(
        return_value=httpx.Response(200, json=page1)
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(
            _BASE_URL, _TOKEN, client=http, admin_token=_ADMIN_TOKEN
        )
        teams = await adapter.list_teams()

    assert teams is not None
    assert len(teams) == 202
    assert route0.called and route1.called
    # Admin path authenticates with the admin token, never the bot token.
    assert route0.calls.last.request.headers["Authorization"] == f"Bearer {_ADMIN_TOKEN}"
    assert _TOKEN not in route0.calls.last.request.headers["Authorization"]


@respx.mock
async def test_list_teams_filters_soft_deleted() -> None:
    teams_json = [_team(1), _team(2, delete_at=1700000000), _team(3)]
    respx.get(_ALL_TEAMS_URL, params={"page": "0", "per_page": "200"}).mock(
        return_value=httpx.Response(200, json=teams_json)
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(
            _BASE_URL, _TOKEN, client=http, admin_token=_ADMIN_TOKEN
        )
        teams = await adapter.list_teams()

    assert teams is not None
    assert [t["id"] for t in teams] == ["team-1", "team-3"]


@respx.mock
async def test_list_teams_bot_fallback_uses_me_teams() -> None:
    """No admin_token → bot-scoped GET /users/me/teams with the bot token."""
    route = respx.get(_TEAMS_URL).mock(
        return_value=httpx.Response(200, json=[_team(1), _team(2, delete_at=5)])
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        teams = await adapter.list_teams()

    assert teams is not None
    assert [t["id"] for t in teams] == ["team-1"]  # soft-deleted filtered
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {_TOKEN}"


@respx.mock
async def test_list_teams_returns_none_on_error() -> None:
    respx.get(_ALL_TEAMS_URL, params={"page": "0", "per_page": "200"}).mock(
        return_value=httpx.Response(401, json={"message": "invalid token"})
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(
            _BASE_URL, _TOKEN, client=http, admin_token=_ADMIN_TOKEN
        )
        teams = await adapter.list_teams()

    assert teams is None


@respx.mock
async def test_list_teams_returns_none_on_transport_error() -> None:
    respx.get(_TEAMS_URL).mock(side_effect=httpx.ConnectError("boom"))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        teams = await adapter.list_teams()

    assert teams is None


def _channel(i: int, *, ctype: str = "O", delete_at: int = 0) -> dict[str, object]:
    return {
        "id": f"chan-{i}",
        "name": f"channel{i}",
        "display_name": f"Channel {i}",
        "type": ctype,
        "purpose": f"purpose {i}",
        "delete_at": delete_at,
    }


def _channels_url(team_id: str) -> str:
    return f"{_BASE_URL}/api/v4/teams/{team_id}/channels"


@respx.mock
async def test_list_channels_paginates_and_filters_soft_deleted() -> None:
    page0 = [_channel(i) for i in range(200)]
    page1 = [_channel(200), _channel(201, delete_at=99)]  # one soft-deleted
    route0 = respx.get(
        _channels_url("team-1"), params={"page": "0", "per_page": "200"}
    ).mock(return_value=httpx.Response(200, json=page0))
    respx.get(_channels_url("team-1"), params={"page": "1", "per_page": "200"}).mock(
        return_value=httpx.Response(200, json=page1)
    )

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(
            _BASE_URL, _TOKEN, client=http, admin_token=_ADMIN_TOKEN
        )
        channels = await adapter.list_channels("team-1")

    assert channels is not None
    assert len(channels) == 201  # 202 fetched − 1 soft-deleted
    assert all(c["id"] != "chan-201" for c in channels)
    # When an admin_token is present it must authenticate the channels path too,
    # never the bot token (guards against a hard-wired bot token on list_channels).
    assert route0.calls.last.request.headers["Authorization"] == f"Bearer {_ADMIN_TOKEN}"
    assert _TOKEN not in route0.calls.last.request.headers["Authorization"]


@respx.mock
async def test_list_channels_uses_bot_token_without_admin() -> None:
    route = respx.get(
        _channels_url("team-1"), params={"page": "0", "per_page": "200"}
    ).mock(return_value=httpx.Response(200, json=[_channel(1)]))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(_BASE_URL, _TOKEN, client=http)
        channels = await adapter.list_channels("team-1")

    assert channels is not None
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {_TOKEN}"


@respx.mock
async def test_list_channels_returns_none_on_error() -> None:
    respx.get(
        _channels_url("team-1"), params={"page": "0", "per_page": "200"}
    ).mock(return_value=httpx.Response(403, json={"message": "forbidden"}))

    async with httpx.AsyncClient() as http:
        adapter = MattermostAdapter(
            _BASE_URL, _TOKEN, client=http, admin_token=_ADMIN_TOKEN
        )
        channels = await adapter.list_channels("team-1")

    assert channels is None


def test_team_url_builds_landing_path() -> None:
    adapter = MattermostAdapter(f"{_BASE_URL}/", _TOKEN)
    assert adapter.team_url("marketing") == f"{_BASE_URL}/marketing"


def test_team_url_encodes_unsafe_segment() -> None:
    adapter = MattermostAdapter(_BASE_URL, _TOKEN)
    # A stray slash must be encoded so it cannot escape the path segment.
    assert adapter.team_url("a/b") == f"{_BASE_URL}/a%2Fb"
