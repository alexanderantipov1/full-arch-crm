"""Mattermost chat provider adapter (ENG-435, Block B).

Implements the :class:`~packages.integrations.chat.base.ChatProvider`
Protocol against the Mattermost server REST API (v4). A single
``post`` coroutine posts a rendered :class:`ChatMessage` to a channel
via ``POST {base_url}/api/v4/posts`` with a bot-token bearer header.

Design notes:

- ``post`` NEVER raises out of the adapter: a non-2xx response or any
  transport error is translated into ``ChatPostResult(ok=False,
  error=...)`` so the notification dispatcher can mark the outbox row
  ``failed`` without a try/except around every provider call. (The
  dispatcher still guards defensively, but the contract is no-raise.)
- The bot token is NEVER logged and NEVER placed in the returned
  ``error`` string. Only the ``base_url``, channel, and HTTP status
  appear in logs.
- httpx usage mirrors the email send path
  (``apps.worker.jobs.email_send``): an explicit
  ``httpx.Timeout(30.0, connect=10.0)`` and an optional injected
  ``AsyncClient`` so the dispatcher can share one pooled client across
  a drain batch (and tests can mock it).

Mattermost message attachments (the rich-card equivalent of Slack
blocks) are carried under ``props.attachments``. We accept them from
either ``ChatMessage.blocks`` (preferred) or
``ChatMessage.extra["attachments"]`` so a rule template can populate
either field without the dispatcher needing Mattermost-specific
knowledge.
"""

from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from packages.core.logging import get_logger

from .base import ChatMessage, ChatPostResult

log = get_logger("integrations.chat.mattermost")

# Mirrors the email dispatcher's timeout budget. Mattermost posts are a
# single small JSON round-trip; 30s overall / 10s connect is generous.
_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Mattermost list endpoints (teams, channels) paginate with ``page`` /
# ``per_page``. 200 is the server's max page size, so most workspaces resolve
# in a single round-trip; the loop still handles larger servers correctly.
_PER_PAGE = 200

# Mattermost ids are 26-character base32-ish tokens (lowercase letters +
# digits). A string matching this shape is treated as an already-resolved
# channel id and passed through without an API round-trip. Channel NAMES
# (slugs) may contain ``-``/``_`` and are not 26 chars, so they never match.
_MM_ID_RE = re.compile(r"^[a-z0-9]{26}$")


