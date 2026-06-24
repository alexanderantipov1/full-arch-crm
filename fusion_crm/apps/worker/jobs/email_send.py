"""Outbound email dispatcher — drain ``outreach.outbound_queue``.

Per ADR-0004 decision #1 + ENG-132 spec. Pulls pending rows with
``SELECT ... FOR UPDATE SKIP LOCKED``, resolves the mailbox
credential, gates on the per-mailbox rate limiter, renders the
template, hands the RFC 5322 bytes to the provider adapter, and
records the terminal outcome.

Job lifecycle for one queue row:

1. Lock the row (``status='locked'``, ``locked_by=worker_id``,
   ``locked_at=now``) inside the ``FOR UPDATE SKIP LOCKED`` lock,
   then COMMIT so the row lock is released and the row is observable
   to other workers as ``locked`` (which they skip).
2. Resolve the mailbox credential via
   ``IntegrationCredentialService.read_by_id`` (defence-in-depth
   tenant check).
3. Check rate limiter. If exceeded → ``reschedule`` with
   ``scheduled_for = now + retry_after`` and continue.
4. Check the suppression list (``SuppressionService.is_suppressed``).
   If suppressed → mark send ``unsubscribed`` + queue row
   ``succeeded`` + audit, continue.
5. Resolve the send + template, build the ``PersonRenderContext``,
   render, mint HMAC tokens, build RFC 5322 bytes (with optional
   tracking pixel when the template's ``tracking_enabled`` is true).
6. Dispatch via the provider adapter. Translate the result:
   - ``SendResult`` → ``send.status='sent'``, queue row ``succeeded``,
     audit ``outreach.email.sent``.
   - ``RateLimitError`` → backoff + reschedule; after max retries
     fail the row.
   - ``TransientError`` → backoff + reschedule; after max retries
     fail the row.
   - ``PermanentError`` → ``send.status='failed'``, queue row
     ``failed``, audit ``outreach.email.failed``.

ENG-134 additions:

- Unsubscribe URL is now the HMAC-signed
  ``{tracking_base_url}/outreach/unsubscribe/{token}`` (one-click POST)
  plus a manual confirmation form at ``/u/{token}``. Both lead to
  the same backend handler.
- When the resolved template has ``tracking_enabled = true``, the
  builder injects a 1x1 tracking pixel pointing at
  ``{tracking_base_url}/outreach/track/open/{token}``. Categories
  in ``TRACKING_FORBIDDEN_CATEGORIES`` (clinical / transactional /
  operational) can never have tracking_enabled=true, so the
  category gate is enforced at template create / update time and
  re-checked here defensively.

The worker writes audit rows under a synthesised SYSTEM principal —
queue drains happen outside any user request, so there is no API
principal to inherit. The audit row carries ``credential_id`` +
``recipient_hash`` (HMAC) + result code; never raw email.

Idempotency: each queue row moves through ``pending → locked →
{succeeded|failed|pending}`` under explicit state checks. If the
worker crashes between lock and dispatch, the row stays ``locked``
until a Stage 2 reconciliation pass demotes it back to ``pending``.
"""

from __future__ import annotations

import os
import random
import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.config import get_settings
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import PersonUID, TenantId
from packages.db.session import async_session
from packages.identity.service import IdentityService, normalise_email
from packages.integrations.google_workspace.client import GoogleWorkspaceClient
from packages.integrations.google_workspace.send import (
    GmailSendAdapter,
    PermanentError,
    RateLimitError,
    SendAdapter,
    TransientError,
)
from packages.integrations.microsoft_365.client import MicrosoftClient
from packages.integrations.microsoft_365.send import GraphSendAdapter
from packages.ops.service import OpsService
from packages.outreach.email_builder import build_rfc822
from packages.outreach.models import (
    TRACKING_FORBIDDEN_CATEGORIES,
    Campaign,
    OutboundQueue,
    OutboundQueueStatus,
    Send,
    SendStatus,
    Template,
)
from packages.outreach.rate_limiter import (
    RateLimiter,
    RateLimiterUnavailable,
)
from packages.outreach.render import PersonRenderContext, render_with_trace
from packages.outreach.repository import (
    OutboundQueueRepository,
    SendRepository,
    TemplateRepository,
)
from packages.outreach.schemas import TemplateOut
from packages.outreach.send_service import (
    AUDIT_EMAIL_FAILED,
    AUDIT_EMAIL_RATE_LIMITED,
    AUDIT_EMAIL_SENT,
    AUDIT_EMAIL_SUPPRESSED,
    _hash_email,
)
from packages.outreach.service import SuppressionService
from packages.outreach.tracking_tokens import (
    TokenNotConfigured,
    mint_open_token,
    mint_unsubscribe_token,
)
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)

