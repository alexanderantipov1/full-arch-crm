"""Shared helpers for the two-tenant cross-tenant isolation safety net.

Lives next to ``conftest.py`` so the dataclass + capability flag are
importable by both the conftest fixture and the integration sweep
test (``tests/integration/test_tenant_isolation.py``). The leading
underscore tells pytest this is NOT a test module.

See ``tests/conftest.py`` for the docstring on Phase A vs Phase B.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


def _detect_tenant_schema_available() -> bool:
    """Return True when ENG-123's ``tenant_id`` columns + ``tenant.*``
    schema are present.

    Probes both:

    - ``identity.person.tenant_id`` exists as a column on the ORM model.
    - ``packages.tenant.models.Tenant`` is importable.

    Failing either probe → returns False so the suite skips Phase B
    assertions cleanly. We probe BOTH (instead of just one) to fail
    closed if only half of ENG-123 has merged.
    """
    try:
        from packages.identity.models import Person
    except Exception:  # pragma: no cover — surfaced via pytest.skip
        return False

    person_columns = {col.name for col in Person.__table__.columns}  # type: ignore[attr-defined]
    if "tenant_id" not in person_columns:
        return False

    try:
        # ENG-123 lands packages/tenant/models.py with a Tenant model.
        from packages.tenant.models import Tenant  # type: ignore[import-not-found]  # noqa: F401
    except Exception:
        return False

    return True


TENANT_SCHEMA_AVAILABLE: bool = _detect_tenant_schema_available()


@dataclass(frozen=True)
class TwoTenantContext:
    """Yielded by the ``two_tenant_db`` fixture.

    Attributes
    ----------
    session :
        Live ``AsyncSession`` (Phase B) or ``None`` (Phase A — schema
        not yet present). Tests requiring live DB MUST guard on
        ``session is not None`` or use ``TENANT_SCHEMA_AVAILABLE``.
    tenant_a_id :
        UUID of the seeded ``tenant.tenant`` row with slug ``tenant-a``
        (Phase B) or a stable random UUID (Phase A).
    tenant_b_id :
        Same as ``tenant_a_id`` but for slug ``tenant-b``.
    seeded_ids :
        Dict from seed name to per-tenant ID maps:
        ``{"tenant_a": <uuid>, "tenant_b": <uuid>}``. Empty in
        Phase A; populated in Phase B. Seed names cover every
        tenant-scoped repository read target used by the live sweep,
        including tenant roots/config, identity, actor, auth,
        interaction, audit, ingest, integrations, ops, outreach, and
        phi rows.
    """

    session: Any  # AsyncSession | None — Any to keep mypy quiet in Phase A.
    tenant_a_id: uuid.UUID
    tenant_b_id: uuid.UUID
    seeded_ids: dict[str, dict[str, uuid.UUID]]
