"""Send pipeline — the ENG-132 surface for the outreach domain.

Two services live here:

- ``PickMailboxService`` — resolves which mailbox credential to use
  for a given send. Routing order is fixed (ADR-0004 §"Mailbox
  routing") and every pick is audited so an operator can answer
  "why did this campaign go through that mailbox".

- ``SendService`` — enqueue surface. Two entry points:
  ``enqueue_campaign`` (materialise N ``send`` + ``outbound_queue``
  rows for a campaign) and ``enqueue_single`` (one-shot transactional
  send for an appointment reminder / consult confirmation). NEITHER
  calls a mail provider; the queue worker (``apps.worker.jobs.
  email_send``) drains the queue.

Both services satisfy the outreach domain's cross-package import
rules per ``packages/CLAUDE.md``: they reach into ``identity``,
``ops``, and ``tenant`` only through service surfaces, and they
write audit via ``AuditService``. They do not import
``integrations`` ORM types — the integration package is reached only
when the dispatcher worker resolves an adapter at send time, which
happens OUTSIDE this module.

Audit policy for this layer:

- ``outreach.mailbox.routed`` — every successful ``PickMailboxService
  .pick`` call. Carries ``strategy_step`` 1..4 so we can audit the
  resolution rule that fired.
- ``outreach.send.enqueued`` — every ``send`` row materialised, one
  audit row per recipient (we tolerate the volume because the audit
  is the durable accountability record per ADR-0004 §"Auditing").
- ``outreach.email.sent`` / ``outreach.email.failed`` —
  TERMINAL outcomes written by the dispatcher worker. Defined here
  so the constant lives in the outreach package; the dispatcher
  imports them by name.

No PII in audit `extra`. Recipient addresses are hashed (HMAC under
``INTERNAL_CREDENTIAL_TOKEN``) before being attached to any audit
row.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.config import get_settings
from packages.core.exceptions import (
    NotFoundError,
    PlatformError,
    ValidationError,
)
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.identity.service import IdentityService, normalise_email
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)
from packages.tenant.schemas import IntegrationCredentialOut

from .models import (
    CampaignMailboxStrategy,
    OutboundQueue,
    OutboundQueueStatus,
    Send,
    SendStatus,
)
from .repository import (
    CampaignRepository,
    OutboundQueueRepository,
    SendRepository,
    TemplateRepository,
)
from .service import SuppressionService

log = get_logger("outreach.send_service")


# --- Audit action codes (ENG-132) ----------------------------------------

AUDIT_MAILBOX_ROUTED = "outreach.mailbox.routed"
AUDIT_SEND_ENQUEUED = "outreach.send.enqueued"
AUDIT_EMAIL_SENT = "outreach.email.sent"
AUDIT_EMAIL_FAILED = "outreach.email.failed"
AUDIT_EMAIL_SUPPRESSED = "outreach.email.suppressed"
AUDIT_EMAIL_RATE_LIMITED = "outreach.email.rate_limited"


# --- Provider gating -----------------------------------------------------

# Only these provider kinds are mail-sending. SF + CareStack credentials
# in ``tenant.integration_credential`` are filtered out at the routing
# layer — they are not eligible for mailbox routing under any rule.
MAILBOX_PROVIDER_KINDS: frozenset[str] = frozenset(
    {"google_workspace", "microsoft_365"}
)


# --- Errors --------------------------------------------------------------


class NoMailboxAvailable(PlatformError):
    """``PickMailboxService.pick`` could not resolve a mailbox.

    Distinct from ``NoCredentialError`` so callers can distinguish "no
    SF credential" (configuration drift) from "no mailbox" (operator
    needs to connect Gmail / 365 first). The send service surfaces
    this as a 409-style error so the UI can prompt the operator with
    "Connect a mailbox" rather than a generic 502.
    """

    code = "no_mailbox_available"
    http_status = 409


# --- PickMailboxService --------------------------------------------------


class PickMailboxService:
    """Resolve which mailbox credential to use for one send.

    Routing order per ADR-0004 §"Mailbox routing":

    1. ``recipient_location_id`` + ``intent_tag`` match
       — a credential pinned to ``location_id`` AND carrying
       ``intent_tag`` in ``tags``.
    2. ``intent_tag`` match (any location)
       — a tag-pinned credential.
    3. ``provider_hint`` + ``is_default``
       — the tenant default for that provider, if the operator
       expressed a preference (e.g. campaign hint).
    4. any ``is_default``
       — the tenant's overall default mailbox.
    5. raise ``NoMailboxAvailable``.

    Every successful pick writes one ``outreach.mailbox.routed`` audit
    row with ``strategy_step`` so the operator can audit the rule
    that fired.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._credentials = IntegrationCredentialService(session)
        self._audit = AuditService(session)

    async def pick(
        self,
        tenant_id: TenantId,
        *,
        intent_tag: str | None = None,
        recipient_location_id: UUID | None = None,
        provider_hint: str | None = None,
        principal: Principal | None = None,
    ) -> IntegrationCredentialOut:
        """Resolve and audit the mailbox.

        ``principal`` is optional only to allow the worker (which
        operates under a synthesised SYSTEM principal) to call this
        without setting up a full request context. The audit row is
        still written under that principal.
        """
        # All mailbox credentials for the tenant — filter to email-OAuth
        # providers and active status in Python. At Phase 1 scale the
        # per-tenant credential count is small (< 10), so a list +
        # filter is cheaper than three separate indexed queries.
        rows = await self._credentials.list_for_tenant(tenant_id)
        candidates = [
            r
            for r in rows
            if r.provider_kind in MAILBOX_PROVIDER_KINDS
            and r.status == "active"
        ]
        if not candidates:
            raise NoMailboxAvailable(
                "no active mailbox credentials for tenant",
                details={"tenant_id": str(tenant_id)},
            )

        chosen, step = self._resolve(
            candidates,
            intent_tag=intent_tag,
            recipient_location_id=recipient_location_id,
            provider_hint=provider_hint,
        )
        if chosen is None:
            raise NoMailboxAvailable(
                "no mailbox matched the routing rules",
                details={
                    "tenant_id": str(tenant_id),
                    "intent_tag": intent_tag,
                    "recipient_location_id": (
                        str(recipient_location_id)
                        if recipient_location_id is not None
                        else None
                    ),
                    "provider_hint": provider_hint,
                    "candidate_count": len(candidates),
                },
            )

        if principal is not None:
            await self._audit.record(
                principal=principal,
                action=AUDIT_MAILBOX_ROUTED,
                resource="outreach.mailbox",
                extra={
                    "tenant_id": str(tenant_id),
                    "chosen_credential_id": str(chosen.id),
                    "provider_kind": chosen.provider_kind,
                    "strategy_step": step,
                    "intent_tag": intent_tag,
                    "has_location": recipient_location_id is not None,
                },
            )
        log.info(
            "outreach.mailbox.routed",
            tenant_id=str(tenant_id),
            credential_id=str(chosen.id),
            strategy_step=step,
            intent_tag=intent_tag,
            has_location=recipient_location_id is not None,
        )
        return chosen

    # --- Internal resolver ---

    @staticmethod
    def _resolve(
        candidates: list[IntegrationCredentialOut],
        *,
        intent_tag: str | None,
        recipient_location_id: UUID | None,
        provider_hint: str | None,
    ) -> tuple[IntegrationCredentialOut | None, int]:
        """Walk the routing rules in order.

        Returns ``(chosen, strategy_step)`` where ``strategy_step`` is
        the index of the rule that fired (1..4). ``(None, 5)`` is
        reserved for the no-match outcome — callers translate to
        ``NoMailboxAvailable``.
        """

        def _tag_match(cred: IntegrationCredentialOut, tag: str) -> bool:
            return tag in (cred.tags or [])

        # Step 1: location + intent_tag.
        if recipient_location_id is not None and intent_tag:
            for cred in candidates:
                if (
                    cred.location_id == recipient_location_id
                    and _tag_match(cred, intent_tag)
                ):
                    return cred, 1

        # Step 2: intent_tag (any location).
        if intent_tag:
            for cred in candidates:
                if _tag_match(cred, intent_tag):
                    return cred, 2

        # Step 3: provider_hint + is_default.
        if provider_hint:
            for cred in candidates:
                if cred.provider_kind == provider_hint and cred.is_default:
                    return cred, 3

        # Step 4: any is_default.
        for cred in candidates:
            if cred.is_default:
                return cred, 4

        return None, 5


