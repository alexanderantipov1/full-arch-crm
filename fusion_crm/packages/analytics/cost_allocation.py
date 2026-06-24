"""Cost-per-lead allocator (ENG-512) — pure, DB-free arithmetic.

Allocates ad spend to the persons (leads) it produced, so the fact builder can
fill ``analytics.fact_patient_journey.marketing_cost_allocated``. Kept pure (no
I/O) so the reconciliation / zero-lead / fallback semantics are exhaustively
unit-tested without a Postgres; the fact builder
(:mod:`packages.analytics.fact_builder`) bridges the attribution chain and the
``marketing`` spend tables into the plain inputs this module consumes.

Allocation model — two tiers, ad first then campaign on the *residual*:

1. **Ad tier.** For each ``(ad, day)`` with leads attributed to that ad on that
   day, split that ad's spend evenly across those leads
   (``spend ÷ leads = cost per lead``). An ad that spent but produced **zero**
   attributed leads contributes its spend to ``spend_without_leads`` — surfaced,
   never hidden, never re-allocated.
2. **Campaign tier (fallback).** A lead attributed to a campaign but **not** to
   a covered ad falls back to the campaign. The campaign's *residual* spend
   (campaign-level spend minus the spend of all its ad-level rows) is split
   evenly across those fallback leads. Residual with no fallback leads is also
   ``spend_without_leads``.
3. **Uncovered → $0.** A lead with no attributed spend at either tier gets
   ``0.0`` (the explicit "uncovered" value, not NULL).

Precedence per lead: **ad → campaign → $0**. Reconciliation: summed over a
window, ``allocated_total + spend_without_leads == Σ campaign spend`` whenever
each ad rolls up to a campaign whose campaign-level total is ≥ its ad-level
total (the normal Meta case where campaign spend = Σ ad spend).

Money is split **cent-exact** (largest-remainder): per ``(ad/campaign, day)``
group the spend is converted to integer cents and distributed so the Σ of the
per-lead rounded amounts equals the group's spend cents EXACTLY — an indivisible
split like ``$100 / 6`` never over-allocates to ``$100.02``. Callers persist the
returned per-person ``amount`` verbatim (a second independent ``round`` would
re-introduce the drift).

A lead is only **ad covered** when the resolved ad's parent campaign matches the
lead's own resolved campaign (or the lead has no resolved campaign to
contradict). A lead resolved to an ad in a *different* campaign is a bad bridge:
it draws none of that ad's spend and falls back to its own campaign tier — so a
slug/id mismatch reduces coverage, never mis-allocates.

Keys are opaque strings in a single namespace (the fact builder passes platform
external ids); ``day`` is the lead's ``lead_date`` calendar day matched to the
spend ``metric_date``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

# Provenance source tags stamped on the fact row's marketing_cost_allocated.
SOURCE_AD = "marketing.ad_metric_daily_ad:cost_per_lead"
SOURCE_CAMPAIGN = "marketing.ad_metric_daily:cost_per_lead_campaign_fallback"
SOURCE_UNCOVERED = "marketing:uncovered_no_attributed_spend"


def _split_cents(amount: float, shares: int) -> list[float]:
    """Split ``amount`` (money) across ``shares`` parts, cent-exact.

    Largest-remainder on integer cents: every part gets ``cents // shares`` and
    the first ``cents % shares`` parts get one extra cent, so the Σ of the
    returned amounts == ``round(amount * 100)`` cents EXACTLY (no float-share +
    independent per-row rounding drift). ``shares`` is always ``>= 1`` (callers
    skip empty groups). A zero ``amount`` yields all-zero parts.
    """
    total_cents = round(amount * 100)
    base, remainder = divmod(total_cents, shares)
    return [
        round((base + (1 if i < remainder else 0)) / 100.0, 2)
        for i in range(shares)
    ]


@dataclass(frozen=True)
class AllocLead:
    """One lead to allocate spend to.

    ``ad_key`` / ``campaign_key`` are the resolved platform spend keys (external
    ids) the lead's attribution chain bridged to, or ``None`` when the chain has
    no node at that level (or it did not bridge to any captured spend row).
    """

    person_uid: UUID
    day: date
    ad_key: str | None
    campaign_key: str | None
    confidence: float | None = None


@dataclass(frozen=True)
class PersonCost:
    """The cost allocated to one person + its provenance inputs."""

    amount: float
    source: str
    confidence: float | None


@dataclass
class AllocationSummary:
    """Roll-up of one allocation run (logged + returned for surfacing)."""

    allocated_total: float = 0.0
    spend_without_leads: float = 0.0
    ad_covered_leads: int = 0
    campaign_covered_leads: int = 0
    uncovered_leads: int = 0


@dataclass
class AllocationResult:
    per_person: dict[UUID, PersonCost] = field(default_factory=dict)
    summary: AllocationSummary = field(default_factory=AllocationSummary)


def allocate(
    leads: list[AllocLead],
    *,
    ad_spend: dict[tuple[str, date], float],
    campaign_spend: dict[tuple[str, date], float],
    ad_to_campaign: dict[str, str | None],
) -> AllocationResult:
    """Allocate spend to leads. See module docstring for the model.

    ``ad_spend`` / ``campaign_spend`` are complete per-key/day spend over the
    window; ``ad_to_campaign`` maps each ad key to its campaign key (or ``None``)
    so the campaign residual can subtract ad-level spend.
    """
    result = AllocationResult()

    # --- group leads by ad and by campaign key + day ---
    leads_by_ad: dict[tuple[str, date], list[AllocLead]] = defaultdict(list)
    leads_by_campaign: dict[tuple[str, date], list[AllocLead]] = defaultdict(list)
    for lead in leads:
        if lead.ad_key is not None:
            leads_by_ad[(lead.ad_key, lead.day)].append(lead)
        if lead.campaign_key is not None:
            leads_by_campaign[(lead.campaign_key, lead.day)].append(lead)

    covered: set[UUID] = set()

    # --- ad tier ---
    # A lead is "ad covered" when a spend row exists for its (ad, day), even if
    # that day's spend is 0 (the ad legitimately spent nothing) — so it does NOT
    # fall through to the campaign tier. Only a MISSING ad row falls back.
    for (ad_key, day), spend in ad_spend.items():
        # Only leads whose resolved campaign matches this ad's parent campaign
        # genuinely belong to this ad. A lead resolved to an ad in a DIFFERENT
        # campaign is a bad bridge → it must not draw this ad's spend (it falls
        # to its own campaign tier); a lead with no resolved campaign cannot
        # contradict, so it stays. Mismatches reduce coverage, never mis-allocate.
        parent_campaign = ad_to_campaign.get(ad_key)
        group = [
            lead
            for lead in leads_by_ad.get((ad_key, day), [])
            if lead.campaign_key is None or lead.campaign_key == parent_campaign
        ]
        if not group:
            # Ad spent but produced no (matched) attributed leads → surfaced.
            result.summary.spend_without_leads += spend
            continue
        for lead, share in zip(group, _split_cents(spend, len(group)), strict=True):
            result.per_person[lead.person_uid] = PersonCost(
                amount=share, source=SOURCE_AD, confidence=lead.confidence
            )
            covered.add(lead.person_uid)
            result.summary.ad_covered_leads += 1
            result.summary.allocated_total += share

    # --- campaign tier (residual) ---
    # ad_total[(campaign, day)] = spend of ALL ad rows under that campaign that
    # day (whether or not they had leads), so the residual is the campaign spend
    # not represented at ad level at all (uncaptured / campaign-only spend).
    ad_total: dict[tuple[str, date], float] = defaultdict(float)
    for (ad_key, day), spend in ad_spend.items():
        camp = ad_to_campaign.get(ad_key)
        if camp is not None:
            ad_total[(camp, day)] += spend

    for (camp_key, day), camp_spend in campaign_spend.items():
        residual = camp_spend - ad_total.get((camp_key, day), 0.0)
        if residual < 0:
            residual = 0.0
        fallback = [
            lead
            for lead in leads_by_campaign.get((camp_key, day), [])
            if lead.person_uid not in covered
        ]
        if not fallback or residual <= 0:
            result.summary.spend_without_leads += residual
            continue
        for lead, share in zip(
            fallback, _split_cents(residual, len(fallback)), strict=True
        ):
            result.per_person[lead.person_uid] = PersonCost(
                amount=share, source=SOURCE_CAMPAIGN, confidence=lead.confidence
            )
            covered.add(lead.person_uid)
            result.summary.campaign_covered_leads += 1
            result.summary.allocated_total += share

    # --- uncovered → $0 ---
    for lead in leads:
        if lead.person_uid in covered:
            continue
        result.per_person[lead.person_uid] = PersonCost(
            amount=0.0, source=SOURCE_UNCOVERED, confidence=None
        )
        result.summary.uncovered_leads += 1

    return result
