"""Tree-assembly tests for the attribution funnel analytics (ENG-450, Block D).

Unit style (no Postgres fixture): a fake repo returns canned aggregate rows so
the pure tree-building + cross-domain attribution logic is exercised directly.
The SQL itself is verified separately against a real DB.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.attribution.service import AttributionService
from packages.core.exceptions import ValidationError
from packages.core.types import TenantId

_TENANT = TenantId(uuid.uuid4())


class _Node:
    def __init__(self, level: str, slug: str, label: str) -> None:
        self.id = uuid.uuid4()
        self.level = level
        self.slug = slug
        self.label = label


def _service_with_nodes(nodes: list[_Node]) -> tuple[AttributionService, MagicMock]:
    session = MagicMock()
    session.flush = AsyncMock()
    service = AttributionService(session)
    repo = MagicMock()

    async def list_nodes(_t, *, level=None):
        return [n for n in nodes if level is None or n.level == level]

    async def find_node(_t, *, level, slug):
        return next(
            (n for n in nodes if n.level == level and n.slug == slug), None
        )

    repo.list_nodes = AsyncMock(side_effect=list_nodes)
    repo.find_node = AsyncMock(side_effect=find_node)
    # ENG-572: get_attribution_tree enriches vendor nodes from the vendor entity.
    repo.list_vendors = AsyncMock(return_value=[])
    service._repo = repo  # type: ignore[attr-defined]
    return service, repo


@pytest.mark.asyncio
async def test_tree_rolls_up_and_sorts_by_leads() -> None:
    fb = _Node("channel", "facebook", "Facebook")
    google = _Node("channel", "google", "Google")
    vendor = _Node("vendor", "dima", "Dima")
    camp = _Node("campaign", "spring", "Spring")
    service, repo = _service_with_nodes([fb, google, vendor, camp])

    # Facebook (no vendor) has 2 + 3 leads across two campaigns; Google 1 lead.
    repo.count_leads_by_chain = AsyncMock(
        return_value=[
            (None, fb.id, camp.id, 2),
            (None, fb.id, None, 3),
            (vendor.id, google.id, None, 1),
        ]
    )
    repo.count_needs_review = AsyncMock(return_value=7)
    repo.map_persons_to_chain = AsyncMock(return_value=[])

    tree = await service.get_attribution_tree(_TENANT)

    assert tree.total_leads == 6
    assert tree.needs_review == 7
    # Two top-level vendor buckets: "(unassigned)" (5 leads) before "dima" (1).
    assert [n.label for n in tree.nodes] == ["(unassigned)", "Dima"]
    unassigned = tree.nodes[0]
    assert unassigned.leads == 5
    # Its single channel is Facebook, with two campaign children (3-lead first).
    assert len(unassigned.children) == 1
    fb_node = unassigned.children[0]
    assert fb_node.label == "Facebook"
    assert fb_node.leads == 5
    assert [c.leads for c in fb_node.children] == [3, 2]


@pytest.mark.asyncio
async def test_tree_attributes_collected_and_consults() -> None:
    fb = _Node("channel", "facebook", "Facebook")
    service, repo = _service_with_nodes([fb])
    p1, p2 = uuid.uuid4(), uuid.uuid4()

    repo.count_leads_by_chain = AsyncMock(return_value=[(None, fb.id, None, 2)])
    repo.count_needs_review = AsyncMock(return_value=0)
    repo.map_persons_to_chain = AsyncMock(
        return_value=[(None, fb.id, None, p1), (None, fb.id, None, p2)]
    )

    tree = await service.get_attribution_tree(
        _TENANT,
        collected_by_person={p1: 1000.0, p2: 250.5},
        consults_by_person={p1: (1, 1), p2: (1, 0)},
    )

    node = tree.nodes[0].children[0]  # facebook channel
    assert node.collected_amount == 1250.5
    assert node.consults_scheduled == 2
    assert node.consults_attended == 1
    assert tree.collected_amount == 1250.5


@pytest.mark.asyncio
async def test_tree_period_enriches_flat_fee_and_cpl() -> None:
    vnode = _Node("vendor", "dima", "Dima")
    service, repo = _service_with_nodes([vnode])
    repo.count_leads_by_chain = AsyncMock(return_value=[(vnode.id, None, None, 3)])
    repo.count_needs_review = AsyncMock(return_value=0)
    repo.map_persons_to_chain = AsyncMock(return_value=[])
    repo.list_vendors = AsyncMock(
        return_value=[
            MagicMock(
                slug="dima",
                color="#2563eb",
                flat_monthly_fee=True,
                monthly_fee=Decimal("6000"),
            )
        ]
    )

    tree = await service.get_attribution_tree(_TENANT, period="2026-05")
    node = tree.nodes[0]
    assert node.label == "Dima"
    assert node.color == "#2563eb"
    assert node.monthly_cost == 6000.0
    assert node.cost_per_lead == 2000.0  # 6000 / 3 leads


@pytest.mark.asyncio
async def test_tree_no_period_sets_color_but_no_cost() -> None:
    vnode = _Node("vendor", "dima", "Dima")
    service, repo = _service_with_nodes([vnode])
    repo.count_leads_by_chain = AsyncMock(return_value=[(vnode.id, None, None, 3)])
    repo.count_needs_review = AsyncMock(return_value=0)
    repo.map_persons_to_chain = AsyncMock(return_value=[])
    repo.list_vendors = AsyncMock(
        return_value=[
            MagicMock(
                slug="dima",
                color="#000000",
                flat_monthly_fee=True,
                monthly_fee=Decimal("6000"),
            )
        ]
    )

    tree = await service.get_attribution_tree(_TENANT)  # no period
    node = tree.nodes[0]
    assert node.color == "#000000"
    assert node.monthly_cost is None
    assert node.cost_per_lead is None


@pytest.mark.asyncio
async def test_tree_period_uses_per_month_cost_override() -> None:
    vnode = _Node("vendor", "romi", "ROMI")
    service, repo = _service_with_nodes([vnode])
    repo.count_leads_by_chain = AsyncMock(return_value=[(vnode.id, None, None, 4)])
    repo.count_needs_review = AsyncMock(return_value=0)
    repo.map_persons_to_chain = AsyncMock(return_value=[])
    repo.list_vendors = AsyncMock(
        return_value=[
            MagicMock(
                slug="romi", color=None, flat_monthly_fee=False, monthly_fee=None
            )
        ]
    )
    repo.find_vendor_cost = AsyncMock(
        return_value=MagicMock(amount=Decimal("8000"))
    )

    tree = await service.get_attribution_tree(_TENANT, period="2026-05")
    node = tree.nodes[0]
    assert node.monthly_cost == 8000.0
    assert node.cost_per_lead == 2000.0  # 8000 / 4 leads


@pytest.mark.asyncio
async def test_drill_down_requires_a_level() -> None:
    service, _repo = _service_with_nodes([])
    with pytest.raises(ValidationError):
        await service.list_leads_for_chain_node(_TENANT)


@pytest.mark.asyncio
async def test_drill_down_resolves_slugs_and_none_sentinel() -> None:
    fb = _Node("channel", "facebook", "Facebook")
    service, repo = _service_with_nodes([fb])
    repo.list_lead_attributions_for_node = AsyncMock(return_value=(0, []))
    service._identity.list_by_ids = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    # vendor="__none__" → NULL bucket match; channel="facebook" → its id.
    out = await service.list_leads_for_chain_node(
        _TENANT, vendor="__none__", channel="facebook"
    )
    assert out.total == 0
    _args, kwargs = repo.list_lead_attributions_for_node.call_args
    assert kwargs["match_vendor"] is True and kwargs["vendor_id"] is None
    assert kwargs["match_channel"] is True and kwargs["channel_id"] == fb.id
    assert kwargs["match_campaign"] is False


@pytest.mark.asyncio
async def test_drill_down_unknown_slug_returns_empty_not_null_bucket() -> None:
    # An unknown channel slug (not the __none__ sentinel) resolves to no node →
    # the drill-down returns an empty set WITHOUT querying the repo, rather than
    # silently falling back to the NULL/unassigned bucket.
    service, repo = _service_with_nodes([])
    repo.list_lead_attributions_for_node = AsyncMock(return_value=(0, []))
    service._identity.list_by_ids = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    out = await service.list_leads_for_chain_node(_TENANT, channel="does-not-exist")
    assert out.total == 0 and out.items == []
    repo.list_lead_attributions_for_node.assert_not_called()


@pytest.mark.asyncio
async def test_drill_down_enriches_rows_with_identity_and_cash() -> None:
    fb = _Node("channel", "facebook", "Facebook")
    service, repo = _service_with_nodes([fb])
    person_uid = uuid.uuid4()

    row = MagicMock()
    row.person_uid = person_uid
    row.sf_lead_id = "00Q123"
    row.vendor_id = None
    row.channel_id = fb.id
    row.campaign_id = None
    row.created_by_name = "Olga Kolomyza"
    row.method = "manual"
    row.source_signal = "manual"
    row.confidence = 0.9
    row.resolved_at = __import__("datetime").datetime(
        2026, 6, 15, tzinfo=__import__("datetime").UTC
    )
    repo.list_lead_attributions_for_node = AsyncMock(return_value=(1, [row]))

    ident_email = MagicMock(kind="email", value="lead@example.com")
    ident_phone = MagicMock(kind="phone", value="+15550001111")
    person = MagicMock(
        id=person_uid,
        display_name="Vladyslav Romanchuk",
        identifiers=[ident_email, ident_phone],
    )
    service._identity.list_by_ids = AsyncMock(return_value=[person])  # type: ignore[attr-defined]

    out = await service.list_leads_for_chain_node(
        _TENANT,
        channel="facebook",
        collected_by_person={person_uid: 1234.567},
    )

    assert out.total == 1
    item = out.items[0]
    assert item.person_uid == person_uid
    assert item.display_name == "Vladyslav Romanchuk"
    assert item.email == "lead@example.com"
    assert item.phone == "+15550001111"
    assert item.channel == "Facebook"  # label resolved from node vocabulary
    assert item.vendor is None and item.campaign is None
    assert item.created_by_name == "Olga Kolomyza"
    assert item.collected_amount == 1234.57  # rounded to cents


@pytest.mark.asyncio
async def test_empty_tree_is_zeroed_not_errored() -> None:
    service, repo = _service_with_nodes([])
    repo.count_leads_by_chain = AsyncMock(return_value=[])
    repo.count_needs_review = AsyncMock(return_value=0)
    repo.map_persons_to_chain = AsyncMock(return_value=[])

    tree = await service.get_attribution_tree(_TENANT)
    assert tree.total_leads == 0
    assert tree.needs_review == 0
    assert tree.collected_amount == 0.0
    assert tree.nodes == []
