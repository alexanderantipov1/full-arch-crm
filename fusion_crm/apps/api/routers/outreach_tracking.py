"""Recipient-facing tracking + unsubscribe routes (ENG-134).

Per ADR-0004 §"Tracking" decision #3 (opens off by default, pixel
served from our own domain) + decision #4 (per-tenant suppression,
HMAC tokens, RFC 8058 one-click).

Three handlers, all unauthenticated — the HMAC tokens ARE the auth:

  - ``GET  /outreach/track/open/{token}`` — 1x1 transparent GIF.
    Privately records ``send.status='opened'`` when the template's
    ``tracking_enabled`` is true; ALWAYS returns the pixel so the
    recipient cannot tell whether tracking is active.
  - ``POST /outreach/unsubscribe/{token}`` — RFC 8058 one-click.
    Mail clients send an empty body with
    ``List-Unsubscribe=One-Click`` form data per the spec — we
    accept either. Idempotent: a second submission no-ops.
  - ``GET  /u/{token}`` — confirmation form. No JavaScript; a plain
    HTML POST form (or a short status page when the token is
    already-unsubscribed). Used when a mail client cannot do
    one-click and the recipient clicks the visible link in the
    body.

Hard rules (all enforced here):

  - **No PII in logs.** Audit ``extra`` carries ``send_id`` +
    ``credential_id`` + outcome only.
  - **Tracking pixel never reveals tracking state.** Constant
    200 + 43-byte GIF response regardless of token validity,
    template gate, or send state.
  - **Cache-Control: no-store** on the pixel + unsubscribe
    responses — proxies / browsers MUST NOT cache them.
  - **Tenant isolation.** The send row's ``tenant_id`` is the
    source of truth for every downstream write. The HMAC token
    is the only thing on the wire; we look up the send globally
    (the token validates the lookup) and then use ``send.tenant_id``
    for service calls.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from packages.audit.service import AuditService
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.outreach.models import SendStatus
from packages.outreach.repository import (
    CampaignRepository,
    SendRepository,
    TemplateRepository,
)
from packages.outreach.service import (
    AUDIT_EMAIL_OPENED,
    AUDIT_EMAIL_UNSUBSCRIBED,
    SuppressionService,
)
from packages.outreach.tracking_tokens import (
    TokenInvalid,
    email_matches_unsubscribe_token,
    verify_open_token,
    verify_unsubscribe_token,
)

router = APIRouter(tags=["outreach-tracking"])

log = get_logger("api.outreach_tracking")

# 43-byte GIF89a — 1x1 transparent. Constant; never regenerated per
# request so a downstream cache / WAF cannot infer state from byte
# count or timing.
_TRANSPARENT_GIF = bytes(
    [
        0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00, 0x80, 0x00,
        0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x21, 0xF9, 0x04, 0x01, 0x00,
        0x00, 0x00, 0x00, 0x2C, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
        0x00, 0x02, 0x02, 0x44, 0x01, 0x00, 0x3B,
    ]
)


# Recipient-facing routes never look at the request principal — they
# act under a synthesised SYSTEM principal so the audit trail does
# not slip an ANONYMOUS principal in. Tenant comes from the send row.
def _system_principal_for_tenant(tenant_id: TenantId) -> Principal:
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"source": "outreach.tracking"},
    )


def _pixel_response() -> Response:
    """Return the canonical 200 + GIF + no-store response.

    Factored out so every path (valid token, invalid token, gated
    template) returns the SAME bytes and headers. No information
    leaked through ``Content-Length``, ``Cache-Control``, or any
    other header that differs between branches.
    """
    return Response(
        content=_TRANSPARENT_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- Open tracking pixel -------------------------------------------------


@router.get(
    "/outreach/track/open/{token}",
    response_class=Response,
    include_in_schema=False,  # recipient-facing; not part of operator OpenAPI
)
async def track_open(
    token: Annotated[str, Path(max_length=2048)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """1x1 transparent GIF. Records the open privately when permitted.

    Privacy contract:

    - ALWAYS returns 200 + the pixel — never 4xx, never a redirect.
    - When the token is invalid (bad signature, malformed, wrong
      namespace) we still return the pixel. The recipient learns
      nothing about validity.
    - When the template's ``tracking_enabled`` is false (clinical /
      transactional / operational category, or an opted-out
      marketing template) we still return the pixel. The recipient
      learns nothing about the gate.
    - When the send is already ``opened`` we no-op the state write.
      The campaign counter only ticks on the FIRST open per send.
    - No IP / user-agent is read or logged.
    """
    try:
        payload = verify_open_token(token)
    except TokenInvalid:
        return _pixel_response()

    send_repo = SendRepository(db)
    template_repo = TemplateRepository(db)
    campaign_repo = CampaignRepository(db)

    send = await send_repo.get_global(payload.send_id)
    if send is None:
        return _pixel_response()

    # Resolve the template via the campaign row. Transactional sends
    # (campaign_id IS NULL) are not subject to open tracking in
    # Stage 1 — they only ship under clinical / transactional
    # categories whose template-side gate forbids tracking anyway.
    if send.campaign_id is None:
        return _pixel_response()

    campaign = await campaign_repo.get_for_tenant(
        send.tenant_id, send.campaign_id
    )
    if campaign is None:
        return _pixel_response()

    template = await template_repo.get_for_tenant(
        send.tenant_id, campaign.template_id
    )
    if template is None or not template.tracking_enabled:
        return _pixel_response()

    # Privacy gate cleared. Only update state on the first open and
    # only while the send is still in a pre-open status.
    if send.status == SendStatus.SENT.value:
        send.status = SendStatus.OPENED.value
        campaign.opened_count = (campaign.opened_count or 0) + 1

        tenant_id = TenantId(send.tenant_id)
        principal = _system_principal_for_tenant(tenant_id)
        audit = AuditService(db)
        await audit.record(
            principal=principal,
            action=AUDIT_EMAIL_OPENED,
            resource="outreach.send",
            extra={
                "tenant_id": str(tenant_id),
                "send_id": str(send.id),
                "campaign_id": str(campaign.id),
                "credential_id": str(send.mailbox_credential_id),
                "template_id": str(template.id),
            },
        )

    return _pixel_response()


# --- One-click unsubscribe (RFC 8058) -----------------------------------


@router.post(
    "/outreach/unsubscribe/{token}",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def unsubscribe_one_click(
    token: Annotated[str, Path(max_length=2048)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> PlainTextResponse:
    """RFC 8058 one-click unsubscribe handler.

    The mail client POSTs to this URL with body
    ``List-Unsubscribe=One-Click`` (or an empty body — RFC 8058
    requires we accept both). We verify the HMAC token, confirm the
    bound email matches the send row, add the recipient to
    suppression, and return ``200 Unsubscribed``.

    Failure modes (all return 400 + plain text "Bad request"):

    - Invalid / tampered / cross-namespace token.
    - Token's bound ``email_hash`` does not match the send row.
    - The token references a send that no longer exists. (We do
      not reveal which case — a single 400 keeps the failure mode
      opaque.)

    Idempotent: a second submission for an already-suppressed
    recipient still returns 200, no second audit row beyond the
    initial suppression-add.

    ``request`` is accepted only to allow future logging hooks —
    we never read body / headers here.
    """
    _ = request

    try:
        payload = verify_unsubscribe_token(token)
    except TokenInvalid:
        return PlainTextResponse(
            "Bad request",
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    send_repo = SendRepository(db)
    send = await send_repo.get_global(payload.send_id)
    if send is None or send.tenant_id != payload.tenant_id:
        return PlainTextResponse(
            "Bad request",
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    # Defence-in-depth — confirm the token was minted for THIS send's
    # recipient. A stolen-but-valid token cannot be re-aimed at
    # someone else's send_id because send_id is bound in the token,
    # but we still check the recipient mapping in case a future
    # mint-time bug ever flips that constraint.
    if not email_matches_unsubscribe_token(payload, send.recipient_email):
        return PlainTextResponse(
            "Bad request",
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    tenant_id = TenantId(send.tenant_id)
    principal = _system_principal_for_tenant(tenant_id)

    suppression = SuppressionService(db)
    await suppression.add_suppression(
        tenant_id,
        send.recipient_email,
        reason="one_click",
        principal=principal,
        source_send_id=send.id,
    )

    # Flip the send row's status so the campaign view shows the
    # unsubscribe terminal state. Idempotent: if the row is already
    # ``unsubscribed`` we no-op.
    if send.status != SendStatus.UNSUBSCRIBED.value:
        send.status = SendStatus.UNSUBSCRIBED.value

    audit = AuditService(db)
    await audit.record(
        principal=principal,
        action=AUDIT_EMAIL_UNSUBSCRIBED,
        resource="outreach.send",
        extra={
            "tenant_id": str(tenant_id),
            "send_id": str(send.id),
            "credential_id": str(send.mailbox_credential_id),
            "source": "one_click",
        },
    )

    return PlainTextResponse(
        "Unsubscribed",
        status_code=200,
        headers={"Cache-Control": "no-store"},
    )


# --- Manual unsubscribe form ---------------------------------------------


_FORM_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica,
    Arial, sans-serif;
  max-width: 480px;
  margin: 64px auto;
  padding: 0 24px;
  color: #1f2937;
  line-height: 1.5;
}}
h1 {{ font-size: 18px; margin-bottom: 16px; }}
p  {{ font-size: 14px; margin-bottom: 16px; }}
button {{
  appearance: none;
  background: #111827;
  color: #fff;
  border: 0;
  border-radius: 6px;
  font-size: 14px;
  padding: 10px 20px;
  cursor: pointer;
}}
button:hover {{ background: #1f2937; }}
.muted {{ color: #6b7280; font-size: 12px; margin-top: 32px; }}
</style>
</head>
<body>
<h1>{heading}</h1>
<p>{body}</p>
{form}
<p class="muted">Token reference: {token_ref}</p>
</body>
</html>
"""

