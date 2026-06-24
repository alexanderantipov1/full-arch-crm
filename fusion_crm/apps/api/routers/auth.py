"""Session + access-list endpoints for the staff frontend.

Behind Cloud IAP, every request carries the verified Google identity
in the ``X-Goog-Authenticated-User-Email`` header. The frontend's
``useSession`` hook polls ``/api/auth/session`` to decide whether to
render the staff app or redirect to ``/login``. This handler returns
the IAP identity as a stub session.

When the header is absent (local dev with no IAP in front, or a
direct VPC-internal call), we return 401 — the frontend treats both
that and a missing handler the same way.

``/auth/access-list`` reads IAP's IAM policy for both LB backend
services (``fusion-lb-backend-web``, ``fusion-lb-backend-api``) and
returns the merged member list so the Tenant Settings UI can show
who currently has staff access. The fusion-api SA needs
``roles/iam.securityReviewer`` at the project level to call IAP's
``getIamPolicy``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import NAMESPACE_DNS, uuid5

import httpx
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from packages.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

log = logging.getLogger(__name__)

_IAP_HEADER = "x-goog-authenticated-user-email"
_IAP_PREFIX = "accounts.google.com:"

# IAP IAM policy lives at:
#   POST https://iap.googleapis.com/v1/projects/{NUMBER}/iap_web/compute/services/{SVC}:getIamPolicy
_GCP_PROJECT_NUMBER = "800777477533"
# Surface labels are constrained by AccessSurfaceSchema on the FE.
_Surface = Literal["web", "api"]
_IAP_BACKENDS: tuple[tuple[_Surface, str], ...] = (
    ("web", "fusion-lb-backend-web"),
    ("api", "fusion-lb-backend-api"),
)
_IAP_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_IAP_TIMEOUT_S = 10.0
_STAFF_SESSION_COOKIE = "staff_session"
_STAFF_SESSION_MAX_AGE_S = 8 * 60 * 60


def _build_session(email: str) -> dict[str, str]:
    display_name = email.split("@", 1)[0] if "@" in email else email
    staff_id = str(uuid5(NAMESPACE_DNS, f"iap:{email}"))
    expires_at = datetime.now(UTC) + timedelta(hours=8)
    return {
        "staff_id": staff_id,
        "email": email,
        "display_name": display_name,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(payload: LoginIn, response: Response) -> dict[str, object]:
    """Local-dev login. In production all auth flows through Google IAP, so
    this endpoint is never reached behind the LB; the frontend reaches it
    only when running against a non-IAP API (i.e. `npm run dev`). The
    handler accepts any password and mints a session keyed on the supplied
    email so the staff UI can be exercised without setting up IAP locally.
    """
    session = _build_session(payload.email)
    if not get_settings().is_production:
        response.set_cookie(
            _STAFF_SESSION_COOKIE,
            session["staff_id"],
            httponly=True,
            samesite="lax",
            max_age=_STAFF_SESSION_MAX_AGE_S,
            path="/",
        )
    return {"session": session}


@router.get("/session")
async def session(request: Request) -> dict[str, object]:
    iap_email = request.headers.get(_IAP_HEADER, "")
    if iap_email.startswith(_IAP_PREFIX):
        email = iap_email[len(_IAP_PREFIX):]
    elif iap_email:
        email = iap_email
    else:
        email = "anonymous@fusion-crm.local"
    return {"session": _build_session(email)}


# --- /auth/access-list -----------------------------------------------------


MemberKind = Literal["user", "domain", "serviceAccount", "group", "other"]
Surface = _Surface


class AccessMember(BaseModel):
    kind: MemberKind
    value: str
    role: str
    surfaces: list[Surface]


class AccessListOut(BaseModel):
    live: bool
    members: list[AccessMember]
    reason: str | None = None


async def _get_access_token() -> str | None:
    """Fetch an OAuth2 access token via Application Default Credentials.

    Returns None when ADC is not configured (local dev without gcloud
    auth) — caller treats this as the empty-list case.
    """
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(scopes=[_IAP_SCOPE])
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token
    except Exception as exc:
        log.warning("auth.access_list.adc_unavailable: %s", exc)
        return None


def _split_member(raw: str) -> tuple[MemberKind, str]:
    """Split a Google IAM member string like 'user:foo@bar' into (kind, value)."""
    if ":" not in raw:
        return "other", raw
    prefix, _, value = raw.partition(":")
    kinds: dict[str, MemberKind] = {
        "user": "user",
        "domain": "domain",
        "serviceAccount": "serviceAccount",
        "group": "group",
    }
    return kinds.get(prefix, "other"), value


@router.get("/access-list", response_model=AccessListOut)
async def access_list() -> AccessListOut:
    """Return everyone IAP currently grants staff access to.

    Reads the IAM policies for the two LB backend services in parallel
    and merges them by (kind, value, role). The ``surfaces`` array tells
    the UI whether the binding is on web, api, or both.
    """
    token = await _get_access_token()
    if token is None:
        return AccessListOut(
            live=False,
            members=[],
            reason="ADC unavailable — running outside Cloud Run or no gcloud auth",
        )

    merged: dict[tuple[MemberKind, str, str], set[Surface]] = {}
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=_IAP_TIMEOUT_S) as client:
        for surface, backend in _IAP_BACKENDS:
            url = (
                f"https://iap.googleapis.com/v1/projects/{_GCP_PROJECT_NUMBER}"
                f"/iap_web/compute/services/{backend}:getIamPolicy"
            )
            try:
                resp = await client.post(url, headers=headers, json={})
                resp.raise_for_status()
                body = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                log.warning(
                    "auth.access_list.iap_getIamPolicy_failed backend=%s err=%s",
                    backend, exc,
                )
                return AccessListOut(
                    live=False,
                    members=[],
                    reason=f"IAP getIamPolicy failed for {backend}: {exc}",
                )

            for binding in body.get("bindings", []) or []:
                role = binding.get("role", "")
                for raw_member in binding.get("members", []) or []:
                    kind, value = _split_member(raw_member)
                    merged.setdefault((kind, value, role), set()).add(surface)

    members = [
        AccessMember(kind=kind, value=value, role=role, surfaces=sorted(surfaces))
        for (kind, value, role), surfaces in sorted(merged.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ]
    return AccessListOut(live=True, members=members)
