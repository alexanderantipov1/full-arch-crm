"""Service-level tests for ``LocationService.import_locations_from_carestack``.

The repository is mocked here — the goal is to assert the
create / update / deactivate / idempotency rules the service owes to
its callers, not the SQL layer (which gets PostgreSQL coverage in the
integration suite once it expands).

Per ``packages/CLAUDE.md``, the CareStack client is consumed via a
``Protocol`` so the tenant package never imports
``packages.integrations.carestack`` — these tests therefore use a
plain stub class with one ``list_locations`` coroutine.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.tenant.models import Location, Tenant
from packages.tenant.service import LocationService


def _principal() -> Principal:
    return Principal(id=uuid.uuid4(), email="ops@example.com", roles=frozenset({Role.ADMIN}))


def _make_service() -> tuple[LocationService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    service = LocationService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._tenant_repo = MagicMock()  # type: ignore[attr-defined]
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()
    return (
        service,
        service._repo,  # type: ignore[attr-defined]
        service._tenant_repo,  # type: ignore[attr-defined]
        service._audit,  # type: ignore[attr-defined]
    )


class _StubCSClient:
    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self._payload = payload

    async def list_locations(self) -> list[dict[str, Any]]:
        return list(self._payload)


# ---- Fixture data: mirrors the four CareStack locations seen on the live API.

FUSION_EDH: dict[str, Any] = {
    "id": 1,
    "name": "FUSION-EDH",
    "shortName": "EDH",
    "timeZone": "Pacific Standard Time",
    "phone1": "555-0001",
    "address": {
        "addressLine1": "100 EDH Way",
        "addressLine2": "",
        "city": "El Dorado Hills",
        "state": "CA",
        "zipCode": "95762",
    },
    "latitude": 38.685,
    "longitude": -121.082,
    "isActive": True,
}

FUSION_ROS: dict[str, Any] = {
    "id": 8027,
    "name": "FUSION-ROS",
    "shortName": "ROS",
    "timeZone": "Pacific Standard Time",
    "phone1": "555-0002",
    "address": {
        "addressLine1": "200 Roseville Pkwy",
        "addressLine2": "",
        "city": "Roseville",
        "state": "CA",
        "zipCode": "95661",
    },
    "latitude": 38.752,
    "longitude": -121.288,
    "isActive": True,
}

FUSION_COSMO: dict[str, Any] = {
    "id": 9028,
    "name": "FUSION-COSMO",
    "shortName": "COSMO",
    "timeZone": "Pacific Standard Time",
    "phone1": "555-0003",
    "address": {
        "addressLine1": "300 Cosmo Blvd",
        "addressLine2": "Suite 4",
        "city": "Sacramento",
        "state": "CA",
        "zipCode": "95825",
    },
    "latitude": 38.581,
    "longitude": -121.494,
    "isActive": True,
}

FUSION_GALLERIA: dict[str, Any] = {
    "id": 10029,
    "name": "FUSION-GALLERIA",
    "shortName": "GAL",
    "timeZone": "Pacific Standard Time",
    "phone1": "555-0004",
    "address": {
        "addressLine1": "400 Galleria Cir",
        "addressLine2": "",
        "city": "Roseville",
        "state": "CA",
        "zipCode": "95678",
    },
    "latitude": 38.770,
    "longitude": -121.272,
    "isActive": True,
}


def _existing_from_payload(
    raw: dict[str, Any], tenant_id: TenantId, *, is_active: bool = True
) -> Location:
    """Build a ``Location`` ORM row that already matches the upstream payload.

    Used by the "no changes" test case to assert that a re-pull on
    identical data does NOT produce an audit row.
    """
    address = raw["address"]
    location = Location(
        tenant_id=tenant_id,
        external_ref={"carestack_location_id": raw["id"]},
        name=raw["name"],
        short_name=raw["shortName"],
        address_line1=address["addressLine1"] or None,
        address_line2=None,  # empty string normalises to None
        city=address["city"],
        state=address["state"],
        zip=address["zipCode"],
        phone=raw["phone1"],
        timezone_override="America/Los_Angeles",
        latitude=raw["latitude"],
        longitude=raw["longitude"],
        is_active=is_active,
    )
    location.id = uuid.uuid4()
    return location


# ----------------------------------------------------------------- empty


@pytest.mark.asyncio
async def test_import_empty_response_yields_zero_summary() -> None:
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.find_by_carestack_id = AsyncMock(return_value=None)
    repo.list_for_tenant = AsyncMock(return_value=[])

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([]), principal=_principal()
    )

    assert summary.total_seen == 0
    assert summary.created == 0
    assert summary.updated == 0
    assert summary.deactivated == 0
    audit.record.assert_not_called()


# ----------------------------------------------------------------- fresh insert


@pytest.mark.asyncio
async def test_import_fresh_inserts_each_location() -> None:
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.find_by_carestack_id = AsyncMock(return_value=None)
    added: list[Location] = []

    async def _capture_add(loc: Location) -> Location:
        added.append(loc)
        return loc

    repo.add = AsyncMock(side_effect=_capture_add)
    repo.list_for_tenant = AsyncMock(return_value=[])

    summary = await service.import_locations_from_carestack(
        tenant_id,
        _StubCSClient([FUSION_EDH, FUSION_ROS, FUSION_COSMO, FUSION_GALLERIA]),
        principal=_principal(),
    )

    assert summary.total_seen == 4
    assert summary.created == 4
    assert summary.updated == 0
    assert summary.deactivated == 0

    # Field mapping spot-checks on the first row.
    edh = added[0]
    assert edh.tenant_id == tenant_id
    assert edh.external_ref == {"carestack_location_id": 1}
    assert edh.name == "FUSION-EDH"
    assert edh.short_name == "EDH"
    assert edh.address_line1 == "100 EDH Way"
    assert edh.address_line2 is None  # empty string normalised
    assert edh.city == "El Dorado Hills"
    assert edh.state == "CA"
    assert edh.zip == "95762"
    assert edh.phone == "555-0001"
    assert edh.timezone_override == "America/Los_Angeles"
    assert edh.latitude == pytest.approx(38.685)
    assert edh.longitude == pytest.approx(-121.082)
    assert edh.is_active is True

    # One audit row per insert.
    assert audit.record.await_count == 4
    actions = {call.kwargs["action"] for call in audit.record.await_args_list}
    assert actions == {"tenant.location.upsert_from_carestack"}
    ops = [call.kwargs["extra"]["op"] for call in audit.record.await_args_list]
    assert ops == ["create", "create", "create", "create"]


# ----------------------------------------------------------------- update only changed


@pytest.mark.asyncio
async def test_import_updates_only_changed_fields() -> None:
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    # Existing row matches the upstream payload EXCEPT the phone, which
    # was updated upstream.
    existing = _existing_from_payload(FUSION_EDH, tenant_id)
    existing.phone = "555-OLDD"

    repo.find_by_carestack_id = AsyncMock(return_value=existing)
    repo.list_for_tenant = AsyncMock(return_value=[existing])

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([FUSION_EDH]), principal=_principal()
    )

    assert summary.total_seen == 1
    assert summary.created == 0
    assert summary.updated == 1
    assert summary.deactivated == 0
    assert existing.phone == "555-0001"

    # One audit row, op=update.
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    assert extra["op"] == "update"
    assert extra["carestack_location_id"] == 1


# ----------------------------------------------------------------- idempotent re-run


@pytest.mark.asyncio
async def test_import_idempotent_no_audit_when_unchanged() -> None:
    """Re-running with identical payload does NOT write audit rows."""
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    existing = _existing_from_payload(FUSION_EDH, tenant_id)
    repo.find_by_carestack_id = AsyncMock(return_value=existing)
    repo.list_for_tenant = AsyncMock(return_value=[existing])

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([FUSION_EDH]), principal=_principal()
    )

    assert summary.total_seen == 1
    assert summary.created == 0
    assert summary.updated == 0
    assert summary.deactivated == 0
    audit.record.assert_not_called()


# ----------------------------------------------------------------- deactivate missing


@pytest.mark.asyncio
async def test_import_deactivates_local_rows_missing_upstream() -> None:
    """A row that exists locally but vanishes upstream is deactivated."""
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    # Two local rows; upstream now only returns one.
    upstream_present = _existing_from_payload(FUSION_EDH, tenant_id)
    upstream_gone = _existing_from_payload(FUSION_COSMO, tenant_id)

    async def _find_by_cs_id(_tid: TenantId, cs_id: int) -> Location | None:
        if cs_id == FUSION_EDH["id"]:
            return upstream_present
        return None

    repo.find_by_carestack_id = AsyncMock(side_effect=_find_by_cs_id)
    repo.list_for_tenant = AsyncMock(return_value=[upstream_present, upstream_gone])

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([FUSION_EDH]), principal=_principal()
    )

    assert summary.total_seen == 1
    assert summary.created == 0
    assert summary.updated == 0
    assert summary.deactivated == 1
    assert upstream_gone.is_active is False
    assert upstream_present.is_active is True

    # Single audit row for the deactivation; the unchanged row produces nothing.
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    assert extra["op"] == "deactivate"
    assert extra["carestack_location_id"] == FUSION_COSMO["id"]


@pytest.mark.asyncio
async def test_import_does_not_redeactivate_already_inactive_rows() -> None:
    """Already-inactive missing rows do NOT produce a fresh audit row."""
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    long_dead = _existing_from_payload(FUSION_COSMO, tenant_id, is_active=False)
    repo.find_by_carestack_id = AsyncMock(return_value=None)
    repo.list_for_tenant = AsyncMock(return_value=[long_dead])

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([]), principal=_principal()
    )

    assert summary.deactivated == 0
    audit.record.assert_not_called()


# ----------------------------------------------------------------- skip non-CS rows on deactivation


@pytest.mark.asyncio
async def test_import_leaves_non_carestack_rows_alone() -> None:
    """Rows without a ``carestack_location_id`` are not touched."""
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    bare_row = Location(
        tenant_id=tenant_id,
        external_ref={"some_other_provider": "x"},
        name="Manual Entry",
        is_active=True,
    )
    bare_row.id = uuid.uuid4()

    repo.find_by_carestack_id = AsyncMock(return_value=None)
    repo.list_for_tenant = AsyncMock(return_value=[bare_row])

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([]), principal=_principal()
    )

    assert summary.deactivated == 0
    assert bare_row.is_active is True
    audit.record.assert_not_called()


# ----------------------------------------------------------------- malformed upstream row


@pytest.mark.asyncio
async def test_import_skips_rows_with_non_integer_id() -> None:
    service, repo, tenant_repo, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.find_by_carestack_id = AsyncMock(return_value=None)
    repo.add = AsyncMock(side_effect=lambda loc: loc)
    repo.list_for_tenant = AsyncMock(return_value=[])

    bad = {**FUSION_EDH, "id": "not-an-int"}

    summary = await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([bad, FUSION_ROS]), principal=_principal()
    )

    # total_seen counts the response length; created counts only the row that mapped.
    assert summary.total_seen == 2
    assert summary.created == 1


# ----------------------------------------------------------------- tenant missing


@pytest.mark.asyncio
async def test_import_raises_when_tenant_not_found() -> None:
    from packages.core.exceptions import NotFoundError

    service, _, tenant_repo, _ = _make_service()
    tenant_repo.get = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.import_locations_from_carestack(
            TenantId(uuid.uuid4()),
            _StubCSClient([FUSION_EDH]),
            principal=_principal(),
        )


# ----------------------------------------------------------------- timezone fallback


@pytest.mark.asyncio
async def test_import_unknown_timezone_falls_through_unchanged() -> None:
    """Unknown Windows zones pass through; known ones are mapped to IANA."""
    service, repo, tenant_repo, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    captured: list[Location] = []
    repo.find_by_carestack_id = AsyncMock(return_value=None)

    def _capture_add(loc: Location) -> Location:
        captured.append(loc)
        return loc

    repo.add = AsyncMock(side_effect=_capture_add)
    repo.list_for_tenant = AsyncMock(return_value=[])

    weird = {**FUSION_EDH, "id": 42, "timeZone": "Some Made Up Standard Time"}

    await service.import_locations_from_carestack(
        tenant_id, _StubCSClient([weird]), principal=_principal()
    )

    assert captured[0].timezone_override == "Some Made Up Standard Time"
