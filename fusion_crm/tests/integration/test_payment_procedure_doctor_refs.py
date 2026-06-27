"""DB-backed tests for payment operation-code + doctor resolution.

``IngestService.get_payment_procedure_doctor_refs`` powers the PM Payments
page's Operation + Doctor columns: given the ``source_event_id`` (raw_event PK)
carried on each payment row, it resolves the performed operation (CDT code) and
performing clinician.

ENG-551 correction: ``accounting_transaction.procedureCodeId`` is NOT a CDT
catalog id — its value is a ``treatment_procedure.id`` (the procedure INSTANCE
id; id spaces ~1.7M–24.7M vs the catalog's 5k–438k). The ENG-547 fixture
encoded the wrong assumption (it seeded an accounting raw whose
``procedureCodeId`` was a catalog id directly), so the direct join matched 0
legs on real data. The real chain is two hops:

    accounting.procedureCodeId (= treatment_procedure.id)
      → treatment_procedure.upsert raw payload (by payload ``id``)
      → its real CDT ``procedureCodeId`` → catalog.procedure_code (code + desc)
      → its ``providerId``               → ingest.carestack_provider name

Doctor prefers the treatment procedure's provider (filled ~100%); the
accounting provider (filled ~77%) is the fallback only when no procedure is
linked.

These tests seed a fresh tenant (rolled back on teardown) with the catalog, the
provider directory, accounting-transaction raw_events, and the linked
treatment-procedure raw_events, then assert the full-chain resolution, the
honest ``None`` gaps, the doctor preference + fallback, that clinical fields
never surface, and tenant scoping.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.catalog.models import ProcedureCode
from packages.core.types import TenantId
from packages.ingest.models import CareStackProvider, RawEvent
from packages.ingest.service import IngestService
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_BASE = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
# ``catalog.procedure_code`` is workspace-level (not tenant-scoped) and the dev
# DB carries the real CareStack catalog. Use synthetic sentinel CDT ids far
# outside CareStack's real id range so the seed never collides with committed
# rows; the whole session rolls back on teardown.
_IMPLANT_CODE_ID = 990_000_001
_EVAL_CODE_ID = 990_000_002
_UNKNOWN_CODE_ID = 990_000_099
# Treatment-procedure INSTANCE ids (the values accounting.procedureCodeId
# actually holds — high range, matching the real id space).
_TP_IMPLANT = 24_700_001
_TP_EVAL = 24_700_002
_TP_UNRESOLVED_CDT = 24_700_003
_TP_MISSING = 24_700_099  # accounting points here but no tp raw is seeded
_DOCTOR_ID = 3
_OTHER_PROVIDER_ID = 7  # appears on accounting only; not in the directory
_UNKNOWN_PROVIDER_ID = 888_888


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_reference(session: AsyncSession, tenant_id: TenantId) -> None:
    session.add(
        ProcedureCode(
            carestack_code_id=_IMPLANT_CODE_ID,
            code="D6010",
            description="Surgical placement of implant body",
        )
    )
    session.add(
        ProcedureCode(
            carestack_code_id=_EVAL_CODE_ID,
            code="D0120",
            description="Periodic oral evaluation",
        )
    )
    session.add(
        CareStackProvider(
            tenant_id=tenant_id,
            provider_carestack_id=_DOCTOR_ID,
            first_name="Jane",
            last_name="Smith",
            provider_type="Doctor",
        )
    )
    await session.flush()


async def _seed_accounting_raw(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    transaction_id: str,
    tp_instance_id: int | None,
    provider_id: int | None,
) -> RawEvent:
    """Seed an accounting-transaction raw.

    ``tp_instance_id`` lands in the payload's ``procedureCodeId`` key — it is a
    ``treatment_procedure.id`` (instance id), NOT a CDT id (ENG-551).
    """
    payload: dict[str, object] = {
        "id": int(transaction_id),
        "amount": 250.0,
        "transactionType": "credit",
        # Clinical free text that must NEVER influence the resolution and is
        # never selected by the repo query.
        "notes": "accounting note must NEVER reach the dashboard",
    }
    if tp_instance_id is not None:
        payload["procedureCodeId"] = tp_instance_id
    if provider_id is not None:
        payload["providerId"] = provider_id
    raw = RawEvent(
        tenant_id=tenant_id,
        source="carestack",
        event_type="carestack.accounting_transaction.upsert",
        external_id=f"{transaction_id}:2026-05-01T12:00:00Z",
        received_at=_BASE,
        payload=payload,
    )
    session.add(raw)
    await session.flush()
    return raw


async def _seed_treatment_procedure_raw(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    tp_id: int,
    cdt_code_id: int,
    provider_id: int | None,
    received_at: datetime | None = None,
) -> RawEvent:
    """Seed a treatment-procedure raw the accounting tp instance id links to.

    The ``external_id`` deliberately differs from the payload ``id`` so the
    tests prove resolution keys on ``payload->>'id'``, not ``external_id``. The
    clinical fields (tooth/surfaces/notes/statusId/dates) must NEVER be selected
    or surfaced.
    """
    payload: dict[str, object] = {
        "id": tp_id,
        "procedureCodeId": cdt_code_id,
        "toothNumber": "19",
        "surfaces": "MOD",
        "notes": "treatment note must NEVER reach the dashboard",
        "statusId": 3,
        "treatmentDate": "2026-05-01T00:00:00Z",
    }
    if provider_id is not None:
        payload["providerId"] = provider_id
    raw = RawEvent(
        tenant_id=tenant_id,
        source="carestack",
        event_type="carestack.treatment_procedure.upsert",
        external_id=f"tp-{tp_id}:2026-05-01T12:00:00Z",
        received_at=received_at or _BASE,
        payload=payload,
    )
    session.add(raw)
    await session.flush()
    return raw


async def test_resolves_code_and_doctor_via_treatment_procedure(
    db_session: AsyncSession,
) -> None:
    """The full two-hop chain resolves both operation code and doctor."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc")
    await _seed_reference(db_session, tenant_id)

    # Linked treatment procedures: the real CDT id + the performing provider.
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_IMPLANT,
        cdt_code_id=_IMPLANT_CODE_ID, provider_id=_DOCTOR_ID,
    )
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_EVAL,
        cdt_code_id=_EVAL_CODE_ID, provider_id=_DOCTOR_ID,
    )
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_UNRESOLVED_CDT,
        cdt_code_id=_UNKNOWN_CODE_ID, provider_id=_DOCTOR_ID,
    )

    # Accounting legs carry the treatment_procedure INSTANCE id, not a CDT id.
    both = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1001",
        tp_instance_id=_TP_IMPLANT, provider_id=None,
    )
    code_only = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1002",
        tp_instance_id=_TP_EVAL, provider_id=None,
    )
    # tp present but its CDT id is not in the catalog → code "—" yet the tp's
    # provider still resolves the doctor.
    cdt_unresolved = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1003",
        tp_instance_id=_TP_UNRESOLVED_CDT, provider_id=None,
    )
    # No procedureCodeId at all (unallocated advance) → all None.
    neither = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1004",
        tp_instance_id=None, provider_id=None,
    )

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_id,
        [
            both.id,
            code_only.id,
            cdt_unresolved.id,
            neither.id,
            uuid.uuid4(),  # raw id with no captured row → simply absent
        ],
    )

    assert refs[both.id] == {
        "operation_code": "D6010",
        "operation_description": "Surgical placement of implant body",
        "doctor_name": "Dr Jane Smith",
        "doctor_provider_id": _DOCTOR_ID,
    }
    assert refs[code_only.id] == {
        "operation_code": "D0120",
        "operation_description": "Periodic oral evaluation",
        "doctor_name": "Dr Jane Smith",
        "doctor_provider_id": _DOCTOR_ID,
    }
    # tp linked but its CDT id not in catalog → operation None, doctor resolves.
    assert refs[cdt_unresolved.id] == {
        "operation_code": None,
        "operation_description": None,
        "doctor_name": "Dr Jane Smith",
        "doctor_provider_id": _DOCTOR_ID,
    }
    # No procedure linked → all scalars None (UI renders "—"); the raw IS in the
    # map (we read its accounting row, it just carried no procedure id).
    assert refs[neither.id] == {
        "operation_code": None,
        "operation_description": None,
        "doctor_name": None,
        "doctor_provider_id": None,
    }
    # Clinical fields from BOTH raw layers never surface.
    for row in refs.values():
        assert set(row.keys()) == {
            "operation_code",
            "operation_description",
            "doctor_name",
            "doctor_provider_id",
        }
        assert "MOD" not in row.values()
        assert "19" not in row.values()
        for value in row.values():
            assert "note must NEVER" not in str(value)


