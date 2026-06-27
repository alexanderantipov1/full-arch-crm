"""DB-backed test for the ENG-284 strict payment-code classification migration.

Replays the migration's two server-side statements
(``DELETE_SPURIOUS_PAYMENT_EVENTS_SQL`` and
``RECLASSIFY_PAYMENT_EVENTS_SQL``) against a seeded slice of
``interaction.event`` linked to ``ingest.raw_event`` and asserts:

1. A payment-kind event whose raw carries a NON-payment
   ``transactionCode`` (``PROCEDURECOMPLETED``, ``PATIENTADJUSTMENT``,
   ``FEEUPDATION``) is DELETED — these are spurious copies of forensic
   data that ENG-283's over-broad ``isReversed`` rule wrote and that
   the strict allow-list (ENG-284 runtime) would never have emitted.
2. A payment-kind event whose raw has NO ``transactionCode`` at all
   (NULL or missing key) is DELETED too.
3. A surviving payment event whose raw carries a payment
   ``transactionCode`` is RECLASSIFIED to the allow-list mapping for
   that code — ``PATPAYMENTAPPLIED`` mislabeled as
   ``payment_recorded`` flips to ``payment_applied``, ``PATIENTPAYMENTS``
   with ``isReversed=true`` flips to ``payment_reversed``, a correctly
   labeled ``PATIENTPAYMENTS`` row is left untouched.
4. A second run of both statements changes ZERO rows
   (idempotent — re-running the migration is a no-op).
5. Non-payment-kind events (e.g. ``invoice_created``,
   ``treatment_proposed``) are left untouched even when their raw
   carries a non-payment ``transactionCode``.

Like the ENG-270 backfill test, we import the SQL constants directly
from the migration module so the assertion stays in the test session's
transaction (rolled back on teardown) and does not depend on the
migration head pointer in the live test database.

Per-seeded-row assertions only (no global ``rowcount`` checks) — the
local dev database may already contain CareStack payment events from
prior pulls.
"""

from __future__ import annotations

import importlib.util
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.types import TenantId
from packages.identity.models import Person
from packages.ingest.models import RawEvent
from packages.interaction.models import Event
from tests._fixtures.workflow_ready import seed_tenant, workflow_ready_db_session

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "db"
    / "alembic"
    / "versions"
    / "20260530_1200_c7d8e9f0a1b2_strict_payment_code_classify.py"
)
_spec = importlib.util.spec_from_file_location(
    "eng_284_strict_classify_migration", _MIGRATION_PATH
)
assert _spec is not None and _spec.loader is not None, _MIGRATION_PATH
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)
DELETE_SPURIOUS_PAYMENT_EVENTS_SQL: str = _migration.DELETE_SPURIOUS_PAYMENT_EVENTS_SQL
DELETE_DUPLICATE_MISCLASSIFIED_EVENTS_SQL: str = (
    _migration.DELETE_DUPLICATE_MISCLASSIFIED_EVENTS_SQL
)
RECLASSIFY_PAYMENT_EVENTS_SQL: str = _migration.RECLASSIFY_PAYMENT_EVENTS_SQL


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with workflow_ready_db_session() as session:
        yield session


async def _seed_person(session: AsyncSession, tenant_id: TenantId) -> Person:
    person = Person(
        tenant_id=tenant_id,
        given_name="Strict",
        family_name="Classify",
        display_name="Strict Classify",
    )
    session.add(person)
    await session.flush()
    return person


async def _seed_raw_event(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    payload: dict[str, Any],
    external_id: str,
) -> RawEvent:
    raw = RawEvent(
        tenant_id=tenant_id,
        source="carestack",
        event_type="carestack.accounting_transaction.upsert",
        external_id=external_id,
        received_at=datetime.now(UTC),
        payload=payload,
    )
    session.add(raw)
    await session.flush()
    return raw


async def _seed_event(
    session: AsyncSession,
    tenant_id: TenantId,
    *,
    person_uid: uuid.UUID,
    raw_event_id: uuid.UUID | None,
    kind: str,
    source_external_id: str,
    source_kind: str = "carestack_accounting_transaction",
    source_provider: str = "carestack",
) -> Event:
    event = Event(
        tenant_id=tenant_id,
        person_uid=person_uid,
        kind=kind,
        source_provider=source_provider,
        source_event_id=raw_event_id,
        data_class="billing",
        source_kind=source_kind,
        source_external_id=source_external_id,
        review_status="auto",
        occurred_at=datetime.now(UTC),
        summary=f"{kind} from {source_provider}:{source_external_id}",
        payload={},
    )
    session.add(event)
    await session.flush()
    return event


