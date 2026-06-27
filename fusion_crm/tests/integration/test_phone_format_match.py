"""Integration: cross-format phone matching at the SQL layer.

Reproduces the duplicate-person class fixed by ENG-562 — one person's phone
stored digit-only (a CareStack-style write) and another's in E.164 (a
Salesforce-style write). Before the ``value_match_key`` fix the resolver's
exact-string lookups never matched them, so a duplicate person was created.
These tests assert the repository now finds the match regardless of stored
format. Numbers are synthetic (reserved ``555-01xx`` range).

Needs a real Postgres test DB at the new migration (``value_match_key``
column). Skips cleanly when the DB or column is unavailable so the unit suite
stays green without a container.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from packages.core.types import TenantId
from packages.identity.models import Person, PersonIdentifier
from packages.identity.repository import IdentityRepository

pytestmark = pytest.mark.asyncio


async def _session_or_skip():
    try:
        from packages.db.session import SessionFactory
    except Exception:  # pragma: no cover - no DB wiring
        pytest.skip("no DB session factory available")
    session = SessionFactory()
    has_col = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='identity' AND table_name='person_identifier' "
            "AND column_name='value_match_key')"
        )
    )
    if not has_col:
        await session.rollback()
        await session.close()
        pytest.skip("value_match_key column not present (migration not applied)")
    return session


async def _seed_person(
    repo: IdentityRepository, tenant_id: TenantId, name: str, phone: str
) -> uuid.UUID:
    person = Person(tenant_id=tenant_id, given_name=name, family_name="Tester")
    await repo.add_person(person)
    await repo.add_identifier(
        PersonIdentifier(
            tenant_id=tenant_id,
            person_id=person.id,
            kind="phone",
            value=phone,
        )
    )
    return person.id


async def test_find_persons_sharing_identifier_across_formats() -> None:
    session = await _session_or_skip()
    try:
        repo = IdentityRepository(session)
        tenant_id = TenantId(uuid.uuid4())
        # Tenant FK is enforced; seed a minimal tenant row.
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, primary_email) "
                "VALUES (:id, :slug, :name, :email)"
            ),
            {
                "id": str(tenant_id),
                "slug": f"t-{uuid.uuid4().hex[:8]}",
                "name": "PF test",
                "email": f"{uuid.uuid4().hex[:8]}@example.test",
            },
        )
        cs_id = await _seed_person(repo, tenant_id, "Alex", "2015550123")
        sf_id = await _seed_person(repo, tenant_id, "Alex", "+12015550123")
        await session.flush()

        # From the digit-only side, the E.164 person must surface.
        shared = await repo.find_persons_sharing_identifier(
            tenant_id, "phone", "2015550123", cs_id
        )
        assert sf_id in {p.id for p in shared}

        # And candidate lookup with an E.164 hint finds the digit-only person.
        candidates = await repo.list_candidate_persons_by_identifiers(
            tenant_id, None, "+12015550123"
        )
        assert {cs_id, sf_id} <= {p.id for p in candidates}
    finally:
        await session.rollback()
        await session.close()