async def test_doctor_falls_back_to_accounting_provider_when_no_tp(
    db_session: AsyncSession,
) -> None:
    """No linked treatment procedure → operation "—" and doctor falls back to
    the accounting ``providerId``."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc-fallback")
    await _seed_reference(db_session, tenant_id)

    # accounting references a tp instance id that has no captured tp raw.
    no_tp = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1101",
        tp_instance_id=_TP_MISSING, provider_id=_DOCTOR_ID,
    )

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_id, [no_tp.id]
    )

    assert refs[no_tp.id] == {
        "operation_code": None,
        "operation_description": None,
        "doctor_name": "Dr Jane Smith",
        "doctor_provider_id": _DOCTOR_ID,
    }


async def test_doctor_prefers_treatment_procedure_provider(
    db_session: AsyncSession,
) -> None:
    """When a procedure is linked, its provider wins over the accounting one."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc-prefer")
    await _seed_reference(db_session, tenant_id)

    # tp provider is the directory doctor; accounting carries a DIFFERENT id
    # that is NOT in the directory — the result must echo the tp provider.
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_IMPLANT,
        cdt_code_id=_IMPLANT_CODE_ID, provider_id=_DOCTOR_ID,
    )
    raw = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1201",
        tp_instance_id=_TP_IMPLANT, provider_id=_OTHER_PROVIDER_ID,
    )

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_id, [raw.id]
    )

    assert refs[raw.id] == {
        "operation_code": "D6010",
        "operation_description": "Surgical placement of implant body",
        "doctor_name": "Dr Jane Smith",
        "doctor_provider_id": _DOCTOR_ID,
    }


