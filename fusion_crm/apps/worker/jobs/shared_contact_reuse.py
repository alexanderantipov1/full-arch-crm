"""Shared-contact-reuse Messenger alert scan (ENG-555, Layer D).

Whenever an incoming record reuses an existing **shared contact** (a phone or
email already held by another person), nudge staff to capture a distinct contact
per person. The reuse signal already exists: the matcher writes an OPEN
``identity.match_candidate`` with a Tier-2 ambiguous rule
(``phone_only_ambiguous`` / ``email_only_ambiguous``) on that path
(``IdentityService.resolve_or_create_from_hint`` → ``_apply_open_ambiguous``).

``identity`` MUST NOT import ``integrations`` (packages import matrix), so the
matcher cannot emit directly. This worker job (ENG-498 scan-job pattern, mirroring
``consultation_reminders.py``) reads the signal via ``IdentityService`` and emits
the notification via the ``integrations`` notification runtime, routed per-location
to the leads channel (ENG-458).

Safety:

* **No retro-blast.** The scan only reads candidates created at/after
  ``Settings.notifications_cutoff_at``; if that is unset the job is a NO-OP
  (we refuse to scan the pre-existing open backlog without an explicit cutoff).
  ``emit`` independently re-checks the same cutoff via ``source_created_at``.
* **At-most-once.** ``emit(dedupe_key = candidate id)`` claims the durable
  ``integrations.notification_emitted`` ledger, so re-runs / overlapping ticks
  / restarts never double-post.
* **Dark by default.** ``emit`` short-circuits unless ``NOTIFICATIONS_ENABLED``
  and a matching rule is seeded — so the whole job is a safe no-op until the
  operator configures routing.
* **No PHI.** The emit context carries only opaque person uids, deep links, and
  the contact KIND ("phone"/"email", never the value). The clinic name is NOT
  rendered — the alert lands in the location's own leads channel, so the channel
  is the location context. Logs carry counts + opaque uids only (never raw
  exception text).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.identity.schemas import MatchCandidateOut
from packages.identity.service import IdentityService
from packages.integrations.chat.event_service import (
    NotificationEventService,
    build_deep_link,
)
from packages.integrations.chat.events import EVENT_SHARED_CONTACT_REUSE
from packages.ops.service import OpsService
from packages.tenant.service import TenantService

log = get_logger("worker.shared_contact_reuse")

# match_rule → the contact KIND surfaced on the card (the type, never the value).
_RULE_TO_KIND = {
    "phone_only_ambiguous": "phone",
    "email_only_ambiguous": "email",
}

# Keyset page size for the per-tenant reuse-candidate scan.
_PAGE_SIZE = 500


def _reuse_principal(tenant_id: TenantId) -> Principal:
    """System principal for the scan tick (mirrors the ingest scheduler)."""
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:shared_contact_reuse_scan"},
    )


async def _resolve_location(
    ops: OpsService,
    tenant_id: TenantId,
    *person_uids: UUID,
) -> str | None:
    """Best-effort ``location_id`` for the candidate (ENG-458 team routing only).

    Tries each person in order (incoming first, then existing), picking that
    person's most-recent ``person_location_profile``. Returns the location id as
    a string used solely to route the alert to that location's leads-channel
    team. A miss yields ``None`` so the alert still routes to the default team —
    never raises out of the scan.

    The clinic NAME is intentionally NOT surfaced: the alert already lands in
    the location's own leads channel, so the channel IS the location context,
    and the payload stays on the strict opaque-uid/deep-link/contact-kind
    allowlist (ENG-555 Codex review — no rendered location label).
    """
    for person_uid in person_uids:
        try:
            profiles = await ops.list_person_location_profiles_for_person(
                tenant_id, person_uid
            )
        except PlatformError:
            continue
        if not profiles:
            continue
        latest = max(
            profiles,
            key=lambda p: p.last_evidence_at or p.created_at,
        )
        return str(latest.location_id)
    return None


async def _emit_for_tenant(
    session: Any, tenant_id: TenantId, after: datetime
) -> int:
    """Emit shared-contact-reuse alerts for one tenant's new reuse signals."""
    identity = IdentityService(session)
    ops = OpsService(session)
    events = NotificationEventService(session)
    principal = _reuse_principal(tenant_id)

    emitted = 0
    cursor_created_at: datetime | None = None
    cursor_id: UUID | None = None
    while True:
        # Keyset-paginate so EVERY post-cutoff open candidate is visited, not
        # just the first page (the bare limit would starve rows beyond page 1
        # once the head rows are emitted — ENG-555 Codex review). ``emit``'s
        # ledger dedupe makes re-visiting an already-alerted candidate a no-op.
        page: list[MatchCandidateOut] = (
            await identity.list_open_reuse_candidates_created_after(
                tenant_id,
                after,
                after_created_at=cursor_created_at,
                after_id=cursor_id,
                limit=_PAGE_SIZE,
            )
        )
        if not page:
            break
        for cand in page:
            # ``source_person_uid`` is the incoming person on the reuse path;
            # fall back to the existing (candidate) person if it is unset.
            incoming = cand.source_person_uid or cand.candidate_person_uid
            existing = cand.candidate_person_uid
            contact_kind = _RULE_TO_KIND.get(cand.match_rule, "contact")

            location_id = await _resolve_location(ops, tenant_id, incoming, existing)

            context: dict[str, object] = {
                "contact_kind": contact_kind,
                "other_person_uid": str(existing),
                "other_deep_link": build_deep_link(existing),
                # ENG-458: route per-location to the leads channel's team.
                "location_id": location_id,
            }
            rows = await events.emit(
                tenant_id,
                EVENT_SHARED_CONTACT_REUSE,
                context,
                principal=principal,
                person_uid=incoming,
                dedupe_key=str(cand.id),
                source_created_at=cand.created_at,
            )
            # Count only candidates that actually enqueued ≥1 outbox row.
            # emit() returns [] when dark (NOTIFICATIONS_ENABLED off), no rule
            # matched, before the cutoff, or the dedupe claim lost — so the
            # summary never overstates work in those no-op cases (ENG-555 review).
            if rows:
                emitted += 1
        cursor_created_at, cursor_id = page[-1].created_at, page[-1].id
        if len(page) < _PAGE_SIZE:
            break
    return emitted