async def _kind_or_none(session: AsyncSession, event_id: uuid.UUID) -> str | None:
    row = await session.execute(
        sa.text("SELECT kind FROM interaction.event WHERE id = :id"),
        {"id": event_id},
    )
    value = row.scalar()
    return value if value is None else str(value)


async def _run_strict_classify(session: AsyncSession) -> tuple[int, int, int]:
    """Execute the three migration statements; return per-statement rowcounts.

    The rowcounts are returned so the idempotency assertion below can
    insist that a second pass touches ZERO rows from THIS migration's
    perspective — the test still seeds and asserts per-row so the
    rowcount check stays meaningful even when the dev DB carries
    unrelated payment events.
    """
    deleted_spurious = await session.execute(
        sa.text(DELETE_SPURIOUS_PAYMENT_EVENTS_SQL)
    )
    deleted_dupes = await session.execute(
        sa.text(DELETE_DUPLICATE_MISCLASSIFIED_EVENTS_SQL)
    )
    updated = await session.execute(sa.text(RECLASSIFY_PAYMENT_EVENTS_SQL))
    return (
        deleted_spurious.rowcount or 0,  # type: ignore[attr-defined]
        deleted_dupes.rowcount or 0,  # type: ignore[attr-defined]
        updated.rowcount or 0,  # type: ignore[attr-defined]
    )