log = get_logger("worker.email_send")

# Conservative defaults — the dispatcher is poll-driven and a small
# batch keeps each tick short. Bumping ``BATCH_SIZE`` is safe up to
# the worker concurrency budget; over that and we start fighting
# the rate limiter unnecessarily.
BATCH_SIZE = 25

# Retry caps (per-row). 429 / transient share the same backoff curve
# (exp + jitter) but different attempt caps because 5xx tends to
# resolve faster than a 24h Gmail daily-cap window.
MAX_RATE_LIMIT_RETRIES = 3
MAX_TRANSIENT_RETRIES = 5

# Backoff bounds (seconds).
_BACKOFF_BASE = 30.0
_BACKOFF_MAX = 60 * 60.0  # 1 hour
_BACKOFF_JITTER_FRAC = 0.2


def _system_principal(tenant_id: TenantId | None) -> Principal:
    """A synthesised principal for worker-side audit rows."""
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"source": "worker.email_send"},
    )


def _worker_id() -> str:
    """Identifier the row's ``locked_by`` carries.

    Host + pid is enough to disambiguate stuck rows during incident
    response.
    """
    host = socket.gethostname() or "unknown"
    return f"{host}/{os.getpid()}"


def _backoff_seconds(attempts: int) -> float:
    """Exponential backoff with jitter, capped at ``_BACKOFF_MAX``."""
    base = min(_BACKOFF_BASE * (2 ** max(attempts, 0)), _BACKOFF_MAX)
    jitter = base * _BACKOFF_JITTER_FRAC
    return max(1.0, base + random.uniform(-jitter, jitter))


async def drain_outbound_queue(ctx: dict) -> dict:
    """One drain pass over ``outreach.outbound_queue``.

    Schedule every ~10 s from the arq cron config or invoke from the
    CLI. Each call drains at most ``BATCH_SIZE`` rows and returns a
    summary the caller / arq keep_result can record.
    """
    _ = ctx
    summary: dict[str, int] = {
        "sent": 0,
        "failed": 0,
        "deferred": 0,
        "suppressed": 0,
    }
    now = datetime.now(UTC)
    worker_id = _worker_id()

    # Lock + commit pass — release the row lock as fast as we can so
    # other workers can drain in parallel.
    locked: list[
        tuple[UUID, UUID, UUID, UUID, int]
    ] = []  # (queue_id, tenant_id, credential_id, send_id, attempts)
    async with async_session() as session:
        queue_repo = OutboundQueueRepository(session)
        rows = await queue_repo.lock_batch(
            worker_id=worker_id, batch_size=BATCH_SIZE, now=now
        )
        for row in rows:
            locked.append(
                (
                    row.id,
                    row.tenant_id,
                    row.credential_id,
                    row.send_id,
                    row.attempts or 0,
                )
            )

    if not locked:
        return summary

    settings = get_settings()
    redis_client = redis_async.from_url(
        str(settings.redis_url), decode_responses=False
    )
    rate_limiter = RateLimiter(redis_client)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0)
        ) as http:
            for queue_id, tenant_id_raw, credential_id, send_id, attempts in locked:
                tenant_id = TenantId(tenant_id_raw)
                outcome = await _process_one(
                    queue_id=queue_id,
                    tenant_id=tenant_id,
                    credential_id=credential_id,
                    send_id=send_id,
                    attempts=attempts,
                    rate_limiter=rate_limiter,
                    http=http,
                )
                summary[outcome] = summary.get(outcome, 0) + 1
    finally:
        try:
            await redis_client.aclose()
        except Exception:  # noqa: BLE001 — best-effort close
            pass

    log.info("outreach.dispatcher.tick", summary=summary, worker_id=worker_id)
    return summary


