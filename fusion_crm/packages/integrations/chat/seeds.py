"""Idempotent default notification-rule seeds (ENG-436 C / ENG-437 D).

Block C seeded a single ``lead.created`` rule. Block D extends this to a
default rule per canonical event type
(:mod:`packages.integrations.chat.events`) plus one field-control rule
that routes phone-less leads to a dedicated channel.

ENG-460: the lead + consultation rules now use RICH Mattermost attachment
cards that carry the real person (``{{name}}`` / ``{{phone}}``) — the
messenger is an authorized PHI surface and the renderer runs in
``phi_mode="full"`` (``Settings.messenger_phi_full``). The remaining rules
(opportunity / ownership / ingest-alerts) stay de-identified one-liners
(see :mod:`packages.integrations.chat.render`).

Idempotent on ``(tenant_id, event_type, channel)`` — a second run finds
each existing row and leaves the rule set unchanged. NOT run in a
migration; invoked from bootstrap / dev tooling. The session is owned by
the caller (no commit here).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId

from ..models import NotificationRule
from ..notification_repository import NotificationRuleRepository
from .events import (
    EVENT_CONSULTATION_REMINDER,
    EVENT_CONSULTATION_SCHEDULED,
    EVENT_INGEST_SYNC_FAILED,
    EVENT_LEAD_CREATED,
    EVENT_OPPORTUNITY_STAGE_CHANGED,
    EVENT_OWNERSHIP_CHANGED,
    EVENT_SHARED_CONTACT_REUSE,
)

# --- Channels ---
DEFAULT_LEAD_CREATED_CHANNEL = "leads"
LEADS_MISSING_INFO_CHANNEL = "leads-missing-info"
OPPORTUNITY_CHANNEL = "opportunities"
OWNERSHIP_CHANNEL = "ownership"
INGEST_ALERTS_CHANNEL = "ingest-alerts"

# ENG-458: rules store the bare, environment-independent channel NAME. The
# dispatcher resolves it to a concrete channel id at post time
# (``MattermostAdapter.resolve_channel_id``), and the emit engine prefixes it
# with the consultation's team (``team/scheduls``) for per-location routing —
# so a single rule serves every clinic and NO hardcoded, per-environment
# channel id lives in the codebase anymore.
SCHEDULS_CHANNEL = "scheduls"

# ENG-486 / ENG-458: T-15m reminder for a CONFIRMED consultation posts to
# #consult-reminders, routed per-location the same way.
CONSULT_REMINDERS_CHANNEL = "consult-reminders"

# ENG-555 (Layer D): shared-contact-reuse alerts route to the same per-location
# leads channel, "tagged" as a lead-hygiene nudge (Mattermost has no first-class
# tags — the channel + card title carry the meaning).
SHARED_CONTACT_REUSE_CHANNEL = DEFAULT_LEAD_CREATED_CHANNEL

# --- Rich card templates (ENG-460) ---
#
# The messenger is an AUTHORIZED PHI surface, so these cards carry the real
# person ({{name}} / {{phone}}) — substituted verbatim by the renderer in
# ``phi_mode="full"`` (``Settings.messenger_phi_full``). They use Mattermost
# message attachments (carried under the template's ``blocks`` list, which the
# dispatch passes through to ``ChatMessage.blocks`` → ``props.attachments``).
# ``text`` is a plain-text fallback for clients that don't render attachments.
# When the PHI flag is off the renderer falls back to the allowlist and
# {{name}}/{{phone}} render blank — the card degrades gracefully.

# Mattermost attachment colors (sidebar bar).
_LEAD_CARD_COLOR = "#36a64f"  # green — a fresh inbound lead
_CONSULTATION_CARD_COLOR = "#2d8cff"  # blue — a scheduled consultation

LEAD_CREATED_RICH_TEMPLATE: dict[str, object] = {
    "text": "🆕 New lead: {{name}} — {{phone}} ({{source}}) — {{deep_link}}",
    "blocks": [
        {
            "color": _LEAD_CARD_COLOR,
            "fallback": "New lead {{name}} ({{source}}) — {{deep_link}}",
            "title": "🆕 New lead",
            "title_link": "{{deep_link}}",
            "text": "**{{name}}**",
            "fields": [
                {"title": "Phone", "value": "{{phone}}", "short": True},
                {"title": "Source", "value": "{{source}}", "short": True},
                {
                    "title": "CRM",
                    "value": "[Open in CRM]({{deep_link}})",
                    "short": False,
                },
            ],
        }
    ],
}

LEAD_MISSING_INFO_RICH_TEMPLATE: dict[str, object] = {
    "text": "🆕 New lead (no phone): {{name}} ({{source}}) — {{deep_link}}",
    "blocks": [
        {
            "color": _LEAD_CARD_COLOR,
            "fallback": "New lead {{name}} is missing a phone — {{deep_link}}",
            "title": "🆕 New lead — missing phone",
            "title_link": "{{deep_link}}",
            "text": "**{{name}}**",
            "fields": [
                {"title": "Source", "value": "{{source}}", "short": True},
                {
                    "title": "CRM",
                    "value": "[Open in CRM]({{deep_link}})",
                    "short": False,
                },
            ],
        }
    ],
}

CONSULTATION_SCHEDULED_RICH_TEMPLATE: dict[str, object] = {
    # ENG-465 / 465b / 465c: the old card showed "Provider: carestack" (the
    # SOURCE SYSTEM, not the doctor) and was cluttered with meaningless Kind /
    # Duration / Source fields. The card now surfaces the real DOCTOR, CLINIC,
    # TC OWNER, patient PHONE, and a readable WHEN. Optional values render
    # [redacted] when absent and are pruned by the renderer so no dangling label
    # remains.
    #
    # ENG-465c: the Confirmation field was REMOVED. This notification fires at
    # booking/creation time, but the patient confirms (via SMS) just before the
    # visit — so at creation it is almost always not-yet-confirmed and was
    # premature/misleading. Confirmation belongs to a separate future
    # status-change notification, not the "new consultation" card.
    #
    # Plain-text fallback (clients that don't render attachments). Kept to
    # ALWAYS-present fields only — patient / when / link — so a missing doctor /
    # clinic never leaves a "[redacted]" in the fallback line.
    "text": (
        "📅 Consultation scheduled: {{name}} — {{scheduled_when}} — {{deep_link}}"
    ),
    "blocks": [
        {
            "color": _CONSULTATION_CARD_COLOR,
            "fallback": "Consultation scheduled for {{name}} — {{deep_link}}",
            "title": "📅 Consultation scheduled",
            "title_link": "{{deep_link}}",
            "text": "**{{name}}**",
            "fields": [
                {"title": "Phone", "value": "{{phone}}", "short": True},
                {"title": "Doctor", "value": "{{doctor}}", "short": True},
                {"title": "Clinic", "value": "{{clinic}}", "short": True},
                {"title": "When", "value": "{{scheduled_when}}", "short": True},
                {"title": "Owner (TC)", "value": "{{owner}}", "short": True},
                {
                    "title": "CRM",
                    "value": "[Open in CRM]({{deep_link}})",
                    "short": False,
                },
            ],
        }
    ],
}

_REMINDER_CARD_COLOR = "#e8912d"  # amber — an imminent visit

CONSULTATION_REMINDER_RICH_TEMPLATE: dict[str, object] = {
    # ENG-486: fires ~15 min before a CONFIRMED consultation. Headline is the
    # assigned doctor (resolved into ops.consultation.provider_clinician_name by
    # ENG-487) plus the patient and a readable start time. Optional values render
    # [redacted] and are pruned when absent.
    #
    # ENG-543: ``{{doctor_mention}}`` is the doctor's Mattermost ``@username``
    # (mapped via the provider actor's ``mattermost_username`` identifier). It
    # MUST live in ``text`` (the post message) — Mattermost only notifies on
    # @mentions in the message body, not inside attachment fields. Renders blank
    # when the provider is unmapped, so the line degrades to just the name.
    "text": (
        "⏰ Consultation in 15 min: {{name}} with {{doctor}} {{doctor_mention}} "
        "— {{scheduled_when}} — {{deep_link}}"
    ),
    "blocks": [
        {
            "color": _REMINDER_CARD_COLOR,
            "fallback": "Consultation in 15 min: {{name}} — {{deep_link}}",
            "title": "⏰ Consultation starting soon (15 min)",
            "title_link": "{{deep_link}}",
            "text": "**{{name}}**",
            "fields": [
                {"title": "Doctor", "value": "{{doctor}}", "short": True},
                {"title": "When", "value": "{{scheduled_when}}", "short": True},
                {
                    "title": "CRM",
                    "value": "[Open in CRM]({{deep_link}})",
                    "short": False,
                },
            ],
        }
    ],
}

# --- Shared-contact-reuse alert (ENG-555, Layer D) ---
#
# PHI-FREE BY CONSTRUCTION. Unlike the lead/consultation cards, this template
# references ONLY non-PHI placeholders: opaque ``person_uid`` values, deep links,
# and the contact KIND ("phone"/"email" — the type, never the value). It carries
# NO {{name}}/{{phone}}/{{email}}/clinic-label, so it stays safe regardless of
# ``Settings.messenger_phi_full``. The scan job never puts the contact value, a
# name, or a location label into the emit context (the alert routes to the
# location's own leads channel, so the channel IS the location context — ENG-555
# Codex review). Business purpose: nudge staff to capture a distinct contact per
# person.
_REUSE_CARD_COLOR = "#9b59b6"  # purple — an identity-hygiene nudge

SHARED_CONTACT_REUSE_TEMPLATE: dict[str, object] = {
    "text": (
        "♻️ Shared {{contact_kind}} reused — a new record reuses a "
        "{{contact_kind}} already on file. Capture a "
        "distinct contact per person. New: {{deep_link}} · Existing: "
        "{{other_deep_link}}"
    ),
    "blocks": [
        {
            "color": _REUSE_CARD_COLOR,
            "fallback": (
                "Shared {{contact_kind}} reused — capture a distinct contact "
                "per person — {{deep_link}}"
            ),
            "title": "♻️ Shared contact reused",
            "title_link": "{{deep_link}}",
            "text": (
                "A new record reuses a **{{contact_kind}}** already on file. "
                "Capture a distinct contact per person."
            ),
            "fields": [
                {"title": "Contact type", "value": "{{contact_kind}}", "short": True},
                {
                    "title": "New record",
                    "value": "[Open in CRM]({{deep_link}})",
                    "short": False,
                },
                {
                    "title": "Existing record",
                    "value": "[Open in CRM]({{other_deep_link}})",
                    "short": False,
                },
            ],
        }
    ],
}

# Kept for backward compatibility with Block C callers / tests.
DEFAULT_LEAD_CREATED_EVENT = EVENT_LEAD_CREATED
DEFAULT_LEAD_CREATED_TEMPLATE: dict[str, object] = LEAD_CREATED_RICH_TEMPLATE


# One default rule per event type. Each is a tuple of
# ``(event_type, channel, conditions, template, description)`` using only
# de-identified, allowlisted placeholders.
_DEFAULT_RULES: tuple[
    tuple[str, str, list[dict[str, object]], dict[str, object], str], ...
] = (
    (
        EVENT_LEAD_CREATED,
        DEFAULT_LEAD_CREATED_CHANNEL,
        [],
        LEAD_CREATED_RICH_TEMPLATE,
        "Default: notify on new lead",
    ),
    (
        # Field-control rule: leads created WITHOUT a phone get routed to a
        # dedicated triage channel. The emit context carries a NON-PII boolean
        # ``has_phone`` (never the phone value); the rule fires only when it is
        # explicitly ``False``. (The old predicate ``{lead.Phone, is_empty}``
        # was a bug — ``lead.Phone`` is absent from context, so ``is_empty``
        # matched EVERY lead. ``has_phone == False`` fires only on real
        # phone-less leads.) The template never renders the number.
        EVENT_LEAD_CREATED,
        LEADS_MISSING_INFO_CHANNEL,
        [{"field": "has_phone", "op": "eq", "value": False}],
        LEAD_MISSING_INFO_RICH_TEMPLATE,
        "Field control: new lead with no phone",
    ),
    (
        # ENG-457: announce a genuinely-NEW consultation to #scheduls. The
        # boundary emits ONLY on created consults (dedupe_key = consultation
        # id), so this rule never fires on re-ingest or backfill. ENG-460: the
        # card is a rich attachment carrying the real patient {{name}} plus
        # provider / status / kind / scheduled_at (full-mode render).
        EVENT_CONSULTATION_SCHEDULED,
        SCHEDULS_CHANNEL,
        [],
        CONSULTATION_SCHEDULED_RICH_TEMPLATE,
        "Default: notify on newly-scheduled consultation",
    ),
    (
        # ENG-486: T-15m reminder. The scan job emits ONLY for consultations
        # whose source_status is 'Confirmed' and which start within the next
        # 15 min (dedupe_key = consultation id → at-most-once ever). No
        # condition needed here — the scanner already filters confirmed+due.
        EVENT_CONSULTATION_REMINDER,
        CONSULT_REMINDERS_CHANNEL,
        [],
        CONSULTATION_REMINDER_RICH_TEMPLATE,
        "Default: remind 15 min before a confirmed consultation",
    ),
    (
        EVENT_OPPORTUNITY_STAGE_CHANGED,
        OPPORTUNITY_CHANNEL,
        [],
        {"text": "Opportunity {{person_uid}} stage → {{stage}} — {{deep_link}}"},
        "Default: notify on opportunity stage change",
    ),
    (
        EVENT_OWNERSHIP_CHANGED,
        OWNERSHIP_CHANNEL,
        [],
        {"text": "Ownership changed for {{person_uid}} ({{owner_role}}) — {{deep_link}}"},
        "Default: notify on ownership change",
    ),
    (
        EVENT_INGEST_SYNC_FAILED,
        INGEST_ALERTS_CHANNEL,
        [],
        {"text": "Sync failed: {{provider}} {{object}} ({{sync_status}})"},
        "Default: alert on failed ingest sync run",
    ),
    (
        # ENG-555 (Layer D): always alert when an incoming record reuses an
        # existing shared contact (open match_candidate with an ambiguous
        # phone/email rule). The scan job emits ONLY for candidates created
        # after NOTIFICATIONS_CUTOFF_AT (dedupe_key = candidate id → at-most-once
        # ever), so the 1,144 pre-existing open candidates are never blasted. No
        # condition — the scanner already filters reuse rules + cutoff.
        EVENT_SHARED_CONTACT_REUSE,
        SHARED_CONTACT_REUSE_CHANNEL,
        [],
        SHARED_CONTACT_REUSE_TEMPLATE,
        "Default: alert when an incoming record reuses a shared contact",
    ),
)


async def _upsert_rule(
    rules: NotificationRuleRepository,
    tenant_id: TenantId,
    *,
    event_type: str,
    channel: str,
    conditions: list[dict[str, object]],
    template: dict[str, object],
    description: str,
) -> NotificationRule:
    existing = await rules.find_by_event_and_channel(tenant_id, event_type, channel)
    if existing is not None:
        return existing
    rule = NotificationRule(
        tenant_id=tenant_id,
        event_type=event_type,
        channel=channel,
        conditions=[dict(c) for c in conditions],
        template=dict(template),
        provider_kind="mattermost",
        enabled=True,
        description=description,
    )
    await rules.add(rule)
    return rule


async def seed_default_notification_rules(
    session: AsyncSession, tenant_id: TenantId
) -> NotificationRule:
    """Upsert the full default rule set for ``tenant_id``.

    Seeds one rule per canonical event type plus the phone-less
    field-control rule. Idempotent on ``(tenant_id, event_type,
    channel)``. Returns the flagship ``lead.created`` → ``leads`` rule
    (existing or newly created) to preserve the Block C return contract;
    use :func:`seed_all_notification_rules` to get the full list.
    """
    rules = await seed_all_notification_rules(session, tenant_id)
    # The flagship rule is the first entry in ``_DEFAULT_RULES``.
    return rules[0]


async def seed_all_notification_rules(
    session: AsyncSession, tenant_id: TenantId
) -> list[NotificationRule]:
    """Upsert every default rule; return them in ``_DEFAULT_RULES`` order."""
    repo = NotificationRuleRepository(session)
    seeded: list[NotificationRule] = []
    for event_type, channel, conds, template, description in _DEFAULT_RULES:
        seeded.append(
            await _upsert_rule(
                repo,
                tenant_id,
                event_type=event_type,
                channel=channel,
                conditions=conds,
                template=template,
                description=description,
            )
        )
    return seeded


__all__ = [
    "CONSULTATION_SCHEDULED_RICH_TEMPLATE",
    "DEFAULT_LEAD_CREATED_CHANNEL",
    "DEFAULT_LEAD_CREATED_EVENT",
    "DEFAULT_LEAD_CREATED_TEMPLATE",
    "INGEST_ALERTS_CHANNEL",
    "LEAD_CREATED_RICH_TEMPLATE",
    "LEAD_MISSING_INFO_RICH_TEMPLATE",
    "CONSULT_REMINDERS_CHANNEL",
    "LEADS_MISSING_INFO_CHANNEL",
    "OPPORTUNITY_CHANNEL",
    "OWNERSHIP_CHANNEL",
    "SCHEDULS_CHANNEL",
    "SHARED_CONTACT_REUSE_CHANNEL",
    "SHARED_CONTACT_REUSE_TEMPLATE",
    "seed_all_notification_rules",
    "seed_default_notification_rules",
]