@pytest.mark.asyncio
async def test_strict_classify_deletes_spurious_payment_events(
    db_session: AsyncSession,
) -> None:
    """Payment-kind events whose raw is non-payment are deleted."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-284-delete")
    person = await _seed_person(db_session, tenant_id)

    # Reversed PROCEDURECOMPLETED — written by ENG-283 as
    # payment_reversed; strict allow-list says this is a charge, no
    # payment event should ever exist for it.
    raw_charge = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PROCEDURECOMPLETED", "isReversed": True},
        external_id=f"raw-charge-{uuid.uuid4().hex[:8]}",
    )
    event_charge = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_charge.id,
        kind="payment_reversed",
        source_external_id=f"cs-charge-{uuid.uuid4().hex[:8]}",
    )

    # Reversed PATIENTADJUSTMENT — same shape.
    raw_adjust = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATIENTADJUSTMENT", "isReversed": True},
        external_id=f"raw-adjust-{uuid.uuid4().hex[:8]}",
    )
    event_adjust = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_adjust.id,
        kind="payment_reversed",
        source_external_id=f"cs-adjust-{uuid.uuid4().hex[:8]}",
    )

    # Reversed FEEUPDATION.
    raw_fee = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "FEEUPDATION", "isReversed": True},
        external_id=f"raw-fee-{uuid.uuid4().hex[:8]}",
    )
    event_fee = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_fee.id,
        kind="payment_reversed",
        source_external_id=f"cs-fee-{uuid.uuid4().hex[:8]}",
    )

    # Raw with NO transactionCode at all but isReversed=true — the
    # ENG-283 emit would have written this as payment_reversed too.
    raw_no_code = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"isReversed": True, "amount": 50.0},
        external_id=f"raw-nocode-{uuid.uuid4().hex[:8]}",
    )
    event_no_code = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_no_code.id,
        kind="payment_reversed",
        source_external_id=f"cs-nocode-{uuid.uuid4().hex[:8]}",
    )

    await db_session.flush()

    await _run_strict_classify(db_session)

    for event_id in (
        event_charge.id,
        event_adjust.id,
        event_fee.id,
        event_no_code.id,
    ):
        assert await _kind_or_none(db_session, event_id) is None, (
            f"spurious payment event {event_id} should have been deleted"
        )


@pytest.mark.asyncio
async def test_strict_classify_reclassifies_mislabeled_payment_events(
    db_session: AsyncSession,
) -> None:
    """Survivors get the correct kind from their raw's transactionCode."""
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-284-reclassify")
    person = await _seed_person(db_session, tenant_id)

    # PATPAYMENTAPPLIED that landed (locally re-polluted) in
    # payment_recorded must flip to payment_applied.
    raw_applied = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATPAYMENTAPPLIED"},
        external_id=f"raw-applied-{uuid.uuid4().hex[:8]}",
    )
    event_applied = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_applied.id,
        kind="payment_recorded",
        source_external_id=f"cs-applied-{uuid.uuid4().hex[:8]}",
    )

    # PATIENTPAYMENTS with isReversed=true must flip to payment_reversed
    # (this is a real reversed payment — survives the DELETE pass).
    raw_reversed_payment = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATIENTPAYMENTS", "isReversed": True},
        external_id=f"raw-revpay-{uuid.uuid4().hex[:8]}",
    )
    event_reversed_payment = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_reversed_payment.id,
        kind="payment_recorded",
        source_external_id=f"cs-revpay-{uuid.uuid4().hex[:8]}",
    )

    # Correctly labeled PATIENTPAYMENTS — must be left untouched.
    raw_ok = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATIENTPAYMENTS"},
        external_id=f"raw-ok-{uuid.uuid4().hex[:8]}",
    )
    event_ok = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_ok.id,
        kind="payment_recorded",
        source_external_id=f"cs-ok-{uuid.uuid4().hex[:8]}",
    )

    # PATIENTPAYMENTSDELETE mislabeled as payment_recorded — must flip
    # to payment_reversed.
    raw_delete = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATIENTPAYMENTSDELETE"},
        external_id=f"raw-delete-{uuid.uuid4().hex[:8]}",
    )
    event_delete = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_delete.id,
        kind="payment_recorded",
        source_external_id=f"cs-delete-{uuid.uuid4().hex[:8]}",
    )

    # PATIENTREFUND mislabeled as payment_recorded — must flip to
    # payment_refunded.
    raw_refund = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATIENTREFUND"},
        external_id=f"raw-refund-{uuid.uuid4().hex[:8]}",
    )
    event_refund = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_refund.id,
        kind="payment_recorded",
        source_external_id=f"cs-refund-{uuid.uuid4().hex[:8]}",
    )

    # ENG-284 acceptance: PATPAYMENTAPPLIED with isReversed=true must
    # stay at payment_applied (the reversal of an allocation leg is
    # still an allocation; the paired PATIENTPAYMENTSDELETE row
    # carries the cash reversal). The ENG-283 emit dropped these into
    # payment_reversed, where they pulled Collected ~$40k negative
    # against the dev DB.
    raw_reversed_allocation = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATPAYMENTAPPLIED", "isReversed": True},
        external_id=f"raw-revalloc-{uuid.uuid4().hex[:8]}",
    )
    event_reversed_allocation = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_reversed_allocation.id,
        kind="payment_reversed",
        source_external_id=f"cs-revalloc-{uuid.uuid4().hex[:8]}",
    )

    await db_session.flush()

    await _run_strict_classify(db_session)

    assert await _kind_or_none(db_session, event_applied.id) == "payment_applied"
    assert (
        await _kind_or_none(db_session, event_reversed_payment.id) == "payment_reversed"
    )
    assert await _kind_or_none(db_session, event_ok.id) == "payment_recorded"
    assert await _kind_or_none(db_session, event_delete.id) == "payment_reversed"
    assert await _kind_or_none(db_session, event_refund.id) == "payment_refunded"
    assert (
        await _kind_or_none(db_session, event_reversed_allocation.id)
        == "payment_applied"
    )


@pytest.mark.asyncio
async def test_strict_classify_leaves_non_payment_kinds_alone(
    db_session: AsyncSession,
) -> None:
    """``invoice_created`` / ``treatment_proposed`` are not touched even
    when their raw carries a non-payment ``transactionCode`` — the
    DELETE pass restricts to payment kinds only.
    """
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-284-untouched")
    person = await _seed_person(db_session, tenant_id)

    # invoice_created linked to a raw with no transactionCode — must
    # not be deleted (different kind set; the DELETE filter excludes it).
    raw_invoice = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"invoiceNumber": "INV-1"},
        external_id=f"raw-inv-{uuid.uuid4().hex[:8]}",
    )
    event_invoice = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_invoice.id,
        kind="invoice_created",
        source_kind="carestack_invoice",
        source_external_id=f"cs-inv-{uuid.uuid4().hex[:8]}",
    )

    # treatment_proposed linked to a raw with a non-payment
    # transactionCode — same expectation.
    raw_treatment = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PROCEDURECOMPLETED"},
        external_id=f"raw-tx-{uuid.uuid4().hex[:8]}",
    )
    event_treatment = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_treatment.id,
        kind="treatment_proposed",
        source_kind="carestack_treatment_procedure",
        source_external_id=f"cs-tx-{uuid.uuid4().hex[:8]}",
    )

    await db_session.flush()

    await _run_strict_classify(db_session)

    assert await _kind_or_none(db_session, event_invoice.id) == "invoice_created"
    assert (
        await _kind_or_none(db_session, event_treatment.id) == "treatment_proposed"
    )


