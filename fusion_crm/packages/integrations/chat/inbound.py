"""Signed inbound parsing + token verification for Mattermost (ENG-438).

Block E (signed inbound) accepts two kinds of Mattermost callbacks:

* **outgoing webhooks** — thread replies / channel messages that match a
  trigger word. Mattermost posts a form-encoded (or JSON) body carrying a
  shared ``token`` plus ``channel_id`` / ``user_id`` / ``post_id`` / ``text``;
* **interactive message actions** — button clicks whose JSON body carries a
  ``context`` (our integration places the shared token at
  ``context.token``) plus a ``trigger_id`` / ``user_id``.

Mattermost authenticates BOTH with a shared TOKEN (not an HMAC by default).
The platform never receives our ``tenant_id`` on the wire, so we resolve the
tenant by matching the presented token against every ACTIVE
``mattermost`` / ``webhook_secret`` credential, constant-time-comparing the
presented token to each stored token. The match yields the ``tenant_id``.

SECURITY (this is a PUBLIC endpoint — fail closed):

* Token comparison uses :func:`hmac.compare_digest` (constant-time) so a
  timing side-channel cannot leak the secret.
* A missing or non-matching token resolves to ``None`` — the route turns
  that into a 401/403. Nothing is captured.
* The token is NEVER logged, never placed in an error message, never
  returned. This module emits NO log lines that include the token.

This module is pure parse + verify so the route stays thin (invariant #5):
no DB writes, no business logic. The route wires parse → verify → capture.
"""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from packages.core.types import TenantId
from packages.tenant.credential_service import IntegrationCredentialService

# Credential coordinates the inbound shared secret is stored under. The bot
# token (outbound posting) is a SEPARATE row under ``credential_kind="api_key"``
# resolved by ``resolver.py``; the inbound secret is its own row so rotating
# one does not disturb the other.
INBOUND_PROVIDER_KIND = "mattermost"
INBOUND_CREDENTIAL_KIND = "webhook_secret"

# Raw-event coordinates (verbatim capture into ``ingest.raw_event``).
INBOUND_SOURCE = "mattermost"
EVENT_TYPE_WEBHOOK = "mattermost.webhook"
EVENT_TYPE_ACTION = "mattermost.action"


@dataclass(frozen=True, slots=True)
class ParsedInbound:
    """Normalised view of a Mattermost inbound callback.

    ``token`` is the presented shared secret (used only for verification —
    never persisted, never logged). ``payload`` is the FULL verbatim inbound
    body captured to ``ingest.raw_event``. ``external_id`` is the vendor's
    stable identifier for dedupe (``post_id`` for webhooks, ``trigger_id``
    for actions); it may be ``None`` when the body omits it.
    """

    event_type: str
    token: str | None
    external_id: str | None
    user_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _extract_context_token(payload: Mapping[str, Any]) -> str | None:
    """Pull the token an interactive action carries in ``context.token``."""
    context = payload.get("context")
    if isinstance(context, Mapping):
        return _str_or_none(context.get("token"))
    return None


def _extract_context_value(payload: Mapping[str, Any], key: str) -> str | None:
    context = payload.get("context")
    if isinstance(context, Mapping):
        return _str_or_none(context.get(key))
    return None


def parse_webhook(payload: Mapping[str, Any]) -> ParsedInbound:
    """Parse an outgoing-webhook body (form-encoded or JSON, already a dict).

    The token is at the top-level ``token`` field per the Mattermost
    outgoing-webhook contract. ``external_id`` is the ``post_id`` for dedupe.
    """
    return ParsedInbound(
        event_type=EVENT_TYPE_WEBHOOK,
        token=_str_or_none(payload.get("token")),
        external_id=_str_or_none(payload.get("post_id")),
        user_id=_str_or_none(payload.get("user_id")),
        payload=dict(payload),
    )


def parse_action(payload: Mapping[str, Any]) -> ParsedInbound:
    """Parse an interactive message action body (JSON, already a dict).

    The integration places the shared token in the action ``context.token``;
    we also accept a top-level ``token`` as a fallback. ``external_id`` is
    the ``trigger_id`` for dedupe; ``user_id`` is read from the top level or
    from ``context.user_id``.
    """
    token = _extract_context_token(payload) or _str_or_none(payload.get("token"))
    user_id = _str_or_none(payload.get("user_id")) or _extract_context_value(
        payload, "user_id"
    )
    return ParsedInbound(
        event_type=EVENT_TYPE_ACTION,
        token=token,
        external_id=_str_or_none(payload.get("trigger_id")),
        user_id=user_id,
        payload=dict(payload),
    )


