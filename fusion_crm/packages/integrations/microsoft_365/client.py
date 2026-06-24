"""Microsoft Graph API client — ``/me/sendMail`` + ``/me`` profile.

Mirrors ``GoogleWorkspaceClient`` so the outreach send pipeline can
treat both providers symmetrically. Tokens come from
``tenant.integration_credential`` only — no env factory.

Graph's ``sendMail`` accepts a JSON body (not RFC 822 base64 like
Gmail). The shape is::

    {
      "message": {
        "subject": "...",
        "body": {"contentType": "HTML", "content": "..."},
        "toRecipients": [...],
        "ccRecipients": [...],
        "bccRecipients": [...]
      },
      "saveToSentItems": true
    }

The ENG-132 send service is responsible for assembling this body.
This client takes either a pre-built JSON dict (for new code) OR
RFC 822 bytes (for parity with the Gmail surface; Graph's
``sendMail`` does NOT accept RFC 822 directly — we convert by
decoding into structured JSON via ``_rfc822_to_graph_message``).

ENG-134 (2026-05-11) adds two read helpers used by the bounce
poller worker:

  - ``list_messages`` — ``GET /me/messages`` with a ``$filter`` /
    ``$select`` query so the poller can pull NDRs (filtering by
    ``from/emailAddress/address eq 'postmaster@*'``-style) without
    fetching message bodies.
  - ``get_message_with_headers`` — single ``/me/messages/{id}`` with
    ``$select=internetMessageHeaders,from,subject`` so we read only
    the headers needed to match the bounced original message-id.

These methods require ``Mail.Read`` scope. ENG-131 only granted
``Mail.Send``; ENG-134's connect flow CLAUDE.md documents the
additional scope and operators re-consent.

Stage 1 Phase 1 favours the JSON path; the RFC 822 conversion is a
thin best-effort to keep callers symmetric.
"""

from __future__ import annotations

import email
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from email.message import Message
from typing import Any, Self
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.tenant.credential_service import IntegrationCredentialService

from .exceptions import MicrosoftAPIError, MicrosoftOAuthError
from .oauth import MicrosoftOAuthClient, MicrosoftTokens

log = get_logger("integrations.microsoft_365.client")

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
SEND_MAIL_PATH = "/me/sendMail"
PROFILE_PATH = "/me"
MESSAGES_PATH = "/me/messages"

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_REFRESH_SKEW_SECONDS = 60


RefreshPersistFn = Callable[[MicrosoftTokens], Awaitable[None]]


