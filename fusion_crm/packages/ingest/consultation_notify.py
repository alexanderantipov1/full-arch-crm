"""Messenger emit at the consultation ingest boundary (ENG-457, Block C).

This is the seam that announces a *genuinely-new* consultation to the
``#scheduls`` chat channel exactly once, WITHOUT letting ``packages.ingest``
import ``packages.integrations`` (forbidden by the package import matrix in
``packages/CLAUDE.md`` — ``ingest → integrations`` is ✗).

The actual fan-out lives in
``packages.integrations.chat.event_service.NotificationEventService.emit``.
Here we declare only the minimal :class:`ConsultationNotifier` Protocol that
``emit`` satisfies (typed with stdlib / ``core`` types only) and a thin helper
that builds the de-identified context and applies the created-only rule. The
concrete ``NotificationEventService`` is constructed at the worker job boundary
(``apps/worker/jobs/ingest_scheduled.py``), which legitimately depends on both
``ingest`` and ``integrations``, and injected here as a ``ConsultationNotifier``.

Why this stays a no-op on the wrong paths:

* **Backfill suppression by construction** — the bulk paths
  (``import_all_since`` / ``pull_all_since``) never receive a notifier, so this
  helper is never invoked on a backfill. The recent / scheduled pull paths are
  the only callers that pass one.
* **Created-only** — we emit ONLY when ``upsert.was_created`` is True. A
  re-ingest that updates (or no-ops) an existing consultation does not announce.
* **Exactly once** — ``dedupe_key`` is the consultation id, so even if the
  created path ran twice the durable ledger inside ``emit`` claims the key and
  the second attempt is a no-op. ``source_created_at`` (provider-created instant,
  UTC) drives the historical cutoff guard.

ENG-460: the messenger is an AUTHORIZED PHI surface, so the context now also
carries the patient's real ``name`` (resolved by the caller at the boundary
via ``IdentityService`` and passed in as ``person_name``) so the ``#scheduls``
card is useful to staff. The provider / status / consultation_kind /
scheduled_at fields stay as before. The renderer runs in ``phi_mode="full"``
(``Settings.messenger_phi_full``) so these substitute verbatim; flipping the
flag off falls back to the de-identified allowlist (name renders blank).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from packages.core.security import Principal
from packages.core.types import TenantId
from packages.interaction.schemas import SourceProvider
from packages.ops.schemas import ConsultationUpsertResult

# Canonical event code. Kept as a local literal (not imported from
# ``integrations``) so this module honours the import matrix; the seed +
# emit-site share the string via ``packages.integrations.chat.events``.
CONSULTATION_SCHEDULED_EVENT = "consultation.scheduled"


class ConsultationNotifier(Protocol):
    """The minimal emit surface this boundary needs.

    Structurally satisfied by
    ``packages.integrations.chat.event_service.NotificationEventService``. Typed
    here with only stdlib / ``core`` types so ``packages.ingest`` never imports
    ``packages.integrations``.
    """

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
    ) -> object: ...


async def emit_consultation_scheduled_notification(
    notifier: ConsultationNotifier | None,
    tenant_id: TenantId,
    upsert: ConsultationUpsertResult,
    *,
    source_provider: SourceProvider,
    principal: Principal,
    person_name: str | None = None,
    person_phone: str | None = None,
    doctor_name: str | None = None,
    clinic_name: str | None = None,
    owner_name: str | None = None,
) -> None:
    """Announce a newly-created consultation to the messenger, exactly once.

    No-op when:

    * ``notifier`` is ``None`` (backfill / any path that did not opt in), or
    * ``upsert.was_created`` is ``False`` (re-ingest / update / no-op upsert).

    On a genuinely-new consultation, emits ``consultation.scheduled`` with the
    consultation id as the dedupe key and the provider-created instant as the
    cutoff signal. The emit itself is guarded by ``notifications_enabled`` (OFF
    by default), the historical cutoff, and the durable dedupe ledger.

    ENG-460: ``person_name`` (resolved by the caller via ``IdentityService``)
    is carried into the context so the card shows the real patient.

    ENG-465: the card is enriched so ``#scheduls`` is actually useful to staff.
    The caller resolves — all at the worker boundary, where the session may
    read ``identity`` / ``actor`` / ``ops`` / ``tenant`` — and passes in:

    * ``person_phone`` — the patient's primary phone (``IdentityService``);
    * ``doctor_name`` — the clinician resolved from the appointment's
      ``providerIds`` (``ActorService.find_by_identifier``), NOT the source
      system label;
    * ``clinic_name`` — the location name (``LocationService``);
    * ``owner_name`` — the TC / funnel owner (covering Opportunity owner,
      falling back to the Lead owner; ``OpsService``).

    These (plus the patient name) are the only PHI / name fields and render
    verbatim under ``phi_mode="full"``. Each is optional: when ``None`` the
    placeholder renders ``[redacted]`` and the renderer prunes the field so the
    card carries no dangling label. ``scheduled_when`` is a human-readable
    rendering of the scheduled instant.

    ENG-465b/c declutter: the Kind, Duration, and Source fields were dropped, and
    the Confirmation field was removed entirely — this notification fires at
    booking time, when the patient has almost never confirmed yet, so the signal
    was premature/misleading. Confirmation belongs to a separate future
    status-change notification, not the "new consultation" card.
    """
    if notifier is None or not upsert.was_created:
        return

    consultation = upsert.consultation
    context: dict[str, object] = {
        "provider": source_provider,
        "status": consultation.status.value,
        "scheduled_at": consultation.scheduled_at.isoformat(),
        "scheduled_when": _format_scheduled_when(consultation.scheduled_at),
        "name": person_name,
        "phone": person_phone,
        "doctor": doctor_name,
        "clinic": clinic_name,
        "owner": owner_name,
        # ENG-458: drives per-location routing — the engine maps this to the
        # consultation's Mattermost team (its clinic's ``#scheduls``). Not a
        # template placeholder; ``None`` when the consultation has no location.
        "location_id": (
            str(consultation.location_id)
            if consultation.location_id is not None
            else None
        ),
    }
    await notifier.emit(
        tenant_id,
        CONSULTATION_SCHEDULED_EVENT,
        context,
        principal=principal,
        person_uid=consultation.person_uid,
        dedupe_key=str(consultation.id),
        source_created_at=_as_utc(consultation.provider_created_at),
    )


def _format_scheduled_when(value: datetime) -> str:
    """Render a scheduled instant as a clear, human-readable string.

    Example: ``Jun 20, 2026 3:00 PM UTC``. The timezone abbreviation is
    always shown so staff are never guessing the offset; a naive value is
    treated as UTC (mirrors ``_as_utc``). ``%-I`` drops the leading zero on
    the hour for a natural reading.
    """
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    tz_label = aware.tzname() or "UTC"
    return aware.strftime("%b %-d, %Y %-I:%M %p ") + tz_label


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a provider-created instant to timezone-aware UTC.

    ``provider_created_at`` may be naive (legacy rows) or carry a non-UTC
    offset; the cutoff comparison in ``emit`` needs an aware UTC value. ``None``
    passes through (no cutoff signal → only enablement + dedupe gate the emit).
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "CONSULTATION_SCHEDULED_EVENT",
    "ConsultationNotifier",
    "emit_consultation_scheduled_notification",
]
