"""Internal credential resolver — Next.js → FastAPI bridge.

Provides decrypted credential payloads to the Next.js server-side route
handlers (which then make outbound SF / CareStack HTTP calls). Gated by a
shared ``X-Internal-Token`` header so only the same trust zone can read
plaintext payloads — never reachable from the public internet.

This router is mounted at ``/_internal`` and the path is intentionally
ugly so it does not look like a stable public surface. Production traffic
should never hit it directly; the Next.js server uses it via in-cluster
networking.

Surface:

  - ``GET /_internal/credentials/{provider}/{kind}`` — return the
    decrypted payload as JSON. Returns 401 on missing / mismatched
    token, 404 on no row found, 503 on resolver-not-configured (the
    operator forgot to set ``INTERNAL_CREDENTIAL_TOKEN``).
  - ``PUT /_internal/credentials/{provider}/{kind}`` — upsert a fresh
    payload (used by the Next.js refresh-token flow when SF returns a
    new ``access_token``). Same auth gate.

The resolver uses ``IntegrationCredentialService`` which audits every
read/write — the payload itself never appears in any audit ``extra``.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import (
    get_db,
    get_principal_with_tenant,
)
from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

router = APIRouter(prefix="/_internal", tags=["internal"])


class InternalAuthError(PlatformError):
    """401 Unauthorized — internal token missing / mismatched."""

    code = "internal_unauthorized"
    http_status = 401


class InternalNotConfiguredError(PlatformError):
    """503 Service Unavailable — INTERNAL_CREDENTIAL_TOKEN not set on the API."""

    code = "internal_resolver_not_configured"
    http_status = 503


def _check_internal_token(token_header: str | None) -> None:
    """Raise unless ``token_header`` matches Settings.internal_credential_token.

    Compared via ``hmac.compare_digest`` to avoid timing leaks. We do NOT
    log the header value — that is the secret.
    """
    settings = get_settings()
    expected = settings.internal_credential_token
    if expected is None:
        raise InternalNotConfiguredError(
            "INTERNAL_CREDENTIAL_TOKEN is not set on the API",
        )
    if not token_header:
        raise InternalAuthError("missing X-Internal-Token header")
    expected_value = expected.get_secret_value()
    if not hmac.compare_digest(token_header, expected_value):
        raise InternalAuthError("X-Internal-Token mismatch")


HeaderToken = Annotated[
    str | None,
    Header(alias="X-Internal-Token", description="Shared resolver token"),
]


@router.get("/credentials/{provider_kind}/{credential_kind}")
async def read_credential(
    provider_kind: str,
    credential_kind: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    x_internal_token: HeaderToken = None,
) -> dict[str, Any]:
    """Return the decrypted credential payload for the request tenant.

    The tenant is resolved by ``get_principal_with_tenant`` from
    ``Settings.tenant_default_slug`` (Phase 1) or future per-tenant
    auth (Phase 2). Body is the plaintext credential payload — the
    Next.js client copies it into outbound requests.

    Errors map to the standard envelope:

      - 503 ``internal_resolver_not_configured`` — operator forgot to
        set ``INTERNAL_CREDENTIAL_TOKEN``.
      - 401 ``internal_unauthorized`` — header missing / mismatched.
      - 404 ``no_credential`` — no active row for the tuple.
      - 422 ``validation_error`` — bad enum.
    """
    _check_internal_token(x_internal_token)

    tenant_id = principal.require_tenant()
    svc = IntegrationCredentialService(db)
    try:
        payload = await svc.read_for(
            TenantId(tenant_id), provider_kind, credential_kind
        )
    except NoCredentialError:
        # Bubble up to PlatformError handler so the JSON envelope shape
        # is consistent with the rest of the API.
        raise
    return payload


@router.put("/credentials/{provider_kind}/{credential_kind}")
async def upsert_credential(
    provider_kind: str,
    credential_kind: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
    x_internal_token: HeaderToken = None,
) -> dict[str, Any]:
    """Upsert a fresh credential payload for the request tenant.

    Used by the Next.js SF refresh-token flow: when the SF token endpoint
    returns a new ``access_token``, the Next.js OAuth handler PUTs the
    new payload back so the DB stays the source of truth.

    Body shape depends on ``(provider, kind)``; the service does not
    validate inner keys (they are provider-specific). The whole dict is
    encrypted into the envelope.
    """
    _check_internal_token(x_internal_token)
    if not isinstance(payload, dict):
        # FastAPI parses JSON for us, but be defensive.
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    tenant_id = principal.require_tenant()
    svc = IntegrationCredentialService(db)
    cred = await svc.upsert(
        TenantId(tenant_id),
        provider_kind,
        credential_kind,
        payload,
        principal=principal,
    )
    return {
        "ok": True,
        "credential_id": str(cred.id),
        "provider_kind": cred.provider_kind,
        "credential_kind": cred.credential_kind,
        "is_default": cred.is_default,
    }
