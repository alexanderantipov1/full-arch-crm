"""T-15m confirmed-consultation reminder scan (ENG-486).

A cron job that, every minute, finds CONFIRMED consultations starting within the
next 15 minutes and posts a reminder (naming the assigned doctor) to the
``#consult-reminders`` Mattermost channel — exactly once per consultation.

Design:

* **Confirmed** = ``ops.consultation.source_status == 'Confirmed'`` — the
  verbatim CareStack status preserved by ENG-487 (the bucketed ``status``
  collapses "Confirmed" into SCHEDULED).
* **Due window** = ``(now, now + 15m]``. A consultation fires on the first tick
  where it enters the window; the renderer / dispatcher do the rest.
* **At-most-once** = the emit carries ``dedupe_key = consultation id``, so the
  durable ``integrations.notification_emitted`` ledger inside ``emit`` claims
  the key once and every later tick is a no-op — robust across worker restarts
  and overlapping ticks. (Trade-off: a reschedule does not re-remind; acceptable
  for v1, noted as a follow-up.)
* **Doctor** is read straight off ``provider_clinician_name`` (populated by
  ENG-487). The patient name is resolved via ``IdentityService`` at this worker
  boundary (the messenger is an authorized PHI surface).

The whole job is a safe no-op until an operator flips ``NOTIFICATIONS_ENABLED``
on — ``NotificationEventService.emit`` short-circuits when notifications are
disabled, and again when no rule matches the event.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from packages.actor.service import ActorService
from packages.core.logging import get_logger
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.db.session import async_session
from packages.identity.service import IdentityService, PersonUID
from packages.integrations.chat.event_service import NotificationEventService
from packages.integrations.chat.events import EVENT_CONSULTATION_REMINDER
from packages.ops.schemas import ConsultationOut
from packages.ops.service import OpsService
from packages.tenant.service import TenantService

log = get_logger("worker.consultation_reminders")

_REMINDER_HORIZON = timedelta(minutes=15)


def _reminder_principal(tenant_id: TenantId) -> Principal:
    """System principal for the scan tick (mirrors the ingest scheduler)."""
    return Principal(
        id=None,
        email=None,
        tenant_id=tenant_id,
        roles=frozenset({Role.SYSTEM}),
        context={"actor": "system:consultation_reminder_scan"},
    )


def _format_scheduled_when(value: datetime) -> str:
    """Human-readable start instant, e.g. ``Jun 17, 2026 9:00 AM UTC``."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.strftime("%b %-d, %Y %-I:%M %p ") + (aware.tzname() or "UTC")


async def _emit_for_tenant(
    session: Any, tenant_id: TenantId, now: datetime
) -> int:
    """Emit reminders for one tenant's due confirmed consultations."""
    ops = OpsService(session)
    identity = IdentityService(session)
    events = NotificationEventService(session)
    actors = ActorService(session)
    principal = _reminder_principal(tenant_id)

    due: list[ConsultationOut] = await ops.list_confirmed_due_for_reminder(
        tenant_id, after=now, until=now + _REMINDER_HORIZON
    )
    emitted = 0
    for consult in due:
        # Patient name is a nice-to-have; a missing person must never crash the
        # tick (the card renders the name blank / pruned when absent).
        name: str | None = None
        try:
            person = await identity.get_person(
                tenant_id, PersonUID(consult.person_uid)
            )
            name = (
                person.display_name
                or person.given_name
                or person.family_name
            )
        except Exception:  # noqa: BLE001 — name is optional; never fatal
            log.info(
                "consultation_reminders.person_unresolved",
                tenant_id=str(tenant_id),
                person_uid=str(consult.person_uid),
            )

        # ENG-543: @mention the assigned doctor so they get pinged. Map the
        # consultation's CareStack provider id -> the doctor actor's
        # ``mattermost_username`` identifier. Renders blank (pruned) when the
        # provider is unmapped — the card still shows the plain name. A miss
        # never blocks the reminder.
        doctor_mention = ""
        if consult.provider_carestack_id:
            username = await actors.resolve_linked_identifier(
                tenant_id,
                "carestack_provider_id",
                consult.provider_carestack_id,
                "mattermost_username",
            )
            if username:
                doctor_mention = f"@{username}"

        context: dict[str, object] = {
            "name": name,
            "doctor": consult.provider_clinician_name,
            "doctor_mention": doctor_mention,
            "scheduled_when": _format_scheduled_when(consult.scheduled_at),
            "scheduled_at": consult.scheduled_at.isoformat(),
            # ENG-458: route the reminder to the consultation's clinic team.
            "location_id": (
                str(consult.location_id)
                if consult.location_id is not None
                else None
            ),
        }
        await events.emit(
            tenant_id,
            EVENT_CONSULTATION_REMINDER,
            context,
            principal=principal,
            person_uid=consult.person_uid,
            dedupe_key=str(consult.id),
        )
        emitted += 1
    return emitted


async def scan_consultation_reminders(ctx: dict[str, Any]) -> dict[str, int]:
    """Cron entrypoint: scan every tenant for due confirmed consultations."""
    _ = ctx
    now = datetime.now(UTC)
    summary = {"tenants": 0, "emitted": 0, "failed": 0}

    async with async_session() as session:
        tenants = await TenantService(session).list_tenants()

    for tenant in tenants:
        tenant_id = TenantId(tenant.id)
        summary["tenants"] += 1
        try:
            async with async_session() as session:
                emitted = await _emit_for_tenant(session, tenant_id, now)
                # emit() enqueues outbox rows + claims ledger on THIS session;
                # commit so the dispatcher can pick them up.
                await session.commit()
            summary["emitted"] += emitted
        except Exception as exc:  # noqa: BLE001 — one tenant must not abort the rest
            summary["failed"] += 1
            log.error(
                "consultation_reminders.tenant_failed",
                tenant_id=str(tenant_id),
                error=str(exc)[:200],
            )

    if summary["emitted"]:
        log.info("consultation_reminders.scan", **summary)
    return summary