class MicrosoftClient:
    """Microsoft Graph v1.0 client. One instance per request / job."""

    def __init__(
        self,
        *,
        access_token: str,
        expires_at: datetime | None,
        oauth_client: MicrosoftOAuthClient,
        on_refresh: RefreshPersistFn | None,
        refresh_token: str | None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._expires_at = expires_at
        self._refresh_token = refresh_token
        self._oauth = oauth_client
        self._on_refresh = on_refresh
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None

    # ----------------------------------------------------------------- factory

    @classmethod
    async def from_credential(
        cls,
        credential_id: UUID,
        *,
        session: AsyncSession,
        principal: Principal,
        oauth_client: MicrosoftOAuthClient | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> Self:
        cred_svc = IntegrationCredentialService(session)
        payload = await cred_svc.read_by_id(credential_id, tenant_id=principal.tenant_id)
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        expires_at_raw = payload.get("expires_at")
        if not isinstance(access, str) or not access:
            raise MicrosoftOAuthError("credential payload missing access_token")
        if refresh is not None and not isinstance(refresh, str):
            raise MicrosoftOAuthError("credential payload refresh_token has wrong type")

        expires_at: datetime | None = None
        if isinstance(expires_at_raw, (int, float)):
            expires_at = datetime.fromtimestamp(float(expires_at_raw), tz=UTC)
        elif isinstance(expires_at_raw, str):
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
            except ValueError:
                expires_at = None

        oauth = oauth_client if oauth_client is not None else MicrosoftOAuthClient.from_settings(
            http=http,
        )

        async def _persist(new_tokens: MicrosoftTokens) -> None:
            updated = dict(payload)
            updated["access_token"] = new_tokens.access_token
            updated["expires_at"] = new_tokens.expires_at.timestamp()
            if new_tokens.refresh_token is not None:
                # Microsoft rolls refresh tokens — always overwrite.
                updated["refresh_token"] = new_tokens.refresh_token
            await cred_svc.upsert(
                tenant_id=principal.require_tenant(),
                provider_kind="microsoft_365",
                credential_kind="oauth_token",
                payload=updated,
                principal=principal,
                mailbox_email=payload.get("mailbox_email")
                if isinstance(payload.get("mailbox_email"), str)
                else None,
                last_refreshed_at=datetime.now(UTC),
                expires_at=new_tokens.expires_at,
            )

        return cls(
            access_token=access,
            expires_at=expires_at,
            oauth_client=oauth,
            on_refresh=_persist,
            refresh_token=refresh,
            http=http,
        )

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> MicrosoftClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ----------------------------------------------------------------- API

    async def get_profile(self) -> dict[str, Any]:
        """Verify the token works. Returns the ``/me`` Graph object."""
        body = await self._request_json("GET", PROFILE_PATH, attempt=0)
        if not isinstance(body, dict):
            raise MicrosoftAPIError("graph /me returned non-object body")
        return body

    async def send_message(
        self,
        rfc822_bytes: bytes | None = None,
        *,
        graph_message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a single message via ``POST /me/sendMail``.

        Either provide ``graph_message`` (preferred — the ENG-132
        renderer builds this directly) or ``rfc822_bytes`` (Gmail
        parity; converted to a Graph message body via
        ``_rfc822_to_graph_message``).

        Graph's ``/me/sendMail`` returns 202 with empty body and no
        message id — Microsoft does not expose the equivalent of
        Gmail's returned ``messageId`` on this endpoint. Callers that
        need correlation must look up sent items via Graph after the
        fact (Stage 2 work).
        """
        if graph_message is None and rfc822_bytes is None:
            raise MicrosoftAPIError(
                "send_message called without graph_message or rfc822_bytes"
            )
        body = graph_message or _rfc822_to_graph_message(rfc822_bytes or b"")
        json_body = {"message": body, "saveToSentItems": True}
        result = await self._request_json(
            "POST",
            SEND_MAIL_PATH,
            json_body=json_body,
            attempt=0,
        )
        # Graph returns 202 with no body. Surface a deterministic
        # envelope so callers do not need to special-case "empty dict".
        return {
            "message_id": None,
            "thread_id": None,
            "raw": result if isinstance(result, dict) else {},
        }

    async def list_messages(
        self,
        *,
        filter_query: str | None = None,
        select: list[str] | None = None,
        top: int = 50,
        order_by: str = "receivedDateTime desc",
    ) -> dict[str, Any]:
        """``GET /me/messages`` — list message headers matching ``$filter``.

        Used by the ENG-134 bounce poller with a filter like
        ``startsWith(from/emailAddress/address, 'postmaster@')``.
        Returns the raw Graph response (``{"value": [...], "@odata.nextLink": "..."}``).

        Sets ``Prefer: outlook.body-content-type="text"`` is unnecessary
        when ``$select`` excludes ``body``; we keep this method
        body-free so the bounce poller stays metadata-only.
        """
        params: list[tuple[str, str]] = [
            ("$top", str(max(1, min(top, 1000)))),
            ("$orderby", order_by),
        ]
        if filter_query:
            params.append(("$filter", filter_query))
        if select:
            params.append(("$select", ",".join(select)))
        body = await self._request_json(
            "GET",
            MESSAGES_PATH,
            params=params,
            attempt=0,
        )
        if not isinstance(body, dict):
            raise MicrosoftAPIError("graph /me/messages returned non-object body")
        if "value" not in body:
            body["value"] = []
        return body

    async def get_message_with_headers(
        self,
        message_id: str,
        *,
        select: list[str] | None = None,
    ) -> dict[str, Any]:
        """``GET /me/messages/{id}`` — single-message metadata fetch.

        Defaults ``$select`` to a short list that covers everything
        the bounce poller needs (``internetMessageHeaders``,
        ``subject``, ``from``). Callers may override but should keep
        ``body`` off the list — the worker is metadata-only by design.
        """
        if not message_id:
            raise MicrosoftAPIError(
                "get_message_with_headers called with empty message_id"
            )
        chosen = select or [
            "id",
            "subject",
            "from",
            "internetMessageHeaders",
            "internetMessageId",
        ]
        params: list[tuple[str, str]] = [("$select", ",".join(chosen))]
        body = await self._request_json(
            "GET",
            f"{MESSAGES_PATH}/{message_id}",
            params=params,
            attempt=0,
        )
        if not isinstance(body, dict):
            raise MicrosoftAPIError("graph /me/messages/{id} returned non-object")
        return body

    # ----------------------------------------------------------------- private

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: list[tuple[str, str]] | dict[str, str] | None = None,
        attempt: int,
    ) -> Any:
        url = f"{GRAPH_API_BASE}{path}"
        await self._refresh_if_close_to_expiry()

        response = await self._http.request(
            method,
            url,
            headers=self._auth_headers(),
            json=json_body,
            params=params,
        )

        if response.status_code == 401 and attempt == 0:
            log.info("graph.401_refreshing", path=path)
            await self._refresh_access_token()
            return await self._request_json(
                method,
                path,
                json_body=json_body,
                params=params,
                attempt=attempt + 1,
            )

        if response.status_code == 401:
            raise MicrosoftOAuthError(
                "graph 401 after refresh — refresh token expired or revoked",
                details={"status": 401},
            )

        if response.status_code >= 400:
            raise MicrosoftAPIError(
                f"graph {method} {path} failed: {response.status_code}",
                details={
                    "status": response.status_code,
                    "body": response.text[:500],
                },
            )

        if response.status_code in {202, 204} or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise MicrosoftAPIError(
                "graph returned non-JSON body",
                details={"status": response.status_code, "path": path},
            ) from exc

    async def _refresh_if_close_to_expiry(self) -> None:
        if self._expires_at is None:
            return
        cutoff = datetime.now(UTC) + timedelta(seconds=_REFRESH_SKEW_SECONDS)
        if self._expires_at > cutoff:
            return
        await self._refresh_access_token()

    async def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            raise MicrosoftOAuthError("no refresh_token available — cannot refresh")
        new_tokens = await self._oauth.refresh(refresh_token=self._refresh_token)
        self._access_token = new_tokens.access_token
        self._expires_at = new_tokens.expires_at
        if new_tokens.refresh_token:
            self._refresh_token = new_tokens.refresh_token
        if self._on_refresh is not None:
            await self._on_refresh(new_tokens)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


def _rfc822_to_graph_message(raw: bytes) -> dict[str, Any]:
    """Best-effort conversion from RFC 822 bytes → Graph message body.

    The proper ENG-132 path produces a Graph message body directly; this
    function exists for callers that already have an RFC 822 buffer and
    want symmetry with the Gmail client. Headers and body are extracted
    from the parsed ``email.message.Message``; non-ASCII / multipart
    nuances follow Python's stdlib parser.
    """
    if not raw:
        raise MicrosoftAPIError(
            "send_message rfc822 path called with empty bytes"
        )
    parsed: Message = email.message_from_bytes(raw)
    subject = parsed.get("Subject", "")

    # Body — pick text/html if available, otherwise text/plain.
    html_body: str | None = None
    text_body: str | None = None
    if parsed.is_multipart():
        for part in parsed.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and html_body is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    html_body = payload.decode(part.get_content_charset() or "utf-8", "replace")
            elif ctype == "text/plain" and text_body is None:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    text_body = payload.decode(part.get_content_charset() or "utf-8", "replace")
    else:
        payload = parsed.get_payload(decode=True)
        if isinstance(payload, bytes):
            text_body = payload.decode(parsed.get_content_charset() or "utf-8", "replace")

    body_struct: dict[str, str]
    if html_body is not None:
        body_struct = {"contentType": "HTML", "content": html_body}
    else:
        body_struct = {"contentType": "Text", "content": text_body or ""}

    def _addr_list(header_name: str) -> list[dict[str, dict[str, str]]]:
        raw_value = parsed.get_all(header_name) or []
        result: list[dict[str, dict[str, str]]] = []
        for entry in raw_value:
            for piece in entry.split(","):
                addr = piece.strip()
                if not addr:
                    continue
                # Strip optional ``Name <addr@host>`` shape.
                if "<" in addr and ">" in addr:
                    addr = addr[addr.index("<") + 1 : addr.index(">")]
                result.append({"emailAddress": {"address": addr}})
        return result

    return {
        "subject": subject,
        "body": body_struct,
        "toRecipients": _addr_list("To"),
        "ccRecipients": _addr_list("Cc"),
        "bccRecipients": _addr_list("Bcc"),
    }


__all__ = [
    "GRAPH_API_BASE",
    "MESSAGES_PATH",
    "MicrosoftClient",
    "PROFILE_PATH",
    "SEND_MAIL_PATH",
]
