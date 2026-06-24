"""HMAC token helpers for ENG-134 — open tracking + one-click unsubscribe.

Two distinct, namespace-prefixed token families share the same secret
(``Settings.internal_credential_token``). Namespacing prevents an
attacker who steals an "open" token from replaying it as an
"unsubscribe" token, even though both use the same HMAC key.

Per ADR-0004 §"Tracking" decision #4:

    The HMAC key is the existing ``INTERNAL_CREDENTIAL_TOKEN`` (from
    ENG-125) namespaced by ``"unsubscribe:"`` — no new secret to
    provision.

Token format (URL-safe base64 of a single JSON line, then ``"."``,
then a hex HMAC-SHA256 over ``<namespace>|<json line>``)::

    <b64url(json)>.<hex_hmac>

Open tokens carry ``{send_id}``. Unsubscribe tokens additionally
carry ``{tenant_id, email_h}`` (the normalised email hashed under the
same key so a stolen token still does not leak the address).
Verification always uses ``hmac.compare_digest`` to avoid timing
leaks; mismatched namespace, tamper, or missing field all surface as
the same ``TokenInvalid`` error so callers cannot distinguish failure
modes (which would help oracle attacks).

Privacy note for opens: we DO NOT include the recipient or the
tenant inside the open-token payload — only the ``send_id``. The
send row itself carries everything we need, and a short payload
keeps the URL compact (Gmail / Outlook truncate ``<img src>`` URLs
above a few hundred characters in some clients).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError, ValidationError

# Namespace prefixes — both join the HMAC input before signing.
OPEN_NAMESPACE = "open:"
UNSUBSCRIBE_NAMESPACE = "unsubscribe:"


class TokenInvalid(ValidationError):
    """Raised when a tracking / unsubscribe token fails verification.

    Mapped by the FastAPI middleware to a 422 — the recipient endpoint
    handlers translate further (open-pixel returns 200 + pixel anyway,
    unsubscribe returns 400 with a generic message).
    """

    code = "tracking_token_invalid"


class TokenNotConfigured(PlatformError):
    """Raised when ``INTERNAL_CREDENTIAL_TOKEN`` is unset.

    Without the HMAC key we cannot mint or verify tokens. Surfaces as
    503 ``not_configured`` so the operator sees the misconfig rather
    than silent token-validation failures.
    """

    code = "tracking_token_not_configured"
    http_status = 503


@dataclass(frozen=True, slots=True)
class OpenTokenPayload:
    """Decoded open-tracking token."""

    send_id: UUID


@dataclass(frozen=True, slots=True)
class UnsubscribeTokenPayload:
    """Decoded one-click unsubscribe token.

    ``email_hash`` is the HMAC-SHA256 of the normalised recipient email
    under the same key, hex-truncated to 32 chars. Used by the
    unsubscribe endpoint to confirm the token was minted for THIS
    recipient (defence-in-depth against a stolen-but-valid token being
    re-pointed at someone else's address). Never reversible.
    """

    tenant_id: UUID
    send_id: UUID
    email_hash: str


# --- HMAC key ---------------------------------------------------------------


def _hmac_key() -> bytes:
    """Return the HMAC key bytes from ``Settings.internal_credential_token``."""
    settings = get_settings()
    secret = settings.internal_credential_token
    if secret is None:
        raise TokenNotConfigured(
            "INTERNAL_CREDENTIAL_TOKEN is not set; tracking tokens cannot be signed",
        )
    return secret.get_secret_value().encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    pad = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * pad))


def _sign(namespace: str, line: bytes) -> str:
    """HMAC-SHA256 over ``<namespace>|<line>`` — hex-encoded."""
    payload = namespace.encode("utf-8") + b"|" + line
    return hmac.new(_hmac_key(), payload, hashlib.sha256).hexdigest()


def _email_hash(email_normalised: str) -> str:
    """HMAC-SHA256 of the normalised email, hex-truncated to 32 chars.

    The same key is used here as for token signing so a recipient
    address can be matched against a token without the key being
    duplicated. Truncation to 128 bits keeps the hash short while
    leaving collision resistance well beyond any practical attack.
    """
    digest = hmac.new(_hmac_key(), email_normalised.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:32]


# --- Open token ------------------------------------------------------------


def mint_open_token(*, send_id: UUID) -> str:
    """Mint a signed token for the 1x1 tracking pixel URL.

    Embedded by the send pipeline into the rendered HTML when the
    template's ``tracking_enabled = true``. The pixel route decodes
    the token and (privately) flips ``send.status = 'opened'`` once
    if the gate still permits.
    """
    payload: dict[str, Any] = {"send_id": str(send_id)}
    line = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = _sign(OPEN_NAMESPACE, line)
    return f"{_b64encode(line)}.{sig}"


def verify_open_token(token: str) -> OpenTokenPayload:
    """Verify an open token; return the decoded payload.

    Raises ``TokenInvalid`` for malformed / tampered / cross-namespace
    tokens. The recipient-facing pixel endpoint swallows the exception
    and still returns the pixel so the recipient cannot distinguish a
    valid token from an invalid one.
    """
    line, _decoded = _verify(token, OPEN_NAMESPACE)
    raw_send = _decoded.get("send_id")
    try:
        send_id = UUID(str(raw_send))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TokenInvalid("open token send_id invalid") from exc
    _ = line  # signature already validated
    return OpenTokenPayload(send_id=send_id)


# --- Unsubscribe token -----------------------------------------------------


def mint_unsubscribe_token(
    *,
    tenant_id: UUID,
    send_id: UUID,
    recipient_email_normalised: str,
) -> str:
    """Mint a signed token for the RFC 8058 one-click unsubscribe URL.

    The token binds three values: tenant (so it cannot be replayed to
    another tenant's unsubscribe endpoint), send (so the audit trail
    points at exactly one campaign / transactional send), and the
    recipient (so a stolen token cannot be re-aimed at someone else).
    """
    payload: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "send_id": str(send_id),
        "email_h": _email_hash(recipient_email_normalised),
    }
    line = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = _sign(UNSUBSCRIBE_NAMESPACE, line)
    return f"{_b64encode(line)}.{sig}"


def verify_unsubscribe_token(token: str) -> UnsubscribeTokenPayload:
    """Verify a one-click unsubscribe token; return the payload.

    The endpoint translates ``TokenInvalid`` to a 400 plain-text
    response — never reveals whether the token was tampered, expired,
    or pointed at the wrong tenant.
    """
    line, decoded = _verify(token, UNSUBSCRIBE_NAMESPACE)
    raw_tenant = decoded.get("tenant_id")
    raw_send = decoded.get("send_id")
    email_hash = decoded.get("email_h")
    try:
        tenant_id = UUID(str(raw_tenant))
        send_id = UUID(str(raw_send))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TokenInvalid("unsubscribe token tenant_id/send_id invalid") from exc
    if not isinstance(email_hash, str) or len(email_hash) != 32:
        raise TokenInvalid("unsubscribe token email_h invalid")
    _ = line  # signature already validated
    return UnsubscribeTokenPayload(
        tenant_id=tenant_id,
        send_id=send_id,
        email_hash=email_hash,
    )


def email_matches_unsubscribe_token(
    payload: UnsubscribeTokenPayload, recipient_email_normalised: str
) -> bool:
    """Defence-in-depth: confirm the token was minted for THIS email.

    Used by the unsubscribe endpoint when it looks up the send row and
    compares the stored recipient against the token's bound hash. A
    mismatch is a signal of either a stolen token or a bug in mint-
    time; both translate to 400.
    """
    expected = _email_hash(recipient_email_normalised)
    return hmac.compare_digest(expected, payload.email_hash)


# --- Internals -------------------------------------------------------------


def _verify(token: str, namespace: str) -> tuple[bytes, dict[str, Any]]:
    """Shared verification path: decode + signature check + JSON parse."""
    if not token or "." not in token:
        raise TokenInvalid("token malformed")

    body, sig = token.rsplit(".", 1)
    try:
        line = _b64decode(body)
    except (ValueError, TypeError) as exc:
        raise TokenInvalid("token base64 decode failed") from exc

    expected_sig = _sign(namespace, line)
    if not hmac.compare_digest(sig, expected_sig):
        raise TokenInvalid("token signature mismatch")

    try:
        decoded = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TokenInvalid("token json decode failed") from exc
    if not isinstance(decoded, dict):
        raise TokenInvalid("token payload is not an object")
    return line, decoded


__all__ = [
    "OPEN_NAMESPACE",
    "OpenTokenPayload",
    "TokenInvalid",
    "TokenNotConfigured",
    "UNSUBSCRIBE_NAMESPACE",
    "UnsubscribeTokenPayload",
    "email_matches_unsubscribe_token",
    "mint_open_token",
    "mint_unsubscribe_token",
    "verify_open_token",
    "verify_unsubscribe_token",
]