@pytest.mark.asyncio
async def test_strict_classify_drops_wrong_kind_when_correct_sibling_exists(
    db_session: AsyncSession,
) -> None:
    """When the same ``source_external_id`` carries BOTH a wrong-kind
    row and the correctly-classified sibling, the wrong-kind row is
    DELETED. Without this step the step-3 UPDATE would collide with
    the ENG-269 cross-pull UNIQUE on
    ``(tenant_id, source_provider, source_kind, source_external_id, kind)``.
    """
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-284-dupe")
    person = await _seed_person(db_session, tenant_id)

    # Two events on the same source_external_id pointing at distinct raws
    # but both representing a PATPAYMENTAPPLIED transaction. The legacy
    # row carries kind=payment_recorded (the ENG-283 mislabel); the
    # newer row carries the correct kind=payment_applied (what a
    # re-pull on top of the ENG-283 reclassify migration would have
    # produced). Both raws have the same transactionCode so step-3's
    # CASE picks the same target.
    shared_external_id = f"cs-dup-{uuid.uuid4().hex[:8]}"

    raw_old = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATPAYMENTAPPLIED"},
        external_id=f"raw-dup-old-{uuid.uuid4().hex[:8]}",
    )
    event_wrong_kind = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_old.id,
        kind="payment_recorded",
        source_external_id=shared_external_id,
    )

    raw_new = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATPAYMENTAPPLIED"},
        external_id=f"raw-dup-new-{uuid.uuid4().hex[:8]}",
    )
    event_correct_kind = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_new.id,
        kind="payment_applied",
        source_external_id=shared_external_id,
    )

    await db_session.flush()

    spurious, dupes, updated = await _run_strict_classify(db_session)
    # The legacy mislabel is gone; the correct sibling is preserved.
    assert dupes >= 1, (spurious, dupes, updated)
    assert await _kind_or_none(db_session, event_wrong_kind.id) is None
    assert (
        await _kind_or_none(db_session, event_correct_kind.id) == "payment_applied"
    )


@pytest.mark.asyncio
async def test_strict_classify_is_idempotent(db_session: AsyncSession) -> None:
    """Running both statements a second time leaves the seeded slice
    unchanged AND reports zero rows touched for the seeded events.

    The global rowcount on the second pass is asserted to be zero
    because the test seeds in a fresh transaction; nothing else in the
    dev DB can need fixing inside this session.
    """
    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-284-idempotent")
    person = await _seed_person(db_session, tenant_id)

    # One DELETE-target, one UPDATE-target, one no-op survivor.
    raw_charge = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PROCEDURECOMPLETED", "isReversed": True},
        external_id=f"raw-charge-{uuid.uuid4().hex[:8]}",
    )
    event_charge = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_charge.id,
        kind="payment_reversed",
        source_external_id=f"cs-charge-{uuid.uuid4().hex[:8]}",
    )
    raw_applied = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATPAYMENTAPPLIED"},
        external_id=f"raw-applied-{uuid.uuid4().hex[:8]}",
    )
    event_applied = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_applied.id,
        kind="payment_recorded",
        source_external_id=f"cs-applied-{uuid.uuid4().hex[:8]}",
    )
    raw_ok = await _seed_raw_event(
        db_session,
        tenant_id,
        payload={"transactionCode": "PATIENTPAYMENTS"},
        external_id=f"raw-ok-{uuid.uuid4().hex[:8]}",
    )
    event_ok = await _seed_event(
        db_session,
        tenant_id,
        person_uid=person.id,
        raw_event_id=raw_ok.id,
        kind="payment_recorded",
        source_external_id=f"cs-ok-{uuid.uuid4().hex[:8]}",
    )

    await db_session.flush()

    first_spurious, first_dupes, first_updated = await _run_strict_classify(db_session)
    # First pass touches at least the seeded DELETE + UPDATE targets;
    # rowcounts can be larger in a polluted dev DB so the bound is
    # ``>= 1`` not ``== 1``. The duplicate-suppression DELETE pass may
    # legitimately touch pre-existing ENG-269 duplicates in the live
    # DB; only the second-pass-must-be-zero assertion below is the
    # meaningful idempotency check.
    assert first_spurious >= 1
    assert first_updated >= 1
    assert first_dupes >= 0

    # State after first pass.
    assert await _kind_or_none(db_session, event_charge.id) is None
    assert await _kind_or_none(db_session, event_applied.id) == "payment_applied"
    assert await _kind_or_none(db_session, event_ok.id) == "payment_recorded"

    # Second pass — no rows touched in the entire transaction, including
    # any pre-existing dev-DB pollution that the first pass already
    # cleaned.
    second_spurious, second_dupes, second_updated = await _run_strict_classify(
        db_session
    )
    assert second_spurious == 0
    assert second_dupes == 0
    assert second_updated == 0

    # State unchanged after second pass.
    assert await _kind_or_none(db_session, event_charge.id) is None
    assert await _kind_or_none(db_session, event_applied.id) == "payment_applied"
    assert await _kind_or_none(db_session, event_ok.id) == "payment_recorded"


