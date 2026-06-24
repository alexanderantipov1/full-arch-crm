"""Service tests for vendor claims + unassigned signatures (ENG-571).

In-memory fake-repo style (no Postgres in the unit suite). Covers claim CRUD +
validation, the resolver picking up active claims as vendor-level rules, and the
unassigned-signature aggregation (ingest mocked).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.attribution.models import Vendor, VendorClaim
from packages.attribution.schemas import VendorClaimIn
from packages.attribution.service import (
    AttributionService,
    _claim_value_matches,
    _vendor_tokens,
)
from packages.core.exceptions import ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId

_TENANT = TenantId(uuid.uuid4())
_PRINCIPAL = Principal(id=uuid.uuid4(), email="ops@example.com")


def _make_service() -> tuple[AttributionService, list[Vendor], list[VendorClaim]]:
    vendors: list[Vendor] = []
    claims: list[VendorClaim] = []
    session = MagicMock()
    session.flush = AsyncMock()
    service = AttributionService(session)

    async def find_vendor(_t, vid):
        return next((v for v in vendors if v.id == vid), None)

    async def list_vendors(_t, *, active_only=False):
        return [v for v in vendors if not active_only or v.active]

    async def list_vendor_claims(_t, *, vendor_id=None, active_only=False):
        return [
            c
            for c in claims
            if (vendor_id is None or c.vendor_id == vendor_id)
            and (not active_only or c.active)
        ]

    async def find_vendor_claim(_t, cid):
        return next((c for c in claims if c.id == cid), None)

    async def add_vendor_claim(c):
        c.id = uuid.uuid4()
        claims.append(c)
        return c

    async def delete_vendor_claim(c):
        claims.remove(c)

    async def list_rules(_t, *, active_only=True):
        return []

    async def list_nodes(_t, *, level=None):
        return []

    repo = MagicMock()
    repo.find_vendor = AsyncMock(side_effect=find_vendor)
    repo.list_vendors = AsyncMock(side_effect=list_vendors)
    repo.list_vendor_claims = AsyncMock(side_effect=list_vendor_claims)
    repo.find_vendor_claim = AsyncMock(side_effect=find_vendor_claim)
    repo.add_vendor_claim = AsyncMock(side_effect=add_vendor_claim)
    repo.delete_vendor_claim = AsyncMock(side_effect=delete_vendor_claim)
    repo.list_rules = AsyncMock(side_effect=list_rules)
    repo.list_nodes = AsyncMock(side_effect=list_nodes)
    service._repo = repo  # type: ignore[attr-defined]
    service._audit = MagicMock(record=AsyncMock())  # type: ignore[attr-defined]
    return service, vendors, claims


def _vendor(slug: str = "dima", name: str = "Dima") -> Vendor:
    v = Vendor(tenant_id=_TENANT, slug=slug, name=name, kind="agency", active=True)
    v.id = uuid.uuid4()
    return v


@pytest.mark.parametrize(
    "op,needle,value,expected",
    [
        ("eq", "fb_dima", "FB_Dima", True),
        ("eq", "fb_dima", "fb_other", False),
        ("prefix", "fb_", "fb_dima", True),
        ("prefix", "fb_", "ig_dima", False),
        ("ilike", "dima", "campaign_dima_2026", True),
        ("ilike", "%dima%", "x_dima_y", True),
        ("ilike", "zzz", "abc", False),
    ],
)
def test_claim_value_matches(op, needle, value, expected) -> None:
    assert _claim_value_matches(op, needle, value) is expected


@pytest.mark.asyncio
async def test_create_claim_rejects_unknown_field() -> None:
    service, vendors, _claims = _make_service()
    v = _vendor()
    vendors.append(v)
    with pytest.raises(ValidationError):
        await service.create_vendor_claim(
            _TENANT,
            v.id,
            VendorClaimIn(match_field="not_a_field", match_value="x"),
            principal=_PRINCIPAL,
            reresolve=False,
        )


@pytest.mark.asyncio
async def test_create_claim_rejects_unknown_op() -> None:
    service, vendors, _claims = _make_service()
    v = _vendor()
    vendors.append(v)
    with pytest.raises(ValidationError):
        await service.create_vendor_claim(
            _TENANT,
            v.id,
            VendorClaimIn(match_field="utm_source", match_op="regex", match_value="x"),
            principal=_PRINCIPAL,
            reresolve=False,
        )


@pytest.mark.asyncio
async def test_create_claim_unknown_vendor_returns_none() -> None:
    service, *_ = _make_service()
    out = await service.create_vendor_claim(
        _TENANT,
        uuid.uuid4(),
        VendorClaimIn(match_field="utm_source", match_value="fb_dima"),
        principal=_PRINCIPAL,
        reresolve=False,
    )
    assert out is None


@pytest.mark.asyncio
async def test_create_list_delete_claim() -> None:
    service, vendors, claims = _make_service()
    v = _vendor()
    vendors.append(v)
    out = await service.create_vendor_claim(
        _TENANT,
        v.id,
        VendorClaimIn(match_field="utm_source", match_op="eq", match_value="fb_dima"),
        principal=_PRINCIPAL,
        reresolve=False,
    )
    assert out is not None and out.origin == "manual"
    assert len(claims) == 1
    listed = await service.list_vendor_claims(_TENANT, vendor_id=v.id)
    assert [c.match_value for c in listed] == ["fb_dima"]
    assert await service.delete_vendor_claim(_TENANT, out.id, principal=_PRINCIPAL)
    assert claims == []
    assert (
        await service.delete_vendor_claim(_TENANT, uuid.uuid4(), principal=_PRINCIPAL)
        is False
    )


@pytest.mark.asyncio
async def test_load_rules_includes_active_vendor_claims() -> None:
    service, vendors, claims = _make_service()
    v = _vendor(slug="romi", name="ROMI")
    vendors.append(v)
    claims.append(
        VendorClaim(
            tenant_id=_TENANT,
            vendor_id=v.id,
            priority=50,
            match_field="utm_source",
            match_op="eq",
            match_value="romi_fb",
            active=True,
            origin="manual",
        )
    )
    rules = await service.load_rules(_TENANT)
    vendor_rules = [r for r in rules if r.set_level == "vendor"]
    assert len(vendor_rules) == 1
    r = vendor_rules[0]
    assert (r.set_slug, r.set_label, r.match_value) == ("romi", "ROMI", "romi_fb")


def test_vendor_tokens_drops_generic_words() -> None:
    assert _vendor_tokens("Dima Media", "dima_media") == {"dima"}
    assert _vendor_tokens("ROMI Agency", "romi") == {"romi"}
    assert "house" not in _vendor_tokens("In-house", "in_house")


@pytest.mark.asyncio
async def test_create_claim_origin_agent() -> None:
    service, vendors, _claims = _make_service()
    v = _vendor()
    vendors.append(v)
    out = await service.create_vendor_claim(
        _TENANT,
        v.id,
        VendorClaimIn(match_field="utm_source", match_value="fb_dima", origin="agent"),
        principal=_PRINCIPAL,
        reresolve=False,
    )
    assert out is not None and out.origin == "agent"


@pytest.mark.asyncio
async def test_create_claim_rejects_unknown_origin() -> None:
    service, vendors, _claims = _make_service()
    v = _vendor()
    vendors.append(v)
    with pytest.raises(ValidationError):
        await service.create_vendor_claim(
            _TENANT,
            v.id,
            VendorClaimIn(
                match_field="utm_source", match_value="x", origin="robot"
            ),
            principal=_PRINCIPAL,
            reresolve=False,
        )


@pytest.mark.asyncio
async def test_suggest_claims_for_vendor_token_match() -> None:
    service, vendors, _claims = _make_service()
    v = _vendor(slug="dima_media", name="Dima Media")
    vendors.append(v)
    leads = [(uuid.uuid4(), "L1"), (uuid.uuid4(), "L2")]
    service._repo.list_unassigned_leads = AsyncMock(return_value=leads)
    service._repo.count_unassigned_leads = AsyncMock(return_value=2)

    async def latest_payload_values(_t, *, event_type, external_ids, payload_key):
        if payload_key == "utm_source__c":
            return {"L1": "fb_dima", "L2": "google_x"}
        return {}

    service._ingest.latest_payload_values = AsyncMock(  # type: ignore[attr-defined]
        side_effect=latest_payload_values
    )

    out = await service.suggest_claims_for_vendor(_TENANT, v.id)
    assert out is not None
    # only "fb_dima" matches the "dima" token; "google_x" does not.
    assert [(i.match_field, i.value) for i in out.items] == [
        ("utm_source", "fb_dima")
    ]
    assert "dima" in out.items[0].rationale


@pytest.mark.asyncio
async def test_suggest_matches_whole_word_not_substring() -> None:
    service, vendors, _claims = _make_service()
    v = _vendor(slug="art", name="Art")  # 3-letter token "art"
    vendors.append(v)
    service._repo.list_unassigned_leads = AsyncMock(
        return_value=[(uuid.uuid4(), "L1"), (uuid.uuid4(), "L2")]
    )
    service._repo.count_unassigned_leads = AsyncMock(return_value=2)

    async def lpv(_t, *, event_type, external_ids, payload_key):
        if payload_key == "utm_campaign__c":
            return {"L1": "smart_campaign", "L2": "fb_art_spring"}
        return {}

    service._ingest.latest_payload_values = AsyncMock(side_effect=lpv)  # type: ignore[attr-defined]

    out = await service.suggest_claims_for_vendor(_TENANT, v.id)
    vals = [i.value for i in out.items]
    assert "fb_art_spring" in vals  # "art" is a whole token here
    assert "smart_campaign" not in vals  # "art" inside "smart" must NOT match


@pytest.mark.asyncio
async def test_suggest_excludes_already_claimed_signature() -> None:
    service, vendors, claims = _make_service()
    v = _vendor(slug="dima_media", name="Dima Media")
    vendors.append(v)
    claims.append(
        VendorClaim(
            tenant_id=_TENANT,
            vendor_id=v.id,
            priority=100,
            match_field="utm_source",
            match_op="eq",
            match_value="fb_dima",
            active=True,
            origin="manual",
        )
    )
    service._repo.list_unassigned_leads = AsyncMock(return_value=[(uuid.uuid4(), "L1")])
    service._repo.count_unassigned_leads = AsyncMock(return_value=1)

    async def lpv(_t, *, event_type, external_ids, payload_key):
        return {"L1": "fb_dima"} if payload_key == "utm_source__c" else {}

    service._ingest.latest_payload_values = AsyncMock(side_effect=lpv)  # type: ignore[attr-defined]

    out = await service.suggest_claims_for_vendor(_TENANT, v.id)
    assert out.items == []  # fb_dima already claimed by this vendor


@pytest.mark.asyncio
async def test_suggest_claims_unknown_vendor_returns_none() -> None:
    service, *_ = _make_service()
    assert await service.suggest_claims_for_vendor(_TENANT, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_unassigned_signatures_aggregates() -> None:
    service, *_ = _make_service()
    # 3 unassigned leads.
    leads = [(uuid.uuid4(), "L1"), (uuid.uuid4(), "L2"), (uuid.uuid4(), "L3")]
    service._repo.list_unassigned_leads = AsyncMock(return_value=leads)
    service._repo.count_unassigned_leads = AsyncMock(return_value=5)  # > 3 → capped

    async def latest_payload_values(_t, *, event_type, external_ids, payload_key):
        if payload_key == "utm_source__c":
            return {"L1": "fb_dima", "L2": "fb_dima", "L3": "google_x"}
        return {}

    service._ingest.latest_payload_values = AsyncMock(  # type: ignore[attr-defined]
        side_effect=latest_payload_values
    )

    out = await service.unassigned_signatures(_TENANT, lead_limit=3)
    assert out.scanned == 3
    assert out.capped is True
    top = out.items[0]
    assert (top.match_field, top.value, top.lead_count) == ("utm_source", "fb_dima", 2)
    assert any(
        i.value == "google_x" and i.lead_count == 1 for i in out.items
    )
