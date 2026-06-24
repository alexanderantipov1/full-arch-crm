"""Canonical workspace event-type taxonomy (ENG-437, Block D).

One place that names the events the notification rule engine understands.
A ``NotificationRule.event_type`` and a ``NotificationEventService.emit``
call site MUST use one of these constants — never a free-form string —
so seeds, rules, and emit call sites cannot silently drift apart.

This module resolves ENG-436 open decision #5 (the default event
taxonomy) with a documented, minimal set:

* ``lead.created`` — a new ops Lead row was created (flagship, wired in
  Block D).
* ``consultation.scheduled`` — a genuinely-new ops Consultation row was
  created at the SF Event / CareStack Appointment ingest boundary
  (ENG-457, Block C; routed to ``#scheduls``).
* ``opportunity.stage_changed`` — an ops Opportunity moved stage
  (deferred wiring → Block D2).
* ``ownership.changed`` — a Lead/Opportunity owner changed
  (deferred wiring → Block D2).
* ``ingest.sync_failed`` — an external sync run ended in ``failed``
  (deferred wiring → Block D2).
* ``identity.shared_contact_reuse`` — an incoming record reused an existing
  shared contact (phone/email already held by another person), surfaced as a
  new OPEN ``identity.match_candidate`` (ENG-555, Layer D). Emitted by the
  ``shared_contact_reuse`` scan job to nudge staff to capture a distinct
  contact per person.

The set is intentionally small. Adding an event = add a constant here,
add a default rule in ``seeds.py``, and wire an ``emit`` call at the
service/boundary that owns the state change.
"""

from __future__ import annotations

EVENT_LEAD_CREATED = "lead.created"
EVENT_CONSULTATION_SCHEDULED = "consultation.scheduled"
EVENT_CONSULTATION_REMINDER = "consultation.reminder_t15"
EVENT_OPPORTUNITY_STAGE_CHANGED = "opportunity.stage_changed"
EVENT_OWNERSHIP_CHANGED = "ownership.changed"
EVENT_INGEST_SYNC_FAILED = "ingest.sync_failed"
EVENT_SHARED_CONTACT_REUSE = "identity.shared_contact_reuse"

# Every event type the engine knows about. Used by seeds + tests as the
# canonical roster.
ALL_EVENT_TYPES: tuple[str, ...] = (
    EVENT_LEAD_CREATED,
    EVENT_CONSULTATION_SCHEDULED,
    EVENT_CONSULTATION_REMINDER,
    EVENT_OPPORTUNITY_STAGE_CHANGED,
    EVENT_OWNERSHIP_CHANGED,
    EVENT_INGEST_SYNC_FAILED,
    EVENT_SHARED_CONTACT_REUSE,
)


__all__ = [
    "ALL_EVENT_TYPES",
    "EVENT_CONSULTATION_REMINDER",
    "EVENT_CONSULTATION_SCHEDULED",
    "EVENT_INGEST_SYNC_FAILED",
    "EVENT_LEAD_CREATED",
    "EVENT_OPPORTUNITY_STAGE_CHANGED",
    "EVENT_OWNERSHIP_CHANGED",
    "EVENT_SHARED_CONTACT_REUSE",
]