async def _process_one(
    *,
    queue_id: UUID,
    tenant_id: TenantId,
    credential_id: UUID,
    send_id: UUID,
    attempts: int,
    rate_limiter: RateLimiter,
    http: httpx.AsyncClient,
) -> str:
    """Drive one locked queue row to a terminal state.

    Returns ``"sent" | "failed" | "deferred" | "suppressed"`` so the
    drain summary stays compact.
    """
    principal = _system_principal(tenant_id)

    async with async_session() as session:
        queue_repo = OutboundQueueRepository(session)
        send_repo = SendRepository(session)
        template_repo = TemplateRepository(session)
        suppression = SuppressionService(session)
        audit = AuditService(session)
        identity_svc = IdentityService(session)
        ops_svc = OpsService(session)
        credentials = IntegrationCredentialService(session)

        queue_row = await queue_repo.get(queue_id)
        if queue_row is None or queue_row.status != OutboundQueueStatus.LOCKED.value:
            return "deferred"

        send_row = await send_repo.get_for_tenant(tenant_id, send_id)
        if send_row is None:
            await queue_repo.mark_failed(
                queue_row,
                last_error="send row missing",
                now=datetime.now(UTC),
            )
            return "failed"

        # --- Credential + provider_kind resolution ----------------------
        try:
            credential = await credentials.read_by_id(
                credential_id, tenant_id=tenant_id
            )
        except NoCredentialError as exc:
            await queue_repo.mark_failed(
                queue_row,
                last_error=f"credential missing: {exc.message}",
                now=datetime.now(UTC),
            )
            send_row.status = SendStatus.FAILED.value
            send_row.error_text = "credential missing"
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_FAILED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "reason": "credential_missing",
                },
            )
            return "failed"

        provider_kind = await _resolve_provider_kind(
            credentials=credentials,
            tenant_id=tenant_id,
            credential_id=credential_id,
        )
        if provider_kind not in {"google_workspace", "microsoft_365"}:
            await queue_repo.mark_failed(
                queue_row,
                last_error=f"non-mail provider: {provider_kind!r}",
                now=datetime.now(UTC),
            )
            send_row.status = SendStatus.FAILED.value
            send_row.error_text = "non-mail provider"
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_FAILED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "reason": "non_mail_provider",
                    "provider_kind": provider_kind,
                },
            )
            return "failed"

        # --- Rate limiter ------------------------------------------------
        try:
            decision = await rate_limiter.check_and_consume(
                credential_id, provider_kind
            )
        except RateLimiterUnavailable as exc:
            await queue_repo.reschedule(
                queue_row,
                scheduled_for=datetime.now(UTC) + timedelta(seconds=15),
                last_error=f"rate limiter unavailable: {exc.message}",
                bump_attempts=False,
            )
            return "deferred"

        if not decision.allowed:
            await queue_repo.reschedule(
                queue_row,
                scheduled_for=datetime.now(UTC)
                + timedelta(seconds=max(decision.retry_after_seconds, 1)),
                last_error="rate_limited",
                bump_attempts=False,
            )
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_RATE_LIMITED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "window_seconds": decision.window_seconds,
                    "retry_after_seconds": decision.retry_after_seconds,
                    "stage": "pre_dispatch",
                },
            )
            return "deferred"

        # --- Suppression check ------------------------------------------
        # Defence-in-depth — the send service also checks suppression at
        # enqueue (ENG-132 + ENG-134), but a recipient may have hit the
        # unsubscribe link between enqueue and drain. Normalise here so
        # the lookup matches the stored ``recipient_email_normalised``.
        normalised_recipient = normalise_email(send_row.recipient_email)
        if await suppression.is_suppressed(tenant_id, normalised_recipient):
            send_row.status = SendStatus.UNSUBSCRIBED.value
            await queue_repo.mark_succeeded(queue_row, now=datetime.now(UTC))
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_SUPPRESSED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "recipient_hash": _hash_email(send_row.recipient_email),
                    "stage": "dispatcher",
                },
            )
            return "suppressed"

        # --- Render the template ----------------------------------------
        template = await _resolve_template(
            session=session,
            template_repo=template_repo,
            tenant_id=tenant_id,
            send_row=send_row,
        )
        if template is None:
            await queue_repo.mark_failed(
                queue_row,
                last_error="template not found at dispatch",
                now=datetime.now(UTC),
            )
            send_row.status = SendStatus.FAILED.value
            send_row.error_text = "template missing"
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_FAILED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "reason": "template_missing",
                },
            )
            return "failed"

        context = await _build_render_context(
            identity=identity_svc,
            ops=ops_svc,
            tenant_id=tenant_id,
            person_uid=send_row.person_uid,
        )
        rendered, _trace = render_with_trace(
            TemplateOut.model_validate(template), context
        )

        # --- Build RFC 5322 envelope ------------------------------------
        mailbox_email_raw = credential.get("mailbox_email")
        mailbox_email = (
            mailbox_email_raw
            if isinstance(mailbox_email_raw, str) and "@" in mailbox_email_raw
            else None
        )
        if mailbox_email is None:
            await queue_repo.mark_failed(
                queue_row,
                last_error="mailbox_email missing on credential",
                now=datetime.now(UTC),
            )
            send_row.status = SendStatus.FAILED.value
            send_row.error_text = "mailbox_email missing"
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_FAILED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "reason": "mailbox_email_missing",
                },
            )
            return "failed"

        # --- ENG-134: mint HMAC tokens + build URLs ----------------------
        tracking_base = get_settings().effective_tracking_base_url
        try:
            unsubscribe_token = mint_unsubscribe_token(
                tenant_id=tenant_id,
                send_id=send_row.id,
                recipient_email_normalised=normalised_recipient,
            )
        except TokenNotConfigured:
            # The internal token has not been provisioned. We refuse
            # to send mail with an unsigned unsubscribe URL — without
            # the token the recipient cannot opt out, which violates
            # RFC 8058. Fail loudly so the operator notices.
            await queue_repo.mark_failed(
                queue_row,
                last_error="INTERNAL_CREDENTIAL_TOKEN not configured",
                now=datetime.now(UTC),
            )
            send_row.status = SendStatus.FAILED.value
            send_row.error_text = "tracking_token_not_configured"
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_FAILED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "reason": "tracking_token_not_configured",
                },
            )
            return "failed"

        unsub_url = (
            f"{tracking_base}/outreach/unsubscribe/{unsubscribe_token}"
        )
        unsub_mailto = (
            f"mailto:unsubscribe@{mailbox_email.rsplit('@', 1)[1]}"
            f"?subject=unsub-{send_row.id}"
        )

        # Tracking pixel: only when the template opted in AND the
        # category gate allows it. The template service enforces both
        # at create / update time; we re-check here defensively so a
        # data drift cannot ship a pixel inside a clinical email.
        tracking_pixel_url: str | None = None
        if (
            template.tracking_enabled
            and template.category not in TRACKING_FORBIDDEN_CATEGORIES
        ):
            try:
                open_token = mint_open_token(send_id=send_row.id)
                tracking_pixel_url = (
                    f"{tracking_base}/outreach/track/open/{open_token}"
                )
            except TokenNotConfigured:
                # Without the secret we still ship the email — opens
                # are a soft feature, unlike the unsubscribe URL above.
                # The send proceeds without a pixel.
                tracking_pixel_url = None

        rfc822_bytes = build_rfc822(
            from_address=mailbox_email,
            from_display_name=_display_name_from_credential(credential),
            to=send_row.recipient_email,
            subject=rendered.subject,
            body_html=rendered.body_html,
            body_text=rendered.body_text,
            list_unsubscribe_url=unsub_url,
            list_unsubscribe_mailto=unsub_mailto,
            tracking_pixel_url=tracking_pixel_url,
        )

        # --- Dispatch via adapter ---------------------------------------
        adapter = await _build_adapter(
            provider_kind=provider_kind,
            credential_id=credential_id,
            session=session,
            principal=principal,
            http=http,
        )

        try:
            result = await adapter.send(rfc822_bytes)
        except RateLimitError as exc:
            return await _handle_rate_limit(
                queue_repo=queue_repo,
                queue_row=queue_row,
                send_row=send_row,
                audit=audit,
                principal=principal,
                tenant_id=tenant_id,
                send_id=send_id,
                credential_id=credential_id,
                attempts=attempts,
                error=exc,
            )
        except TransientError as exc:
            return await _handle_transient(
                queue_repo=queue_repo,
                queue_row=queue_row,
                send_row=send_row,
                audit=audit,
                principal=principal,
                tenant_id=tenant_id,
                send_id=send_id,
                credential_id=credential_id,
                attempts=attempts,
                error=exc,
            )
        except PermanentError as exc:
            return await _handle_permanent(
                queue_repo=queue_repo,
                queue_row=queue_row,
                send_row=send_row,
                audit=audit,
                principal=principal,
                tenant_id=tenant_id,
                send_id=send_id,
                credential_id=credential_id,
                error=exc,
            )
        except Exception as exc:  # noqa: BLE001 — last-resort fail
            await queue_repo.mark_failed(
                queue_row,
                last_error=f"unexpected adapter error: {type(exc).__name__}",
                now=datetime.now(UTC),
            )
            send_row.status = SendStatus.FAILED.value
            send_row.error_text = "dispatcher exception"
            await audit.record(
                principal=principal,
                action=AUDIT_EMAIL_FAILED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send_id),
                    "credential_id": str(credential_id),
                    "reason": "exception",
                    "error_type": type(exc).__name__,
                },
            )
            return "failed"

        # --- Terminal success -------------------------------------------
        send_row.status = SendStatus.SENT.value
        send_row.message_id = result.message_id
        send_row.sent_at = datetime.now(UTC)
        await queue_repo.mark_succeeded(queue_row, now=datetime.now(UTC))
        await audit.record(
            principal=principal,
            action=AUDIT_EMAIL_SENT,
            resource="outreach.send",
            extra={
                "tenant_id": str(tenant_id),
                "send_id": str(send_id),
                "credential_id": str(credential_id),
                "provider_kind": provider_kind,
                "has_message_id": result.message_id is not None,
                "has_tracking_pixel": tracking_pixel_url is not None,
                "recipient_hash": _hash_email(send_row.recipient_email),
            },
        )
        return "sent"