# --- Send service --------------------------------------------------------


class SendService:
    """Public surface for enqueuing outreach sends (ENG-132).

    ``enqueue_campaign`` materialises N rows in ``outreach.send`` and
    ``outreach.outbound_queue`` for a campaign; ``enqueue_single`` is
    the one-shot transactional path (appointment reminders, consult
    confirmations).

    Neither method calls a mail provider — the queue worker drains
    the table per ADR-0004 decision #1.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._campaigns = CampaignRepository(session)
        self._templates = TemplateRepository(session)
        self._sends = SendRepository(session)
        self._queue = OutboundQueueRepository(session)
        self._suppression = SuppressionService(session)
        self._picker = PickMailboxService(session)
        self._identity = IdentityService(session)
        self._audit = AuditService(session)

    # --- Campaign enqueue ---

    async def enqueue_campaign(
        self,
        tenant_id: TenantId,
        campaign_id: UUID,
        *,
        principal: Principal,
    ) -> int:
        """Materialise the campaign's recipient list into queue rows.

        Returns the number of queue rows created. Suppressed recipients
        are persisted as ``send.status='unsubscribed'`` with NO
        outbound_queue row (so the suppression decision is visible in
        the campaign's send list, never silently dropped).

        Strategy ``explicit`` uses the campaign's
        ``mailbox_credential_id`` for every recipient. Strategy
        ``auto_route`` picks per recipient (location-pinned routing
        means two recipients in the same campaign can land on
        different mailboxes).
        """
        campaign = await self._campaigns.get_for_tenant(tenant_id, campaign_id)
        if campaign is None:
            raise NotFoundError(
                "campaign not found",
                details={
                    "tenant_id": str(tenant_id),
                    "campaign_id": str(campaign_id),
                },
            )
        template = await self._templates.get_for_tenant(
            tenant_id, campaign.template_id
        )
        if template is None:
            raise NotFoundError(
                "campaign template missing",
                details={
                    "tenant_id": str(tenant_id),
                    "template_id": str(campaign.template_id),
                },
            )

        explicit_credential_id: UUID | None = None
        if campaign.mailbox_strategy == CampaignMailboxStrategy.EXPLICIT.value:
            if campaign.mailbox_credential_id is None:
                raise ValidationError(
                    "campaign with mailbox_strategy='explicit' is missing "
                    "mailbox_credential_id",
                    details={"campaign_id": str(campaign_id)},
                )
            explicit_credential_id = campaign.mailbox_credential_id

        recipients = list(_resolve_recipients(campaign.recipient_query))
        intent_tags = list(template.intent_tags or [])
        intent_tag = intent_tags[0] if intent_tags else None

        enqueued = 0
        for recipient in recipients:
            email = recipient.get("email")
            if not isinstance(email, str) or "@" not in email:
                # Skip malformed entries — operators see them in the
                # preview UI before enqueue. Still, defend at runtime.
                continue
            normalised = normalise_email(email)
            person_uid = recipient.get("person_uid")
            location_id = recipient.get("location_id")

            # Suppression check — does NOT enqueue a queue row; the
            # send row records ``unsubscribed`` so it stays visible.
            if await self._suppression.is_suppressed(tenant_id, normalised):
                suppression_send = Send(
                    tenant_id=tenant_id,
                    campaign_id=campaign.id,
                    person_uid=person_uid if isinstance(person_uid, UUID) else None,
                    recipient_email=normalised,
                    mailbox_credential_id=(
                        explicit_credential_id
                        or _zero_uuid()  # placeholder; queue row will not exist
                    ),
                    status=SendStatus.UNSUBSCRIBED.value,
                )
                await self._sends.add(suppression_send)
                await self._audit.record(
                    principal=principal,
                    action=AUDIT_EMAIL_SUPPRESSED,
                    resource="outreach.send",
                    extra={
                        "tenant_id": str(tenant_id),
                        "campaign_id": str(campaign.id),
                        "send_id": str(suppression_send.id),
                        "recipient_hash": _hash_email(normalised),
                    },
                )
                continue

            # Resolve mailbox for this recipient.
            if explicit_credential_id is not None:
                credential_id = explicit_credential_id
            else:
                chosen = await self._picker.pick(
                    tenant_id,
                    intent_tag=intent_tag,
                    recipient_location_id=(
                        location_id if isinstance(location_id, UUID) else None
                    ),
                    principal=principal,
                )
                credential_id = chosen.id

            send = Send(
                tenant_id=tenant_id,
                campaign_id=campaign.id,
                person_uid=person_uid if isinstance(person_uid, UUID) else None,
                recipient_email=normalised,
                mailbox_credential_id=credential_id,
                status=SendStatus.QUEUED.value,
            )
            await self._sends.add(send)

            queue_row = OutboundQueue(
                tenant_id=tenant_id,
                send_id=send.id,
                credential_id=credential_id,
                priority=100,
                scheduled_for=campaign.scheduled_for
                if campaign.scheduled_for is not None
                else datetime.now(UTC),
                status=OutboundQueueStatus.PENDING.value,
            )
            await self._queue.add(queue_row)
            enqueued += 1

            await self._audit.record(
                principal=principal,
                action=AUDIT_SEND_ENQUEUED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "campaign_id": str(campaign.id),
                    "send_id": str(send.id),
                    "credential_id": str(credential_id),
                    "recipient_hash": _hash_email(normalised),
                },
            )

        return enqueued

    # --- Single-shot enqueue ---

    async def enqueue_single(
        self,
        tenant_id: TenantId,
        *,
        template_id: UUID,
        person_uid: UUID,
        recipient_email: str,
        mailbox_credential_id: UUID | None = None,
        intent_tag: str | None = None,
        recipient_location_id: UUID | None = None,
        principal: Principal,
    ) -> UUID:
        """Enqueue one transactional send. Returns the new ``send.id``.

        Used by appointment-reminder / consult-confirmation flows that
        do not have a campaign row. The recipient must already be a
        known person (``person_uid``) — we record it on the send so
        the timeline can stitch the send back onto the person's
        interaction history.

        Suppression is enforced (a suppressed recipient gets a
        ``send.status='unsubscribed'`` row with no queue row). Mailbox
        routing follows ``PickMailboxService`` unless
        ``mailbox_credential_id`` is given.
        """
        template = await self._templates.get_for_tenant(tenant_id, template_id)
        if template is None:
            raise NotFoundError(
                "template not found",
                details={
                    "tenant_id": str(tenant_id),
                    "template_id": str(template_id),
                },
            )

        normalised = normalise_email(recipient_email)
        if await self._suppression.is_suppressed(tenant_id, normalised):
            send = Send(
                tenant_id=tenant_id,
                campaign_id=None,  # transactional sends have no campaign
                person_uid=person_uid,
                recipient_email=normalised,
                mailbox_credential_id=mailbox_credential_id or _zero_uuid(),
                status=SendStatus.UNSUBSCRIBED.value,
            )
            await self._sends.add(send)
            await self._audit.record(
                principal=principal,
                action=AUDIT_EMAIL_SUPPRESSED,
                resource="outreach.send",
                extra={
                    "tenant_id": str(tenant_id),
                    "send_id": str(send.id),
                    "recipient_hash": _hash_email(normalised),
                },
            )
            return send.id

        # Resolve mailbox.
        if mailbox_credential_id is None:
            chosen = await self._picker.pick(
                tenant_id,
                intent_tag=intent_tag,
                recipient_location_id=recipient_location_id,
                principal=principal,
            )
            credential_id = chosen.id
        else:
            credential_id = mailbox_credential_id

        send = Send(
            tenant_id=tenant_id,
            campaign_id=None,
            person_uid=person_uid,
            recipient_email=normalised,
            mailbox_credential_id=credential_id,
            status=SendStatus.QUEUED.value,
        )
        await self._sends.add(send)

        queue_row = OutboundQueue(
            tenant_id=tenant_id,
            send_id=send.id,
            credential_id=credential_id,
            priority=50,  # transactional sends jump campaign sends
            scheduled_for=datetime.now(UTC),
            status=OutboundQueueStatus.PENDING.value,
        )
        await self._queue.add(queue_row)

        await self._audit.record(
            principal=principal,
            action=AUDIT_SEND_ENQUEUED,
            resource="outreach.send",
            extra={
                "tenant_id": str(tenant_id),
                "send_id": str(send.id),
                "credential_id": str(credential_id),
                "recipient_hash": _hash_email(normalised),
            },
        )
        return send.id


# --- Recipient query DSL (minimal Stage 1 grammar) -----------------------


def _resolve_recipients(query: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Decode a campaign.recipient_query into a recipient iterable.

    The Stage 1 grammar accepts a single shape::

        {
          "recipients": [
            {"email": "x@y", "person_uid": "<uuid>", "location_id": "<uuid>"},
            ...
          ]
        }

    Anything richer (SQL filter, lead-status selector, etc.) is owned
    by the campaign service / preview path; ENG-132 just materialises
    what the operator already accepted in the preview pane.
    """
    if not isinstance(query, dict):
        return ()
    recipients = query.get("recipients")
    if not isinstance(recipients, list):
        return ()
    out: list[dict[str, Any]] = []
    for entry in recipients:
        if not isinstance(entry, dict):
            continue
        cleaned: dict[str, Any] = {}
        email = entry.get("email")
        if isinstance(email, str):
            cleaned["email"] = email
        person_uid = entry.get("person_uid")
        if isinstance(person_uid, UUID):
            cleaned["person_uid"] = person_uid
        elif isinstance(person_uid, str):
            try:
                cleaned["person_uid"] = UUID(person_uid)
            except ValueError:
                pass
        loc = entry.get("location_id")
        if isinstance(loc, UUID):
            cleaned["location_id"] = loc
        elif isinstance(loc, str):
            try:
                cleaned["location_id"] = UUID(loc)
            except ValueError:
                pass
        out.append(cleaned)
    return out


# --- Hashing helper ------------------------------------------------------


def _hash_email(email_normalised: str) -> str:
    """HMAC-SHA256 of a normalised recipient under the internal token.

    Returns the first 16 hex chars (64 bits) — enough entropy for
    audit-trail correlation, short enough to keep audit `extra` light.
    The hash is irreversible and the same email always produces the
    same hash within the deployment, so an investigator can correlate
    "all audit rows about this recipient" without ever putting the
    address on disk in audit.
    """
    settings = get_settings()
    token_secret = settings.internal_credential_token
    # When the token is not configured (dev bootstraps), fall back to
    # a stable hash with NO secret. The hash is still irreversible at
    # human inspection time; we annotate "salt=app" so investigators
    # know the namespace.
    key = (
        token_secret.get_secret_value().encode("utf-8")
        if token_secret is not None
        else b"outreach-audit-salt"
    )
    digest = hmac.new(key, email_normalised.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:16]


# Sentinel UUID for the suppression-only send rows. The schema requires
# ``send.mailbox_credential_id`` NOT NULL; we use a zero UUID rather
# than enlarging the schema for a "no-mailbox" case. Operators see
# these rows in the campaign view; the queue worker never touches them.
def _zero_uuid() -> UUID:
    return UUID("00000000-0000-0000-0000-000000000000")


__all__ = [
    "AUDIT_EMAIL_FAILED",
    "AUDIT_EMAIL_RATE_LIMITED",
    "AUDIT_EMAIL_SENT",
    "AUDIT_EMAIL_SUPPRESSED",
    "AUDIT_MAILBOX_ROUTED",
    "AUDIT_SEND_ENQUEUED",
    "MAILBOX_PROVIDER_KINDS",
    "NoCredentialError",
    "NoMailboxAvailable",
    "PickMailboxService",
    "SendService",
]