async def scan_shared_contact_reuse(ctx: dict[str, Any]) -> dict[str, int]:
    """Cron entrypoint: alert on every new shared-contact-reuse signal.

    Returns a summary ``{"tenants", "emitted", "failed"}``. When
    ``NOTIFICATIONS_CUTOFF_AT`` is unset the scan is a no-op (returns
    ``{"tenants": 0, "emitted": 0, "failed": 0}``) — see module docstring.
    """
    _ = ctx
    settings = get_settings()
    summary = {"tenants": 0, "emitted": 0, "failed": 0}

    cutoff = settings.notifications_cutoff_at
    if cutoff is None:
        # No-retro guard: without an explicit cutoff we will not scan the
        # pre-existing open backlog. Safe no-op; operator sets the env var.
        log.info("shared_contact_reuse.skipped_no_cutoff")
        return summary
    after = cutoff if cutoff.tzinfo is not None else cutoff.replace(tzinfo=UTC)

    async with async_session() as session:
        tenants = await TenantService(session).list_tenants()

    for tenant in tenants:
        tenant_id = TenantId(tenant.id)
        summary["tenants"] += 1
        try:
            async with async_session() as session:
                emitted = await _emit_for_tenant(session, tenant_id, after)
                # emit() enqueues outbox rows + claims the ledger on THIS
                # session; commit so the dispatcher can pick them up.
                await session.commit()
            summary["emitted"] += emitted
        except Exception as exc:  # noqa: BLE001 — one tenant must not abort the rest
            summary["failed"] += 1
            # Log the exception CLASS only — arbitrary exception text could echo
            # a value that does not belong in a PHI-free log (ENG-555 review).
            log.error(
                "shared_contact_reuse.tenant_failed",
                tenant_id=str(tenant_id),
                error_type=type(exc).__name__,
            )

    if summary["emitted"]:
        log.info("shared_contact_reuse.scan", **summary)
    return summary
