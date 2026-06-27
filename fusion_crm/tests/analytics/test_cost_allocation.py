"""Unit tests for the cost-per-lead allocator (ENG-512).

Pure / DB-free: exercises the allocation model directly — reconciliation
(Σ allocated + spend_without_leads == Σ campaign spend), zero-lead ads
surfaced as spend_without_leads, the ad → campaign → $0 fallback hierarchy, and
even splitting across co-attributed leads.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from packages.analytics.cost_allocation import (
    SOURCE_AD,
    SOURCE_CAMPAIGN,
    SOURCE_UNCOVERED,
    AllocLead,
    allocate,
)

_DAY = date(2026, 6, 18)
_DAY2 = date(2026, 6, 19)


def _pid() -> uuid.UUID:
    return uuid.uuid4()


def test_ad_tier_splits_spend_evenly_across_leads() -> None:
    a, b = _pid(), _pid()
    leads = [
        AllocLead(a, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9),
        AllocLead(b, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9),
    ]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 100.0},
        campaign_spend={("c1", _DAY): 100.0},
        ad_to_campaign={"ad1": "c1"},
    )
    assert result.per_person[a].amount == pytest.approx(50.0)
    assert result.per_person[b].amount == pytest.approx(50.0)
    assert result.per_person[a].source == SOURCE_AD
    assert result.per_person[a].confidence == 0.9
    # ad spend fully consumed; campaign residual is 0 → nothing without leads.
    assert result.summary.allocated_total == pytest.approx(100.0)
    assert result.summary.spend_without_leads == pytest.approx(0.0)
    assert result.summary.ad_covered_leads == 2


def test_zero_lead_ad_is_surfaced_not_hidden() -> None:
    a = _pid()
    leads = [AllocLead(a, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9)]
    # ad1 has the lead + $40; ad2 spent $60 but produced no attributed lead.
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 40.0, ("ad2", _DAY): 60.0},
        campaign_spend={("c1", _DAY): 100.0},
        ad_to_campaign={"ad1": "c1", "ad2": "c1"},
    )
    assert result.per_person[a].amount == pytest.approx(40.0)
    # ad2's $60 has no leads → spend_without_leads; campaign residual is 0.
    assert result.summary.spend_without_leads == pytest.approx(60.0)
    assert result.summary.allocated_total == pytest.approx(40.0)
    # reconciliation: allocated + without_leads == campaign spend
    assert (
        result.summary.allocated_total + result.summary.spend_without_leads
        == pytest.approx(100.0)
    )


def test_campaign_fallback_when_no_ad_match() -> None:
    a = _pid()
    # Lead has a campaign node but its ad node didn't bridge to a spend row.
    leads = [AllocLead(a, _DAY, ad_key=None, campaign_key="c1", confidence=0.5)]
    result = allocate(
        leads,
        ad_spend={},
        campaign_spend={("c1", _DAY): 80.0},
        ad_to_campaign={},
    )
    assert result.per_person[a].amount == pytest.approx(80.0)
    assert result.per_person[a].source == SOURCE_CAMPAIGN
    assert result.summary.campaign_covered_leads == 1
    assert result.summary.spend_without_leads == pytest.approx(0.0)


def test_campaign_residual_excludes_ad_tier_spend() -> None:
    # ad1 ($60, 1 lead) is ad-covered; a second lead has only the campaign.
    # Campaign total $100 → residual $40 goes to the campaign-only lead.
    a, b = _pid(), _pid()
    leads = [
        AllocLead(a, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9),
        AllocLead(b, _DAY, ad_key=None, campaign_key="c1", confidence=0.5),
    ]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 60.0},
        campaign_spend={("c1", _DAY): 100.0},
        ad_to_campaign={"ad1": "c1"},
    )
    assert result.per_person[a].amount == pytest.approx(60.0)
    assert result.per_person[a].source == SOURCE_AD
    assert result.per_person[b].amount == pytest.approx(40.0)
    assert result.per_person[b].source == SOURCE_CAMPAIGN
    assert result.summary.spend_without_leads == pytest.approx(0.0)
    assert result.summary.allocated_total == pytest.approx(100.0)


def test_uncovered_lead_gets_zero() -> None:
    a = _pid()
    leads = [AllocLead(a, _DAY, ad_key=None, campaign_key=None, confidence=None)]
    result = allocate(
        leads, ad_spend={}, campaign_spend={}, ad_to_campaign={}
    )
    assert result.per_person[a].amount == pytest.approx(0.0)
    assert result.per_person[a].source == SOURCE_UNCOVERED
    assert result.summary.uncovered_leads == 1


def test_day_isolation_no_cross_day_bleed() -> None:
    # Same ad, two days: each day's spend allocates only to that day's leads.
    a, b = _pid(), _pid()
    leads = [
        AllocLead(a, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9),
        AllocLead(b, _DAY2, ad_key="ad1", campaign_key="c1", confidence=0.9),
    ]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 30.0, ("ad1", _DAY2): 70.0},
        campaign_spend={("c1", _DAY): 30.0, ("c1", _DAY2): 70.0},
        ad_to_campaign={"ad1": "c1"},
    )
    assert result.per_person[a].amount == pytest.approx(30.0)
    assert result.per_person[b].amount == pytest.approx(70.0)


def test_reconciliation_over_mixed_window() -> None:
    # Two campaigns, ad + campaign tiers + a zero-lead ad. Total allocated +
    # spend_without_leads must equal total campaign spend.
    a, b, c, d = _pid(), _pid(), _pid(), _pid()
    leads = [
        AllocLead(a, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9),
        AllocLead(b, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.9),
        AllocLead(c, _DAY, ad_key=None, campaign_key="c2", confidence=0.5),
        AllocLead(d, _DAY, ad_key=None, campaign_key=None, confidence=None),
    ]
    ad_spend = {("ad1", _DAY): 100.0, ("ad_zero", _DAY): 25.0}
    # c1 campaign spend = its ad spend (ad1 + ad_zero), the normal Meta case.
    campaign_spend = {("c1", _DAY): 125.0, ("c2", _DAY): 50.0}
    result = allocate(
        leads,
        ad_spend=ad_spend,
        campaign_spend=campaign_spend,
        ad_to_campaign={"ad1": "c1", "ad_zero": "c1"},
    )
    total_campaign_spend = sum(campaign_spend.values())
    # ad_zero's $25 is part of c1's spend but produced no leads → it sits in
    # spend_without_leads, NOT re-allocated to c1's ad-covered leads.
    assert result.summary.spend_without_leads == pytest.approx(25.0)
    assert result.summary.allocated_total == pytest.approx(
        total_campaign_spend - 25.0
    )
    assert result.per_person[d].source == SOURCE_UNCOVERED


# --- Blocker 2: cent-exact (largest-remainder) reconciliation -------------


def test_cent_exact_indivisible_hundred_over_six() -> None:
    # $100 split across 6 co-attributed leads. A naive float share + per-row
    # round(.,2) would give 16.67*6 = 100.02 (over-allocation). The cent-exact
    # split must sum to EXACTLY 10000 cents: 4 leads @16.67 + 2 leads @16.66.
    pids = [_pid() for _ in range(6)]
    leads = [AllocLead(p, _DAY, ad_key="ad1", campaign_key="c1") for p in pids]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 100.0},
        campaign_spend={("c1", _DAY): 100.0},
        ad_to_campaign={"ad1": "c1"},
    )
    cents = sorted(round(result.per_person[p].amount * 100) for p in pids)
    assert sum(cents) == 10000
    assert cents == [1666, 1666, 1667, 1667, 1667, 1667]
    # The group's allocated total reconciles to the spend cents exactly.
    assert round(result.summary.allocated_total * 100) == 10000


def test_cent_exact_penny_over_three() -> None:
    # $0.01 across 3 leads → exactly one cent total: one lead 1¢, two 0¢.
    pids = [_pid() for _ in range(3)]
    leads = [AllocLead(p, _DAY, ad_key="ad1", campaign_key="c1") for p in pids]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 0.01},
        campaign_spend={("c1", _DAY): 0.01},
        ad_to_campaign={"ad1": "c1"},
    )
    cents = sorted(round(result.per_person[p].amount * 100) for p in pids)
    assert sum(cents) == 1
    assert cents == [0, 0, 1]


def test_cent_exact_campaign_residual_indivisible() -> None:
    # The campaign-tier residual is split cent-exact too: $100 residual / 3.
    pids = [_pid() for _ in range(3)]
    leads = [AllocLead(p, _DAY, ad_key=None, campaign_key="c1") for p in pids]
    result = allocate(
        leads,
        ad_spend={},
        campaign_spend={("c1", _DAY): 100.0},
        ad_to_campaign={},
    )
    cents = sorted(round(result.per_person[p].amount * 100) for p in pids)
    assert sum(cents) == 10000
    assert cents == [3333, 3333, 3334]


# --- Blocker 3b: ad/campaign mismatch must not mis-allocate ---------------


def test_ad_in_wrong_campaign_falls_back_to_campaign_tier() -> None:
    # Lead resolved to ad "ad1" but to campaign "c2"; ad1's parent is "c1". The
    # ad bridge is wrong → the lead must NOT draw ad1's spend; it falls back to
    # its own campaign c2. ad1's $50 becomes spend_without_leads (surfaced).
    a = _pid()
    leads = [AllocLead(a, _DAY, ad_key="ad1", campaign_key="c2", confidence=0.7)]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 50.0},
        campaign_spend={("c2", _DAY): 30.0},
        ad_to_campaign={"ad1": "c1"},
    )
    assert result.per_person[a].source == SOURCE_CAMPAIGN
    assert result.per_person[a].amount == pytest.approx(30.0)
    assert result.summary.spend_without_leads == pytest.approx(50.0)
    assert result.summary.ad_covered_leads == 0


def test_ad_with_matching_campaign_is_ad_covered() -> None:
    # Control for the above: when the ad's parent campaign matches the lead's
    # resolved campaign, the lead IS ad-covered (no spurious fallback).
    a = _pid()
    leads = [AllocLead(a, _DAY, ad_key="ad1", campaign_key="c1", confidence=0.7)]
    result = allocate(
        leads,
        ad_spend={("ad1", _DAY): 50.0},
        campaign_spend={("c1", _DAY): 50.0},
        ad_to_campaign={"ad1": "c1"},
    )
    assert result.per_person[a].source == SOURCE_AD
    assert result.per_person[a].amount == pytest.approx(50.0)
    assert result.summary.spend_without_leads == pytest.approx(0.0)
