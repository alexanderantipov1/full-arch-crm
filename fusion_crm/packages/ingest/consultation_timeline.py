"""Timeline event emission for consultation ingest flows."""

from __future__ import annotations

from uuid import UUID

from packages.core.types import TenantId
from packages.interaction.schemas import (
    EventIn,
    EventKind,
    ResponsibilityAssignmentIn,
    SourceKind,
    SourceProvider,
)
from packages.interaction.service import InteractionService, summary_for_event
from packages.ops.models import ConsultationStatus
from packages.ops.schemas import ConsultationUpsertResult

_STATUS_EVENT_KIND: dict[ConsultationStatus, EventKind] = {
    ConsultationStatus.CANCELLED: "consultation_cancelled",
    ConsultationStatus.COMPLETED: "consultation_completed",
    ConsultationStatus.NO_SHOW: "consultation_no_show",
    ConsultationStatus.RESCHEDULED: "consultation_rescheduled",
}


async def emit_consultation_timeline_event(
    interaction: InteractionService,
    tenant_id: TenantId,
    upsert: ConsultationUpsertResult,
    *,
    source_provider: SourceProvider,
    source_kind: SourceKind,
    source_external_id: str,
    source_event_id: UUID,
    responsibilities: list[ResponsibilityAssignmentIn] | None = None,
) -> None:
    """Append one workflow-ready timeline event for a consultation lifecycle change.

    The event payload intentionally stays empty. Provider payloads, notes, and
    descriptions remain in ``ingest.raw_event`` only.

    ``responsibilities`` (ENG-416) are written atomically with the event row
    when supplied — typically a TC actor under ``operational`` and a doctor
    under ``clinical``. Empty list means the caller could not resolve any
    responsible actor (e.g. walk-in with no doctor); the event still lands.
    """
    kind = _consultation_event_kind(upsert)
    if kind is None:
        return

    consultation = upsert.consultation
    await interaction.create_event(
        tenant_id,
        EventIn(
            person_uid=consultation.person_uid,
            kind=kind,
            source_provider=source_provider,
            source_event_id=source_event_id,
            data_class="operational",
            source_kind=source_kind,
            source_external_id=source_external_id,
            projection_ref_type="ops_consultation",
            projection_ref_id=consultation.id,
            review_status="auto",
            occurred_at=consultation.scheduled_at,
            summary=summary_for_event(
                kind=kind,
                source_provider=source_provider,
                source_id=source_external_id,
            ),
            payload={},
            responsibilities=responsibilities or [],
        ),
    )


def _consultation_event_kind(upsert: ConsultationUpsertResult) -> EventKind | None:
    if not upsert.was_changed:
        return None

    status = upsert.consultation.status
    if status == ConsultationStatus.SCHEDULED:
        if upsert.was_created:
            return "consultation_scheduled"
        if upsert.was_status_change or upsert.was_scheduled_at_change:
            return "consultation_rescheduled"
        return None
    return _STATUS_EVENT_KIND.get(status)
