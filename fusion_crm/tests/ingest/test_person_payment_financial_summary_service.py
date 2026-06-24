"""Unit tests for ``IngestService.person_payment_financial_summary`` (ENG-306).

Verifies the service-level composition of the per-person financial summary:
the four numbers (Billed, Adjustments, Paid, Balance) plus snapshot
timestamp aggregation. Real-DB integration is covered by the SQL-shape
tests in ``test_person_payment_repository_sql.py``; here we lock in the
service contract.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.service import IngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_service() -> tuple[IngestService, MagicMock]:
    session = MagicMock()
    service = IngestService(session)
    service._repo = MagicMock(  # type: ignore[attr-defined]
        spec=[
            "latest_payment_summary_by_patient",
            "sum_accounting_totals_by_patient",
        ]
    )
    return service, service._repo  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_no_carestack_patient_ids_returns_empty_state() -> None:
    """No CareStack link → zeros + ``snapshot_received_at=None``.

    The UI keys off ``snapshot_received_at is None`` to render ``"—"`` in
    every slot; zero floats here just keep the DTO well-typed.
    """
    service, repo = _make_service()
    repo.latest_payment_summary_by_patient = AsyncMock(return_value={})
    repo.sum_accounting_totals_by_patient = AsyncMock(return_value={})

    result = await service.person_payment_financial_summary(_TENANT_ID, [])

    assert result.billed == 0.0
    assert result.adjustments == 0.0
    assert result.paid == 0.0
    assert result.balance == 0.0
    assert result.snapshot_received_at is None
    assert result.carestack_patient_ids == []
    assert result.patient_count == 0
    # Service must NOT call the repository when there is nothing to look up.
    repo.latest_payment_summary_by_patient.assert_not_awaited()
    repo.sum_accounting_totals_by_patient.assert_not_awaited()


@pytest.mark.asyncio
async def test_single_patient_with_snapshot_returns_all_four_numbers() -> None:
    service, repo = _make_service()
    snapshot_at = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    repo.latest_payment_summary_by_patient = AsyncMock(
        return_value={
            "PT-9981": {"balance": 1200.0, "paid": 800.0, "received_at": snapshot_at}
        }
    )

    async def sum_by_codes(
        tenant_id: TenantId,
        patient_ids: list[str],
        *,
        transaction_codes: tuple[str, ...],
    ) -> dict[str, float]:
        if "PROCEDURECOMPLETED" in transaction_codes:
            return {"PT-9981": 2500.00}
        if "PATIENTADJUSTMENT" in transaction_codes:
            return {"PT-9981": -150.00}
        return {}

    repo.sum_accounting_totals_by_patient = AsyncMock(side_effect=sum_by_codes)

    result = await service.person_payment_financial_summary(_TENANT_ID, ["PT-9981"])

    assert result.billed == pytest.approx(2500.0)
    assert result.adjustments == pytest.approx(-150.0)
    assert result.paid == pytest.approx(800.0)
    assert result.balance == pytest.approx(1200.0)
    assert result.snapshot_received_at == snapshot_at
    assert result.carestack_patient_ids == ["PT-9981"]
    assert result.patient_count == 1


@pytest.mark.asyncio
async def test_multiple_carestack_links_sum_across_patients() -> None:
    """A single person with multiple CS patient ids: numbers and patient_count both add."""
    service, repo = _make_service()
    later = datetime(2026, 5, 25, 14, 0, tzinfo=UTC)
    earlier = datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
    repo.latest_payment_summary_by_patient = AsyncMock(
        return_value={
            "PT-9981": {"balance": 100.0, "paid": 200.0, "received_at": later},
            "PT-9982": {"balance": 50.0, "paid": 75.0, "received_at": earlier},
        }
    )

    async def sum_by_codes(
        tenant_id: TenantId,
        patient_ids: list[str],
        *,
        transaction_codes: tuple[str, ...],
    ) -> dict[str, float]:
        if "PROCEDURECOMPLETED" in transaction_codes:
            return {"PT-9981": 1000.0, "PT-9982": 500.0}
        if "PATIENTADJUSTMENT" in transaction_codes:
            return {"PT-9981": -50.0}
        return {}

    repo.sum_accounting_totals_by_patient = AsyncMock(side_effect=sum_by_codes)

    result = await service.person_payment_financial_summary(
        _TENANT_ID, ["PT-9982", "PT-9981"]
    )

    assert result.billed == pytest.approx(1500.0)
    assert result.adjustments == pytest.approx(-50.0)
    assert result.paid == pytest.approx(275.0)
    assert result.balance == pytest.approx(150.0)
    # The freshest snapshot across patient ids wins for the timestamp line.
    assert result.snapshot_received_at == later
    # Sorted + deduped for stable rendering downstream.
    assert result.carestack_patient_ids == ["PT-9981", "PT-9982"]
    assert result.patient_count == 2


@pytest.mark.asyncio
async def test_carestack_link_but_no_snapshot_keeps_received_at_none() -> None:
    """Patient id resolved but the backfill hasn't covered them yet.

    Billed/Adjustments can still surface from the accounting journal, but
    the UI must show ``"—"`` everywhere because the authoritative balance
    is unknown. The empty-state signal is ``snapshot_received_at is None``;
    the four floats stay whatever the journal produced — the UI ignores
    them in that mode.
    """
    service, repo = _make_service()
    repo.latest_payment_summary_by_patient = AsyncMock(return_value={})
    repo.sum_accounting_totals_by_patient = AsyncMock(
        return_value={"PT-9981": 100.0}
    )

    result = await service.person_payment_financial_summary(_TENANT_ID, ["PT-9981"])

    assert result.snapshot_received_at is None
    assert result.paid == 0.0
    assert result.balance == 0.0
    assert result.carestack_patient_ids == ["PT-9981"]
    assert result.patient_count == 1


@pytest.mark.asyncio
async def test_dedupes_and_sorts_carestack_patient_ids() -> None:
    """Duplicate / unsorted inputs MUST NOT inflate the rendered count."""
    service, repo = _make_service()
    repo.latest_payment_summary_by_patient = AsyncMock(return_value={})
    repo.sum_accounting_totals_by_patient = AsyncMock(return_value={})

    result = await service.person_payment_financial_summary(
        _TENANT_ID, ["PT-9982", "PT-9981", "PT-9982", ""]
    )

    assert result.carestack_patient_ids == ["PT-9981", "PT-9982"]
    assert result.patient_count == 2


@pytest.mark.asyncio
async def test_latest_balance_by_patient_drops_patients_without_snapshot() -> None:
    """The Payments badge map must not invent zero balances for unsnapshotted patients."""
    service, repo = _make_service()
    repo.latest_payment_summary_by_patient = AsyncMock(
        return_value={
            "PT-9981": {
                "balance": 250.0,
                "paid": 100.0,
                "received_at": datetime(2026, 5, 25, tzinfo=UTC),
            }
        }
    )

    result = await service.latest_balance_by_patient(
        _TENANT_ID, ["PT-9981", "PT-NONE"]
    )

    assert result == {"PT-9981": 250.0}
