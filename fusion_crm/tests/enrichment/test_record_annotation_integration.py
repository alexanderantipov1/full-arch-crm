"""Integration tests for the enrichment annotation store (ENG-439, Block F).

Exercises ``EnrichmentService`` against the REAL local Postgres so the
``enrichment.record_annotation`` table, its CHECK constraint, the cross-schema
FKs (``tenant.tenant.id``, ``actor.actor.id``), and tenant-scoped reads are all
verified against the actual DB shape — not a mock. The suite skips cleanly
when no local DB is reachable so it does not block DB-less environments.

Covered scenarios:

1. add_annotation persists a row AND writes the audit row in the same UoW.
2. list_for_subject returns only the current tenant's rows (isolation).
3. the DB CHECK constraint rejects a bad ``source`` value.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from packages.core.security import Principal, Role
from packages.core.types import TenantId

try:  # noqa: SIM105 — import builds the engine from DATABASE_URL.
    from packages.db.session import async_session

    _IMPORT_OK = True
except Exception:  # noqa: BLE001 — environment not configured for a DB
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK, reason="DATABASE_URL / Settings not configured for a live DB"
)


def _principal(tenant_id: TenantId) -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="staff@example.com",
        tenant_id=tenant_id,
        roles=frozenset({Role.ADMIN}),
    )


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


async def _seed_tenant(slug_prefix: str) -> TenantId:
    from sqlalchemy import text

    tid = uuid.uuid4()
    slug = f"{slug_prefix}-{tid.hex[:12]}"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO tenant.tenant (id, slug, name, timezone, locale, status, "
                "created_at, updated_at) VALUES (:id, :slug, :name, 'UTC', 'en-US', "
                "'active', now(), now())"
            ),
            {"id": tid, "slug": slug, "name": "ENG-439 Test"},
        )
    return TenantId(tid)


async def _cleanup_tenant(tid: TenantId) -> None:
    from sqlalchemy import text

    async with async_session() as session:
        await session.execute(
            text("DELETE FROM enrichment.record_annotation WHERE tenant_id = :id"),
            {"id": tid},
        )
        await session.execute(
            text("DELETE FROM audit.access_log WHERE tenant_id = :id"), {"id": tid}
        )
        await session.execute(
            text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": tid}
        )


@pytest.fixture
async def tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")
    tid = await _seed_tenant("eng439-test")
    try:
        yield tid
    finally:
        await _cleanup_tenant(tid)


@pytest.fixture
async def other_tenant_id() -> AsyncIterator[TenantId]:
    if not await _db_reachable():
        pytest.skip("local Postgres not reachable (127.0.0.1:5434)")
    tid = await _seed_tenant("eng439-other")
    try:
        yield tid
    finally:
        await _cleanup_tenant(tid)


# --- 1. persistence + audit ---------------------------------------------


async def test_add_annotation_persists_and_audits(tenant_id: TenantId) -> None:
    from sqlalchemy import text

    from packages.enrichment.schemas import AnnotationIn
    from packages.enrichment.service import EnrichmentService

    subject_id = uuid.uuid4()
    async with async_session() as session:
        svc = EnrichmentService(session)
        row = await svc.add_annotation(
            tenant_id,
            AnnotationIn(
                subject_type="person",
                subject_id=subject_id,
                key="consult_notes",
                value={"text": "Prefers morning slots"},
                source="ui",
                note="intake call",
            ),
            principal=_principal(tenant_id),
        )
        annotation_id = row.id
        await session.commit()

    async with async_session() as session:
        stored = (
            await session.execute(
                text(
                    "SELECT subject_type, subject_id, key, value, source, note "
                    "FROM enrichment.record_annotation WHERE id = :id"
                ),
                {"id": annotation_id},
            )
        ).one()
        assert stored.subject_type == "person"
        assert stored.subject_id == subject_id
        assert stored.key == "consult_notes"
        assert stored.value == {"text": "Prefers morning slots"}
        assert stored.source == "ui"
        assert stored.note == "intake call"

        audit_row = (
            await session.execute(
                text(
                    "SELECT action, resource, person_uid, extra "
                    "FROM audit.access_log WHERE tenant_id = :tid "
                    "AND action = 'enrichment.annotation.add'"
                ),
                {"tid": tenant_id},
            )
        ).one()
        assert audit_row.action == "enrichment.annotation.add"
        assert audit_row.resource == "enrichment.record_annotation"
        assert audit_row.person_uid == subject_id
        # value text must NOT have leaked into the audit extra.
        assert "Prefers morning slots" not in str(audit_row.extra)
        assert audit_row.extra.get("key") == "consult_notes"


# --- 2. tenant isolation ------------------------------------------------


async def test_list_for_subject_is_tenant_scoped(
    tenant_id: TenantId, other_tenant_id: TenantId
) -> None:
    from packages.enrichment.schemas import AnnotationIn
    from packages.enrichment.service import EnrichmentService

    # Same subject id in BOTH tenants — only the caller's tenant rows return.
    subject_id = uuid.uuid4()

    async with async_session() as session:
        svc = EnrichmentService(session)
        await svc.add_annotation(
            tenant_id,
            AnnotationIn(
                subject_type="person",
                subject_id=subject_id,
                key="k",
                value={"text": "mine"},
                source="ui",
            ),
            principal=_principal(tenant_id),
        )
        await svc.add_annotation(
            other_tenant_id,
            AnnotationIn(
                subject_type="person",
                subject_id=subject_id,
                key="k",
                value={"text": "theirs"},
                source="ui",
            ),
            principal=_principal(other_tenant_id),
        )
        await session.commit()

    async with async_session() as session:
        svc = EnrichmentService(session)
        rows = await svc.list_for_subject(tenant_id, "person", subject_id)
        assert len(rows) == 1
        assert rows[0].tenant_id == tenant_id
        assert rows[0].value == {"text": "mine"}


# --- 3. DB CHECK constraint on source -----------------------------------


async def test_db_check_constraint_rejects_bad_source(tenant_id: TenantId) -> None:
    import sqlalchemy.exc

    from packages.enrichment.models import RecordAnnotation

    async with async_session() as session:
        # Bypass the service guard to exercise the DB-level CHECK directly.
        session.add(
            RecordAnnotation(
                tenant_id=tenant_id,
                subject_type="person",
                subject_id=uuid.uuid4(),
                key="k",
                value={},
                source="webhook",  # not in ('ui','chat','agent')
            )
        )
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await session.flush()
        await session.rollback()
