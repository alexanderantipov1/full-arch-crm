"""Service tests for the vendor entity (ENG-570).

Mirrors the in-memory fake-repo style of ``test_service.py`` (no Postgres in the
unit suite). Covers: ensure_node mirroring vendor nodes into vendors, the
in-house vs agency kind, the Unassigned bucket never becoming a vendor, manual
CRUD, slug derivation/dedup, and the back-link when a node appears after a
manually-created vendor.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.attribution.models import SourceNode, Vendor
from packages.attribution.schemas import (
    SourceNodeIn,
    VendorCostIn,
    VendorIn,
    VendorUpdateIn,
)
from packages.attribution.service import AttributionService
from packages.core.exceptions import ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId

_TENANT = TenantId(uuid.uuid4())
_PRINCIPAL = Principal(id=uuid.uuid4(), email="ops@example.com")


def _make_service() -> tuple[AttributionService, list[SourceNode], list[Vendor]]:
    nodes: list[SourceNode] = []
    vendors: list[Vendor] = []
    session = MagicMock()
    session.flush = AsyncMock()
    service = AttributionService(session)

    async def find_node(_t, *, level, slug):
        return next(
            (n for n in nodes if n.level == level and n.slug == slug), None
        )

    async def add_node(n):
        n.id = uuid.uuid4()
        nodes.append(n)
        return n

    async def find_vendor_by_slug(_t, slug):
        return next((v for v in vendors if v.slug == slug), None)

    async def find_vendor(_t, vid):
        return next((v for v in vendors if v.id == vid), None)

    async def add_vendor(v):
        v.id = uuid.uuid4()
        vendors.append(v)
        return v

    async def list_vendors(_t, *, active_only=False):
        return [v for v in vendors if not active_only or v.active]

    costs: list = []

    async def list_vendor_costs(_t, vendor_id):
        return [c for c in costs if c.vendor_id == vendor_id]

    async def find_vendor_cost(_t, vendor_id, period_month):
        return next(
            (
                c
                for c in costs
                if c.vendor_id == vendor_id and c.period_month == period_month
            ),
            None,
        )

    async def add_vendor_cost(c):
        c.id = uuid.uuid4()
        costs.append(c)
        return c

    async def delete_vendor_cost(c):
        costs.remove(c)

    repo = MagicMock()
    repo.find_node = AsyncMock(side_effect=find_node)
    repo.add_node = AsyncMock(side_effect=add_node)
    repo.find_vendor_by_slug = AsyncMock(side_effect=find_vendor_by_slug)
    repo.find_vendor = AsyncMock(side_effect=find_vendor)
    repo.add_vendor = AsyncMock(side_effect=add_vendor)
    repo.list_vendors = AsyncMock(side_effect=list_vendors)
    repo.list_vendor_costs = AsyncMock(side_effect=list_vendor_costs)
    repo.find_vendor_cost = AsyncMock(side_effect=find_vendor_cost)
    repo.add_vendor_cost = AsyncMock(side_effect=add_vendor_cost)
    repo.delete_vendor_cost = AsyncMock(side_effect=delete_vendor_cost)
    service._repo = repo  # type: ignore[attr-defined]
    service._audit = MagicMock(record=AsyncMock())  # type: ignore[attr-defined]
    return service, nodes, vendors


@pytest.mark.asyncio
async def test_ensure_vendor_node_mirrors_to_entity() -> None:
    service, _nodes, vendors = _make_service()
    node = await service.ensure_node(
        _TENANT, SourceNodeIn(level="vendor", slug="dima", label="Dima")
    )
    assert len(vendors) == 1
    assert vendors[0].slug == "dima"
    assert vendors[0].kind == "agency"
    assert vendors[0].source_node_id == node.id
    # Idempotent: re-ensuring the same node does not duplicate the vendor.
    await service.ensure_node(
        _TENANT, SourceNodeIn(level="vendor", slug="dima", label="Dima Media")
    )
    assert len(vendors) == 1


@pytest.mark.asyncio
async def test_in_house_node_creates_in_house_vendor() -> None:
    service, _nodes, vendors = _make_service()
    await service.ensure_node(
        _TENANT, SourceNodeIn(level="vendor", slug="in_house", label="In-house")
    )
    assert vendors[0].kind == "in_house"


@pytest.mark.asyncio
async def test_unassigned_node_is_not_a_vendor() -> None:
    service, _nodes, vendors = _make_service()
    await service.ensure_node(
        _TENANT, SourceNodeIn(level="vendor", slug="unassigned", label="Unassigned")
    )
    assert vendors == []


@pytest.mark.asyncio
async def test_channel_node_creates_no_vendor() -> None:
    service, _nodes, vendors = _make_service()
    await service.ensure_node(
        _TENANT, SourceNodeIn(level="channel", slug="facebook", label="Facebook")
    )
    assert vendors == []


@pytest.mark.asyncio
async def test_create_vendor_derives_slug_and_dedups() -> None:
    service, _nodes, vendors = _make_service()
    out = await service.create_vendor(
        _TENANT, VendorIn(name="ROMI Agency"), principal=_PRINCIPAL
    )
    assert out.slug == "romi_agency"
    assert out.source_node_id is None  # no node learned yet
    assert len(vendors) == 1
    # Same derived slug → rejected.
    with pytest.raises(ValidationError):
        await service.create_vendor(
            _TENANT, VendorIn(name="ROMI Agency"), principal=_PRINCIPAL
        )


@pytest.mark.asyncio
async def test_create_vendor_rejects_unknown_kind() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.create_vendor(
            _TENANT, VendorIn(name="X", kind="reseller"), principal=_PRINCIPAL
        )


@pytest.mark.asyncio
async def test_manual_vendor_backlinks_when_node_appears() -> None:
    service, _nodes, vendors = _make_service()
    # Operator creates the vendor before any traffic exists.
    await service.create_vendor(
        _TENANT, VendorIn(name="Daniel Creatives", slug="daniel"), principal=_PRINCIPAL
    )
    assert vendors[0].source_node_id is None
    # The resolver later produces the matching vendor node → back-link, no dup.
    node = await service.ensure_node(
        _TENANT, SourceNodeIn(level="vendor", slug="daniel", label="Daniel Creatives")
    )
    assert len(vendors) == 1
    assert vendors[0].source_node_id == node.id


@pytest.mark.asyncio
async def test_update_and_deactivate_vendor() -> None:
    service, _nodes, vendors = _make_service()
    created = await service.create_vendor(
        _TENANT, VendorIn(name="Acme"), principal=_PRINCIPAL
    )
    updated = await service.update_vendor(
        _TENANT,
        created.id,
        VendorUpdateIn(name="Acme Media", kind="in_house", color="#ff0000"),
        principal=_PRINCIPAL,
    )
    assert updated is not None
    assert updated.name == "Acme Media"
    assert updated.kind == "in_house"
    assert updated.color == "#ff0000"

    ok = await service.deactivate_vendor(_TENANT, created.id, principal=_PRINCIPAL)
    assert ok is True
    assert vendors[0].active is False

    # Unknown id → no-op signals.
    assert (
        await service.update_vendor(
            _TENANT, uuid.uuid4(), VendorUpdateIn(name="Nope"), principal=_PRINCIPAL
        )
        is None
    )
    assert (
        await service.deactivate_vendor(_TENANT, uuid.uuid4(), principal=_PRINCIPAL)
        is False
    )


@pytest.mark.asyncio
async def test_create_vendor_with_flat_monthly_fee() -> None:
    service, _nodes, _vendors = _make_service()
    out = await service.create_vendor(
        _TENANT,
        VendorIn(name="Flat Co", monthly_fee=5000, flat_monthly_fee=True),
        principal=_PRINCIPAL,
    )
    assert out.monthly_fee == 5000.0
    assert out.flat_monthly_fee is True
    assert out.fee_currency == "USD"


@pytest.mark.asyncio
async def test_update_vendor_fee_fields() -> None:
    service, _nodes, _vendors = _make_service()
    created = await service.create_vendor(
        _TENANT, VendorIn(name="Var Co"), principal=_PRINCIPAL
    )
    updated = await service.update_vendor(
        _TENANT,
        created.id,
        VendorUpdateIn(flat_monthly_fee=False, monthly_fee=1234.5),
        principal=_PRINCIPAL,
    )
    assert updated is not None
    assert updated.flat_monthly_fee is False
    assert updated.monthly_fee == 1234.5


@pytest.mark.asyncio
async def test_vendor_month_cost_upsert_list_delete() -> None:
    service, _nodes, _vendors = _make_service()
    vendor = await service.create_vendor(
        _TENANT,
        VendorIn(name="Monthly Co", flat_monthly_fee=False),
        principal=_PRINCIPAL,
    )
    # set March
    c1 = await service.set_vendor_cost(
        _TENANT,
        vendor.id,
        VendorCostIn(period_month="2026-03", amount=7000),
        principal=_PRINCIPAL,
    )
    assert c1 is not None and c1.amount == 7000.0
    # upsert March (same month → update in place, not a second row)
    await service.set_vendor_cost(
        _TENANT,
        vendor.id,
        VendorCostIn(period_month="2026-03", amount=7500, note="raised"),
        principal=_PRINCIPAL,
    )
    # add April
    await service.set_vendor_cost(
        _TENANT,
        vendor.id,
        VendorCostIn(period_month="2026-04", amount=6000),
        principal=_PRINCIPAL,
    )
    rows = await service.list_vendor_costs(_TENANT, vendor.id)
    assert {r.period_month: r.amount for r in rows} == {
        "2026-03": 7500.0,
        "2026-04": 6000.0,
    }
    # delete March
    assert (
        await service.delete_vendor_cost(
            _TENANT, vendor.id, "2026-03", principal=_PRINCIPAL
        )
        is True
    )
    rows = await service.list_vendor_costs(_TENANT, vendor.id)
    assert [r.period_month for r in rows] == ["2026-04"]


@pytest.mark.asyncio
async def test_set_vendor_cost_unknown_vendor_returns_none() -> None:
    service, *_ = _make_service()
    out = await service.set_vendor_cost(
        _TENANT,
        uuid.uuid4(),
        VendorCostIn(period_month="2026-03", amount=100),
        principal=_PRINCIPAL,
    )
    assert out is None


@pytest.mark.asyncio
async def test_list_vendors_active_only() -> None:
    service, _nodes, _vendors = _make_service()
    a = await service.create_vendor(
        _TENANT, VendorIn(name="A"), principal=_PRINCIPAL
    )
    await service.create_vendor(_TENANT, VendorIn(name="B"), principal=_PRINCIPAL)
    await service.deactivate_vendor(_TENANT, a.id, principal=_PRINCIPAL)

    all_rows = await service.list_vendors(_TENANT)
    active = await service.list_vendors(_TENANT, active_only=True)
    assert len(all_rows) == 2
    assert [v.name for v in active] == ["B"]