async def test_uses_newest_treatment_procedure_payload(
    db_session: AsyncSession,
) -> None:
    """A procedure is re-pulled on every lifecycle change; the NEWEST payload
    per tp id wins (its CDT id + provider are the resolved ones)."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc-newest")
    await _seed_reference(db_session, tenant_id)

    # Older capture carried the eval code; the newest carries the implant code.
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_IMPLANT,
        cdt_code_id=_EVAL_CODE_ID, provider_id=_DOCTOR_ID,
        received_at=_BASE,
    )
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_IMPLANT,
        cdt_code_id=_IMPLANT_CODE_ID, provider_id=_DOCTOR_ID,
        received_at=_BASE + timedelta(hours=1),
    )
    raw = await _seed_accounting_raw(
        db_session, tenant_id, transaction_id="1301",
        tp_instance_id=_TP_IMPLANT, provider_id=None,
    )

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_id, [raw.id]
    )

    assert refs[raw.id]["operation_code"] == "D6010"


async def test_batched_across_many_rows(db_session: AsyncSession) -> None:
    """A page of many accounting legs resolves in one batched pass."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc-batch")
    await _seed_reference(db_session, tenant_id)
    await _seed_treatment_procedure_raw(
        db_session, tenant_id, tp_id=_TP_IMPLANT,
        cdt_code_id=_IMPLANT_CODE_ID, provider_id=_DOCTOR_ID,
    )

    raws = [
        await _seed_accounting_raw(
            db_session, tenant_id, transaction_id=str(1400 + i),
            tp_instance_id=_TP_IMPLANT, provider_id=None,
        )
        for i in range(5)
    ]

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_id, [r.id for r in raws]
    )

    assert len(refs) == 5
    for r in raws:
        assert refs[r.id]["operation_code"] == "D6010"
        assert refs[r.id]["doctor_name"] == "Dr Jane Smith"