def tokens_match(presented: str, stored: str) -> bool:
    """Constant-time equality for two shared tokens.

    Wraps :func:`hmac.compare_digest` so the comparison cannot leak the
    secret through response timing. Returns ``False`` for empty inputs
    (fail closed) — an empty stored secret must never authenticate.
    """
    if not presented or not stored:
        return False
    return hmac.compare_digest(presented, stored)


async def resolve_tenant_from_token(
    credentials: IntegrationCredentialService,
    presented_token: str | None,
) -> TenantId | None:
    """Resolve the tenant that owns ``presented_token`` (or ``None``).

    Loads every ACTIVE ``mattermost`` / ``webhook_secret`` credential across
    tenants and constant-time-compares the presented token against EACH
    stored ``token`` WITHOUT an early return — so neither response timing nor
    match position leaks which credential matched, and a duplicate token
    shared across two tenants cannot silently pick the first one. The match
    yields a ``tenant_id`` ONLY when EXACTLY ONE distinct tenant matched.

    Fails closed:

    * absent / empty token → ``None`` (no DB read);
    * zero stored credentials match → ``None``;
    * TWO OR MORE distinct tenants match (ambiguous shared secret) → ``None``.

    Disambiguation is by *tenant*, not by credential row: multiple matching
    rows that all belong to the SAME tenant (e.g. a rotated/secondary inbound
    secret) are NOT ambiguous — they resolve to that one tenant. Only a token
    shared across DIFFERENT tenants fails closed.

    The token is never logged here or by the credential service.
    """
    if not presented_token:
        return None

    rows = await credentials.list_active_payloads_across_tenants(
        INBOUND_PROVIDER_KIND, INBOUND_CREDENTIAL_KIND
    )

    # Full scan, no early return: collect EVERY matching tenant so a
    # duplicate token across tenants is detected (fail closed on ambiguity).
    matched: set[TenantId] = set()
    for tenant_id, payload in rows:
        stored = payload.get("token")
        if isinstance(stored, str) and tokens_match(presented_token, stored):
            matched.add(tenant_id)

    # Exactly one distinct tenant → resolve; zero or ambiguous (>=2) → None.
    if len(matched) == 1:
        return next(iter(matched))
    return None


REDACTED = "[redacted]"


def redact_auth_tokens(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a COPY of ``payload`` with the live auth token(s) redacted.

    The verbatim inbound body is captured to ``ingest.raw_event`` as the
    forensic copy — but the Mattermost shared TOKEN is the live authentication
    secret and must NOT be persisted (it is the same secret the next request
    presents). This replaces the top-level ``token`` and the action
    ``context.token`` with :data:`REDACTED` while preserving EVERYTHING else
    verbatim. The original ``payload`` is never mutated.
    """
    redacted = dict(payload)
    if "token" in redacted:
        redacted["token"] = REDACTED
    context = redacted.get("context")
    if isinstance(context, Mapping) and "token" in context:
        new_context = dict(context)
        new_context["token"] = REDACTED
        redacted["context"] = new_context
    return redacted


def is_health_check(payload: Mapping[str, Any]) -> bool:
    """True for an empty / URL-verification ping that carries no token.

    Mattermost (and operators testing the URL) may send an empty body or a
    bare ping. We answer those with a 200 WITHOUT capturing anything and
    WITHOUT requiring a token — but only when there is genuinely no actionable
    content (no token AND no identifying ids). A body that carries a token is
    always run through verification.
    """
    if not payload:
        return True
    has_token = _str_or_none(payload.get("token")) is not None or (
        _extract_context_token(payload) is not None
    )
    has_ids = any(
        _str_or_none(payload.get(key)) is not None
        for key in ("post_id", "trigger_id", "user_id", "channel_id", "text")
    )
    return not has_token and not has_ids


__all__ = [
    "EVENT_TYPE_ACTION",
    "EVENT_TYPE_WEBHOOK",
    "INBOUND_CREDENTIAL_KIND",
    "INBOUND_PROVIDER_KIND",
    "INBOUND_SOURCE",
    "ParsedInbound",
    "is_health_check",
    "REDACTED",
    "parse_action",
    "parse_webhook",
    "redact_auth_tokens",
    "resolve_tenant_from_token",
    "tokens_match",
]
