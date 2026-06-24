"""Pure attribution waterfall (ENG-448).

Given a lead's normalized signals (and the tenant's mapping rules), resolve the
distribution chain in priority order. Pure — no I/O — so every branch is
unit-tested. The service layer reads the signals (from the captured SF lead
payload + identity source links) and persists the result.

Priority ladder (channel is decided by the first match; deeper levels and
vendor fill from whatever data is present):

1. digital     — utm_source / last_touch_source
2. phone       — CallRail / inbound flag / a "direct line" campaign name
3. campaign    — a campaign name present though source is empty
4. manual      — a creator (staff) present and no marketing signal
5. reactivation— the person existed in CareStack before the SF lead
6. needs_review— nothing recognizable (target ~0%)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# utm_source / last_touch_source value (lowercased) → channel slug.
_CHANNEL_ALIASES: dict[str, str] = {
    "facebook": "facebook",
    "fb": "facebook",
    "instagram": "instagram",
    "ig": "instagram",
    "google": "google",
    "adwords": "google",
    "tiktok": "tiktok",
    "bing": "google",
    "direct": "direct",
    "referral": "referral",
    "organic": "organic",
}

# Campaign names that denote an inbound phone line (e.g. "ella old direct line").
_DIRECT_LINE_RE = re.compile(r"direct line|redirect|ai redirect", re.IGNORECASE)


@dataclass(frozen=True)
class LeadSignals:
    """Normalized attribution signals extracted from a lead (ENG-448)."""

    utm_source: str | None = None
    utm_medium: str | None = None
    last_touch_source: str | None = None
    campaign: str | None = None
    ad_set: str | None = None
    ad: str | None = None
    form: str | None = None
    hubspot_lead_source: str | None = None
    is_callrail: bool = False
    callrail_inbound: bool = False
    created_by_name: str | None = None
    has_earlier_carestack: bool = False
    # Raw values keyed by the field names mapping rules match on.
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    """One mapping rule (pattern → chain node), passed to the resolver."""

    match_field: str
    match_op: str  # eq | ilike | prefix
    match_value: str
    set_level: str
    set_slug: str
    set_label: str
    priority: int = 100


@dataclass
class ChainResult:
    """Resolved chain — slug/label per level, plus method/confidence/signal."""

    channel: tuple[str, str] | None = None
    campaign: tuple[str, str] | None = None
    ad_set: tuple[str, str] | None = None
    ad: tuple[str, str] | None = None
    form: tuple[str, str] | None = None
    vendor: tuple[str, str] | None = None
    # The record creator (CreatedBy.Name), captured for EVERY lead: a staff
    # person for manual entries (= the source), or an integration / pipeline
    # account for digital ones (a fallback signal when utm is missing).
    created_by_name: str | None = None
    method: str = "auto"
    confidence: float = 0.0
    source_signal: str = "needs_review"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:160] or "unknown"


def _node(value: str | None) -> tuple[str, str] | None:
    if not value or not value.strip():
        return None
    return (_slugify(value), value.strip())


def _channel_slug(source: str) -> str:
    return _CHANNEL_ALIASES.get(source.strip().lower(), _slugify(source))


def _is_staff_creator(name: str) -> bool:
    """A real staff person (manual entry) vs an automation/marketing account."""
    lowered = name.lower()
    bot_markers = ("marketing", "creatives", "api", "zapier", "integration", "bot",
                   "automation", "system")
    return not any(m in lowered for m in bot_markers)


def _rule_matches(rule: Rule, signals: LeadSignals) -> bool:
    value = signals.raw.get(rule.match_field)
    if value is None:
        return False
    if rule.match_op == "eq":
        return value.strip().lower() == rule.match_value.strip().lower()
    if rule.match_op == "prefix":
        return value.strip().lower().startswith(rule.match_value.strip().lower())
    # default: ilike (substring, case-insensitive; '%' wildcards stripped)
    needle = rule.match_value.strip().lower().strip("%")
    return needle in value.lower()


def resolve(signals: LeadSignals, rules: list[Rule] | None = None) -> ChainResult:
    """Resolve a lead's attribution chain. Never returns a silent 'unknown'."""
    result = ChainResult()

    # The record creator is captured for EVERY lead (not just manual). For ad
    # leads it is the integration account; useful as a fallback and for rules.
    if signals.created_by_name and signals.created_by_name.strip():
        result.created_by_name = signals.created_by_name.strip()

    # Deeper levels fill from whatever the data carries, regardless of branch.
    result.campaign = _node(signals.campaign)
    result.ad_set = _node(signals.ad_set)
    result.ad = _node(signals.ad)
    result.form = _node(signals.form or signals.hubspot_lead_source)

    src = signals.utm_source or signals.last_touch_source
    if src and src.strip():
        slug = _channel_slug(src)
        result.channel = (slug, src.strip())
        result.source_signal = "digital"
        result.confidence = 0.9
    elif (
        signals.is_callrail
        or signals.callrail_inbound
        or (signals.campaign and _DIRECT_LINE_RE.search(signals.campaign))
        or (signals.hubspot_lead_source or "").strip().lower() == "callrail"
    ):
        result.channel = ("phone", "Phone / Call")
        result.source_signal = "phone"
        result.confidence = 0.8
    elif signals.campaign and signals.campaign.strip():
        result.channel = ("direct", "Direct")
        result.source_signal = "campaign"
        result.confidence = 0.5
    elif signals.created_by_name and _is_staff_creator(signals.created_by_name):
        # A real staff person entered it by hand → manual is the source.
        result.channel = ("manual", "Manual entry")
        result.source_signal = "manual"
        result.confidence = 0.7
    elif signals.has_earlier_carestack:
        result.channel = ("existing_patient", "Existing patient")
        result.source_signal = "reactivation"
        result.confidence = 0.6
    elif result.created_by_name:
        # No marketing / phone / staff signal, but SOME account created it
        # (e.g. an integration / pipeline). We still know the creator — a
        # mapping rule can turn it into a channel/vendor (ENG-449). Not unknown.
        result.source_signal = "created_by"
        result.confidence = 0.3
    else:
        result.source_signal = "needs_review"
        result.confidence = 0.0

    # Mapping rules (highest priority first) set vendor / override a level.
    for rule in sorted(rules or [], key=lambda r: r.priority):
        if not _rule_matches(rule, signals):
            continue
        node = (rule.set_slug, rule.set_label)
        if rule.set_level == "vendor":
            result.vendor = node
        elif rule.set_level == "channel":
            result.channel = node
        elif rule.set_level == "campaign":
            result.campaign = node
        elif rule.set_level == "ad_set":
            result.ad_set = node
        elif rule.set_level == "ad":
            result.ad = node
        elif rule.set_level == "form":
            result.form = node
        if result.source_signal != "needs_review":
            result.method = "rule"

    return result