async def test_empty_ids_returns_empty_map(db_session: AsyncSession) -> None:
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc-empty")
    assert (
        await IngestService(db_session).get_payment_procedure_doctor_refs(
            tenant_id, []
        )
        == {}
    )


async def test_ignores_non_accounting_raw_events(
    db_session: AsyncSession,
) -> None:
    """A raw id that is not an accounting transaction is not resolved.

    The accounting repo query is pinned to
    ``carestack.accounting_transaction.upsert`` so a stray raw_event PK (e.g. an
    invoice row) never leaks codes from an unrelated payload.
    """
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="pay-proc-doc-type")
    await _seed_reference(db_session, tenant_id)
    invoice_raw = RawEvent(
        tenant_id=tenant_id,
        source="carestack",
        event_type="carestack.invoice.upsert",
        external_id="5501",
        received_at=_BASE,
        payload={"invoiceId": 5501, "procedureCodeId": _TP_IMPLANT},
    )
    db_session.add(invoice_raw)
    await db_session.flush()

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_id, [invoice_raw.id]
    )
    assert refs == {}


async def test_provider_lookup_is_tenant_scoped(
    db_session: AsyncSession,
) -> None:
    """A provider id from another tenant never resolves to a name (ENG-547).

    Both ``ingest.carestack_provider`` AND the treatment-procedure raw_events
    are tenant-scoped, so tenant B resolves its operation from its OWN procedure
    (and the workspace-level catalog) but cannot borrow tenant A's provider
    directory. This asserts the asymmetry: code resolves, doctor does not, and
    ``doctor_provider_id`` is still echoed honestly.
    """
    tenant_a = TenantId(uuid.uuid4())
    tenant_b = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_a, label="pay-proc-doc-tenant-a")
    await seed_tenant(db_session, tenant_b, label="pay-proc-doc-tenant-b")

    # Workspace-level catalog row (shared) + provider directory ONLY in tenant A.
    db_session.add(
        ProcedureCode(
            carestack_code_id=_IMPLANT_CODE_ID,
            code="D6010",
            description="Surgical placement of implant body",
        )
    )
    db_session.add(
        CareStackProvider(
            tenant_id=tenant_a,
            provider_carestack_id=_DOCTOR_ID,
            first_name="Jane",
            last_name="Smith",
            provider_type="Doctor",
        )
    )
    await db_session.flush()

    # Tenant B owns its procedure (same tp id + provider id) and accounting leg.
    await _seed_treatment_procedure_raw(
        db_session, tenant_b, tp_id=_TP_IMPLANT,
        cdt_code_id=_IMPLANT_CODE_ID, provider_id=_DOCTOR_ID,
    )
    raw_b = await _seed_accounting_raw(
        db_session, tenant_b, transaction_id="2001",
        tp_instance_id=_TP_IMPLANT, provider_id=None,
    )

    refs = await IngestService(db_session).get_payment_procedure_doctor_refs(
        tenant_b, [raw_b.id]
    )

    # Code resolves (workspace catalog); doctor does NOT (tenant-A directory is
    # invisible to tenant B); the procedure's provider id is still echoed.
    assert refs[raw_b.id] == {
        "operation_code": "D6010",
        "operation_description": "Surgical placement of implant body",
        "doctor_name": None,
        "doctor_provider_id": _DOCTOR_ID,
    }
