"""Extract normalized attribution signals from a Salesforce lead payload (ENG-448).

Pure — maps the captured SF field names onto :class:`LeadSignals`. The wide
full-fidelity capture (ENG-425) provides every field, including the nested
``CreatedBy.Name`` and the click/campaign attribution set.
"""

from __future__ import annotations

from collections.abc import Mapping

from .waterfall import LeadSignals

# Canonical signal name → SF payload field. The canonical names are what
# ``mapping_rule.match_field`` matches on, so they are the stable contract.
_RAW_FIELDS: dict[str, str] = {
    "utm_source": "utm_source__c",
    "utm_medium": "utm_medium__c",
    "utm_campaign": "utm_campaign__c",
    "utm_content": "utm_content__c",
    "utm_adgroup": "utm_adgroup__c",
    "utm_creative": "utm_creative__c",
    "last_touch_source": "last_touch_source__c",
    "last_touch_medium": "last_touch_medium__c",
    "last_touch_campaign": "last_touch_campaign__c",
    "first_touch_campaign": "first_touch_campaign__c",
    "hubspot_lead_source": "Hubspot_Lead_Source__c",
    "record_source_detail": "Record_Source_Detail__c",
    "lead_source": "LeadSource",
    "business_unit": "Business_Unit__c",
    "assigned_center": "Assigned_Center__c",
}


def _s(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _created_by_name(payload: Mapping[str, object]) -> str | None:
    created_by = payload.get("CreatedBy")
    if isinstance(created_by, Mapping):
        name = created_by.get("Name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def build_signals(
    payload: Mapping[str, object], *, has_earlier_carestack: bool = False
) -> LeadSignals:
    """Build :class:`LeadSignals` from a captured SF lead payload."""
    raw: dict[str, str] = {}
    for canonical, sf_field in _RAW_FIELDS.items():
        value = _s(payload, sf_field)
        if value is not None:
            raw[canonical] = value

    created_by = _created_by_name(payload)
    if created_by is not None:
        # Exposed so mapping rules can match on the creator (e.g. an integration
        # account "ApiX-Drive" → a channel/vendor) when utm is missing.
        raw["created_by"] = created_by

    hubspot = _s(payload, "Hubspot_Lead_Source__c")
    return LeadSignals(
        utm_source=_s(payload, "utm_source__c"),
        utm_medium=_s(payload, "utm_medium__c"),
        last_touch_source=_s(payload, "last_touch_source__c"),
        campaign=_s(payload, "utm_campaign__c") or _s(payload, "last_touch_campaign__c"),
        ad_set=_s(payload, "utm_adgroup__c"),
        ad=_s(payload, "utm_content__c") or _s(payload, "utm_creative__c"),
        form=_s(payload, "Record_Source_Detail__c"),
        hubspot_lead_source=hubspot,
        is_callrail=(hubspot or "").strip().lower() == "callrail",
        callrail_inbound=bool(payload.get("Callrail_Inbound__c")),
        created_by_name=created_by,
        has_earlier_carestack=has_earlier_carestack,
        raw=raw,
    )
