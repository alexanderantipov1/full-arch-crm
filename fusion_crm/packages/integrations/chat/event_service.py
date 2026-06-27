"""NotificationEventService — the rule engine entry point (ENG-437, Block D).

This is the single call any state-changing site uses to fan a workspace
event out to chat channels. Given a canonical ``event_type`` (see
:mod:`packages.integrations.chat.events`) and an event ``context``, it:

1. loads the tenant's *enabled* rules for that event type;
2. evaluates each rule's ``conditions`` against the context
   (:func:`packages.integrations.chat.conditions.evaluate`);
3. for every matching rule, renders the rule's ``template`` through the
   de-identification guardrail
   (:func:`packages.integrations.chat.render.render`); and
4. enqueues one :class:`NotificationOutbox` row per match via
   :class:`NotificationService` (status ``pending``), for the dispatcher
   to drain.

The service shares the caller's session and NEVER commits — the
boundary (API request / worker job) owns the unit of work, so the
outbox rows land in the same transaction as the state change (the
transactional-outbox pattern). Returns the enqueued rows.

The context is enriched with three engine-provided variables before
render: ``person_uid`` (opaque), ``deep_link`` (built from the existing
``web_app_base_url`` setting), and ``event_type``.

ENG-460: the messenger is an AUTHORIZED PHI surface, so by default
(``Settings.messenger_phi_full=True``) the renderer runs in
``phi_mode="full"`` and substitutes any context variable verbatim —
callers may (and do) pass the patient's real name / phone / provider so
cards are useful to staff. When the flag is False the renderer falls back
to the historical ``deidentified`` mode (allowlist only); in that mode the
allowlist is the backstop that guarantees nothing un-listed leaks.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.tenant.service import LocationService

from ..models import NotificationOutbox
from ..notification_repository import (
    NotificationEmittedRepository,
    NotificationRuleRepository,
)
from ..notification_schemas import (
    NotificationOutboxIn,
    NotificationProviderKind,
)
from ..notification_service import NotificationService
from . import conditions, render

log = get_logger("integrations.notification.event")

# A resolved Mattermost channel id (26-char base32-ish). A rule channel that
# already matches this shape, or one that is team-qualified (``team/channel``),
# is left as-is by ``_qualify_channel``.
_MM_ID_RE = re.compile(r"^[a-z0-9]{26}$")

# Reserved context keys (ENG-458). ``mattermost_team`` pins the target team
# directly; ``location_id`` lets the engine derive the team from the entity's
# ``tenant.location.external_ref['mattermost_team']`` mapping. Neither is a
# template placeholder — they only drive per-location routing.
CTX_TEAM = "mattermost_team"
CTX_LOCATION_ID = "location_id"
LOCATION_TEAM_KEY = "mattermost_team"


def build_deep_link(person_uid: UUID) -> str:
    """Build the staff deep link for a person from the existing base URL.

    Reuses ``Settings.web_app_base_url`` (the Next.js staff frontend host)
    rather than introducing a new env var / deploy contract. Shape mirrors
    the staff person-detail route ``/persons/{uid}``.
    """
    base = get_settings().web_app_base_url.rstrip("/")
    return f"{base}/persons/{person_uid}"


def _as_utc(value: datetime) -> datetime:
    """Normalise a datetime to aware-UTC, assuming UTC when it is naive.

    Guards the cutoff comparison: a naive ``NOTIFICATIONS_CUTOFF_AT`` env value
    compared against an aware provider timestamp would raise ``TypeError``.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class NotificationEventService:
    """Resolve rules for an event and enqueue de-identified outbox rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._rules = NotificationRuleRepository(session)
        self._notifications = NotificationService(session)
        self._emitted = NotificationEmittedRepository(session)
        self._locations = LocationService(session)

    async def emit(
        self,
        tenant_id: TenantId,
        event_type: str,
        context: dict[str, object],
        *,
        principal: Principal,
        person_uid: UUID | None = None,
        dedupe_key: str | None = None,
        source_created_at: datetime | None = None,
    ) -> list[NotificationOutbox]:
        """Fan ``event_type`` out to every matching, enabled rule.

        The reusable API for the new-entity notification wiring (ENG-456 /
        ENG-457). Guards short-circuit to ``[]`` (enqueue nothing) so the
        method stays a safe no-op in the suppressed cases:

        1. **Enablement** — if ``Settings.notifications_enabled`` is False the
           whole engine is dark; return immediately. This is the default, so
           the wiring lands without sending anything until an operator flips
           it on.
        2. **Historical cutoff** — if ``source_created_at`` is supplied AND a
           ``Settings.notifications_cutoff_at`` is configured AND the entity
           predates the cutoff, suppress (a backfilled pre-existing entity
           must not page anyone).
        3. **Idempotency** — checked AFTER rules are resolved and conditions
           matched (so a no-rule / no-match emit never burns the dedupe key
           and permanently suppresses a future real notification). If
           ``dedupe_key`` is supplied and ≥1 rule matches, claim it in the
           durable ledger; if the claim loses (already emitted), suppress.
           The claim and the outbox enqueue share THIS session, so the
           boundary commits them atomically — a claimed-but-not-enqueued
           state cannot occur.

        Args:
            tenant_id: the tenant whose rules to evaluate.
            event_type: a canonical event code (see
                :mod:`packages.integrations.chat.events`).
            context: non-PII event facts; used both for condition
                evaluation and (through the allowlist) template render.
            principal: the acting principal (forwarded to the audit row
                that :meth:`NotificationService.enqueue` writes).
            person_uid: the global person this event concerns, if any;
                drives ``{{person_uid}}`` and ``{{deep_link}}``.
            dedupe_key: a stable opaque key for the entity (typically the
                provider entity id, e.g. an SF Lead Id). When provided,
                guarantees AT MOST ONE emit per ``(tenant, event_type,
                dedupe_key)`` EVER. When ``None``, no dedupe is performed
                (legacy behaviour — used by the API ``lead.created`` path,
                which is single-shot by construction).
            source_created_at: the instant the source entity was created in
                the originating system. When provided and before the
                configured cutoff, the emit is suppressed.

        Returns the enqueued (pending) outbox rows, in rule order. Does
        NOT commit.

        Backfill contract: bulk / backfill call sites (ENG-456 / ENG-457)
        MUST either NOT route through ``emit`` at all, or MUST pass a stable
        ``dedupe_key`` so a re-run is a no-op. Passing ``source_created_at``
        alongside a cutoff additionally suppresses pre-cutoff historical
        entities. A's contract is that this guard is bulletproof; B/C own
        wiring the call sites correctly.
        """
        settings = get_settings()

        # Guard 1 — master enablement. Dark by default.
        if not settings.notifications_enabled:
            return []

        # Guard 2 — historical cutoff. Suppress entities created before it.
        # Both sides are normalised to aware-UTC first: a naive
        # ``NOTIFICATIONS_CUTOFF_AT`` env value compared against an aware
        # provider timestamp would otherwise raise ``TypeError`` and fail the
        # whole sync tick.
        cutoff = settings.notifications_cutoff_at
        if source_created_at is not None and cutoff is not None and (
            _as_utc(source_created_at) < _as_utc(cutoff)
        ):
            log.info(
                "notification.event.skipped_pre_cutoff",
                event_type=event_type,
                person_uid=str(person_uid) if person_uid else None,
            )
            return []

        rules = await self._rules.list_enabled_for_event(tenant_id, event_type)
        if not rules:
            return []

        # ENG-460: the messenger is an authorized PHI surface (only staff with
        # PHI access read the Mattermost team), so cards carry real name /
        # phone / provider. ``phi_mode="full"`` substitutes any context var
        # verbatim; the historical ``deidentified`` mode (allowlist only) is
        # kept behind the flag for a clean rollback.
        phi_mode = "full" if settings.messenger_phi_full else "deidentified"

        # Engine-provided render variables layered over the caller context.
        # The caller context wins for overlapping keys EXCEPT the three the
        # engine owns, which are authoritative.
        render_context: dict[str, object] = dict(context)
        render_context["event_type"] = event_type
        if person_uid is not None:
            render_context["person_uid"] = str(person_uid)
            render_context["deep_link"] = build_deep_link(person_uid)

        # Determine which rules actually match BEFORE the idempotency claim, so
        # a no-rule / no-condition-match path NEVER burns the dedupe key — that
        # would permanently suppress a future real notification once a matching
        # rule exists. ``rule.conditions`` is JSONB typed ``list[object]``.
        matching = [
            rule
            for rule in rules
            if conditions.evaluate(
                cast("list[dict[str, Any]]", list(rule.conditions or [])), context
            )
        ]
        if not matching:
            return []

        # Guard 3 — idempotency claim, taken ONLY now that ≥1 row will truly be
        # enqueued. Lose the claim ⇒ already emitted. Claim + enqueue share this
        # session; the caller boundary commits them atomically.
        if dedupe_key is not None:
            claimed = await self._emitted.claim(tenant_id, event_type, dedupe_key)
            if not claimed:
                log.info(
                    "notification.event.skipped_duplicate",
                    event_type=event_type,
                    person_uid=str(person_uid) if person_uid else None,
                )
                return []

        # ENG-458: per-location routing. Resolve the target team ONCE per emit
        # (the event concerns one entity, hence one location). The rule stores a
        # bare, environment-independent channel name (e.g. ``scheduls``); we
        # qualify it to ``team/scheduls`` so the dispatcher posts to the right
        # team's channel. No team → bare name → adapter's default team.
        team = await self._resolve_team(tenant_id, context)

        enqueued: list[NotificationOutbox] = []
        for rule in matching:
            payload = render.render(
                dict(rule.template or {}), render_context, phi_mode=phi_mode
            )
            provider_kind: NotificationProviderKind = rule.provider_kind  # type: ignore[assignment]
            row = await self._notifications.enqueue(
                tenant_id,
                NotificationOutboxIn(
                    event_type=event_type,
                    channel=_qualify_channel(rule.channel, team),
                    payload=payload,
                    provider_kind=provider_kind,
                    rule_id=rule.id,
                ),
                principal=principal,
            )
            enqueued.append(row)

        log.info(
            "notification.event.emitted",
            event_type=event_type,
            rules_considered=len(rules),
            rows_enqueued=len(enqueued),
            person_uid=str(person_uid) if person_uid else None,
        )
        return enqueued

    async def _resolve_team(
        self, tenant_id: TenantId, context: dict[str, object]
    ) -> str | None:
        """Resolve the Mattermost team for this event, or ``None`` (default).

        Precedence: an explicit ``mattermost_team`` in the context wins;
        otherwise a ``location_id`` is mapped through
        ``tenant.location.external_ref['mattermost_team']``. Any miss (no keys,
        unknown location, no mapping, lookup error) returns ``None`` so the
        channel stays bare and the adapter falls back to its default team —
        never raises out of the emit path.
        """
        explicit = context.get(CTX_TEAM)
        if isinstance(explicit, str) and explicit:
            return explicit

        location_raw = context.get(CTX_LOCATION_ID)
        if not isinstance(location_raw, str) or not location_raw:
            return None
        try:
            location = await self._locations.get_location(
                tenant_id, UUID(location_raw)
            )
        except (PlatformError, ValueError):
            # Unknown/foreign location or malformed id — fall back to default.
            return None
        team = (location.external_ref or {}).get(LOCATION_TEAM_KEY)
        return team if isinstance(team, str) and team else None


def _qualify_channel(channel: str, team: str | None) -> str:
    """Prefix a bare channel name with ``team/`` for team-scoped routing.

    Leaves the value untouched when there is no team, when it is already
    team-qualified (contains ``/``), or when it is already a resolved 26-char
    channel id — so legacy id-valued rules keep working unchanged.

    NOTE: the ``team/channel`` shape is Mattermost-specific. Today Mattermost is
    the only chat provider (``resolver.py`` builds no other adapter); if another
    provider is ever wired, this qualification must move behind a per-provider
    addressing strategy rather than baking a Mattermost reference into the
    provider-agnostic outbox ``channel`` column.
    """
    if not team:
        return channel
    if "/" in channel or _MM_ID_RE.match(channel):
        return channel
    return f"{team}/{channel}"


__all__ = ["NotificationEventService", "build_deep_link"]
