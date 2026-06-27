"""The repository choke point must stamp ``value_match_key`` on every insert.

``IdentityRepository.add_identifier`` is the single insert path for
``identity.person_identifier`` (both ``create_person`` and
``upsert_by_identifier`` route through it), so deriving the canonical match key
there guarantees no insert escapes without one.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.identity.models import PersonIdentifier
from packages.identity.repository import IdentityRepository


def _mock_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_add_identifier_stamps_phone_match_key() -> None:
    repo = IdentityRepository(_mock_session())
    ident = PersonIdentifier(
        tenant_id=TenantId(uuid.uuid4()),
        person_id=uuid.uuid4(),
        kind="phone",
        value="2015550123",
    )
    await repo.add_identifier(ident)
    assert ident.value_match_key == "+12015550123"


@pytest.mark.asyncio
async def test_add_identifier_stamps_email_match_key() -> None:
    repo = IdentityRepository(_mock_session())
    ident = PersonIdentifier(
        tenant_id=TenantId(uuid.uuid4()),
        person_id=uuid.uuid4(),
        kind="email",
        value="Foo@Bar.com",
    )
    await repo.add_identifier(ident)
    assert ident.value_match_key == "foo@bar.com"