# --- Terminal handlers ---------------------------------------------------


async def _handle_rate_limit(
    *,
    queue_repo: OutboundQueueRepository,
    queue_row: OutboundQueue,
    send_row: Send,
    audit: AuditService,
    principal: Principal,
    tenant_id: TenantId,
    send_id: UUID,
    credential_id: UUID,
    attempts: int,
    error: RateLimitError,
) -> str:
    if attempts >= MAX_RATE_LIMIT_RETRIES:
        await queue_repo.mark_failed(
            queue_row,
            last_error=f"rate-limit retries exhausted: {error.message}",
            now=datetime.now(UTC),
        )
        send_row.status = SendStatus.FAILED.value
        send_row.error_text = "rate_limit_exhausted"
        await audit.record(
            principal=principal,
            action=AUDIT_EMAIL_FAILED,
            resource="outreach.send",
            extra={
                "tenant_id": str(tenant_id),
                "send_id": str(send_id),
                "credential_id": str(credential_id),
                "reason": "rate_limit_exhausted",
            },
        )
        return "failed"

    retry_after = error.retry_after_seconds or _backoff_seconds(attempts)
    await queue_repo.reschedule(
        queue_row,
        scheduled_for=datetime.now(UTC) + timedelta(seconds=retry_after),
        last_error=f"rate_limit (attempt {attempts + 1})",
    )
    await audit.record(
        principal=principal,
        action=AUDIT_EMAIL_RATE_LIMITED,
        resource="outreach.send",
        extra={
            "tenant_id": str(tenant_id),
            "send_id": str(send_id),
            "credential_id": str(credential_id),
            "attempt": attempts + 1,
            "retry_after_seconds": int(retry_after),
            "stage": "provider",
        },
    )
    return "deferred"


