"""Pure waterfall + signal-extraction tests (ENG-448)."""

from __future__ import annotations

from packages.attribution.signals import build_signals
from packages.attribution.waterfall import LeadSignals, Rule, resolve


def test_digital_facebook() -> None:
    r = resolve(LeadSignals(utm_source="Facebook", utm_medium="Paid_social",
                            campaign="Roseville Lead Gen Fusion", ad="Done with Dentures"))
    assert r.channel == ("facebook", "Facebook")
    assert r.source_signal == "digital"
    assert r.campaign == ("roseville_lead_gen_fusion", "Roseville Lead Gen Fusion")
    assert r.ad == ("done_with_dentures", "Done with Dentures")


def test_phone_via_callrail_hubspot() -> None:
    r = resolve(LeadSignals(hubspot_lead_source="CallRail"))
    assert r.channel == ("phone", "Phone / Call")
    assert r.source_signal == "phone"


def test_phone_via_direct_line_campaign() -> None:
    r = resolve(LeadSignals(campaign="ella old direct line"))
    assert r.channel == ("phone", "Phone / Call")
    assert r.source_signal == "phone"


def test_campaign_only_when_source_empty() -> None:
    r = resolve(LeadSignals(campaign="Galleria Kickoff Campaign"))
    assert r.channel == ("direct", "Direct")
    assert r.source_signal == "campaign"
    assert r.campaign == ("galleria_kickoff_campaign", "Galleria Kickoff Campaign")


def test_manual_via_staff_creator() -> None:
    r = resolve(LeadSignals(created_by_name="Olga Kolomyza"))
    assert r.channel == ("manual", "Manual entry")
    assert r.created_by_name == "Olga Kolomyza"
    assert r.source_signal == "manual"


def test_marketing_account_creator_is_created_by_not_manual() -> None:
    # An integration / marketing account is NOT a manual staff entry, but the
    # creator is still captured (a fallback signal, not "unknown").
    r = resolve(LeadSignals(created_by_name="Fusion Marketing (Inactive)"))
    assert r.source_signal == "created_by"
    assert r.created_by_name == "Fusion Marketing (Inactive)"
    assert r.channel is None  # a mapping rule can assign one later


def test_creator_is_captured_for_digital_leads_too() -> None:
    # Even an ad lead records its creator (the integration account).
    r = resolve(LeadSignals(utm_source="Facebook", created_by_name="ApiX-Drive"))
    assert r.source_signal == "digital"
    assert r.created_by_name == "ApiX-Drive"


def test_reactivation() -> None:
    r = resolve(LeadSignals(has_earlier_carestack=True))
    assert r.channel == ("existing_patient", "Existing patient")
    assert r.source_signal == "reactivation"


def test_needs_review_when_no_signal() -> None:
    r = resolve(LeadSignals())
    assert r.channel is None
    assert r.source_signal == "needs_review"
    assert r.confidence == 0.0


def test_rule_sets_vendor_and_marks_method_rule() -> None:
    rules = [
        Rule(
            match_field="utm_campaign",
            match_op="ilike",
            match_value="Roseville",
            set_level="vendor",
            set_slug="dima",
            set_label="Dima",
        )
    ]
    sig = LeadSignals(
        utm_source="Facebook",
        campaign="Roseville Lead Gen Fusion",
        raw={"utm_campaign": "Roseville Lead Gen Fusion"},
    )
    r = resolve(sig, rules)
    assert r.vendor == ("dima", "Dima")
    assert r.method == "rule"


def test_build_signals_from_manual_lead_payload() -> None:
    # A Vladyslav-style lead: nested CreatedBy, no marketing fields.
    payload = {
        "Id": "00Q1",
        "CreatedBy": {"Name": "Olga Kolomyza"},
        "Business_Unit__c": "Fusion Dental Implants",
        "utm_source__c": None,
        "Hubspot_Lead_Source__c": None,
    }
    sig = build_signals(payload)
    assert sig.created_by_name == "Olga Kolomyza"
    assert sig.utm_source is None
    r = resolve(sig)
    assert r.source_signal == "manual"
    assert r.created_by_name == "Olga Kolomyza"


def test_build_signals_digital_payload_populates_raw() -> None:
    payload = {
        "utm_source__c": "Facebook",
        "utm_campaign__c": "Galleria Kickoff Campaign",
        "utm_content__c": "Single Implant",
        "Hubspot_Lead_Source__c": "Dental Implants Club Lead Capturing Form FB",
    }
    sig = build_signals(payload)
    assert sig.utm_source == "Facebook"
    assert sig.raw["utm_campaign"] == "Galleria Kickoff Campaign"
    assert sig.form is None  # Record_Source_Detail empty
    assert sig.hubspot_lead_source.startswith("Dental Implants")
