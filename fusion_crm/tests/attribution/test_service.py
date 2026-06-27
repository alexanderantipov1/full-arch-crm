"""Service tests for AttributionService (ENG-447).

No Postgres fixture in the unit suite, so the real service runs against an
in-memory store; the fake repo assigns the PK that a DB flush would normally
populate.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.attribution.models import LeadAttribution, MappingRule, SourceNode
from packages.attribution.schemas import (
    LeadAttributionIn,
    MappingRuleIn,
    SourceNodeIn,
)
from packages.attribution.service import (
    DEFAULT_CHANNELS,
    DEFAULT_VENDORS,
    AttributionService,
)
from packages.core.exceptions import ValidationError
from packages.core.security import Principal
from packages.core.types import TenantId

_TENANT = TenantId(uuid.uuid4())
_PRINCIPAL = Principal(id=uuid.uuid4(), email="ops@example.com")


def _make_service() -> tuple[AttributionService, list, list, list]:
    nodes: list[SourceNode] = []
    leads: list[LeadAttribution] = []
    rules: list[MappingRule] = []
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

    async def list_nodes(_t, *, level=None):
        return [n for n in nodes if level is None or n.level == level]

    async def find_la(_t, puid):
        return next((row for row in leads if row.person_uid == puid), None)

    async def add_la(row):
        row.id = uuid.uuid4()
        leads.append(row)
        return row

    async def add_rule(rule):
        rule.id = uuid.uuid4()
        rules.append(rule)
        return rule

    async def find_rule(_t, rule_id):
        return next((r for r in rules if r.id == rule_id), None)

    async def delete_rule(rule):
        rules.remove(rule)

    # Vendor entity store (ENG-570) — ensure_node now mirrors vendor-level nodes
    # into vendors, so the fake repo must answer the vendor lookups too.
    vendors: list = []

    async def find_vendor_by_slug(_t, slug):
        return next((v for v in vendors if v.slug == slug), None)

    async def add_vendor(v):
        v.id = uuid.uuid4()
        vendors.append(v)
        return v

    repo = MagicMock()
    repo.find_rule = AsyncMock(side_effect=find_rule)
    repo.delete_rule = AsyncMock(side_effect=delete_rule)
    repo.find_node = AsyncMock(side_effect=find_node)
    repo.add_node = AsyncMock(side_effect=add_node)
    repo.list_nodes = AsyncMock(side_effect=list_nodes)
    repo.find_lead_attribution = AsyncMock(side_effect=find_la)
    repo.add_lead_attribution = AsyncMock(side_effect=add_la)
    repo.add_rule = AsyncMock(side_effect=add_rule)
    repo.find_vendor_by_slug = AsyncMock(side_effect=find_vendor_by_slug)
    repo.add_vendor = AsyncMock(side_effect=add_vendor)
    service._repo = repo  # type: ignore[attr-defined]
    service._audit = MagicMock(record=AsyncMock())  # type: ignore[attr-defined]
    return service, nodes, leads, rules


@pytest.mark.asyncio
async def test_ensure_node_is_idempotent() -> None:
    service, nodes, _l, _r = _make_service()
    a = await service.ensure_node(
        _TENANT, SourceNodeIn(level="channel", slug="facebook", label="Facebook")
    )
    b = await service.ensure_node(
        _TENANT, SourceNodeIn(level="channel", slug="facebook", label="Facebook (FB)")
    )
    assert a.id == b.id  # same node reused
    assert len(nodes) == 1
    assert b.label == "Facebook (FB)"  # label refreshed


@pytest.mark.asyncio
async def test_ensure_node_rejects_unknown_level() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.ensure_node(
            _TENANT, SourceNodeIn(level="planet", slug="x", label="X")
        )


@pytest.mark.asyncio
async def test_seed_default_nodes() -> None:
    service, nodes, _l, _r = _make_service()
    n = await service.seed_default_nodes(_TENANT)
    assert n == len(DEFAULT_CHANNELS) + len(DEFAULT_VENDORS)
    assert len(nodes) == n
    # re-run is idempotent
    await service.seed_default_nodes(_TENANT)
    assert len(nodes) == n


@pytest.mark.asyncio
async def test_upsert_lead_attribution_creates_then_updates() -> None:
    service, _n, leads, _r = _make_service()
    puid = uuid.uuid4()
    ch = uuid.uuid4()
    out = await service.upsert_lead_attribution(
        _TENANT,
        LeadAttributionIn(
            person_uid=puid, channel_id=ch, method="auto", source_signal="digital"
        ),
    )
    assert out.channel_id == ch
    assert len(leads) == 1
    ch2 = uuid.uuid4()
    out2 = await service.upsert_lead_attribution(
        _TENANT, LeadAttributionIn(person_uid=puid, channel_id=ch2, method="auto")
    )
    assert out2.channel_id == ch2  # updated in place
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_manual_attribution_is_sticky() -> None:
    service, *_ = _make_service()
    puid = uuid.uuid4()
    manual_ch = uuid.uuid4()
    await service.upsert_lead_attribution(
        _TENANT,
        LeadAttributionIn(person_uid=puid, channel_id=manual_ch, method="manual"),
    )
    # An auto re-resolution must NOT clobber the manual choice.
    out = await service.upsert_lead_attribution(
        _TENANT,
        LeadAttributionIn(person_uid=puid, channel_id=uuid.uuid4(), method="auto"),
    )
    assert out.method == "manual"
    assert out.channel_id == manual_ch


@pytest.mark.asyncio
async def test_create_rule_rejects_unknown_level() -> None:
    service, *_ = _make_service()
    with pytest.raises(ValidationError):
        await service.create_rule(
            _TENANT,
            MappingRuleIn(
                match_field="utm_campaign",
                match_value="Dima%",
                set_level="galaxy",
                set_node_id=uuid.uuid4(),
            ),
            principal=_PRINCIPAL,
        )


@pytest.mark.asyncio
async def test_resolve_and_store_ensures_nodes_and_persists() -> None:
    from packages.attribution.waterfall import LeadSignals

    service, nodes, leads, _r = _make_service()
    puid = uuid.uuid4()
    out = await service.resolve_and_store(
        _TENANT,
        puid,
        LeadSignals(utm_source="Facebook", campaign="Galleria Kickoff Campaign"),
        sf_lead_id="00Q1",
    )
    assert out.source_signal == "digital"
    assert out.channel_id is not None
    assert out.campaign_id is not None
    slugs = {(n.level, n.slug) for n in nodes}
    assert ("channel", "facebook") in slugs
    assert ("campaign", "galleria_kickoff_campaign") in slugs
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_resolve_and_store_manual_records_agent() -> None:
    from packages.attribution.waterfall import LeadSignals

    service, _n, leads, _r = _make_service()
    out = await service.resolve_and_store(
        _TENANT, uuid.uuid4(), LeadSignals(created_by_name="Olga Kolomyza")
    )
    assert out.source_signal == "manual"
    assert out.created_by_name == "Olga Kolomyza"
    assert leads[0].channel_id is not None


@pytest.mark.asyncio
async def test_create_rule_ok() -> None:
    service, _n, _l, rules = _make_service()
    out = await service.create_rule(
        _TENANT,
        MappingRuleIn(
            match_field="utm_campaign",
            match_op="prefix",
            match_value="Dima",
            set_level="vendor",
            set_node_id=uuid.uuid4(),
        ),
        principal=_PRINCIPAL,
    )
    assert out.set_level == "vendor"
    assert len(rules) == 1


@pytest.mark.asyncio
async def test_delete_rule() -> None:
    service, _n, _l, rules = _make_service()
    out = await service.create_rule(
        _TENANT,
        MappingRuleIn(
            match_field="utm_campaign",
            match_value="Dima",
            set_level="vendor",
            set_node_id=uuid.uuid4(),
        ),
        principal=_PRINCIPAL,
    )
    assert await service.delete_rule(_TENANT, out.id, principal=_PRINCIPAL) is True
    assert len(rules) == 0
    # deleting again → not found
    assert await service.delete_rule(_TENANT, out.id, principal=_PRINCIPAL) is False


@pytest.mark.asyncio
async def test_set_override_is_manual_and_sticky() -> None:
    from packages.attribution.schemas import LeadOverrideIn, SourceRef
    from packages.attribution.waterfall import LeadSignals

    service, _n, leads, _r = _make_service()
    puid = uuid.uuid4()
    out = await service.set_override(
        _TENANT,
        puid,
        LeadOverrideIn(
            vendor=SourceRef(slug="dima", label="Dima"),
            channel=SourceRef(slug="facebook", label="Facebook"),
        ),
        principal=_PRINCIPAL,
    )
    assert out.method == "manual"
    assert out.vendor_id is not None and out.channel_id is not None
    vendor_id = out.vendor_id
    # An auto re-resolution must NOT clobber the manual override.
    out2 = await service.resolve_and_store(
        _TENANT, puid, LeadSignals(utm_source="Google")
    )
    assert out2.method == "manual"
    assert out2.vendor_id == vendor_id


@pytest.mark.asyncio
async def test_set_override_keeps_omitted_levels() -> None:
    from packages.attribution.schemas import LeadOverrideIn, SourceRef

    service, _n, _l, _r = _make_service()
    puid = uuid.uuid4()
    await service.set_override(
        _TENANT,
        puid,
        LeadOverrideIn(
            vendor=SourceRef(slug="dima", label="Dima"),
            channel=SourceRef(slug="facebook", label="Facebook"),
        ),
        principal=_PRINCIPAL,
    )
    # Second override touches only channel; vendor must be preserved.
    out = await service.set_override(
        _TENANT,
        puid,
        LeadOverrideIn(channel=SourceRef(slug="google", label="Google")),
        principal=_PRINCIPAL,
    )
    assert out.vendor_id is not None  # kept
    nodes = await service.list_nodes(_TENANT, level="channel")
    assert {n.slug for n in nodes} >= {"facebook", "google"}


@pytest.mark.asyncio
async def test_manual_enrichment_writes_audit() -> None:
    # create_rule / set_override are manual edits → each writes an audit row
    # (packages/attribution CLAUDE.md). Auto-resolution does not.
    from packages.attribution.schemas import LeadOverrideIn, SourceRef

    service, *_ = _make_service()
    await service.create_rule(
        _TENANT,
        MappingRuleIn(
            match_field="utm_campaign",
            match_value="Dima",
            set_level="vendor",
            set_node_id=uuid.uuid4(),
        ),
        principal=_PRINCIPAL,
    )
    await service.set_override(
        _TENANT,
        uuid.uuid4(),
        LeadOverrideIn(channel=SourceRef(slug="facebook", label="Facebook")),
        principal=_PRINCIPAL,
    )
    actions = {
        call.kwargs["action"] for call in service._audit.record.await_args_list
    }
    assert actions == {"attribution.rule.create", "attribution.lead.override"}


def test_source_node_slug_rejects_slash() -> None:
    # A '/' in a slug would break the analytics tree key split (ENG-450).
    import pytest as _pytest
    from pydantic import ValidationError as PydanticValidationError

    with _pytest.raises(PydanticValidationError):
        SourceNodeIn(level="channel", slug="a/b", label="A/B")