async def _handle_transient(
    *,
    queue_repo: OutboundQueueRepository,
    queue_row: OutboundQueue,
    send_row: Send,
    audit: AuditService,
    principal: Principal,
    tenant_id: TenantId,
    send_id: UUID,
    credential_id: UUID,
    attempts: int,
    error: TransientError,
) -> str:
    if attempts >= MAX_TRANSIENT_RETRIES:
        await queue_repo.mark_failed(
            queue_row,
            last_error=f"transient retries exhausted: {error.message}",
            now=datetime.now(UTC),
        )
        send_row.status = SendStatus.FAILED.value
        send_row.error_text = "transient_exhausted"
        await audit.record(
            principal=principal,
            action=AUDIT_EMAIL_FAILED,
            resource="outreach.send",
            extra={
                "tenant_id": str(tenant_id),
                "send_id": str(send_id),
                "credential_id": str(credential_id),
                "reason": "transient_exhausted",
                "status_code": error.status_code,
            },
        )
        return "failed"

    retry_after = _backoff_seconds(attempts)
    await queue_repo.reschedule(
        queue_row,
        scheduled_for=datetime.now(UTC) + timedelta(seconds=retry_after),
        last_error=f"transient (attempt {attempts + 1})",
    )
    return "deferred"


async def _handle_permanent(
    *,
    queue_repo: OutboundQueueRepository,
    queue_row: OutboundQueue,
    send_row: Send,
    audit: AuditService,
    principal: Principal,
    tenant_id: TenantId,
    send_id: UUID,
    credential_id: UUID,
    error: PermanentError,
) -> str:
    await queue_repo.mark_failed(
        queue_row,
        last_error=f"permanent failure: {error.message}",
        now=datetime.now(UTC),
    )
    send_row.status = SendStatus.FAILED.value
    send_row.error_text = error.message
    await audit.record(
        principal=principal,
        action=AUDIT_EMAIL_FAILED,
        resource="outreach.send",
        extra={
            "tenant_id": str(tenant_id),
            "send_id": str(send_id),
            "credential_id": str(credential_id),
            "reason": "permanent",
            "status_code": error.status_code,
        },
    )
    return "failed"


