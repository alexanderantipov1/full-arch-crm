"""Actor repository — data access only. NO business logic.

Repositories take ``AsyncSession`` and return ORM entities. They never commit
(unit-of-work caller is the boundary).

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .models import Actor, ActorIdentifier


class ActorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Actor ---

    async def get_actor(self, tenant_id: TenantId, actor_id: UUID) -> Actor | None:
        stmt = for_tenant(select(Actor), tenant_id, Actor).where(Actor.id == actor_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_type_and_name(
        self,
        tenant_id: TenantId,
        actor_type: str,
        name: str,
    ) -> Actor | None:
        stmt = (
            for_tenant(select(Actor), tenant_id, Actor)
            .where(Actor.actor_type == actor_type)
            .where(Actor.name == name)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_actor(self, actor: Actor) -> Actor:
        self._session.add(actor)
        await self._session.flush()
        return actor

    # --- Identifier ---

    async def find_identifier(
        self,
        tenant_id: TenantId,
        kind: str,
        value: str,
    ) -> ActorIdentifier | None:
        stmt = (
            for_tenant(select(ActorIdentifier), tenant_id, ActorIdentifier)
            .where(ActorIdentifier.kind == kind)
            .where(ActorIdentifier.value == value)
            # Eager-load the parent actor: callers (find_by_identifier →
            # resolve_actor_from_source, wired into live ingest) access
            # ``identifier.actor`` immediately. The reverse relationship is
            # lazy by default, which raises MissingGreenlet under the async
            # session. joinedload keeps it a single round-trip.
            .options(joinedload(ActorIdentifier.actor))
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_identifier(self, identifier: ActorIdentifier) -> ActorIdentifier:
        self._session.add(identifier)
        await self._session.flush()
        return identifier

    async def list_identifiers(
        self, tenant_id: TenantId, actor_id: UUID
    ) -> list[ActorIdentifier]:
        stmt = (
            for_tenant(select(ActorIdentifier), tenant_id, ActorIdentifier)
            .where(ActorIdentifier.actor_id == actor_id)
            .order_by(ActorIdentifier.kind, ActorIdentifier.value)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_actors_with_identifier(
        self, tenant_id: TenantId, kind: str
    ) -> list[tuple[Actor, str]]:
        """List every actor carrying a ``kind`` identifier, with its value.

        Returns ``(actor, identifier_value)`` pairs ordered by actor name.
        Backs the Messenger-settings provider directory (ENG-546): the
        ``carestack_provider_id`` actors are the doctors an operator maps to a
        Mattermost username. An actor with N identifiers of ``kind`` yields N
        rows — for the provider id (one per doctor) that is one row each.
        """
        stmt = (
            for_tenant(
                select(Actor, ActorIdentifier.value), tenant_id, Actor
            )
            .join(ActorIdentifier, ActorIdentifier.actor_id == Actor.id)
            # Defense-in-depth: ``for_tenant`` already scopes Actor, and the
            # join is on actor_id, so the identifier is implicitly tenant-bound.
            # Scope the joined identifier explicitly too — mirrors the explicit
            # tenant filter in ``delete_identifiers``. Behaviour unchanged.
            .where(ActorIdentifier.tenant_id == tenant_id)
            .where(ActorIdentifier.kind == kind)
            .order_by(Actor.name, ActorIdentifier.value)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(actor, value) for actor, value in rows]

    async def delete_identifiers(
        self, tenant_id: TenantId, actor_id: UUID, kind: str
    ) -> int:
        """Delete all ``kind`` identifiers on an actor; return the row count.

        Used by ``ActorService.set_provider_messenger_username`` to purge the
        actor's existing ``mattermost_username`` rows BEFORE attaching the new
        one — ``attach_identifier`` is additive, so without this a re-map leaves
        two rows and ``resolve_linked_identifier`` returns an arbitrary one.
        """
        stmt = (
            delete(ActorIdentifier)
            .where(ActorIdentifier.tenant_id == tenant_id)
            .where(ActorIdentifier.actor_id == actor_id)
            .where(ActorIdentifier.kind == kind)
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)
