"""Tests for IngestService.snapshot_observed_schema (ENG-429).

REST sources (CareStack) derive their full-fidelity schema from the union of
observed payload keys. Drives the real service against an in-memory registry
store plus a mocked payload sampler.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.models import SourceObjectField
from packages.ingest.service import IngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_service(
    payloads: list[dict[str, object]],
) -> tuple[IngestService, list[SourceObjectField]]:
    store: list[SourceObjectField] = []
    session = MagicMock()
    session.add = MagicMock(side_effect=store.append)
    session.flush = AsyncMock()
    service = IngestService(session)

    async def _list(tenant_id, *, provider, object_name):
        return [
            r for r in store if r.provider == provider and r.object_name == object_name
        ]

    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._repo.list_object_fields = AsyncMock(side_effect=_list)  # type: ignore[attr-defined]
    service._repo.sample_recent_payloads = AsyncMock(return_value=payloads)  # type: ignore[attr-defined]
    return service, store


@pytest.mark.asyncio
async def test_snapshot_unions_keys_and_infers_types() -> None:
    payloads = [
        {"id": 1, "firstName": "A", "active": True},
        {"id": 2, "lastName": "B", "tags": ["x"], "address": {"city": "C"}},
    ]
    service, store = _make_service(payloads)
    diff = await service.snapshot_observed_schema(
        _TENANT_ID,
        provider="carestack",
        object_name="patient",
        event_type="carestack.patient.upsert",
    )
    by_name = {r.field_name: r for r in store}
    assert set(by_name) == {"id", "firstName", "active", "lastName", "tags", "address"}
    assert by_name["id"].field_type == "number"
    assert by_name["firstName"].field_type == "string"
    assert by_name["active"].field_type == "boolean"
    assert by_name["tags"].field_type == "array"
    assert by_name["address"].field_type == "object"
    assert sorted(diff.added) == sorted(by_name)


@pytest.mark.asyncio
async def test_snapshot_empty_sample_is_noop() -> None:
    service, store = _make_service([])
    diff = await service.snapshot_observed_schema(
        _TENANT_ID,
        provider="carestack",
        object_name="patient",
        event_type="carestack.patient.upsert",
    )
    assert diff.has_changes is False
    assert store == []  # must NOT deactivate / write anything


@pytest.mark.asyncio
async def test_snapshot_prefers_concrete_type_over_null() -> None:
    # First sample has a null middleName; a later one has a string.
    payloads = [{"middleName": None}, {"middleName": "X"}]
    service, store = _make_service(payloads)
    await service.snapshot_observed_schema(
        _TENANT_ID,
        provider="carestack",
        object_name="patient",
        event_type="carestack.patient.upsert",
    )
    assert next(r for r in store if r.field_name == "middleName").field_type == "string"