# --- Helpers -------------------------------------------------------------


async def _resolve_provider_kind(
    *,
    credentials: IntegrationCredentialService,
    tenant_id: TenantId,
    credential_id: UUID,
) -> str:
    """Look up ``provider_kind`` for the credential via list_for_tenant.

    ``read_by_id`` returns the decrypted payload only — the row's
    ``provider_kind`` is on the DTO instead.
    """
    rows = await credentials.list_for_tenant(tenant_id)
    for row in rows:
        if row.id == credential_id:
            return row.provider_kind
    return ""


async def _build_adapter(
    *,
    provider_kind: str,
    credential_id: UUID,
    session: AsyncSession,
    principal: Principal,
    http: httpx.AsyncClient,
) -> SendAdapter:
    """Construct the right adapter for ``provider_kind``."""
    if provider_kind == "google_workspace":
        gclient = await GoogleWorkspaceClient.from_credential(
            credential_id,
            session=session,
            principal=principal,
            http=http,
        )
        return GmailSendAdapter(gclient)
    if provider_kind == "microsoft_365":
        mclient = await MicrosoftClient.from_credential(
            credential_id,
            session=session,
            principal=principal,
            http=http,
        )
        return GraphSendAdapter(mclient)
    raise ValueError(f"unknown mail provider_kind: {provider_kind}")


async def _resolve_template(
    *,
    session: AsyncSession,
    template_repo: TemplateRepository,
    tenant_id: TenantId,
    send_row: Send,
) -> Template | None:
    """Resolve the template a send row was generated against.

    Campaign sends reach the template via the campaign row;
    transactional sends (``campaign_id IS NULL``) currently rely on a
    future ``send.template_id`` column — until that lands the worker
    returns ``None`` and the row is failed with a clear reason.
    """
    if send_row.campaign_id is None:
        return None
    stmt = (
        select(Campaign)
        .where(Campaign.tenant_id == tenant_id)
        .where(Campaign.id == send_row.campaign_id)
        .limit(1)
    )
    campaign = (await session.execute(stmt)).scalar_one_or_none()
    if campaign is None:
        return None
    return await template_repo.get_for_tenant(tenant_id, campaign.template_id)


async def _build_render_context(
    *,
    identity: IdentityService,
    ops: OpsService,
    tenant_id: TenantId,
    person_uid: UUID | None,
) -> PersonRenderContext:
    """Compose the per-send PersonRenderContext.

    PHI is not read here. When ``person_uid`` is missing (external
    recipient) we return a minimal context — unknown placeholders
    render empty.
    """
    if person_uid is None:
        return PersonRenderContext()

    try:
        person = await identity.get_person(tenant_id, PersonUID(person_uid))
    except Exception:  # noqa: BLE001 — best-effort enrichment
        return PersonRenderContext()

    snapshot = None
    try:
        snapshot = await ops.snapshot(tenant_id, PersonUID(person.id))
    except Exception:  # noqa: BLE001
        snapshot = None

    lead_status: str | None = None
    if snapshot is not None and getattr(snapshot, "last_lead_status", None) is not None:
        lead_status = getattr(snapshot.last_lead_status, "value", None)

    return PersonRenderContext(
        patient_first_name=person.given_name,
        patient_last_name=person.family_name,
        patient_full_name=person.display_name,
        lead_status=lead_status,
    )


def _display_name_from_credential(payload: dict[str, object]) -> str | None:
    """Best-effort sender display name from the credential payload."""
    for key in ("display_name", "name", "displayName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


__all__ = ["drain_outbound_queue"]
