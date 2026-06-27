"""Repository-level tests for ``ActorRepository``.

These assert query *shape* (no DB) — the mocked-session suite that the
rest of tests/actor uses. Real-DB coverage lands with FUS-32.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.actor.repository import ActorRepository
from packages.core.types import TenantId

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


@pytest.mark.asyncio
async def test_find_identifier_eager_loads_actor() -> None:
    """Regression: ``find_identifier`` MUST eager-load ``ActorIdentifier.actor``.

    ``find_by_identifier`` returns ``identifier.actor`` immediately, and that
    path is wired into live ingest via
    ``ActorService.resolve_actor_from_source``. ``ActorIdentifier.actor`` is
    lazy by default, so without an eager load the attribute access raises
    ``MissingGreenlet`` under the async session (it crashed the
    event-responsibility backfill + would break forward attribution). This
    guards the ``joinedload`` so it can't silently regress.
    """
    captured: dict[str, object] = {}

    async def _capture(stmt: object, *args: object, **kwargs: object) -> object:
        captured["stmt"] = stmt
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_capture)

    repo = ActorRepository(session)
    await repo.find_identifier(_TENANT_ID, "salesforce_user_id", "005Vw000008bpQLIAY")

    stmt = captured["stmt"]
    # A loader option is attached (the joinedload).
    assert getattr(stmt, "_with_options", ()), "find_identifier issued no loader option"
    compiled = str(stmt.compile(dialect=postgresql.dialect())).lower()  # type: ignore[attr-defined]
    # joinedload(ActorIdentifier.actor) renders a join that selects the parent
    # actor columns under the ``actor_1`` alias — absence means lazy load.
    assert "actor_1" in compiled, (
        "ActorIdentifier.actor is not eager-loaded — find_by_identifier will "
        "raise MissingGreenlet under the async session"
    )
