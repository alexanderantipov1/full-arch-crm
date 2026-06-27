"""Tests for the responsibility join-table contract (ENG-416).

Covers:
- ``EventIn.responsibilities`` validation (typed roles, default empty).
- ``InteractionService._write_responsibilities`` deduplicates
  ``(actor_id, role)`` pairs before flush so callers passing the same
  owner twice in one event don't fight the composite PK.
- ``InteractionService.set_responsibilities_idempotent`` skips already-
  written rows (the backfill contract).
- ``InteractionService.set_responsibilities_idempotent`` rejects
  unknown roles via :data:`RESPONSIBILITY_ROLES`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.interaction.schemas import EventIn, ResponsibilityAssignmentIn
from packages.interaction.service import InteractionService

_TENANT = TenantId(uuid.uuid4())
_PERSON = uuid.uuid4()
_OCCURRED = datetime(2026, 6, 13, 9, 0, tzinfo=UTC)


def _event_in_with_responsibilities(
    assignments: list[ResponsibilityAssignmentIn],
) -> EventIn:
    """Build a minimal valid ``EventIn`` carrying the assignments."""
    return EventIn(
        person_uid=_PERSON,
        kind="lead_created",
        source_provider="salesforce",
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="00Q-test",
        occurred_at=_OCCURRED,
        summary="Lead created from Salesforce",
        responsibilities=assignments,
    )


def test_event_in_defaults_to_empty_responsibilities() -> None:
    payload = EventIn(
        person_uid=_PERSON,
        kind="lead_created",
        source_provider="salesforce",
        data_class="operational",
        source_kind="salesforce_lead",
        source_external_id="00Q-test",
        occurred_at=_OCCURRED,
        summary="Lead created from Salesforce",
    )
    assert payload.responsibilities == []


def test_event_in_accepts_typed_responsibility() -> None:
    actor_id = uuid.uuid4()
    payload = _event_in_with_responsibilities(
        [ResponsibilityAssignmentIn(actor_id=actor_id, role="operational")]
    )
    assert payload.responsibilities[0].role == "operational"
    assert payload.responsibilities[0].actor_id == actor_id


@pytest.mark.asyncio
async def test_write_responsibilities_dedupes_duplicate_pairs() -> None:
    service = InteractionService.__new__(InteractionService)
    service._session = MagicMock()  # type: ignore[attr-defined]
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._repo.add_responsibilities = AsyncMock(return_value=[])
    service._operational_projection_reader = None  # type: ignore[attr-defined]

    event_id = uuid.uuid4()
    actor_a = uuid.uuid4()
    actor_b = uuid.uuid4()
    assignments = [
        ResponsibilityAssignmentIn(actor_id=actor_a, role="operational"),
        # Exact duplicate
        ResponsibilityAssignmentIn(actor_id=actor_a, role="operational"),
        # Same actor, different role: should NOT be deduped
        ResponsibilityAssignmentIn(actor_id=actor_a, role="clinical"),
        # New actor
        ResponsibilityAssignmentIn(actor_id=actor_b, role="operational"),
    ]

    await service._write_responsibilities(_TENANT, event_id, assignments)

    service._repo.add_responsibilities.assert_awaited_once()
    call_args = service._repo.add_responsibilities.await_args
    written_pairs = call_args.args[2]
    assert len(written_pairs) == 3
    assert (actor_a, "operational") in written_pairs
    assert (actor_a, "clinical") in written_pairs
    assert (actor_b, "operational") in written_pairs


@pytest.mark.asyncio
async def test_set_responsibilities_idempotent_skips_existing() -> None:
    service = InteractionService.__new__(InteractionService)
    service._session = MagicMock()  # type: ignore[attr-defined]
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._operational_projection_reader = None  # type: ignore[attr-defined]

    event_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    # find_existing_responsibility returns truthy for the first call,
    # None for the second → first is skipped, second is written.
    service._repo.find_existing_responsibility = AsyncMock(
        side_effect=[MagicMock(), None]
    )
    service._repo.add_responsibilities = AsyncMock(return_value=[])

    inserted = await service.set_responsibilities_idempotent(
        _TENANT,
        event_id,
        [
            ResponsibilityAssignmentIn(actor_id=actor_id, role="operational"),
            ResponsibilityAssignmentIn(actor_id=actor_id, role="clinical"),
        ],
    )

    assert inserted == 1
    service._repo.add_responsibilities.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_responsibilities_idempotent_rejects_unknown_role() -> None:
    service = InteractionService.__new__(InteractionService)
    service._session = MagicMock()  # type: ignore[attr-defined]
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._operational_projection_reader = None  # type: ignore[attr-defined]
    service._repo.find_existing_responsibility = AsyncMock(return_value=None)
    service._repo.add_responsibilities = AsyncMock(return_value=[])

    bogus = ResponsibilityAssignmentIn.model_construct(
        actor_id=uuid.uuid4(),
        role="bogus",  # type: ignore[arg-type]
    )

    with pytest.raises(ValidationError):
        await service.set_responsibilities_idempotent(
            _TENANT, uuid.uuid4(), [bogus]
        )
