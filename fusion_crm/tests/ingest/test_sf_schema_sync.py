"""Tests for the reusable SfSchemaSync helper (ENG-427)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.schemas import SchemaDiffOut
from packages.ingest.sf_schema_sync import SfSchemaSync

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_STATIC = "Id, OwnerId, Owner.Name, CreatedDate"


def _helper() -> tuple[SfSchemaSync, MagicMock, MagicMock]:
    ingest = MagicMock(spec=["get_object_schema", "sync_object_schema"])
    sf = MagicMock()
    return (
        SfSchemaSync(ingest, sf, object_name="Lead", static_projection=_STATIC),
        ingest,
        sf,
    )


def _row(name: str, *, readable: bool = True, selectable: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        field_name=name, readable=readable, meta={"selectable": selectable}
    )


@pytest.mark.asyncio
async def test_projection_appends_static_relationship_fields() -> None:
    helper, ingest, _sf = _helper()
    ingest.get_object_schema = AsyncMock(return_value=[_row("Id"), _row("OwnerId")])
    projection = await helper.projection(_TENANT_ID)
    fields = [f.strip() for f in projection.split(",")]
    # describe-style scalar fields plus the preserved relationship traversal.
    assert "Id" in fields and "OwnerId" in fields
    assert "Owner.Name" in fields


@pytest.mark.asyncio
async def test_projection_static_fallback_when_describe_empty() -> None:
    helper, ingest, sf = _helper()
    ingest.get_object_schema = AsyncMock(return_value=[])
    sf.describe = AsyncMock(return_value={"fields": []})
    assert await helper.projection(_TENANT_ID) == _STATIC


@pytest.mark.asyncio
async def test_projection_static_fallback_when_describe_raises() -> None:
    helper, ingest, sf = _helper()
    ingest.get_object_schema = AsyncMock(return_value=[])
    sf.describe = AsyncMock(side_effect=RuntimeError("boom"))
    assert await helper.projection(_TENANT_ID) == _STATIC


@pytest.mark.asyncio
async def test_sync_delegates_and_returns_gap() -> None:
    helper, ingest, sf = _helper()
    sf.describe = AsyncMock(return_value={"fields": [{"name": "Id", "type": "id"}]})
    sf.describe_tooling_fields = AsyncMock(
        return_value=[{"QualifiedApiName": "CampaignId", "DataType": "Lookup"}]
    )
    diff = SchemaDiffOut(provider="salesforce", object_name="Lead", added=["Id"])
    ingest.sync_object_schema = AsyncMock(return_value=diff)
    out_diff, gap = await helper.sync(_TENANT_ID)
    assert out_diff is diff
    assert gap == ["CampaignId"]