@pytest.mark.asyncio
async def test_collected_total_aggregate_is_positive_after_strict_classify(
    db_session: AsyncSession,
) -> None:
    """ENG-284 acceptance: after the strict-classify migration runs,
    ``collected_total`` for a seeded mix of payment events lands
    positive — recorded ($1000) − refunded ($50) − reversed ($100)
    = +$850, despite a spurious reversed charge ($500) and reversed
    adjustment ($600) sitting in the seeded data set BEFORE the
    migration. Pre-migration the formula would have read
    1000 − (50 + 100 + 500 + 600) = −250 (the same negative shape that
    produced the dashboard −$71,934 number); post-migration it must
    read +850.
    """
    from packages.interaction.repository import InteractionRepository

    tenant_id = TenantId(uuid.uuid4())
    await seed_tenant(db_session, tenant_id, label="eng-284-aggregate")
    person = await _seed_person(db_session, tenant_id)

    async def _seed_payment(
        *,
        kind: str,
        amount: float,
        transaction_code: str,
        is_reversed: bool = False,
    ) -> Event:
        raw = await _seed_raw_event(
            db_session,
            tenant_id,
            payload={
                "transactionCode": transaction_code,
                "isReversed": is_reversed,
                "amount": amount,
            },
            external_id=f"raw-{kind}-{uuid.uuid4().hex[:8]}",
        )
        event = Event(
            tenant_id=tenant_id,
            person_uid=person.id,
            kind=kind,
            source_provider="carestack",
            source_event_id=raw.id,
            data_class="billing",
            source_kind="carestack_accounting_transaction",
            source_external_id=f"cs-{kind}-{uuid.uuid4().hex[:8]}",
            review_status="auto",
            occurred_at=datetime.now(UTC),
            summary=f"{kind} carestack",
            payload={"amount": amount, "transaction_type": "credit"},
        )
        db_session.add(event)
        await db_session.flush()
        return event

    # Real cash IN — $1000.
    await _seed_payment(
        kind="payment_recorded", amount=1000.0, transaction_code="PATIENTPAYMENTS"
    )
    # Real refund — $50.
    await _seed_payment(
        kind="payment_refunded", amount=50.0, transaction_code="PATIENTREFUND"
    )
    # Real reversed payment — $100.
    await _seed_payment(
        kind="payment_reversed",
        amount=100.0,
        transaction_code="PATIENTPAYMENTS",
        is_reversed=True,
    )
    # Spurious reversed CHARGE — $500. Pre-migration would subtract
    # this from Collected. Must be deleted by upgrade().
    await _seed_payment(
        kind="payment_reversed",
        amount=500.0,
        transaction_code="PROCEDURECOMPLETED",
        is_reversed=True,
    )
    # Spurious reversed ADJUSTMENT — $600.
    await _seed_payment(
        kind="payment_reversed",
        amount=600.0,
        transaction_code="PATIENTADJUSTMENT",
        is_reversed=True,
    )

    await db_session.flush()
    await _run_strict_classify(db_session)

    repo = InteractionRepository(db_session)
    aggregate = await repo.get_treatment_payment_aggregate(tenant_id)
    collected_total = float(aggregate["collected_total"])  # type: ignore[arg-type]

    # 1000 (recorded) − 50 (refunded) − 100 (reversed payment)
    # = +850. Spurious 500 + 600 reversed non-payments must have been
    # deleted, so they no longer subtract.
    assert collected_total == pytest.approx(850.0), aggregate