_CONFIRM_FORM_FRAGMENT = """<form method="post" action="/outreach/unsubscribe/{token}">
<button type="submit">Confirm unsubscribe</button>
</form>"""


@router.get(
    "/u/{token}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def unsubscribe_form(
    token: Annotated[str, Path(max_length=2048)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """Manual unsubscribe confirmation page (no JavaScript).

    Some mail clients still render the ``List-Unsubscribe`` header
    only as a visible body link — RFC 8058's one-click POST applies
    to header-driven clicks only. The GET form gives recipients a
    consistent path even when their client cannot one-click.

    The page is intentionally plain (inline CSS, no external assets)
    so it loads on every mail client preview pane and behind
    aggressive corporate proxies. No JavaScript runs.
    """
    # Verify the token. We DO render a friendly page on failure so
    # the recipient is not stranded with a generic 400.
    try:
        payload = verify_unsubscribe_token(token)
    except TokenInvalid:
        body_html = _FORM_TEMPLATE.format(
            title="Link expired",
            heading="This unsubscribe link is no longer valid.",
            body=(
                "It may have been forwarded, edited, or has been used "
                "already. If you would still like to unsubscribe, please "
                "reply to the email you received and let us know."
            ),
            form="",
            token_ref=_short_token_ref(token),
        )
        return HTMLResponse(
            body_html,
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    send_repo = SendRepository(db)
    send = await send_repo.get_global(payload.send_id)
    if send is None or send.tenant_id != payload.tenant_id:
        body_html = _FORM_TEMPLATE.format(
            title="Link not found",
            heading="We could not find that subscription.",
            body=(
                "If you continue to receive emails, reply to the most "
                "recent message and we will remove you manually."
            ),
            form="",
            token_ref=_short_token_ref(token),
        )
        return HTMLResponse(
            body_html,
            status_code=404,
            headers={"Cache-Control": "no-store"},
        )

    tenant_id = TenantId(send.tenant_id)
    suppression = SuppressionService(db)
    already = await suppression.is_suppressed(tenant_id, send.recipient_email)
    if already:
        body_html = _FORM_TEMPLATE.format(
            title="Unsubscribed",
            heading="You are unsubscribed.",
            body=(
                "We will not send you further marketing emails. If you "
                "would like to re-subscribe in the future, please contact "
                "the sender directly."
            ),
            form="",
            token_ref=_short_token_ref(token),
        )
        return HTMLResponse(
            body_html,
            status_code=200,
            headers={"Cache-Control": "no-store"},
        )

    body_html = _FORM_TEMPLATE.format(
        title="Confirm unsubscribe",
        heading="Are you sure you want to unsubscribe?",
        body=(
            "Click the button below to remove your address from future "
            "marketing emails. You can re-subscribe at any time by "
            "contacting the sender directly."
        ),
        form=_CONFIRM_FORM_FRAGMENT.format(token=token),
        token_ref=_short_token_ref(token),
    )
    return HTMLResponse(
        body_html,
        status_code=200,
        headers={"Cache-Control": "no-store"},
    )


def _short_token_ref(token: str) -> str:
    """Return a short reference for the operator-visible page footer.

    We expose only the first 8 chars — enough for an operator who has
    to manually correlate a support ticket but never enough to
    reconstruct or test the HMAC.
    """
    return (token[:8] + "…") if len(token) > 8 else token


__all__ = ["router"]
