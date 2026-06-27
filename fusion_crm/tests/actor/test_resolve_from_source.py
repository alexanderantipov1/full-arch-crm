"""Service tests for ``ActorService.resolve_actor_from_source`` (ENG-415).

Covers the source-provider → (actor_type, kind, value) mapping and the
idempotency guarantee (re-resolving the same external id returns the
same actor without writing a duplicate identifier).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.actor.models import Actor, ActorIdentifier
from packages.actor.service import (
    ACTOR_KIND_CS_PROVIDER,
    ACTOR_KIND_CS_USER_DETAIL,
    ACTOR_KIND_SF_GROUP,
    ACTOR_KIND_SF_USER,
    ACTOR_KIND_SOFIA,
    ActorService,
    _classify_source,
    _ensure_source_instance,
)
from packages.core.exceptions import ValidationError
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


# ----------------------------------------------------------------- classifier


def test_classify_sf_user() -> None:
    actor_type, kind, value, default = _classify_source(
        "salesforce", "005xx0000001abc"
    )
    assert actor_type == "human"
    assert kind == ACTOR_KIND_SF_USER
    assert value == "005xx0000001abc"
    assert default == "SF User 005xx0000001abc"


def test_classify_sf_group() -> None:
    actor_type, kind, value, _ = _classify_source(
        "salesforce", "00Gxx0000001Queue"
    )
    assert actor_type == "system"
    assert kind == ACTOR_KIND_SF_GROUP
    assert value == "00Gxx0000001Queue"


def test_classify_sf_unknown_prefix() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _classify_source("salesforce", "00Txx0000001foo")
    assert "Salesforce id prefix" in str(excinfo.value)


def test_classify_carestack_provider() -> None:
    actor_type, kind, value, default = _classify_source("carestack", "42")
    assert actor_type == "human"
    assert kind == ACTOR_KIND_CS_PROVIDER
    assert value == "42"
    assert default == "CareStack Provider 42"


def test_classify_carestack_user_detail_prefix() -> None:
    """``userdetail:<id>`` discriminates the join key."""
    actor_type, kind, value, _ = _classify_source(
        "carestack", "userdetail:99"
    )
    assert actor_type == "human"
    assert kind == ACTOR_KIND_CS_USER_DETAIL
    assert value == "99"


def test_classify_sofia_constant() -> None:
    actor_type, kind, value, default = _classify_source("sofia", "sofia_ai")
    assert actor_type == "ai"
    assert kind == ACTOR_KIND_SOFIA
    assert value == "sofia_ai"
    assert default == "Sofia AI"


def test_classify_unknown_provider() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _classify_source("hubspot", "user-1")
    assert "unknown source_provider" in str(excinfo.value)


def test_classify_sofia_rejects_unexpected_id() -> None:
    with pytest.raises(ValidationError):
        _classify_source("sofia", "agent-77")


# ----------------------------------------------------------------- ensure_source_instance


def test_ensure_source_instance_appends_first_time() -> None:
    actor = Actor(name="x", actor_type="human", tenant_id=uuid.uuid4(), meta={})
    _ensure_source_instance(actor, "salesforce-main")
    assert actor.meta == {"sources": ["salesforce-main"]}


def test_ensure_source_instance_idempotent() -> None:
    actor = Actor(
        name="x",
        actor_type="human",
        tenant_id=uuid.uuid4(),
        meta={"sources": ["salesforce-main"]},
    )
    _ensure_source_instance(actor, "salesforce-main")
    assert actor.meta == {"sources": ["salesforce-main"]}


def test_ensure_source_instance_multi_source() -> None:
    actor = Actor(
        name="x",
        actor_type="human",
        tenant_id=uuid.uuid4(),
        meta={"sources": ["salesforce-main"]},
    )
    _ensure_source_instance(actor, "salesforce-sandbox")
    assert actor.meta["sources"] == ["salesforce-main", "salesforce-sandbox"]


# ----------------------------------------------------------------- resolver wiring


def _make_service() -> tuple[ActorService, MagicMock]:
    session = MagicMock()
    service = ActorService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    return service, service._repo  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_resolve_returns_existing_actor_on_repeat() -> None:
    service, repo = _make_service()
    existing_actor = Actor(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        actor_type="human",
        name="Anna Coordinator",
        meta={"sources": ["salesforce-main"]},
    )
    existing_identifier = ActorIdentifier(
        id=uuid.uuid4(),
        tenant_id=existing_actor.tenant_id,
        actor_id=existing_actor.id,
        kind=ACTOR_KIND_SF_USER,
        value="005xx0000001abc",
    )
    existing_identifier.actor = existing_actor
    repo.find_identifier = AsyncMock(return_value=existing_identifier)

    actor = await service.resolve_actor_from_source(
        _TENANT_ID,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="005xx0000001abc",
    )

    assert actor is existing_actor
    repo.find_identifier.assert_awaited_once_with(
        _TENANT_ID, ACTOR_KIND_SF_USER, "005xx0000001abc"
    )


@pytest.mark.asyncio
async def test_resolve_creates_new_actor_with_name_hint() -> None:
    service, repo = _make_service()
    repo.find_identifier = AsyncMock(return_value=None)
    repo.find_by_type_and_name = AsyncMock(return_value=None)

    created_actor: dict[str, Actor] = {}

    async def _add_actor(actor: Actor) -> Actor:
        actor.id = uuid.uuid4()
        created_actor["actor"] = actor
        return actor

    async def _add_identifier(ident: ActorIdentifier) -> ActorIdentifier:
        return ident

    repo.add_actor = AsyncMock(side_effect=_add_actor)
    repo.add_identifier = AsyncMock(side_effect=_add_identifier)

    actor = await service.resolve_actor_from_source(
        _TENANT_ID,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="005xx0000001abc",
        name_hint="Anna Coordinator",
    )

    assert actor.name == "Anna Coordinator"
    assert actor.actor_type == "human"
    # Identifier was attached with the canonical kind + value.
    repo.add_identifier.assert_awaited_once()
    attached: ActorIdentifier = repo.add_identifier.await_args.args[0]
    assert attached.kind == ACTOR_KIND_SF_USER
    assert attached.value == "005xx0000001abc"


@pytest.mark.asyncio
async def test_resolve_group_creates_system_actor() -> None:
    service, repo = _make_service()
    repo.find_identifier = AsyncMock(return_value=None)
    repo.find_by_type_and_name = AsyncMock(return_value=None)

    async def _add_actor(actor: Actor) -> Actor:
        actor.id = uuid.uuid4()
        return actor

    repo.add_actor = AsyncMock(side_effect=_add_actor)
    repo.add_identifier = AsyncMock(side_effect=lambda i: i)

    actor = await service.resolve_actor_from_source(
        _TENANT_ID,
        source_provider="salesforce",
        source_instance="salesforce-main",
        external_id="00Gxx0000001Queue",
        name_hint="Spanish Queue",
    )

    assert actor.actor_type == "system"
    attached: ActorIdentifier = repo.add_identifier.await_args.args[0]
    assert attached.kind == ACTOR_KIND_SF_GROUP


@pytest.mark.asyncio
async def test_resolve_sofia_creates_ai_actor() -> None:
    service, repo = _make_service()
    repo.find_identifier = AsyncMock(return_value=None)
    repo.find_by_type_and_name = AsyncMock(return_value=None)

    async def _add_actor(actor: Actor) -> Actor:
        actor.id = uuid.uuid4()
        return actor

    repo.add_actor = AsyncMock(side_effect=_add_actor)
    repo.add_identifier = AsyncMock(side_effect=lambda i: i)

    actor = await service.resolve_actor_from_source(
        _TENANT_ID,
        source_provider="sofia",
        source_instance="salesforce-main",
        external_id="sofia_ai",
    )

    assert actor.actor_type == "ai"
    assert actor.name == "Sofia AI"
    attached: ActorIdentifier = repo.add_identifier.await_args.args[0]
    assert attached.kind == ACTOR_KIND_SOFIA
    assert attached.value == "sofia_ai"


@pytest.mark.asyncio
async def test_resolve_carestack_provider_creates_human_actor() -> None:
    service, repo = _make_service()
    repo.find_identifier = AsyncMock(return_value=None)
    repo.find_by_type_and_name = AsyncMock(return_value=None)

    async def _add_actor(actor: Actor) -> Actor:
        actor.id = uuid.uuid4()
        return actor

    repo.add_actor = AsyncMock(side_effect=_add_actor)
    repo.add_identifier = AsyncMock(side_effect=lambda i: i)

    actor = await service.resolve_actor_from_source(
        _TENANT_ID,
        source_provider="carestack",
        source_instance="carestack-main",
        external_id="42",
        name_hint="Dr. Smith",
    )

    assert actor.actor_type == "human"
    attached: ActorIdentifier = repo.add_identifier.await_args.args[0]
    assert attached.kind == ACTOR_KIND_CS_PROVIDER
    assert attached.value == "42"


@pytest.mark.asyncio
async def test_resolve_rejects_blank_inputs() -> None:
    service, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.resolve_actor_from_source(
            _TENANT_ID,
            source_provider="",
            source_instance="salesforce-main",
            external_id="005xx0000001abc",
        )
    with pytest.raises(ValidationError):
        await service.resolve_actor_from_source(
            _TENANT_ID,
            source_provider="salesforce",
            source_instance="salesforce-main",
            external_id="",
        )


@pytest.mark.asyncio
async def test_resolve_tracks_new_source_instance_on_existing_actor() -> None:
    """A second instance referencing the same SF user must accumulate
    provenance without creating a second actor."""
    service, repo = _make_service()
    existing_actor = Actor(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        actor_type="human",
        name="Anna Coordinator",
        meta={"sources": ["salesforce-main"]},
    )
    existing_identifier = ActorIdentifier(
        id=uuid.uuid4(),
        tenant_id=existing_actor.tenant_id,
        actor_id=existing_actor.id,
        kind=ACTOR_KIND_SF_USER,
        value="005xx0000001abc",
    )
    existing_identifier.actor = existing_actor
    repo.find_identifier = AsyncMock(return_value=existing_identifier)

    actor = await service.resolve_actor_from_source(
        _TENANT_ID,
        source_provider="salesforce",
        source_instance="salesforce-sandbox",
        external_id="005xx0000001abc",
    )

    assert actor is existing_actor
    assert actor.meta["sources"] == ["salesforce-main", "salesforce-sandbox"]
