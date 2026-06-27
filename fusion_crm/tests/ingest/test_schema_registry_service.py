"""Service-level tests for the full-fidelity schema registry (ENG-426).

``IngestService.sync_object_schema`` reconciles an observed source-object
schema against ``ingest.source_object_field`` and returns the drift shape.
The unit suite has no ingest-schema Postgres fixture, so we drive the real
service against an in-memory store that mimics the registry: the service
mutates ORM rows in place and re-reads them via ``list_object_fields``, so a
plain Python list of :class:`SourceObjectField` objects exercises the full
insert / reactivate / deactivate / type-change / readability logic across
successive calls.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.ingest.models import SourceObjectField
from packages.ingest.schemas import ObservedFieldIn
from packages.ingest.service import IngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_T0 = datetime(2026, 6, 14, 21, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 14, 22, 0, tzinfo=UTC)
_T2 = datetime(2026, 6, 14, 23, 0, tzinfo=UTC)


def _make_service() -> tuple[IngestService, list[SourceObjectField]]:
    """Real ``IngestService`` wired to an in-memory registry store."""
    store: list[SourceObjectField] = []
    session = MagicMock()
    session.add = MagicMock(side_effect=store.append)
    session.flush = AsyncMock()
    service = IngestService(session)

    async def _list(
        tenant_id: TenantId, *, provider: str, object_name: str
    ) -> list[SourceObjectField]:
        return [
            row
            for row in store
            if row.provider == provider and row.object_name == object_name
        ]

    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._repo.list_object_fields = AsyncMock(side_effect=_list)  # type: ignore[attr-defined]
    return service, store


def _f(name: str, *, field_type: str = "string", readable: bool = True) -> ObservedFieldIn:
    return ObservedFieldIn(name=name, field_type=field_type, readable=readable)


# --- validation ---


@pytest.mark.asyncio
async def test_sync_rejects_blank_provider() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.sync_object_schema(
            _TENANT_ID, provider="  ", object_name="Lead", fields=[], observed_at=_T0
        )


@pytest.mark.asyncio
async def test_sync_rejects_blank_object_name() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.sync_object_schema(
            _TENANT_ID, provider="salesforce", object_name="", fields=[], observed_at=_T0
        )


# --- diff behaviour ---


@pytest.mark.asyncio
async def test_first_sync_adds_all_fields() -> None:
    service, store = _make_service()
    diff = await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Id"), _f("CreatedById"), _f("Email")],
        observed_at=_T0,
    )
    assert sorted(diff.added) == ["CreatedById", "Email", "Id"]
    assert diff.removed == []
    assert diff.has_changes is True
    assert len(store) == 3
    assert all(row.active and row.first_seen_at == _T0 for row in store)


@pytest.mark.asyncio
async def test_resync_same_fields_is_idempotent() -> None:
    service, _ = _make_service()
    fields = [_f("Id"), _f("Email")]
    await service.sync_object_schema(
        _TENANT_ID, provider="salesforce", object_name="Lead", fields=fields, observed_at=_T0
    )
    diff = await service.sync_object_schema(
        _TENANT_ID, provider="salesforce", object_name="Lead", fields=fields, observed_at=_T1
    )
    assert diff.has_changes is False
    assert diff.added == [] and diff.removed == []


@pytest.mark.asyncio
async def test_new_field_is_detected() -> None:
    service, _ = _make_service()
    await service.sync_object_schema(
        _TENANT_ID, provider="salesforce", object_name="Lead", fields=[_f("Id")], observed_at=_T0
    )
    diff = await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Id"), _f("utm_source__c")],
        observed_at=_T1,
    )
    assert diff.added == ["utm_source__c"]
    assert diff.removed == []


@pytest.mark.asyncio
async def test_removed_field_is_deactivated_not_deleted() -> None:
    service, store = _make_service()
    await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Id"), _f("Legacy__c")],
        observed_at=_T0,
    )
    diff = await service.sync_object_schema(
        _TENANT_ID, provider="salesforce", object_name="Lead", fields=[_f("Id")], observed_at=_T1
    )
    assert diff.removed == ["Legacy__c"]
    legacy = next(r for r in store if r.field_name == "Legacy__c")
    assert legacy.active is False
    assert len(store) == 2  # row kept, not deleted


@pytest.mark.asyncio
async def test_reappearing_field_is_re_added() -> None:
    service, store = _make_service()
    await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Id"), _f("Flaky__c")],
        observed_at=_T0,
    )
    await service.sync_object_schema(
        _TENANT_ID, provider="salesforce", object_name="Lead", fields=[_f("Id")], observed_at=_T1
    )
    diff = await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Id"), _f("Flaky__c")],
        observed_at=_T2,
    )
    assert diff.added == ["Flaky__c"]
    assert len(store) == 2  # reactivated existing row, no duplicate insert
    flaky = next(r for r in store if r.field_name == "Flaky__c")
    assert flaky.active is True


@pytest.mark.asyncio
async def test_type_change_is_recorded() -> None:
    service, store = _make_service()
    await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Score", field_type="int")],
        observed_at=_T0,
    )
    diff = await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Score", field_type="double")],
        observed_at=_T1,
    )
    assert [c.field for c in diff.type_changed] == ["Score"]
    assert diff.type_changed[0].old_type == "int"
    assert diff.type_changed[0].new_type == "double"
    assert next(r for r in store if r.field_name == "Score").field_type == "double"


@pytest.mark.asyncio
async def test_readability_transition_is_recorded() -> None:
    service, _ = _make_service()
    # First seen as FLS-blocked (readable=False), then granted.
    await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Secret__c", readable=False)],
        observed_at=_T0,
    )
    diff = await service.sync_object_schema(
        _TENANT_ID,
        provider="salesforce",
        object_name="Lead",
        fields=[_f("Secret__c", readable=True)],
        observed_at=_T1,
    )
    assert diff.became_readable == ["Secret__c"]
    assert diff.became_unreadable == []


@pytest.mark.asyncio
async def test_providers_and_objects_are_isolated() -> None:
    service, _ = _make_service()
    await service.sync_object_schema(
        _TENANT_ID, provider="salesforce", object_name="Lead", fields=[_f("Id")], observed_at=_T0
    )
    # Same field name on a different object must not collide.
    diff = await service.sync_object_schema(
        _TENANT_ID,
        provider="carestack",
        object_name="patient",
        fields=[_f("Id")],
        observed_at=_T0,
    )
    assert diff.added == ["Id"]
    assert diff.removed == []
