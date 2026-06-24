"""Unit tests for ``FunnelResponsibilityResolver`` (ENG-416 + ENG-417).

These tests cover the stage-aware decision tree directly without going
through a real DB — the resolver is built for Protocol injection, so
``OpsService`` and ``ActorResolverProtocol`` are mocked.

Covered branches:
- pre-consult event → Lead.OwnerId actor (no Opportunity lookup).
- consult-onward event → covering Opportunity.OwnerId actor.
- consult-onward event with no covering Opportunity → Lead.OwnerId fallback.
- consult-onward event with covering Opportunity that has no OwnerId →
  Lead.OwnerId fallback BUT covering_opportunity_id is still surfaced.
- explicit_owner hint overrides the staged owner.
- clinical_provider hint adds a clinical role ONLY for clinical kinds.
- walk-in (no Lead, no Opportunity, no doctor) → empty assignments,
  no covering link.
- idempotency: the resolver itself is stateless; same inputs → same
  output across calls.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from packages.core.types import TenantId
from packages.ingest.responsibility_resolver import (
    FunnelResponsibilityResolver,
    ProviderOwnerHint,
)

_TENANT = TenantId(uuid.uuid4())
_PERSON = uuid.uuid4()
_NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


def _mock_actor(actor_id: UUID | None = None) -> MagicMock:
    """Return an object with ``.id`` shaped like an ``actor.actor`` row."""
    actor = MagicMock()
    actor.id = actor_id if actor_id is not None else uuid.uuid4()
    return actor


def _build_resolver(
    *,
    lead_owner_id: str | None = None,
    covering: object | None = None,
    covering_owner_id: str | None = None,
    actor_id: UUID | None = None,
) -> tuple[FunnelResponsibilityResolver, MagicMock, MagicMock, UUID]:
    """Construct a resolver with mocked dependencies and known return values."""
    actor_id = actor_id or uuid.uuid4()
    ops = MagicMock()
    ops.get_lead_owner_id = AsyncMock(return_value=lead_owner_id)
    ops.find_covering_opportunity = AsyncMock(return_value=covering)
    ops.get_opportunity_owner_id = AsyncMock(return_value=covering_owner_id)

    actor_service = MagicMock()
    actor_service.resolve_actor_from_source = AsyncMock(
        return_value=_mock_actor(actor_id)
    )
    return (
        FunnelResponsibilityResolver(ops, actor_service),
        ops,
        actor_service,
        actor_id,
    )


# ----------------------------------------------------------------- pre-consult


@pytest.mark.asyncio
async def test_lead_created_uses_lead_owner_no_opportunity_lookup() -> None:
    resolver, ops, actor_service, actor_id = _build_resolver(
        lead_owner_id="005xx0000001abc"
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="lead_created",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )

    assert len(out.assignments) == 1
    assert out.assignments[0].actor_id == actor_id
    assert out.assignments[0].role == "operational"
    assert out.covering_opportunity_id is None
    # Pre-consult MUST NOT touch the Opportunity table — that's how the
    # stage rule is enforced (no covering lookup for lead_*, call_logged,
    # task_*).
    ops.find_covering_opportunity.assert_not_awaited()
    actor_service.resolve_actor_from_source.assert_awaited_once()


@pytest.mark.asyncio
async def test_lead_created_with_no_lead_owner_returns_empty() -> None:
    resolver, _ops, actor_service, _ = _build_resolver(lead_owner_id=None)

    out = await resolver.resolve(
        _TENANT,
        event_kind="lead_created",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )

    assert out.assignments == []
    assert out.covering_opportunity_id is None
    actor_service.resolve_actor_from_source.assert_not_awaited()


# --------------------------------------------------------- consult-onward


@pytest.mark.asyncio
async def test_consultation_scheduled_uses_covering_opportunity_owner() -> None:
    covering_id = uuid.uuid4()
    covering = MagicMock(id=covering_id, extra={"owner_id": "005TC0001"})
    resolver, ops, actor_service, actor_id = _build_resolver(
        covering=covering,
        covering_owner_id="005TC0001",
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="consultation_scheduled",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )

    assert len(out.assignments) == 1
    assert out.assignments[0].actor_id == actor_id
    assert out.assignments[0].role == "operational"
    assert out.covering_opportunity_id == covering_id
    # The covering Opportunity owner wins; Lead.OwnerId must NOT be
    # consulted when the staged Opportunity owner resolves.
    ops.get_lead_owner_id.assert_not_awaited()
    actor_service.resolve_actor_from_source.assert_awaited_once_with(
        _TENANT,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="005TC0001",
        name_hint=None,
        role_hint=None,
    )


@pytest.mark.asyncio
async def test_consult_falls_back_to_lead_owner_when_no_opportunity() -> None:
    resolver, ops, actor_service, actor_id = _build_resolver(
        lead_owner_id="005AGENT01",
        covering=None,
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="consultation_scheduled",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )

    assert len(out.assignments) == 1
    assert out.assignments[0].role == "operational"
    assert out.assignments[0].actor_id == actor_id
    assert out.covering_opportunity_id is None
    ops.find_covering_opportunity.assert_awaited_once()
    ops.get_lead_owner_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_consult_with_opportunity_missing_owner_uses_lead_but_keeps_link() -> None:
    """Opportunity row exists but its OwnerId hasn't been pulled yet.

    The consult should still link to the covering Opportunity (so future
    queries can navigate), but operational attribution falls back to the
    Lead owner.
    """
    covering_id = uuid.uuid4()
    covering = MagicMock(id=covering_id, extra={})
    resolver, ops, _actor_service, actor_id = _build_resolver(
        covering=covering,
        covering_owner_id=None,
        lead_owner_id="005FALLBACK1",
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="consultation_completed",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )

    assert out.covering_opportunity_id == covering_id
    assert len(out.assignments) == 1
    assert out.assignments[0].actor_id == actor_id
    ops.get_lead_owner_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_walk_in_no_lead_no_opportunity_yields_empty() -> None:
    """Pure walk-in: no Lead, no Opportunity, no doctor hint."""
    resolver, _ops, actor_service, _ = _build_resolver(
        lead_owner_id=None, covering=None
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="consultation_completed",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )

    assert out.assignments == []
    assert out.covering_opportunity_id is None
    actor_service.resolve_actor_from_source.assert_not_awaited()


# ------------------------------------------------- explicit override + clinical


@pytest.mark.asyncio
async def test_explicit_owner_hint_overrides_staged_owner() -> None:
    """SF Task.OwnerId for a call event wins over Lead.OwnerId."""
    resolver, ops, actor_service, actor_id = _build_resolver(
        lead_owner_id="005LEAD0001"
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="call_logged",
        person_uid=_PERSON,
        occurred_at=_NOW,
        explicit_owner=ProviderOwnerHint(
            source_provider="salesforce",
            source_instance="salesforce-main",
            external_id="005SOFIA001",
            name_hint="Sofia AI",
        ),
    )

    assert len(out.assignments) == 1
    assert out.assignments[0].actor_id == actor_id
    # Per-touch override means we never fall back to Lead lookup.
    ops.get_lead_owner_id.assert_not_awaited()
    actor_service.resolve_actor_from_source.assert_awaited_once_with(
        _TENANT,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="005SOFIA001",
        name_hint="Sofia AI",
        role_hint=None,
    )


@pytest.mark.asyncio
async def test_clinical_provider_added_only_for_clinical_kind() -> None:
    """Doctor attached for consult kinds; ignored for pre-consult kinds."""
    op_actor_id = uuid.uuid4()
    clinical_actor_id = uuid.uuid4()
    ops = MagicMock()
    ops.get_lead_owner_id = AsyncMock(return_value="005LEAD0001")
    ops.find_covering_opportunity = AsyncMock(return_value=None)
    ops.get_opportunity_owner_id = AsyncMock(return_value=None)

    actor_service = MagicMock()
    # First call → operational actor (Lead owner); second → clinical doctor.
    actor_service.resolve_actor_from_source = AsyncMock(
        side_effect=[_mock_actor(op_actor_id), _mock_actor(clinical_actor_id)]
    )
    resolver = FunnelResponsibilityResolver(ops, actor_service)

    clinical_hint = ProviderOwnerHint(
        source_provider="carestack",
        source_instance="carestack-main",
        external_id="42",
        name_hint="Dr. Example",
        role_hint="provider",
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="consultation_scheduled",
        person_uid=_PERSON,
        occurred_at=_NOW,
        clinical_provider=clinical_hint,
    )

    assert len(out.assignments) == 2
    roles = sorted(a.role for a in out.assignments)
    assert roles == ["clinical", "operational"]
    by_role = {a.role: a.actor_id for a in out.assignments}
    assert by_role["operational"] == op_actor_id
    assert by_role["clinical"] == clinical_actor_id


@pytest.mark.asyncio
async def test_clinical_hint_ignored_on_pre_consult_event() -> None:
    op_actor_id = uuid.uuid4()
    resolver, _ops, actor_service, _ = _build_resolver(
        lead_owner_id="005LEAD0001",
        actor_id=op_actor_id,
    )

    out = await resolver.resolve(
        _TENANT,
        event_kind="lead_created",
        person_uid=_PERSON,
        occurred_at=_NOW,
        clinical_provider=ProviderOwnerHint(
            source_provider="carestack",
            source_instance="carestack-main",
            external_id="42",
        ),
    )

    # Lead event has no clinical role — even if a hint were passed,
    # it must be ignored.
    assert len(out.assignments) == 1
    assert out.assignments[0].role == "operational"
    # The resolver should NOT have called resolve_actor_from_source for
    # the clinical hint at all.
    assert actor_service.resolve_actor_from_source.await_count == 1


@pytest.mark.asyncio
async def test_walk_in_consult_with_doctor_still_returns_doctor() -> None:
    """ENG-417 walk-in: no Opportunity, no Lead, only the doctor."""
    clinical_actor_id = uuid.uuid4()
    ops = MagicMock()
    ops.get_lead_owner_id = AsyncMock(return_value=None)
    ops.find_covering_opportunity = AsyncMock(return_value=None)
    ops.get_opportunity_owner_id = AsyncMock(return_value=None)
    actor_service = MagicMock()
    actor_service.resolve_actor_from_source = AsyncMock(
        return_value=_mock_actor(clinical_actor_id)
    )
    resolver = FunnelResponsibilityResolver(ops, actor_service)

    out = await resolver.resolve(
        _TENANT,
        event_kind="consultation_completed",
        person_uid=_PERSON,
        occurred_at=_NOW,
        clinical_provider=ProviderOwnerHint(
            source_provider="carestack",
            source_instance="carestack-main",
            external_id="7",
        ),
    )

    assert len(out.assignments) == 1
    assert out.assignments[0].role == "clinical"
    assert out.assignments[0].actor_id == clinical_actor_id
    assert out.covering_opportunity_id is None


# ------------------------------------------------- idempotency / structural


@pytest.mark.asyncio
async def test_repeat_calls_with_same_inputs_yield_same_assignments() -> None:
    """The resolver is stateless — re-running yields identical output."""
    actor_id = uuid.uuid4()
    resolver, _, _, _ = _build_resolver(
        lead_owner_id="005LEAD0001", actor_id=actor_id
    )
    a = await resolver.resolve(
        _TENANT,
        event_kind="lead_created",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )
    b = await resolver.resolve(
        _TENANT,
        event_kind="lead_created",
        person_uid=_PERSON,
        occurred_at=_NOW,
    )
    assert a == b
