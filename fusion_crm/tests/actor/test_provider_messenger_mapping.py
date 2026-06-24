"""Integration tests for the provider → Mattermost username mapping (ENG-546).

Exercises ``ActorService.list_provider_messenger_mappings`` and
``set_provider_messenger_username`` against the REAL local Postgres (the same
session/repo stack the consult-reminder resolver uses). Skips cleanly when no
local DB is reachable.

Covered:

1. ``list`` surfaces every ``carestack_provider_id`` actor, with
   ``mattermost_username=None`` until mapped.
2. ``set`` strips a leading ``@`` and persists the handle.
3. CRITICAL INVARIANT — a re-map leaves EXACTLY ONE ``mattermost_username``
   row on the doctor's actor (``attach_identifier`` is additive; the service
   must purge the stale row first), so ``resolve_linked_identifier`` is
   deterministic and the reminder @mentions the right person.
4. ``set`` against an unknown provider id raises ``NotFoundError``.
5. ``set`` with a handle already on another doctor raises ``ValidationError``
   (the operator-typo conflict — a clean 4xx, not a 500) and leaves the first
   doctor's mapping untouched.
6. ``set`` with a handle that strips to empty (``"@"``) raises
   ``ValidationError`` and persists nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId

try:  # noqa: SIM105
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK, reason="DATABASE_URL / Settings not configured for a live DB"
)

_PROVIDER_KIND = "carestack_provider_id"
_MM_KIND = "mattermost_username"


async def _db_reachable() -> bool:
    from sqlalchemy import text

    from packages.db.session import engine

    try:
        await engine.dispose()
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — DB down / unreachable
        return False


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")

    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"eng546-test-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, "
                "status, created_at, updated_at) VALUES (:id, :slug, :name, "
                "'UTC', 'en-US', 'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-546 Test"},
        )
        await session.commit()

    try:
        yield TenantId(tid)
    finally:
        async with async_session() as session:
            # actor_identifier FKs actor with ON DELETE CASCADE — delete actors
            # and the identifier rows go with them.
            await session.execute(
                text("DELETE FROM actor.actor WHERE tenant_id = :id"),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
            )
            await session.commit()


async def _seed_provider(tenant_id: TenantId, provider_id: str, name: str) -> None:
    """Create a doctor actor carrying ``carestack_provider_id=provider_id``."""
    from packages.actor.service import ActorService

    async with async_session() as session:
        await ActorService(session).resolve_actor_from_source(
            tenant_id,
            source_provider="carestack",
            source_instance="test",
            external_id=provider_id,
            name_hint=name,
        )
        await session.commit()


async def _count_mm_rows(tenant_id: TenantId, provider_id: str) -> int:
    """Count ``mattermost_username`` rows on the actor mapped to ``provider_id``."""
    from sqlalchemy import text

    async with async_session() as session:
        result = await session.execute(
            text(
                "SELECT count(*) FROM actor.actor_identifier mm "
                "JOIN actor.actor_identifier cs ON cs.actor_id = mm.actor_id "
                "WHERE mm.tenant_id = :id AND mm.kind = :mm_kind "
                "AND cs.kind = :cs_kind AND cs.value = :provider_id"
            ),
            {
                "id": uuid.UUID(str(tenant_id)),
                "mm_kind": _MM_KIND,
                "cs_kind": _PROVIDER_KIND,
                "provider_id": provider_id,
            },
        )
        return int(result.scalar_one())


async def test_list_surfaces_providers_unmapped_then_mapped(
    tenant_id: TenantId,
) -> None:
    from packages.actor.service import ActorService

    await _seed_provider(tenant_id, "1", "Dr Antipov")
    await _seed_provider(tenant_id, "2", "Dr Ivanova")

    # Before mapping: both providers listed, no username.
    async with async_session() as session:
        rows = await ActorService(session).list_provider_messenger_mappings(
            tenant_id
        )
    by_cs = {r.carestack_provider_id: r for r in rows}
    assert set(by_cs) == {"1", "2"}
    assert by_cs["1"].mattermost_username is None
    assert by_cs["2"].mattermost_username is None
    assert by_cs["1"].actor_name == "Dr Antipov"

    # Map provider 1 (with a leading @, which must be stripped).
    async with async_session() as session:
        svc = ActorService(session)
        out = await svc.set_provider_messenger_username(tenant_id, "1", "@drantipov")
        await session.commit()
    assert out.mattermost_username == "drantipov"

    async with async_session() as session:
        rows = await ActorService(session).list_provider_messenger_mappings(
            tenant_id
        )
    by_cs = {r.carestack_provider_id: r for r in rows}
    assert by_cs["1"].mattermost_username == "drantipov"
    assert by_cs["2"].mattermost_username is None


async def test_remap_leaves_exactly_one_username(tenant_id: TenantId) -> None:
    """The invariant: re-mapping must not leave a stale second row."""
    from packages.actor.service import ActorService

    await _seed_provider(tenant_id, "1", "Dr Antipov")

    async with async_session() as session:
        svc = ActorService(session)
        await svc.set_provider_messenger_username(tenant_id, "1", "drantipov")
        await session.commit()
    assert await _count_mm_rows(tenant_id, "1") == 1

    # Re-map to a different handle.
    async with async_session() as session:
        svc = ActorService(session)
        out = await svc.set_provider_messenger_username(tenant_id, "1", "dr.new")
        await session.commit()
    assert out.mattermost_username == "dr.new"

    # Exactly one row — the stale "drantipov" must be gone.
    assert await _count_mm_rows(tenant_id, "1") == 1

    async with async_session() as session:
        username = await ActorService(session).resolve_linked_identifier(
            tenant_id, _PROVIDER_KIND, "1", _MM_KIND
        )
    assert username == "dr.new"


async def test_set_unknown_provider_raises_not_found(tenant_id: TenantId) -> None:
    from packages.actor.service import ActorService

    async with async_session() as session:
        svc = ActorService(session)
        with pytest.raises(NotFoundError):
            await svc.set_provider_messenger_username(tenant_id, "999", "ghost")


async def test_set_conflicting_username_raises_validation(
    tenant_id: TenantId,
) -> None:
    """Two doctors cannot share one Mattermost handle.

    The username is UNIQUE workspace-wide (``actor_identifier (kind, value)``).
    Mapping provider B to a handle already on provider A is the operator-typo
    case: it must raise ``ValidationError`` (a clean 4xx), NOT 500, and must
    leave A's existing mapping untouched.
    """
    from packages.actor.service import ActorService

    await _seed_provider(tenant_id, "1", "Dr Antipov")
    await _seed_provider(tenant_id, "2", "Dr Ivanova")

    # Provider 1 (A) claims "drantipov".
    async with async_session() as session:
        svc = ActorService(session)
        await svc.set_provider_messenger_username(tenant_id, "1", "drantipov")
        await session.commit()
    assert await _count_mm_rows(tenant_id, "1") == 1

    # Provider 2 (B) tries the same handle — conflict.
    async with async_session() as session:
        svc = ActorService(session)
        with pytest.raises(ValidationError):
            await svc.set_provider_messenger_username(tenant_id, "2", "drantipov")

    # A's mapping is unchanged; B got none.
    async with async_session() as session:
        username = await ActorService(session).resolve_linked_identifier(
            tenant_id, _PROVIDER_KIND, "1", _MM_KIND
        )
    assert username == "drantipov"
    assert await _count_mm_rows(tenant_id, "1") == 1
    assert await _count_mm_rows(tenant_id, "2") == 0


async def test_set_blank_after_normalisation_raises_validation(
    tenant_id: TenantId,
) -> None:
    """A handle that strips to empty (e.g. ``"@"``) is rejected, not persisted."""
    from packages.actor.service import ActorService

    await _seed_provider(tenant_id, "1", "Dr Antipov")

    async with async_session() as session:
        svc = ActorService(session)
        with pytest.raises(ValidationError):
            await svc.set_provider_messenger_username(tenant_id, "1", "@")

    assert await _count_mm_rows(tenant_id, "1") == 0
