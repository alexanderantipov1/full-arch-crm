"""Integration tests for the ENG-408 lead owner-name enrichment script.

Real-PostgreSQL tests (per root testing policy) covering:

* distinct owner-id collection from ``ops.lead.extra``;
* polymorphic resolution — ``005…`` ids query ``User``, ``00G…`` ids
  query ``Group`` (queues);
* the JSONB update writes ``owner_name``, skips already-correct rows,
  and is idempotent on re-run.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.ops.models import Lead
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "backfill_lead_owner_names.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "backfill_lead_owner_names", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("backfill_lead_owner_names", module)
    spec.loader.exec_module(module)
    return module


class _FakeSfClient:
    """Canned SOQL responses; records which sobjects were queried."""

    def __init__(self, names_by_object: dict[str, dict[str, str]]) -> None:
        self._names_by_object = names_by_object
        self.queries: list[str] = []

    async def soql(self, query: str) -> dict[str, object]:
        self.queries.append(query)
        sobject = query.split(" FROM ")[1].split(" WHERE ")[0].strip()
        records = [
            {"Id": rid, "Name": name}
            for rid, name in self._names_by_object.get(sobject, {}).items()
            if f"'{rid}'" in query
        ]
        return {"totalSize": len(records), "done": True, "records": records}


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_lead(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    extra: dict,
) -> Lead:
    person = Person(
        tenant_id=tenant_id,
        given_name="Owner",
        family_name="Backfill",
        display_name="Owner Backfill",
    )
    session.add(person)
    await session.flush()
    lead = Lead(
        tenant_id=tenant_id, person_uid=person.id, source=None, extra=extra
    )
    session.add(lead)
    await session.flush()
    return lead


_USER_ID = "005Vw000008bujNIAQ"
_QUEUE_ID = "00GVw000008sm1RMAQ"


@pytest.mark.asyncio
async def test_resolves_users_and_groups_and_updates_idempotently(
    db_session: AsyncSession,
) -> None:
    script = _load_script()
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="owner-names")

    user_lead = await _seed_lead(
        db_session, tenant_id, extra={"owner_id": _USER_ID}
    )
    queue_lead = await _seed_lead(
        db_session, tenant_id, extra={"owner_id": _QUEUE_ID}
    )
    # Already enriched with the CURRENT name → must not count as pending.
    await _seed_lead(
        db_session,
        tenant_id,
        extra={"owner_id": _USER_ID, "owner_name": "Yelena Myalik"},
    )
    # No owner at all → out of scope.
    await _seed_lead(db_session, tenant_id, extra={})

    owner_ids = await script._distinct_owner_ids(db_session, tenant_id)
    assert set(owner_ids) == {_USER_ID, _QUEUE_ID}

    sf = _FakeSfClient(
        {
            "User": {_USER_ID: "Yelena Myalik"},
            "Group": {_QUEUE_ID: "Intake Queue"},
        }
    )
    names = await script._resolve_owner_names(sf, sorted(owner_ids))
    assert names == {_USER_ID: "Yelena Myalik", _QUEUE_ID: "Intake Queue"}
    # Polymorphic routing: queue ids must be looked up in Group, not User.
    assert any(" FROM Group " in q for q in sf.queries)
    assert all(_QUEUE_ID not in q for q in sf.queries if " FROM User " in q)

    # Dry-run counting: one pending row per owner (the pre-named row is
    # already correct and excluded).
    assert await script._count_pending(
        db_session, tenant_id, _USER_ID, "Yelena Myalik"
    ) == 1
    assert await script._count_pending(
        db_session, tenant_id, _QUEUE_ID, "Intake Queue"
    ) == 1

    # Apply writes the name and is idempotent on re-run.
    assert await script._apply_owner(
        db_session, tenant_id, _USER_ID, "Yelena Myalik"
    ) == 1
    assert await script._apply_owner(
        db_session, tenant_id, _QUEUE_ID, "Intake Queue"
    ) == 1
    assert await script._apply_owner(
        db_session, tenant_id, _USER_ID, "Yelena Myalik"
    ) == 0

    await db_session.refresh(user_lead)
    await db_session.refresh(queue_lead)
    assert user_lead.extra["owner_name"] == "Yelena Myalik"
    assert user_lead.extra["owner_id"] == _USER_ID
    assert queue_lead.extra["owner_name"] == "Intake Queue"
