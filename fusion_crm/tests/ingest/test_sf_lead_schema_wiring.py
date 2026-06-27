"""Block B wiring tests: SfLeadIngestService dynamic projection + sync_schema.

Exercises the ENG-427 seam on the Lead service without a live Salesforce:
* ``_projection`` builds the SOQL field list from the schema registry when it
  is populated, and falls back to the static projection otherwise;
* ``sync_schema`` reconciles describe + Tooling into the registry and returns
  the FLS gap.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.schemas import SchemaDiffOut
from packages.ingest.sf_lead_service import _SF_LEAD_PROJECTION, SfLeadIngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _service() -> tuple[SfLeadIngestService, MagicMock, MagicMock]:
    session = MagicMock()
    sf_client = MagicMock()
    service = SfLeadIngestService(session=session, sf_client=sf_client)
    service._ingest = MagicMock(spec=["get_object_schema", "sync_object_schema"])
    return service, service._ingest, sf_client


def _row(name: str, *, readable: bool = True, selectable: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        field_name=name, readable=readable, meta={"selectable": selectable}
    )


@pytest.mark.asyncio
async def test_projection_built_from_registry_when_populated() -> None:
    service, ingest, _sf = _service()
    ingest.get_object_schema = AsyncMock(
        return_value=[
            _row("Id"),
            _row("CreatedById"),
            _row("SSN__c", readable=False),  # FLS-blocked → excluded
            _row("Address", selectable=False),  # compound parent → excluded
        ]
    )
    projection = await service._projection(_TENANT_ID)
    fields = [f.strip() for f in projection.split(",")]
    assert "Id" in fields and "CreatedById" in fields
    assert "SSN__c" not in fields
    assert "Address" not in fields


@pytest.mark.asyncio
async def test_projection_falls_back_to_static_when_registry_empty() -> None:
    service, ingest, sf = _service()
    ingest.get_object_schema = AsyncMock(return_value=[])
    # Bare mock describe is not awaitable → caught → static fallback.
    projection = await service._projection(_TENANT_ID)
    assert projection == _SF_LEAD_PROJECTION


@pytest.mark.asyncio
async def test_projection_uses_live_describe_when_registry_empty() -> None:
    service, ingest, sf = _service()
    ingest.get_object_schema = AsyncMock(return_value=[])
    sf.describe = AsyncMock(
        return_value={"fields": [{"name": "Id", "type": "id"}, {"name": "X__c", "type": "string"}]}
    )
    projection = await service._projection(_TENANT_ID)
    fields = [f.strip() for f in projection.split(",")]
    assert "Id" in fields and "X__c" in fields
    # Relationship field from the static projection is preserved (ENG-408).
    assert "Owner.Name" in fields


@pytest.mark.asyncio
async def test_sync_schema_reconciles_and_returns_fls_gap() -> None:
    service, ingest, sf = _service()
    sf.describe = AsyncMock(
        return_value={"fields": [{"name": "Id", "type": "id"}]}
    )
    sf.describe_tooling_fields = AsyncMock(
        return_value=[
            {"QualifiedApiName": "Id", "DataType": "Id"},
            {"QualifiedApiName": "CreatedById", "DataType": "Lookup(User)"},
        ]
    )
    diff = SchemaDiffOut(provider="salesforce", object_name="Lead", added=["Id"])
    ingest.sync_object_schema = AsyncMock(return_value=diff)

    out_diff, gap = await service.sync_schema(_TENANT_ID)

    assert out_diff is diff
    assert gap == ["CreatedById"]  # in Tooling, hidden from describe by FLS
    # The registry sync received both the readable Id and the FLS-blocked field.
    observed: list[Any] = ingest.sync_object_schema.await_args.kwargs["fields"]
    by_name = {o.name: o for o in observed}
    assert by_name["Id"].readable is True
    assert by_name["CreatedById"].readable is False
