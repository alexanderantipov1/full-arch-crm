"""Tiny helper for centralising tenant filtering on SQLAlchemy statements.

Each per-tenant repository method appends `WHERE tenant_id = :tenant_id`
to its SELECT/UPDATE/DELETE statement. Doing that inline reads fine on a
single line but is easy to forget; routing through `_for_tenant` makes
the omission visible in code review (the helper is the only common name
used across the codebase for this filter).

Usage:

```python
from packages.db.tenant_scope import for_tenant

async def find_lead_by_person(
    self, tenant_id: TenantId, person_uid: UUID
) -> Lead | None:
    stmt = for_tenant(select(Lead), tenant_id, Lead).where(
        Lead.person_uid == person_uid
    )
    return (await self._session.execute(stmt)).scalar_one_or_none()
```

The helper does NOT enforce that ``model`` actually has a ``tenant_id``
column — that is a static-typing concern, and SQLAlchemy will raise at
construct time if the column is missing.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.sql import Select


def for_tenant(stmt: Select[Any], tenant_id: UUID, model: Any) -> Select[Any]:
    """Append ``WHERE tenant_id = :tenant_id`` to ``stmt``.

    ``model`` is the ORM class whose ``tenant_id`` column the filter
    targets. Passing the model rather than a column reference keeps the
    call sites short and consistent.
    """
    return stmt.where(model.tenant_id == tenant_id)
