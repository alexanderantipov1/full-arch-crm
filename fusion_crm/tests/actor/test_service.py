"""Service-level tests for actor — normalisation invariants.

DB-dependent paths (real upsert / find with a Postgres session) land with
the alembic migration in FUS-32. These tests exercise the pure-Python
normalisation rules + verify that ``ActorService.find_by_identifier``
applies the same canonicalisation as ``attach_identifier`` so cross-call
lookups are symmetric.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.actor.service import (
    ActorService,
    _normalise_identifier_value,
)
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())

# --- pure normalisation ---


def test_normalise_email_lowercases_and_strips() -> None:
    assert _normalise_identifier_value("email", " Anna@Example.COM ") == "anna@example.com"


def test_normalise_phone_e164() -> None:
    # ENG-463: phones canonicalize to E.164 (Twilio-ready, stable match key).
    assert _normalise_identifier_value("phone", "+1 (415) 555-1234") == "+14155551234"
    assert _normalise_identifier_value("phone", "4155551234") == "+14155551234"


def test_normalise_unknown_kind_passes_through() -> None:
    assert _normalise_identifier_value("salesforce_user_id", "005xx0000001YzS") == "005xx0000001YzS"
    assert _normalise_identifier_value("vapi_agent_id", "agent_abc123") == "agent_abc123"


# --- find_by_identifier symmetry (the regression Codex caught) ---


@pytest.mark.asyncio
async def test_find_by_identifier_normalises_email_lookup() -> None:
    """Lookup with mixed-case email must hit the row stored canonical-lower.

    Repo is mocked; the assertion is that the value the service passes to
    ``repo.find_identifier`` is the normalised form, not the raw input.
    """
    session = MagicMock()
    service = ActorService(session)
    service._repo.find_identifier = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await service.find_by_identifier(_TENANT_ID, "email", "Anna@Example.COM")

    service._repo.find_identifier.assert_awaited_once_with(
        _TENANT_ID, "email", "anna@example.com"
    )


@pytest.mark.asyncio
async def test_find_by_identifier_normalises_phone_lookup() -> None:
    session = MagicMock()
    service = ActorService(session)
    service._repo.find_identifier = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await service.find_by_identifier(_TENANT_ID, "phone", "+1 (415) 555-1234")

    service._repo.find_identifier.assert_awaited_once_with(
        _TENANT_ID, "phone", "+14155551234"
    )


@pytest.mark.asyncio
async def test_find_by_identifier_passes_through_other_kinds() -> None:
    session = MagicMock()
    service = ActorService(session)
    service._repo.find_identifier = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await service.find_by_identifier(
        _TENANT_ID, "salesforce_user_id", "005xx0000001YzS"
    )

    service._repo.find_identifier.assert_awaited_once_with(
        _TENANT_ID,
        "salesforce_user_id",
        "005xx0000001YzS",
    )


# --- resolve_linked_identifier (ENG-543: provider id -> mattermost_username) ---


def _ident(kind: str, value: str) -> MagicMock:
    m = MagicMock()
    m.kind = kind
    m.value = value
    return m


@pytest.mark.asyncio
async def test_resolve_linked_identifier_maps_provider_to_mattermost() -> None:
    session = MagicMock()
    service = ActorService(session)
    actor = MagicMock()
    actor.id = uuid.uuid4()
    src = MagicMock()
    src.actor = actor
    service._repo.find_identifier = AsyncMock(return_value=src)  # type: ignore[method-assign]
    service._repo.list_identifiers = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            _ident("carestack_provider_id", "1"),
            _ident("mattermost_username", "drantipov"),
        ]
    )

    out = await service.resolve_linked_identifier(
        _TENANT_ID, "carestack_provider_id", "1", "mattermost_username"
    )

    assert out == "drantipov"
    service._repo.list_identifiers.assert_awaited_once_with(_TENANT_ID, actor.id)


@pytest.mark.asyncio
async def test_resolve_linked_identifier_none_when_actor_missing() -> None:
    session = MagicMock()
    service = ActorService(session)
    service._repo.find_identifier = AsyncMock(return_value=None)  # type: ignore[method-assign]

    out = await service.resolve_linked_identifier(
        _TENANT_ID, "carestack_provider_id", "999", "mattermost_username"
    )

    assert out is None


@pytest.mark.asyncio
async def test_resolve_linked_identifier_none_when_target_absent() -> None:
    session = MagicMock()
    service = ActorService(session)
    actor = MagicMock()
    actor.id = uuid.uuid4()
    src = MagicMock()
    src.actor = actor
    service._repo.find_identifier = AsyncMock(return_value=src)  # type: ignore[method-assign]
    service._repo.list_identifiers = AsyncMock(  # type: ignore[method-assign]
        return_value=[_ident("carestack_provider_id", "1")]
    )

    out = await service.resolve_linked_identifier(
        _TENANT_ID, "carestack_provider_id", "1", "mattermost_username"
    )

    assert out is None