class MattermostAdapter:
    """Post chat messages to a Mattermost workspace via the v4 REST API.

    Construct with the workspace ``base_url`` (e.g.
    ``https://chat.example.com``) and a bot account ``bot_token``. An
    ``httpx.AsyncClient`` may be injected to share a connection pool;
    when omitted the adapter creates (and owns) its own client.
    """

    def __init__(
        self,
        base_url: str,
        bot_token: str,
        client: httpx.AsyncClient | None = None,
        *,
        default_team: str | None = None,
        admin_token: str | None = None,
    ) -> None:
        # Normalise trailing slash so ``{base_url}/api/v4/posts`` never
        # produces a double slash.
        self._base_url = base_url.rstrip("/")
        self._bot_token = bot_token
        # ENG-564: optional system-admin personal access token. When set, the
        # directory listing (``list_teams`` / ``list_channels``) uses it to see
        # ALL teams on the server, not just the bot's memberships. Treated like
        # the bot token: it is NEVER logged and never placed in an error string.
        self._admin_token = admin_token or None
        # ENG-458: the team a BARE channel name resolves against when the
        # channel carries no ``team/`` prefix. With a bot in multiple teams
        # (each owning a same-named channel, e.g. #scheduls) "the first team"
        # is non-deterministic, so callers either qualify the channel as
        # ``team/channel`` or rely on this configured default. ``None`` keeps
        # the legacy first-team behaviour.
        self._default_team = default_team or None
        if client is None:
            self._client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False

    async def post(self, message: ChatMessage) -> ChatPostResult:
        """Post ``message`` to its channel; never raises.

        Returns ``ChatPostResult(ok=True, provider_message_id=<id>)`` on
        a 2xx response, otherwise ``ChatPostResult(ok=False,
        error=...)``. Transport errors (timeouts, DNS, connection
        resets) are caught and reported the same way.
        """
        url = f"{self._base_url}/api/v4/posts"
        headers = {"Authorization": f"Bearer {self._bot_token}"}

        # ``message.channel`` is expected to be a resolved channel id here — the
        # dispatcher resolves names / ``team/channel`` pairs to an id via
        # ``resolve_channel_id`` BEFORE posting (ENG-458). ``post`` stays a
        # verbatim single round-trip so the adapter contract is unchanged.
        props = self._build_props(message)
        body: dict[str, object] = {
            "channel_id": message.channel,
            "message": message.text,
        }
        if props:
            body["props"] = props

        try:
            response = await self._client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            # Never include the token; ``str(exc)`` for httpx errors is the
            # request URL + reason, no auth header.
            log.warning(
                "integrations.chat.mattermost.transport_error",
                base_url=self._base_url,
                channel=message.channel,
                error_type=type(exc).__name__,
            )
            return ChatPostResult(
                ok=False,
                error=f"transport error: {type(exc).__name__}",
            )

        if not response.is_success:
            # Mattermost error bodies carry an ``id`` / ``message`` field;
            # surface the status + provider message (no token in either).
            detail = self._safe_error_detail(response)
            log.warning(
                "integrations.chat.mattermost.post_failed",
                base_url=self._base_url,
                channel=message.channel,
                status_code=response.status_code,
            )
            return ChatPostResult(
                ok=False,
                error=f"mattermost {response.status_code}: {detail}",
            )

        post_id = self._extract_post_id(response)
        log.info(
            "integrations.chat.mattermost.posted",
            base_url=self._base_url,
            channel=message.channel,
            has_post_id=post_id is not None,
        )
        return ChatPostResult(ok=True, provider_message_id=post_id)

    async def resolve_channel_id(self, channel: str) -> str | None:
        """Resolve a Mattermost channel reference to its channel id; never raises.

        ENG-458 — accepts three shapes so notifications route to the right
        team's channel when the bot belongs to several teams:

        * a 26-char Mattermost id → returned unchanged (no API call);
        * ``team/channel`` → resolve ``team`` by name, then the channel in it;
        * a bare ``channel`` name → resolve against the configured
          ``default_team`` (preferred) or, absent that, the bot's first team
          (legacy single-team behaviour).

        Resolution path:

        1. ``GET /api/v4/teams/name/{team}`` → team id (or first-team fallback);
        2. ``GET /api/v4/teams/{team_id}/channels/name/{name}`` → ``id``.

        Returns ``None`` on any non-2xx response, transport error, malformed
        body, or when no team can be determined — the caller decides how to
        surface a failed resolution. The bot token is never logged.
        """
        if _MM_ID_RE.match(channel):
            return channel

        # Mattermost team + channel NAMES (slugs) are URL-name-validated:
        # lowercase alnum plus ``-``/``_``, never ``/``. So a single ``/``
        # unambiguously separates an optional ``team`` prefix from the channel,
        # and ``rpartition`` (split on the LAST ``/``) is safe.
        raw_team, _, channel_name = channel.rpartition("/")
        team_name: str | None = raw_team or None  # rpartition returns "" when no "/"

        if team_name is not None:
            team_id = await self._team_id_by_name(team_name)
        elif self._default_team is not None:
            team_id = await self._team_id_by_name(self._default_team)
        else:
            team_id = await self._first_team_id()
        if team_id is None:
            return None

        # URL-encode the channel name as a single path segment so a stray
        # slash / control char in a caller-supplied name cannot alter the
        # request path (path-injection / wrong-endpoint).
        url = (
            f"{self._base_url}/api/v4/teams/{team_id}"
            f"/channels/name/{quote(channel_name, safe='')}"
        )
        data = await self._get_json(url, log_event="resolve_channel_failed")
        if isinstance(data, dict):
            channel_id = data.get("id")
            if isinstance(channel_id, str) and channel_id:
                return channel_id
        return None

    async def _team_id_by_name(self, team_name: str) -> str | None:
        """Resolve a team NAME (slug) to its id, or ``None``."""
        url = (
            f"{self._base_url}/api/v4/teams/name/"
            f"{quote(team_name, safe='')}"
        )
        data = await self._get_json(url, log_event="resolve_team_failed")
        if isinstance(data, dict):
            team_id = data.get("id")
            if isinstance(team_id, str) and team_id:
                return team_id
        return None

    async def _first_team_id(self) -> str | None:
        """Return the id of the bot's first team, or ``None``."""
        url = f"{self._base_url}/api/v4/users/me/teams"
        data = await self._get_json(url, log_event="resolve_team_failed")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                team_id = first.get("id")
                if isinstance(team_id, str) and team_id:
                    return team_id
        return None

    async def list_teams(self) -> list[dict[str, object]] | None:
        """List teams visible to this adapter; never raises (``None`` on error).

        ENG-564 — backs the staff "Messenger" directory tab:

        * **admin path** (``admin_token`` set): ``GET /api/v4/teams`` paginated,
          returning EVERY team on the server (the operator-required view);
        * **fallback** (only ``bot_token``): ``GET /api/v4/users/me/teams``,
          which returns only the teams the bot is a member of.

        Soft-deleted teams (``delete_at`` != 0) are filtered out. Returns
        ``None`` on any transport / non-2xx / parse error (the service maps
        that to a clean ``IntegrationError``); an empty list means the path
        succeeded but no teams exist. Neither token is ever logged.
        """
        if self._admin_token is not None:
            teams = await self._get_paged(
                "/api/v4/teams",
                token=self._admin_token,
                log_event="list_teams_failed",
            )
        else:
            data = await self._get_json_with_token(
                f"{self._base_url}/api/v4/users/me/teams",
                token=self._bot_token,
                log_event="list_teams_failed",
            )
            teams = (
                [t for t in data if isinstance(t, dict)]
                if isinstance(data, list)
                else None
            )
        if teams is None:
            return None
        return [t for t in teams if not self._is_soft_deleted(t)]

    async def list_channels(
        self, team_id: str
    ) -> list[dict[str, object]] | None:
        """List a team's channels (paginated); never raises (``None`` on error).

        ``GET /api/v4/teams/{team_id}/channels`` across all pages, filtering
        soft-deleted channels (``delete_at`` != 0). Uses the admin token when
        present, otherwise the bot token. ``None`` on any error; ``[]`` when the
        team genuinely has no channels. The token is never logged.
        """
        channels = await self._get_paged(
            f"/api/v4/teams/{quote(team_id, safe='')}/channels",
            token=self._admin_token or self._bot_token,
            log_event="list_channels_failed",
        )
        if channels is None:
            return None
        return [c for c in channels if not self._is_soft_deleted(c)]

    def team_url(self, team_name: str) -> str:
        """Return the Mattermost landing URL for a team NAME (slug); pure.

        ``{base_url}/{team_name}`` — the standard team landing path. The name
        is URL-encoded as a single path segment so a stray slash cannot escape
        the path. No network call.
        """
        return f"{self._base_url.rstrip('/')}/{quote(team_name, safe='')}"

    async def _get_paged(
        self, path: str, *, token: str, log_event: str
    ) -> list[dict[str, object]] | None:
        """GET a paginated MM list endpoint; accumulate all pages.

        Loops ``?page=N&per_page={_PER_PAGE}`` until a page returns fewer than
        ``_PER_PAGE`` items. Returns ``None`` (never raises) if any page errors
        or is not a JSON array; non-dict elements are skipped. The token is
        never logged.
        """
        items: list[dict[str, object]] = []
        page = 0
        while True:
            sep = "&" if "?" in path else "?"
            url = f"{self._base_url}{path}{sep}page={page}&per_page={_PER_PAGE}"
            data = await self._get_json_with_token(
                url, token=token, log_event=log_event
            )
            if not isinstance(data, list):
                return None
            items.extend(item for item in data if isinstance(item, dict))
            if len(data) < _PER_PAGE:
                break
            page += 1
        return items

    @staticmethod
    def _is_soft_deleted(obj: dict[str, object]) -> bool:
        """True when a MM team/channel dict is soft-deleted (``delete_at`` != 0)."""
        delete_at = obj.get("delete_at")
        return isinstance(delete_at, (int, float)) and delete_at != 0

    async def _get_json(self, url: str, *, log_event: str) -> object | None:
        """GET ``url`` with the bot token; return parsed JSON or ``None``.

        Never raises: transport errors, non-2xx responses, and unparseable
        bodies all collapse to ``None`` so ``resolve_channel_id`` keeps its
        no-raise contract. The token is never logged.
        """
        return await self._get_json_with_token(
            url, token=self._bot_token, log_event=log_event
        )

    async def _get_json_with_token(
        self, url: str, *, token: str, log_event: str
    ) -> object | None:
        """GET ``url`` with an explicit bearer ``token``; parsed JSON or ``None``.

        Shared no-raise GET used by both the bot-scoped resolver path and the
        admin/bot directory listing. Transport errors, non-2xx responses, and
        unparseable bodies all collapse to ``None``. The token is never logged.
        """
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = await self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            log.warning(
                f"integrations.chat.mattermost.{log_event}",
                base_url=self._base_url,
                error_type=type(exc).__name__,
            )
            return None
        if not response.is_success:
            log.warning(
                f"integrations.chat.mattermost.{log_event}",
                base_url=self._base_url,
                status_code=response.status_code,
            )
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def aclose(self) -> None:
        """Close the underlying client if this adapter created it."""
        if self._owns_client:
            await self._client.aclose()

    # --- Internals ----------------------------------------------------

    @staticmethod
    def _build_props(message: ChatMessage) -> dict[str, object]:
        """Assemble the Mattermost ``props`` payload for a message.

        Message attachments may arrive via ``blocks`` (preferred) or
        ``extra["attachments"]``. Any other ``extra`` keys are passed
        through as props so a rule can set, e.g., a custom ``from_webhook``
        flag without widening the interface.
        """
        props: dict[str, object] = {}

        attachments: list[object] | None = None
        if message.blocks:
            attachments = list(message.blocks)
        else:
            extra_attachments = message.extra.get("attachments")
            if isinstance(extra_attachments, list):
                attachments = extra_attachments

        if attachments:
            props["attachments"] = attachments

        for key, value in message.extra.items():
            if key == "attachments":
                continue
            props[key] = value

        return props

    @staticmethod
    def _extract_post_id(response: httpx.Response) -> str | None:
        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict):
            post_id = data.get("id")
            if isinstance(post_id, str) and post_id:
                return post_id
        return None

    @staticmethod
    def _safe_error_detail(response: httpx.Response) -> str:
        """Extract a short, token-free error string from the response."""
        try:
            data = response.json()
        except ValueError:
            return response.reason_phrase or "error"
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str) and message:
                return message
        return response.reason_phrase or "error"


__all__ = ["MattermostAdapter"]
