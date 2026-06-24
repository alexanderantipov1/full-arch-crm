"""Service tests for ``ops.opportunity`` (ENG-414).

Mirrors the ``test_consultation.py`` shape: validation, idempotency,
change detection, owner enrichment via the ``extra`` JSONB blob.
Repository / session are mocked — DB-level integration tests run
under ``tests/integration/``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Table

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import PersonUID, TenantId
from packages.ops.models import Opportunity
from packages.ops.schemas import OpportunityIn
from packages.ops.service import OpsService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())
_PERSON_UID: PersonUID = PersonUID(uuid.uuid4())
_NOW = datetime(2026, 6, 13, 19, 0, tzinfo=UTC)


def _make_service() -> tuple[OpsService, MagicMock]:
    session = MagicMock()

    async def _refresh(row: Any) -> None:
        if getattr(row, "id", None) is None:
            row.id = uuid.uuid4()
        if getattr(row, "created_at", None) is None:
            row.created_at = _NOW
        if getattr(row, "updated_at", None) is None:
            row.updated_at = _NOW

    session.refresh = AsyncMock(side_effect=_refresh)
    service = OpsService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._identity = MagicMock()  # type: ignore[attr-defined]
    service._identity.get_person = AsyncMock()
    service._identity.get_person.return_value = MagicMock(id=_PERSON_UID)
    return service, service._repo  # type: ignore[attr-defined]


def _payload(**overrides: object) -> OpportunityIn:
    defaults: dict[str, object] = dict(
        person_uid=_PERSON_UID,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="006xx00000ABC",
        name="Implant case — Jones",
        stage="Consult Booked",
        amount=12500.0,
        close_date=datetime(2026, 7, 1, tzinfo=UTC),
        provider_created_at=datetime(2026, 6, 1, tzinfo=UTC),
        extra={
            "owner_id": "005xx0000001abc",
            "owner_name": "Anna Coordinator",
            "opportunity_stage": "Consult Booked",
        },
    )
    defaults.update(overrides)
    return OpportunityIn(**defaults)  # type: ignore[arg-type]


def _existing(payload: OpportunityIn, **overrides: object) -> Opportunity:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        tenant_id=_TENANT_ID,
        person_uid=payload.person_uid,
        source_provider=payload.source_provider,
        source_instance=payload.source_instance,
        external_id=payload.external_id,
        name=payload.name,
        stage=payload.stage,
        amount=payload.amount,
        close_date=payload.close_date,
        provider_created_at=payload.provider_created_at,
        raw_event_id=payload.raw_event_id,
        extra=dict(payload.extra),
        created_at=_NOW,
        updated_at=_NOW,
    )
    base.update(overrides)
    return Opportunity(**base)  # type: ignore[arg-type]


# ----------------------------------------------------------------- validation


@pytest.mark.asyncio
async def test_upsert_rejects_unknown_provider() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError) as excinfo:
        await service.upsert_opportunity(
            _TENANT_ID, _payload(source_provider="hubspot")
        )
    assert "unknown opportunity provider" in str(excinfo.value)


@pytest.mark.asyncio
async def test_upsert_rejects_missing_person_when_person_uid_supplied() -> None:
    service, _ = _make_service()
    service._identity.get_person.return_value = None  # type: ignore[attr-defined]
    with pytest.raises(NotFoundError):
        await service.upsert_opportunity(_TENANT_ID, _payload())


@pytest.mark.asyncio
async def test_upsert_allows_null_person_uid_on_first_pull() -> None:
    """Opportunity must persist even when AccountId fallback misses."""
    service, repo = _make_service()
    repo.find_opportunity_by_source = AsyncMock(return_value=None)

    async def _add(opp: Opportunity) -> Opportunity:
        opp.id = uuid.uuid4()
        opp.created_at = _NOW
        opp.updated_at = _NOW
        return opp

    repo.add_opportunity = AsyncMock(side_effect=_add)

    result = await service.upsert_opportunity(
        _TENANT_ID, _payload(person_uid=None)
    )
    assert result.was_created is True
    assert result.opportunity.person_uid is None
    # IdentityService is NOT called when person_uid is None.
    service._identity.get_person.assert_not_called()  # type: ignore[attr-defined]


# ----------------------------------------------------------------- idempotency


@pytest.mark.asyncio
async def test_upsert_inserts_when_no_existing_row() -> None:
    service, repo = _make_service()
    repo.find_opportunity_by_source = AsyncMock(return_value=None)

    async def _add(opp: Opportunity) -> Opportunity:
        opp.id = uuid.uuid4()
        opp.created_at = _NOW
        opp.updated_at = _NOW
        return opp

    repo.add_opportunity = AsyncMock(side_effect=_add)

    result = await service.upsert_opportunity(_TENANT_ID, _payload())

    assert result.was_created is True
    assert result.was_changed is True
    assert result.was_owner_change is True
    assert result.was_stage_change is True
    assert result.opportunity.extra["owner_id"] == "005xx0000001abc"
    assert result.opportunity.extra["owner_name"] == "Anna Coordinator"
    repo.find_opportunity_by_source.assert_awaited_once_with(
        tenant_id=_TENANT_ID,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="006xx00000ABC",
    )
    repo.add_opportunity.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_idempotent_when_payload_matches() -> None:
    service, repo = _make_service()
    payload = _payload()
    existing = _existing(payload)
    repo.find_opportunity_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_opportunity(_TENANT_ID, payload)

    assert result.was_created is False
    assert result.was_changed is False
    assert result.was_owner_change is False
    assert result.was_stage_change is False


# ----------------------------------------------------------------- change detection


@pytest.mark.asyncio
async def test_upsert_detects_stage_change() -> None:
    service, repo = _make_service()
    payload = _payload(stage="Treatment Started")
    existing = _existing(payload, stage="Consult Booked")
    repo.find_opportunity_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_opportunity(_TENANT_ID, payload)

    assert result.was_changed is True
    assert result.was_stage_change is True
    assert result.opportunity.stage == "Treatment Started"


@pytest.mark.asyncio
async def test_upsert_detects_owner_change() -> None:
    service, repo = _make_service()
    payload = _payload(
        extra={
            "owner_id": "005xx0000002NEW",
            "owner_name": "Brian TC",
        }
    )
    existing = _existing(
        payload,
        extra={
            "owner_id": "005xx0000001abc",
            "owner_name": "Anna Coordinator",
        },
    )
    repo.find_opportunity_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_opportunity(_TENANT_ID, payload)

    assert result.was_owner_change is True
    assert result.was_changed is True
    assert result.opportunity.extra["owner_id"] == "005xx0000002NEW"
    assert result.opportunity.extra["owner_name"] == "Brian TC"


@pytest.mark.asyncio
async def test_upsert_backfills_person_uid_when_previously_null() -> None:
    """A later pull supplies the AccountId → person_uid the first pull missed."""
    service, repo = _make_service()
    payload = _payload()
    existing = _existing(payload, person_uid=None)
    repo.find_opportunity_by_source = AsyncMock(return_value=existing)

    await service.upsert_opportunity(_TENANT_ID, payload)
    assert existing.person_uid == _PERSON_UID


@pytest.mark.asyncio
async def test_upsert_merges_extra_without_overwriting_with_none() -> None:
    """``extra`` keys present on the existing row must NOT be wiped by None."""
    service, repo = _make_service()
    payload = _payload(
        extra={
            "owner_id": "005xx0000001abc",
            "owner_name": None,  # owner_name not in the new pull's projection
            "opportunity_stage": "Treatment Started",
        }
    )
    existing = _existing(
        payload,
        stage="Treatment Started",
        extra={
            "owner_id": "005xx0000001abc",
            "owner_name": "Anna Coordinator",
            "opportunity_stage": "Treatment Started",
        },
    )
    repo.find_opportunity_by_source = AsyncMock(return_value=existing)

    result = await service.upsert_opportunity(_TENANT_ID, payload)
    # owner_name preserved; only differing keys updated.
    assert result.opportunity.extra["owner_name"] == "Anna Coordinator"


# ----------------------------------------------------------------- model shape


def test_opportunity_model_has_expected_columns() -> None:
    columns = {c.name for c in Opportunity.__table__.columns}
    assert {
        "id",
        "tenant_id",
        "person_uid",
        "source_provider",
        "source_instance",
        "external_id",
        "name",
        "stage",
        "amount",
        "close_date",
        "provider_created_at",
        "raw_event_id",
        "extra",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_opportunity_natural_key_unique_constraint() -> None:
    table = cast(Table, Opportunity.__table__)
    unique_names = {
        c.name for c in table.constraints if getattr(c, "name", None)
    }
    assert "uq_opportunity_source" in unique_names


def test_opportunity_check_constraint_present() -> None:
    table = cast(Table, Opportunity.__table__)
    check_names = {
        c.name
        for c in table.constraints
        if isinstance(c.name, str) and c.name.startswith("ck_")
    }
    assert "ck_opportunity_source_provider" in check_names


def test_opportunity_indexes() -> None:
    table = cast(Table, Opportunity.__table__)
    index_names = {ix.name for ix in table.indexes}
    for required in (
        "ix_opportunity_tenant_id",
        "ix_opportunity_person_uid",
        "ix_opportunity_tenant_person_close",
        "ix_opportunity_tenant_provider_created",
    ):
        assert required in index_names, f"missing index: {required}"
