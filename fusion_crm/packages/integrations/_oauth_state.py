"""Shared OAuth ``state`` parameter — HMAC-signed CSRF token.

Both ``google_workspace`` and ``microsoft_365`` use the same ``state``
shape. We mint a signed token before redirecting the operator to the
provider's authorize URL, then verify it on the callback to defend
against CSRF + cross-tenant grant injection.

Token format (URL-safe base64 of a single JSON line, then ``"."``,
then a hex HMAC-SHA256 over the JSON line)::

    <b64(json)>.<hmac_sha256_hex>

The JSON contains:

  - ``tenant_id``   — UUID string of the tenant initiating the connect
  - ``provider``    — ``"google_workspace"`` | ``"microsoft_365"``
  - ``nonce``       — 16-byte URL-safe random string
  - ``expires_at``  — POSIX timestamp (int) when the token stops being valid
  - ``location_id`` — UUID string or null (pin the credential to a location)
  - ``display_name``— optional operator-set label for the mailbox card

The HMAC key is ``Settings.internal_credential_token`` — already a
strong random value used by the FastAPI ↔ Next.js bridge. Reusing it
avoids provisioning a second secret. The HMAC is keyed on the JSON
*line* (not on individual fields), so any tamper in the payload (a
swapped tenant_id, a forged provider value) breaks verification.

TTL: ten minutes. The operator clicking through Google / Microsoft's
consent UI normally finishes inside a minute, ten leaves headroom for
SSO redirects and occasional flakiness.

Hard rules:

  - Verification ALWAYS uses ``hmac.compare_digest`` — never a string ``==``
    compare. Timing leaks here would let an attacker brute-force tokens.
  - We refuse to mint or verify a state when
    ``Settings.internal_credential_token`` is unset (returns
    ``OAuthStateNotConfigured``) — the caller must surface the operator
    error so the misconfig is loud.
  - The state value is a single opaque string from the caller's point
    of view. Do not attempt to parse the inner JSON outside this module.
"""

from __future__ import annotations

import base64
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError, ValidationError

# Ten-minute TTL — see module docstring.
_DEFAULT_TTL_SECONDS = 10 * 60

ALLOWED_PROVIDERS = frozenset({"google_workspace", "microsoft_365"})


class OAuthStateInvalid(ValidationError):
    """Raised when the OAuth ``state`` token fails verification.

    Mapped by the FastAPI middleware to a 422 ``validation_error`` —
    we deliberately do NOT distinguish between "tampered", "expired",
    and "wrong provider" in the operator-facing message: the failure
    modes are all "start over from the connect button".
    """

    code = "oauth_state_invalid"


class OAuthStateNotConfigured(PlatformError):
    """Raised when ``INTERNAL_CREDENTIAL_TOKEN`` is unset.

    State minting and verification both depend on the HMAC key. If the
    operator has not provisioned it, every connect attempt fails fast
    with a 503 — better than silently generating useless tokens.
    """

    code = "oauth_state_not_configured"
    http_status = 503


@dataclass(frozen=True, slots=True)
class OAuthStatePayload:
    """Decoded state payload after verification.

    The fields exposed here are exactly what callers need to drive the
    callback handler — tenant identity for the credential write, the
    provider branch, optional routing hints carried through the round
    trip.
    """

    tenant_id: UUID
    provider: str
    location_id: UUID | None
    display_name: str | None


def _hmac_key() -> bytes:
    """Return the HMAC key bytes from ``Settings.internal_credential_token``."""
    settings = get_settings()
    secret = settings.internal_credential_token
    if secret is None:
        raise OAuthStateNotConfigured(
            "INTERNAL_CREDENTIAL_TOKEN is not set; OAuth state cannot be signed",
        )
    return secret.get_secret_value().encode("utf-8")


def _b64encode(raw: bytes) -> str:
    """URL-safe base64 with padding stripped (compact, query-string safe)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    """URL-safe base64 decode that tolerates the stripped padding."""
    pad = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * pad))


def _sign(line: bytes) -> str:
    """HMAC-SHA256 over the canonical JSON line, hex-encoded."""
    return hmac.new(_hmac_key(), line, sha256).hexdigest()


def mint_state(
    *,
    tenant_id: UUID,
    provider: str,
    location_id: UUID | None = None,
    display_name: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> str:
    """Mint a signed state token for the OAuth round trip.

    ``provider`` MUST be one of ``ALLOWED_PROVIDERS`` — passing an
    unknown value is a programming error and raises ``ValidationError``.
    """
    if provider not in ALLOWED_PROVIDERS:
        raise ValidationError(
            "unknown OAuth provider for state",
            details={"provider": provider, "allowed": sorted(ALLOWED_PROVIDERS)},
        )

    payload: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "provider": provider,
        "nonce": secrets.token_urlsafe(16),
        "expires_at": int(time.time()) + int(ttl_seconds),
        "location_id": str(location_id) if location_id is not None else None,
        "display_name": display_name,
    }
    line = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = _sign(line)
    return f"{_b64encode(line)}.{sig}"


def verify_state(state: str) -> OAuthStatePayload:
    """Verify a previously-minted state token; return the payload.

    Raises ``OAuthStateInvalid`` for every failure mode (malformed,
    bad signature, expired, unknown provider). The caller treats
    "invalid" as a single operator-visible "start over" signal.
    """
    if not state or "." not in state:
        raise OAuthStateInvalid("state token malformed")

    body, sig = state.rsplit(".", 1)
    try:
        line = _b64decode(body)
    except (ValueError, TypeError) as exc:
        raise OAuthStateInvalid("state token base64 decode failed") from exc

    expected_sig = _sign(line)
    if not hmac.compare_digest(sig, expected_sig):
        raise OAuthStateInvalid("state token signature mismatch")

    try:
        decoded = json.loads(line)
    except json.JSONDecodeError as exc:
        raise OAuthStateInvalid("state token json decode failed") from exc
    if not isinstance(decoded, dict):
        raise OAuthStateInvalid("state token payload is not an object")

    expires_at = decoded.get("expires_at")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise OAuthStateInvalid("state token expired")

    provider = decoded.get("provider")
    if provider not in ALLOWED_PROVIDERS:
        raise OAuthStateInvalid("state token provider unknown")

    raw_tenant = decoded.get("tenant_id")
    try:
        tenant_id = UUID(str(raw_tenant))
    except (TypeError, ValueError, AttributeError) as exc:
        raise OAuthStateInvalid("state token tenant_id invalid") from exc

    raw_location = decoded.get("location_id")
    location_id: UUID | None = None
    if raw_location is not None:
        try:
            location_id = UUID(str(raw_location))
        except (TypeError, ValueError, AttributeError) as exc:
            raise OAuthStateInvalid("state token location_id invalid") from exc

    raw_display = decoded.get("display_name")
    display_name = raw_display if isinstance(raw_display, str) else None

    return OAuthStatePayload(
        tenant_id=tenant_id,
        provider=provider,
        location_id=location_id,
        display_name=display_name,
    )


__all__ = [
    "ALLOWED_PROVIDERS",
    "OAuthStateInvalid",
    "OAuthStateNotConfigured",
    "OAuthStatePayload",
    "mint_state",
    "verify_state",
]
